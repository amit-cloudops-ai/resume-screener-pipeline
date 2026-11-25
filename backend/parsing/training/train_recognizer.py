"""A9 (stretch): train the custom recogniser and (only for the demo window) create / delete its endpoint.

DRY RUN BY DEFAULT: prints the request. Add --go to call AWS. The endpoint is billed per hour: create it only for
the demo video and delete it straight after. Log every hand-made resource in docs/RESOURCES.md (brief rule).

  python backend/parsing/training/train_recognizer.py --bucket B --role-arn ARN [--go]
  python backend/parsing/training/train_recognizer.py --endpoint-for RECOGNIZER_ARN [--go]
  python backend/parsing/training/train_recognizer.py --delete-endpoint ENDPOINT_ARN --go
Upload documents.txt and annotations.csv to s3://BUCKET/training/ first. Hand Amit the ENDPOINT ARN (or write 'disabled').
"""
import argparse
import json

TAGS = [{"Key": "Project", "Value": "resume-screener"}]


def recognizer_request(bucket: str, role_arn: str, name="rs-skill-title-recognizer", version="v1") -> dict:
    return {
        "RecognizerName": name, "VersionName": version, "DataAccessRoleArn": role_arn, "LanguageCode": "en", "Tags": TAGS,
        "InputDataConfig": {
            "DataFormat": "COMPREHEND_CSV", "EntityTypes": [{"Type": "SKILL"}, {"Type": "JOB_TITLE"}],
            "Documents": {"S3Uri": f"s3://{bucket}/training/documents.txt", "InputFormat": "ONE_DOC_PER_LINE"},
            "Annotations": {"S3Uri": f"s3://{bucket}/training/annotations.csv"}},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket")
    ap.add_argument("--role-arn")
    ap.add_argument("--endpoint-for", help="recognizer ARN")
    ap.add_argument("--delete-endpoint", help="endpoint ARN")
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()
    if a.bucket and a.role_arn:
        req, call = recognizer_request(a.bucket, a.role_arn), "create_entity_recognizer"
    elif a.endpoint_for:
        req, call = {"EndpointName": "rs-skill-title-endpoint", "ModelArn": a.endpoint_for, "DesiredInferenceUnits": 1, "Tags": TAGS}, "create_endpoint"
    elif a.delete_endpoint:
        req, call = {"EndpointArn": a.delete_endpoint}, "delete_endpoint"
    else:
        ap.error("give --bucket and --role-arn, or --endpoint-for, or --delete-endpoint")
    print(call, json.dumps(req, indent=2))
    if a.go:
        import boto3
        print(getattr(boto3.client("comprehend"), call)(**req))
    else:
        print("(dry run: nothing was sent; add --go)")


if __name__ == "__main__":
    main()
