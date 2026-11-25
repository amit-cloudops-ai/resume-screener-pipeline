"""Comprehend module (A4): chunk text, standard entities, custom recogniser when configured, merge + de-duplicate.

Standard types used: PERSON (name), ORGANIZATION (employers), DATE.  Custom types: SKILL, JOB_TITLE.
Note: Comprehend's built-in TITLE type is for creative works, so it is deliberately NOT used for job titles.
"""
from botocore.exceptions import ClientError

from errors import classify_client_error

MAX_CHUNK_BYTES = 4500  # safely under Comprehend's per-request limits


def _hard_split(word: str, max_bytes: int):
    """Cut one enormous token into pieces that each fit, never splitting a multi-byte character."""
    piece, size = "", 0
    for ch in word:
        n = len(ch.encode("utf-8"))
        if size + n > max_bytes:
            yield piece
            piece, size = "", 0
        piece, size = piece + ch, size + n
    if piece:
        yield piece


def _split_long_line(line: str, max_bytes: int):
    piece = ""
    for word in line.split(" "):
        candidate = f"{piece} {word}".strip()
        if len(candidate.encode("utf-8")) <= max_bytes:
            piece = candidate
            continue
        if piece:
            yield piece
            piece = ""
        if len(word.encode("utf-8")) > max_bytes:
            parts = list(_hard_split(word, max_bytes))
            yield from parts[:-1]
            word = parts[-1]
        piece = word
    if piece:
        yield piece


def chunk_text(text: str, max_bytes: int = MAX_CHUNK_BYTES) -> list[str]:
    chunks, current = [], ""
    for line in text.split("\n"):
        parts = [line] if len(line.encode("utf-8")) <= max_bytes else list(_split_long_line(line, max_bytes))
        for part in parts:
            candidate = f"{current}\n{part}" if current else part
            if len(candidate.encode("utf-8")) <= max_bytes:
                current = candidate
            else:
                chunks.append(current)
                current = part
    if current.strip():
        chunks.append(current)
    return chunks


def _call(client, chunk_index: int, **kwargs) -> list[dict]:
    try:
        resp = client.detect_entities(**kwargs)
    except ClientError as exc:
        raise classify_client_error(exc)
    return [
        {
            "Text": e["Text"], "Type": e["Type"], "Score": round(float(e.get("Score", 0)), 4),
            "BeginOffset": e.get("BeginOffset"), "EndOffset": e.get("EndOffset"), "Chunk": chunk_index,
        }
        for e in resp.get("Entities", [])
    ]


def detect_entities(text: str, client, endpoint_arn: str = "", language: str = "en") -> dict:
    """Raw result (kept in S3 under parsed/ for audit). 'custom' stays empty when no endpoint is configured."""
    result = {"chunks": 0, "standard": [], "custom": []}
    for index, chunk in enumerate(chunk_text(text)):
        result["chunks"] += 1
        result["standard"] += _call(client, index, Text=chunk, LanguageCode=language)
        if endpoint_arn:
            result["custom"] += _call(client, index, Text=chunk, EndpointArn=endpoint_arn)
    return result


def merge_entities(result: dict) -> list[dict]:
    """Standard + custom, one entry per (type, text), keeping the best score, in reading order."""
    best: dict[tuple, dict] = {}
    for e in result.get("standard", []) + result.get("custom", []):
        key = (e["Type"], e["Text"].casefold())
        if key not in best or e["Score"] > best[key]["Score"]:
            best[key] = e
    return sorted(best.values(), key=lambda e: (e.get("Chunk", 0), e.get("BeginOffset") or 0))
