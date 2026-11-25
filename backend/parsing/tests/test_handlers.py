import json

import pytest

pytest.importorskip("moto", reason="moto not installed: add it to requirements-dev.txt to run the handler tests")
from moto import mock_aws  # noqa: E402

import dlq_handler
import jd_handler
import parse_handler
from errors import TransientError
from fakes import FakeComprehend, FakeTextract, make_env, s3_event_body, score_messages, sqs_event
from records import candidate_id_for

KEY = "resumes/a1b2c3d4e5f6/asha.pdf"
TEXT = ("Asha Verma\nasha@example.com\nSenior DevOps Engineer | Acme Corp | Jan 2019 - Mar 2022\n"
        "Skills: K8s, AWS, Docker, Terraform, Python, Linux, CI/CD")
ENTS = [{"Text": "Asha Verma", "Type": "PERSON", "BeginOffset": 0}, {"Text": "Acme Corp", "Type": "ORGANIZATION", "BeginOffset": 60}]


def textract_for(text):
    return FakeTextract(pages=[text.split("\n")])


def get(deps, job, cid):
    return deps.store.candidates.get_item(Key={"job_id": job, "candidate_id": cid}).get("Item")


@mock_aws
def test_parse_happy_path_writes_candidate_audit_json_and_score_message():
    deps = make_env(textract_for(TEXT), FakeComprehend(standard=ENTS))
    parse_handler.process_event(sqs_event(s3_event_body(KEY)), deps)

    cid = candidate_id_for("a1b2c3d4e5f6", KEY)
    row = get(deps, "a1b2c3d4e5f6", cid)
    assert row["status"] == "PARSED" and row["name"] == "Asha Verma" and row["email"] == "asha@example.com"
    assert {"kubernetes", "aws", "docker", "terraform", "python", "linux", "ci/cd"} <= set(row["skills"])
    assert row["titles"] == ["senior devops engineer"] and row["employers"] == ["Acme Corp"]
    assert float(row["experience_years"]) == 3.2
    assert row["decision"] == "PENDING" and row["decision_history"] == []
    assert deps.s3.get_object(Bucket="rs-dev-uploads", Key=row["parsed_s3_key"])["Body"].read()  # raw audit JSON
    assert score_messages(deps) == [{"job_id": "a1b2c3d4e5f6", "candidate_id": cid, "reason": "CANDIDATE_PARSED"}]
    assert row["source_key"] == KEY and row["file_name"] == "asha.pdf" and row["parser_version"] and row["created_at"]


@mock_aws
def test_reprocessing_same_file_does_not_duplicate_or_overwrite_decision():
    deps = make_env(textract_for(TEXT), FakeComprehend(standard=ENTS))
    parse_handler.process_event(sqs_event(s3_event_body(KEY)), deps)
    cid = candidate_id_for("a1b2c3d4e5f6", KEY)
    deps.store.candidates.update_item(Key={"job_id": "a1b2c3d4e5f6", "candidate_id": cid}, UpdateExpression="SET #d = :d, score = :s",
                                      ExpressionAttributeNames={"#d": "decision"}, ExpressionAttributeValues={":d": "SHORTLISTED", ":s": 88})
    parse_handler.process_event(sqs_event(s3_event_body(KEY)), deps)
    items = deps.store.candidates.scan()["Items"]
    assert len(items) == 1 and items[0]["decision"] == "SHORTLISTED" and items[0]["score"] == 88  # human choice + score untouched


@mock_aws
def test_corrupt_file_gives_exactly_one_failed_job_and_failed_candidate_even_if_delivered_twice():
    deps = make_env(FakeTextract(fail=True))
    ev = sqs_event(s3_event_body("resumes/a1b2c3d4e5f6/bad.pdf"))
    parse_handler.process_event(ev, deps)  # permanent error: no exception (message is acknowledged)
    parse_handler.process_event(ev, deps)
    rows = deps.store.failed_jobs.scan()["Items"]
    assert len(rows) == 1 and rows[0]["error_type"] == "CORRUPT_FILE" and rows[0]["stage"] == "TEXT_EXTRACT"
    assert rows[0]["status"] == "OPEN" and rows[0]["s3_key"] == "resumes/a1b2c3d4e5f6/bad.pdf"
    assert get(deps, "a1b2c3d4e5f6", candidate_id_for("a1b2c3d4e5f6", "resumes/a1b2c3d4e5f6/bad.pdf"))["status"] == "FAILED"
    assert score_messages(deps) == []


@mock_aws
def test_unsupported_type_is_permanent():
    deps = make_env()
    parse_handler.process_event(sqs_event(s3_event_body("resumes/a1b2c3d4e5f6/notes.exe")), deps)
    row = deps.store.failed_jobs.scan()["Items"][0]
    assert row["error_type"] == "UNSUPPORTED_TYPE" and row["stage"] == "TEXT_EXTRACT"


