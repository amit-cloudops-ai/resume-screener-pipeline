import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))
import build_training_data as btd  # noqa: E402
import train_recognizer as tr  # noqa: E402

import taxonomy as tx


def test_training_data_meets_comprehend_minimums_and_offsets_are_exact():
    docs, ann = btd.build(300)
    assert len(docs) >= 250
    for t in ("SKILL", "JOB_TITLE"):
        assert sum(1 for a in ann if a[3] == t) >= 100
    skills = {tx.clean(n) for e in tx.load_taxonomy()["skills"] for n in [e["canonical"], *e["aliases"]]}
    for line, b, e, kind in ann:
        span = docs[line][b:e]
        assert span and span == span.strip()
        if kind == "SKILL":
            assert tx.clean(span) in skills, span


def test_recognizer_request_shape_and_project_tag():
    req = tr.recognizer_request("bkt", "arn:aws:iam::1:role/r")
    cfg = req["InputDataConfig"]
    assert [e["Type"] for e in cfg["EntityTypes"]] == ["SKILL", "JOB_TITLE"]
    assert cfg["Documents"]["S3Uri"] == "s3://bkt/training/documents.txt" and cfg["Annotations"]["S3Uri"].endswith("annotations.csv")
    assert req["Tags"] == [{"Key": "Project", "Value": "resume-screener"}]
