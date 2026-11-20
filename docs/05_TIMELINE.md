# 05 — Timeline & Gates (today = Thu 19 Nov 2026; submit Wed 25 Nov)

| Day | Date | Goal | Gate |
|---|---|---|---|
| Thu | 19 Nov | Repo live, contracts frozen, teammates onboarded, SES prod access requested, custom-recogniser data started | **Gate 0:** everyone can run `make verify` |
| Fri | 20 Nov | Amit: full SAM skeleton deployed to `rs-dev` with stubs (by noon). A: A1-A3. B: B1, B3 | **Gate 1:** `rs-dev` deployed, 401/200 auth works, stubs reachable |
| Sat | 21 Nov | A: A4-A8 on real AWS (dev). B: B2, B4-B6. Amit: UI on mocks, Cognito users | **Gate 2:** one real PDF flows upload -> PARSED row in dev |
| Sun | 22 Nov | Integration day: UI on real API, smoke test on dev, accuracy run on golden set. FEATURE FREEZE 23:59 | **Gate 3:** full E2E (B1-B5) green on `rs-dev` |
| Mon | 23 Nov | `make deploy-prod`, smoke on prod, fix only blockers, alarms test-fired | **Gate 4:** DoD A, B, E ticked on prod |
| Tue | 24 Nov | Demo video, samples, written explanation, cost sheet, README clean-clone test, delete Comprehend endpoint after video | **Gate 5:** DoD C, D, F ticked |
| Wed | 25 Nov | Submit. Nothing new. | — |

## Rules for the schedule
- Gate missed -> cut scope from the stretch list (custom recogniser live endpoint first, then scanned PDFs, then retry endpoint), never move the deadline.
- After Sun 23:59 only bug fixes tied to a DoD box.
- Daily 10-minute sync: what's done (evidence), what's blocked, who needs what from whom. Amit updates docs/STATE.md.