@mock_aws
def test_transient_error_raises_so_sqs_retries_and_writes_no_failed_job():
    deps = make_env(FakeTextract(start_error="ThrottlingException"))
    with pytest.raises(TransientError):
        parse_handler.process_event(sqs_event(s3_event_body(KEY)), deps)
    assert deps.store.failed_jobs.scan()["Items"] == []


@mock_aws
def test_good_resume_in_same_batch_survives_a_transient_failure_elsewhere():
    class Mixed(FakeTextract):
        def start_document_text_detection(self, DocumentLocation, **kw):
            if "flaky" in DocumentLocation["S3Object"]["Name"]:
                raise __import__("fakes").client_error("ThrottlingException")
            return super().start_document_text_detection()

    deps = make_env(Mixed(pages=[TEXT.split("\n")]), FakeComprehend(standard=ENTS))
    with pytest.raises(TransientError):
        parse_handler.process_event(sqs_event(s3_event_body("resumes/a1b2c3d4e5f6/flaky.pdf"), s3_event_body(KEY)), deps)
    assert get(deps, "a1b2c3d4e5f6", candidate_id_for("a1b2c3d4e5f6", KEY))["status"] == "PARSED"


@mock_aws
def test_non_resume_keys_and_test_events_are_ignored():
    deps = make_env()
    parse_handler.process_event(sqs_event(s3_event_body("jd/a1b2c3d4e5f6/jd.txt"), json.dumps({"Event": "s3:TestEvent"}), "garbage",
                                          s3_event_body("resumes/not-a-job-id/x.pdf")), deps)
    assert deps.store.candidates.scan()["Items"] == [] and deps.store.failed_jobs.scan()["Items"] == []


@mock_aws
def test_url_encoded_keys_are_decoded():
    deps = make_env(textract_for(TEXT), FakeComprehend(standard=ENTS))
    parse_handler.process_event(sqs_event(s3_event_body("resumes/a1b2c3d4e5f6/asha+verma%40cv.pdf")), deps)
    assert get(deps, "a1b2c3d4e5f6", candidate_id_for("a1b2c3d4e5f6", "resumes/a1b2c3d4e5f6/asha verma@cv.pdf"))["status"] == "PARSED"


# ---------------- JD
JD = "DevOps Engineer\nWe need AWS, Docker, Kubernetes, Terraform, Python and Linux.\nMinimum 3-5 years of experience."


@mock_aws
def test_jd_parse_stores_fields_and_requests_scoring_of_existing_candidates():
    deps = make_env(FakeTextract(pages=[JD.split("\n")]), FakeComprehend(standard=ENTS))
    deps.store.jobs.put_item(Item={"job_id": "a1b2c3d4e5f6", "title": "Senior DevOps Engineer", "status": "CREATED"})
    for name in ("a", "b"):  # one parsed, one still uploading
        deps.store.upsert_candidate("a1b2c3d4e5f6", name, {"status": "PARSED" if name == "a" else "PARSING"})
    jd_handler.process_event(sqs_event(s3_event_body("jd/a1b2c3d4e5f6/jd.pdf"), arn="arn:aws:sqs:us-east-1:1:rs-dev-jd-queue"), deps)

    job = deps.store.get_job("a1b2c3d4e5f6")
    assert job["status"] == "JD_PARSED" and job["title"] == "Senior DevOps Engineer"
    assert set(job["required_skills"]) == {"aws", "docker", "kubernetes", "terraform", "python", "linux"}
    assert job["jd_titles"] == ["senior devops engineer", "devops engineer"] and int(job["required_years"]) == 3
    assert score_messages(deps) == [{"job_id": "a1b2c3d4e5f6", "candidate_id": "a", "reason": "JD_READY"}]


@mock_aws
def test_jd_without_skills_fails_the_job():
    deps = make_env(FakeTextract(pages=[["We are a friendly company."]]))
    deps.store.jobs.put_item(Item={"job_id": "a1b2c3d4e5f6", "status": "CREATED"})
    jd_handler.process_event(sqs_event(s3_event_body("jd/a1b2c3d4e5f6/jd.pdf")), deps)
    assert deps.store.get_job("a1b2c3d4e5f6")["status"] == "FAILED"
    row = deps.store.failed_jobs.scan()["Items"][0]
    assert row["error_type"] == "JD_NO_SKILLS" and row["stage"] == "JD_PARSE"


def test_required_years_variants():
    assert jd_handler.required_years("5+ years of experience") == 5
    assert jd_handler.required_years("Experience: 2 yrs") == 2
    assert jd_handler.required_years("No requirement here") == 0
    assert jd_handler.required_years("We have been around for 10 years") == 0  # not about experience


