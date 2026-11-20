# RISKS (check at every gate)

| Risk | Impact | Mitigation | Owner |
|---|---|---|---|
| SES sandbox | Shortlist emails fail for unverified addresses | Request production access Thu 19; verify sender + demo candidate emails; email_status FAILED handled in UI | Amit |
| Custom recogniser time/cost | Blocks parsing | Optional via env var; taxonomy fallback passes DoD alone; delete endpoint after demo | A |
| Textract async latency/throttle | Slow or failed parses | Reserved concurrency 5, 100s poll cap, retries -> DLQ | A |
| Scanned PDFs poor OCR | Low accuracy | Only 4/12 golden are scanned; accuracy target applies to the whole set | A |
| Years-of-experience errors | Wrong 20% of score | Date-range union, golden check C3, fallback phrase | A |
| Contract drift | Parts don't fit | Contracts frozen; `make verify` validates fixtures + schemas | Amit |
| AWS credit/cost | Surprise bill | Budget alert; one Comprehend endpoint, 1 unit, only for demo window | Amit |
| ChatGPT looping | Lost days | AGENTS.md + STATE.md + two-strike rule + scoped task IDs | All |
| Late integration | Gate 3 fails | Fixtures let B and UI work before A is done; dev stack Fri noon | Amit |
