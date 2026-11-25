import comprehend_client as cc
from errors import TransientError
from fakes import FakeComprehend
import pytest


def test_chunks_stay_under_limit_and_lose_nothing():
    text = "\n".join(f"line {i} " + "word " * 40 for i in range(200))
    chunks = cc.chunk_text(text)
    assert len(chunks) > 1 and all(len(c.encode()) <= cc.MAX_CHUNK_BYTES for c in chunks)
    assert "\n".join(chunks).split() == text.split()


def test_single_huge_line_and_unicode_are_split_safely():
    chunks = cc.chunk_text("é" * 9000)
    assert all(len(c.encode()) <= cc.MAX_CHUNK_BYTES for c in chunks) and "".join(chunks) == "é" * 9000
    assert cc.chunk_text("a " * 5000)


def test_custom_recogniser_only_called_when_configured():
    c = FakeComprehend(standard=[{"Text": "Asha", "Type": "PERSON"}], custom=[{"Text": "k8s", "Type": "SKILL"}])
    off = cc.detect_entities("hello", c)
    assert off["custom"] == [] and not any("EndpointArn" in k for k in c.calls)
    on = cc.detect_entities("hello", c, endpoint_arn="arn:x")
    assert [e["Type"] for e in on["custom"]] == ["SKILL"]


def test_merge_dedupes_and_keeps_best_score():
    result = {"standard": [{"Text": "Acme", "Type": "ORGANIZATION", "Score": 0.7, "Chunk": 0, "BeginOffset": 5},
                           {"Text": "ACME", "Type": "ORGANIZATION", "Score": 0.9, "Chunk": 1, "BeginOffset": 2}],
              "custom": [{"Text": "Acme", "Type": "SKILL", "Score": 0.8, "Chunk": 0, "BeginOffset": 1}]}
    merged = cc.merge_entities(result)
    assert len(merged) == 2 and [e["Score"] for e in merged if e["Type"] == "ORGANIZATION"] == [0.9]


def test_throttling_becomes_transient():
    with pytest.raises(TransientError):
        cc.detect_entities("hello", FakeComprehend(error="ThrottlingException"))
