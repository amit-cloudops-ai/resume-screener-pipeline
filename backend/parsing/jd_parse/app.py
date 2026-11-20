import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    records = event.get("Records", [])
    logger.info("jd-parse stub request_id=%s record_count=%d", getattr(context, "aws_request_id", "unknown"), len(records))
    return {"batchItemFailures": []}