# ---------------- DLQ
@mock_aws
def test_dlq_writes_failed_job_for_parse_jd_and_score_messages_without_raising():
    deps = make_env()
    deps.store.jobs.put_item(Item={"job_id": "a1b2c3d4e5f6", "status": "CREATED"})
    deps.store.upsert_candidate("a1b2c3d4e5f6", candidate_id_for("a1b2c3d4e5f6", KEY), {"status": "PARSING"})
    arn = "arn:aws:sqs:us-east-1:1:rs-dev-%s-dlq"
    n = dlq_handler.process_event(sqs_event(s3_event_body(KEY), arn=arn % "parse"), deps)
    n += dlq_handler.process_event(sqs_event(s3_event_body("jd/a1b2c3d4e5f6/jd.pdf"), arn=arn % "jd"), deps)
    n += dlq_handler.process_event(sqs_event(json.dumps({"job_id": "a1b2c3d4e5f6", "candidate_id": "c9", "reason": "X"}), arn=arn % "score"), deps)
    n += dlq_handler.process_event(sqs_event("total garbage", arn=arn % "parse"), deps)
    assert n == 4
    rows = {(r["stage"], r["error_type"]) for r in deps.store.failed_jobs.scan()["Items"]}
    assert rows == {("PARSE", "TRANSIENT_EXHAUSTED"), ("JD_PARSE", "TRANSIENT_EXHAUSTED"), ("SCORE", "TRANSIENT_EXHAUSTED"), ("PARSE", "UNKNOWN")}
    assert get(deps, "a1b2c3d4e5f6", candidate_id_for("a1b2c3d4e5f6", KEY))["status"] == "FAILED"
    assert deps.store.get_job("a1b2c3d4e5f6")["status"] == "FAILED"


@mock_aws
def test_dlq_same_message_is_not_duplicated():
    deps = make_env()
    ev = sqs_event(s3_event_body(KEY), arn="arn:aws:sqs:us-east-1:1:rs-dev-parse-dlq")
    dlq_handler.process_event(ev, deps)
    dlq_handler.process_event(ev, deps)
    assert len(deps.store.failed_jobs.scan()["Items"]) == 1


@mock_aws
def test_no_personal_data_in_failed_job_rows_or_logs(caplog):
    deps = make_env(FakeTextract(pages=[["Asha Verma asha@example.com"]]), FakeComprehend(error="ThrottlingException"))
    with pytest.raises(TransientError):
        parse_handler.process_event(sqs_event(s3_event_body(KEY)), deps)
    assert "asha" not in caplog.text.lower() and "verma" not in caplog.text.lower()


@mock_aws
def test_score_dlq_message_takes_s3_key_from_the_candidate_row():
    deps = make_env(textract_for(TEXT), FakeComprehend(standard=ENTS))
    parse_handler.process_event(sqs_event(s3_event_body(KEY)), deps)
    cid = candidate_id_for("a1b2c3d4e5f6", KEY)
    dlq_handler.process_event(sqs_event(json.dumps({"job_id": "a1b2c3d4e5f6", "candidate_id": cid, "reason": "CANDIDATE_PARSED"}),
                                        arn="arn:aws:sqs:us-east-1:1:rs-dev-score-dlq"), deps)
    row = deps.store.failed_jobs.scan()["Items"][0]
    assert row["stage"] == "SCORE" and row["s3_key"] == KEY and row["message_id"] == "m0"
    assert get(deps, "a1b2c3d4e5f6", cid)["status"] == "PARSED"  # a scoring failure does not un-parse the candidate


def _plain(item):
    return json.loads(json.dumps(item, default=float))  # Decimal -> number, as jsonschema expects


@mock_aws
def test_every_row_the_handlers_write_validates_against_the_real_contracts():
    jsonschema = pytest.importorskip("jsonschema")
    from test_contracts import schema  # skips visibly when contracts/ is missing
    candidate_schema, failed_schema = schema("candidate.schema.json"), schema("failed_job.schema.json")

    deps = make_env(textract_for(TEXT), FakeComprehend(standard=ENTS))
    parse_handler.process_event(sqs_event(s3_event_body(KEY)), deps)                              # PARSED
    parse_handler.process_event(sqs_event(s3_event_body("resumes/a1b2c3d4e5f6/x.exe")), deps)    # FAILED + failed_job
    deps.textract = FakeTextract(fail=True)
    parse_handler.process_event(sqs_event(s3_event_body("resumes/a1b2c3d4e5f6/bad.pdf")), deps)  # FAILED + failed_job
    dlq_handler.process_event(sqs_event(s3_event_body(KEY), "garbage", arn="arn:aws:sqs:us-east-1:1:rs-dev-parse-dlq"), deps)
    deps.store.jobs.put_item(Item={"job_id": "a1b2c3d4e5f6", "status": "CREATED"})
    jd_handler.process_event(sqs_event(s3_event_body("jd/a1b2c3d4e5f6/jd.pdf"), arn="arn:aws:sqs:us-east-1:1:rs-dev-jd-dlq"),
                             deps, **{})  # JD_NO_SKILLS path (FakeTextract(fail) -> extraction failure recorded)

    candidates = deps.store.candidates.scan()["Items"]
    failures = deps.store.failed_jobs.scan()["Items"]
    assert len(candidates) >= 3 and len(failures) >= 3
    for row in candidates:
        jsonschema.validate(_plain(row), candidate_schema)
    for row in failures:
        jsonschema.validate(_plain(row), failed_schema)
