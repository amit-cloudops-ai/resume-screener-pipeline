import csv
import io
import json
import types
from decimal import Decimal


try:
    from . import app
except ImportError:
    import app


class FakeTable:
    def __init__(self, pages=None, error=None):
        self.pages = list(pages or [])
        self.error = error
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.pages.pop(0)


def install_table(monkeypatch, table, table_name="candidates"):
    resource = types.SimpleNamespace(Table=lambda name: table)
    monkeypatch.setattr(app.boto3, "resource", lambda service: resource)
    monkeypatch.setenv("CANDIDATES_TABLE", table_name)


def candidate(candidate_id, score, decision="SHORTLISTED", **values):
    return {
        "candidate_id": candidate_id,
        "score": score,
        "decision": decision,
        "score_breakdown": {"skills": {"matched": ["python"], "missing": ["aws"]}},
        "titles": ["Engineer"],
        "email_status": "SENT",
        **values,
    }


def invoke(monkeypatch, table):
    install_table(monkeypatch, table)
    return app.handler({"pathParameters": {"job_id": "a1b2c3d4e5f6"}}, None)


def parsed_response(response):
    return list(csv.DictReader(io.StringIO(response["body"].lstrip("\ufeff"), newline="")))


def test_header_order_and_csv_reader(monkeypatch):
    expected_columns = [
        "rank", "name", "email", "score", "skills_matched", "skills_missing",
        "titles", "experience_years", "decision", "email_status",
    ]
    table = FakeTable([{"Items": [candidate("b", 80)]}])
    response = invoke(monkeypatch, table)
    assert response["statusCode"] == 200
    assert next(csv.reader(io.StringIO(response["body"].lstrip("\ufeff")))) == expected_columns
    assert list(parsed_response(response)[0]) == expected_columns


def test_shortlist_filter_score_order_tie_break_and_ranks(monkeypatch):
    table = FakeTable([{"Items": [
        candidate("z", 90, name="Z"), candidate("ignored", 100, decision="REJECTED"),
        candidate("b", 80, name="B"), candidate("a", 90, name="A"),
        candidate("pending", 99, decision="PENDING"),
    ]}])
    rows = parsed_response(invoke(monkeypatch, table))
    assert [(r["rank"], r["score"], r["name"]) for r in rows] == [
        ("1", "90", "A"), ("2", "90", "Z"), ("3", "80", "B")
    ]


def test_decimal_scores_sort_by_numeric_value_before_candidate_id(monkeypatch):
    table = FakeTable([{"Items": [
        candidate("a", Decimal("9.25"), name="lower"),
        candidate("z", Decimal("10.5"), name="highest"),
        candidate("b", Decimal("10.5"), name="tied"),
    ]}])
    rows = parsed_response(invoke(monkeypatch, table))
    assert [(row["rank"], row["name"], row["score"]) for row in rows] == [
        ("1", "tied", "10.5"),
        ("2", "highest", "10.5"),
        ("3", "lower", "9.25"),
    ]


def test_missing_and_invalid_scores_sort_last_by_candidate_id(monkeypatch):
    table = FakeTable([{"Items": [
        candidate("z", None, name="missing"),
        candidate("b", "invalid", name="invalid"),
        candidate("a", Decimal("NaN"), name="nonfinite"),
        candidate("m", 0, name="scored"),
    ]}])
    rows = parsed_response(invoke(monkeypatch, table))
    assert [row["name"] for row in rows] == ["scored", "nonfinite", "invalid", "missing"]


def test_list_fields_are_serialized_and_special_characters_are_escaped(monkeypatch):
    item = candidate(
        "abc", 88, name='Doe, "Jane"\nSr.',
        score_breakdown={"skills": {"matched": ["C++, systems"], "missing": ['"cloud"']}},
        titles=["Engineer, Platform", "Lead\nArchitect"],
    )
    response = invoke(monkeypatch, FakeTable([{"Items": [item]}]))
    row = parsed_response(response)[0]
    assert row["skills_matched"] == "C++, systems"
    assert row["skills_missing"] == '"cloud"'
    assert row["titles"] == "Engineer, Platform; Lead\nArchitect"
    assert row["name"] == 'Doe, "Jane"\nSr.'
    assert '"Doe, ""Jane""\nSr."' in response["body"]


def test_bom_and_response_headers(monkeypatch):
    response = invoke(monkeypatch, FakeTable([{"Items": []}]))
    assert response["body"].startswith("\ufeff")
    assert response["headers"]["Content-Type"] == "text/csv; charset=utf-8"
    assert response["headers"]["Content-Disposition"] == (
        'attachment; filename="a1b2c3d4e5f6-shortlist.csv"'
    )


def test_empty_shortlist_has_header(monkeypatch):
    response = invoke(monkeypatch, FakeTable([{"Items": [candidate("x", 1, "REJECTED")]}]))
    rows = list(csv.reader(io.StringIO(response["body"].lstrip("\ufeff"))))
    assert rows == [list(app.CSV_COLUMNS)]


def test_queries_all_dynamodb_pages(monkeypatch):
    table = FakeTable([
        {"Items": [candidate("b", 70)], "LastEvaluatedKey": {"job_id": "job", "candidate_id": "b"}},
        {"Items": [candidate("a", 90)]},
    ])
    rows = parsed_response(invoke(monkeypatch, table))
    assert len(table.calls) == 2
    assert table.calls[1]["ExclusiveStartKey"] == {"job_id": "job", "candidate_id": "b"}
    assert [row["score"] for row in rows] == ["90", "70"]


def test_missing_job_id_returns_api_error(monkeypatch):
    response = app.handler({"pathParameters": {}}, None)
    assert response["statusCode"] == 400
    assert json.loads(response["body"]) == {"error": "Missing required path parameter: job_id"}


def test_invalid_job_id_returns_api_error(monkeypatch):
    response = app.handler({"pathParameters": {"job_id": "bad\r\nname"}}, None)
    assert response["statusCode"] == 400
    assert json.loads(response["body"]) == {"error": "Invalid path parameter: job_id"}


def test_dynamodb_error_returns_generic_api_error(monkeypatch):
    response = invoke(monkeypatch, FakeTable(error=RuntimeError("private details")))
    assert response["statusCode"] == 500
    assert json.loads(response["body"]) == {"error": "Internal server error"}
    assert "private details" not in response["body"]
