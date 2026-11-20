# STATE — the live source of truth. UPDATE AT END OF EVERY SESSION.

Last updated: 2026-11-19 (scaffold created)
Current gate: Gate 0
Days left to submit (25 Nov): 6

## Task board (status: TODO / DOING / DONE-UNVERIFIED / VERIFIED; evidence = pasted proof)
| ID | Owner | Task (short) | Status | Evidence |
|---|---|---|---|---|
| P1 | Amit | Repo + CODEOWNERS + CI (docs/SETUP_CHECKLIST.md) | TODO | push repo, CI green, branch protection on |
| P2 | Amit | SAM skeleton + stubs | TODO | |
| P3 | Amit | Cognito + users | TODO | |
| P4 | Amit | API GW + authorizer | TODO | |
| P5 | Amit | SES verify + prod access request | TODO | |
| P6 | Amit | Frontend shell + mocks (after design choice) | TODO | |
| P7 | Amit | Frontend pages | TODO | |
| P8 | Amit | CloudFront deploy | TODO | |
| P9 | Amit | Alarms / budget | TODO | |
| P10 | Amit | E2E smoke script | TODO | |
| P12 | Amit | Demo video, diagram, cost sheet | TODO | |
| A1 | Teammate A | Skills taxonomy | TODO | |
| A2 | Teammate A | Golden set (12) | TODO | |
| A3 | Teammate A | Text extraction | TODO | |
| A4 | Teammate A | Comprehend module | TODO | |
| A5 | Teammate A | Field derivation | TODO | |
| A6 | Teammate A | parse Lambda | TODO | |
| A7 | Teammate A | jd-parse Lambda | TODO | |
| A8 | Teammate A | dlq-consumer Lambda | TODO | |
| A9 | Teammate A | Custom recogniser | TODO | |
| A10 | Teammate A | 3 sample outputs | TODO | |
| B1 | Teammate B | Scoring library + tests | TODO | |
| B2 | Teammate B | score Lambda | TODO | |
| B3 | Teammate B | API jobs + uploads | TODO | |
| B4 | Teammate B | API candidates | TODO | |
| B5 | Teammate B | API decision + SES | TODO | |
| B6 | Teammate B | CSV export | TODO | |
| B7 | Teammate B | failed-jobs API + retry | TODO | |
| B8 | Teammate B | Written NLP explanation | TODO | |
| B9 | Teammate B | Contract tests | TODO | |

## Built and verified (facts only, with evidence)
- Scaffold: `make verify` passes locally (repo OK, contracts OK, tests). Not yet pushed / CI not yet run.

## Blocked (two-strike rule diagnoses go here)
- (none)

## Parking lot (good ideas that are NOT in scope — do not build)
- (none)

## Deployed environment facts (fill as they become real; never guess)
- AWS account ID: 
- rs-dev API URL: 
- rs-dev CloudFront URL: 
- rs-prod API URL: 
- rs-prod CloudFront URL: 
- Cognito user pool ID / client ID (dev): 
- Custom recogniser ARN: (none / disabled)
- SES sender: 
