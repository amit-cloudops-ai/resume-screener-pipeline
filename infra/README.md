# infra/ (Owner: Amit)
`template.yaml` = the ONLY place AWS resources are defined (see docs/01_ARCHITECTURE.md for the full resource list).
Status: TODO (task P2). Every Lambda gets a stub handler first so teammates deploy real code into an already-wired stack.
Not in the template (done once by hand, documented here when done): Cognito recruiter users (`scripts/create_user.sh`), SES identity verification + production access, custom Comprehend recogniser training.

## Read before writing the template
`docs/01_ARCHITECTURE.md` section "Known AWS gotchas" (S3->SQS queue policies, Cognito/CORS, visibility timeouts, Textract permissions, CloudFront OAC, SES sandbox, bucket teardown). Also: apply stack tags `Project=resume-screener` and `Stage` (the Makefile passes them with `--tags`).


## Deployment configuration
The Comprehend endpoint is optional. The stack parameter `CustomRecognizerArn` defaults to `DISABLED` and is copied into each parsing Lambda environment. The same value is mirrored to Parameter Store at `/rs/<stage>/custom-recognizer-arn`. To enable the recogniser, redeploy with `CustomRecognizerArn=<endpoint-arn>`; changing the SSM parameter manually does not update an already-running Lambda environment.

Pass `ALARM_EMAIL` when deploying if you want the SNS subscription and AWS Budget email notification created. Budget alerts are notifications, not spending caps. Keep `SES_SENDER=DISABLED` until the sender identity is verified and the application is configured to handle disabled email delivery.
