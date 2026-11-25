"""All boto3 access for Part A, in one place so handlers stay testable with fakes or moto."""
import json
from dataclasses import dataclass
from functools import cached_property

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

import config
from errors import classify_client_error
from records import candidate_base, now_iso, to_dynamo


class Store:
    """DynamoDB: candidates, jobs, failed_jobs."""

    def __init__(self, resource=None):
        ddb = resource or boto3.resource("dynamodb")
        self.candidates = ddb.Table(config.table_name("candidates"))
        self.jobs = ddb.Table(config.table_name("jobs"))
        self.failed_jobs = ddb.Table(config.table_name("failed_jobs"))

    # ---- candidates (Part A never touches score fields or recruiter decisions)
    def upsert_candidate(self, job_id: str, candidate_id: str, attrs: dict) -> None:
        names, values, sets = {}, {}, []
        for i, (k, v) in enumerate(attrs.items()):
            names[f"#k{i}"], values[f":v{i}"] = k, to_dynamo(v)
            sets.append(f"#k{i} = :v{i}")
        names["#dec"], names["#dh"] = "decision", "decision_history"
        names["#ca"] = "created_at"
        values[":pending"], values[":empty"], values[":now"] = "PENDING", [], now_iso()
        sets += ["#dec = if_not_exists(#dec, :pending)", "#dh = if_not_exists(#dh, :empty)",  # never overwrite a human choice
                 "#ca = if_not_exists(#ca, :now)"]
        try:
            self.candidates.update_item(
                Key={"job_id": job_id, "candidate_id": candidate_id},
                UpdateExpression="SET " + ", ".join(sets),
                ExpressionAttributeNames=names, ExpressionAttributeValues=values)
        except ClientError as exc:
            raise classify_client_error(exc)

    def set_candidate_status(self, job_id, candidate_id, status, source_key=None):
        """Pass source_key whenever it is known: the schema requires source_key + file_name on every row."""
        attrs = {"status": status, **(candidate_base(source_key) if source_key else {})}
        self.upsert_candidate(job_id, candidate_id, attrs)

    def get_candidate(self, job_id: str, candidate_id: str) -> dict | None:
        return self.candidates.get_item(Key={"job_id": job_id, "candidate_id": candidate_id}).get("Item")

    def candidates_for_job(self, job_id: str, statuses=("PARSED", "SCORED")) -> list[str]:
        ids, kwargs = [], {"KeyConditionExpression": Key("job_id").eq(job_id)}
        while True:
            resp = self.candidates.query(**kwargs)
            ids += [i["candidate_id"] for i in resp["Items"] if i.get("status") in statuses]
            if "LastEvaluatedKey" not in resp:
                return ids
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    # ---- jobs
    def get_job(self, job_id: str) -> dict | None:
        return self.jobs.get_item(Key={"job_id": job_id}).get("Item")

    def update_job(self, job_id: str, attrs: dict) -> None:
        names = {f"#k{i}": k for i, k in enumerate(attrs)}
        values = {f":v{i}": to_dynamo(v) for i, v in enumerate(attrs.values())}
        self.jobs.update_item(
            Key={"job_id": job_id},
            UpdateExpression="SET " + ", ".join(f"#k{i} = :v{i}" for i in range(len(attrs))),
            ExpressionAttributeNames=names, ExpressionAttributeValues=values)

    # ---- failed_jobs (deterministic failed_id => the same failure is never duplicated)
    def put_failed_job(self, item: dict) -> None:
        try:
            self.failed_jobs.put_item(Item=to_dynamo(item), ConditionExpression="attribute_not_exists(failed_id)")
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise classify_client_error(exc)
            self.failed_jobs.update_item(  # same failure again: re-open it, do not duplicate
                Key={"failed_id": item["failed_id"]},
                UpdateExpression="SET #s = :open, error_type = :t, error_message = :m",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":open": "OPEN", ":t": item["error_type"], ":m": item["error_message"]})


@dataclass
class Deps:
    s3: object
    textract: object
    comprehend: object
    sqs: object
    store: Store
    endpoint_arn: str = ""

    @cached_property
    def score_queue_url(self) -> str:
        return config.score_queue_url_env() or self.sqs.get_queue_url(QueueName=config.score_queue_name())["QueueUrl"]

    def send_score(self, job_id: str, candidate_id: str, reason: str) -> None:
        """contracts/sqs_messages.md: {job_id, candidate_id, reason}; reason in CANDIDATE_PARSED | JD_READY | RESCORE.
        Part A sends CANDIDATE_PARSED (parse Lambda) and JD_READY (jd-parse Lambda)."""
        body = json.dumps({"job_id": job_id, "candidate_id": candidate_id, "reason": reason})
        try:
            self.sqs.send_message(QueueUrl=self.score_queue_url, MessageBody=body)
        except ClientError as exc:
            raise classify_client_error(exc)


_deps = None


def get_deps() -> Deps:
    global _deps
    if _deps is None:  # built once per warm Lambda
        _deps = Deps(s3=boto3.client("s3"), textract=boto3.client("textract"), comprehend=boto3.client("comprehend"),
                     sqs=boto3.client("sqs"), store=Store(), endpoint_arn=config.comprehend_endpoint_arn())
    return _deps
