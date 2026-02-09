"""Ingest Lambda – accepts log entries via POST and stores them in DynamoDB.

Logging strategy (per alexwlchan.net/2018/error-logging-in-lambdas):
The incoming event is only logged when the handler raises an exception,
keeping CloudWatch costs down during normal operation.
"""

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ["TABLE_NAME"]
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

VALID_SEVERITIES = {"info", "warning", "error"}
# Loose ISO 8601 pattern – accepts common variants
ISO8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$"
)


def _validate(body: dict) -> list[str]:
    """Return a list of validation error messages (empty if valid)."""
    errors = []

    # severity is required and must be one of the allowed values
    severity = body.get("severity")
    if severity is None:
        errors.append("Missing required field: 'severity'")
    elif severity not in VALID_SEVERITIES:
        errors.append(
            f"Invalid severity '{severity}'. Must be one of: {', '.join(sorted(VALID_SEVERITIES))}"
        )

    # message is required
    if not body.get("message"):
        errors.append("Missing required field: 'message'")

    # dateTime is optional but must be valid ISO 8601 if provided
    dt = body.get("dateTime")
    if dt is not None and not ISO8601_RE.match(str(dt)):
        errors.append(f"Invalid dateTime format: '{dt}'. Expected ISO 8601.")

    return errors


def handler(event, context):
    """Lambda Function URL handler for log ingestion."""
    try:
        return _handle(event)
    except Exception:
        # Log the full event only on error (cost-saving pattern)
        logger.exception("Error processing event: %s", json.dumps(event))
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal server error"}),
        }


def _handle(event):
    # Only accept POST requests
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    if method != "POST":
        return {
            "statusCode": 405,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": f"Method {method} not allowed. Use POST."}),
        }

    # Parse JSON body
    raw_body = event.get("body", "")
    if event.get("isBase64Encoded"):
        import base64

        raw_body = base64.b64decode(raw_body).decode("utf-8")

    try:
        body = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Request body must be valid JSON"}),
        }

    # Validate
    errors = _validate(body)
    if errors:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"errors": errors}),
        }

    # Build the DynamoDB item
    log_id = body.get("id") or str(uuid.uuid4())
    date_time = body.get("dateTime") or datetime.now(timezone.utc).isoformat()

    item = {
        "LogID": log_id,
        "DateTime": date_time,
        "Severity": body["severity"],
        "Message": body["message"],
        # Fixed partition key for the GSI so all logs land in one partition
        "LogType": "LOG",
    }

    table.put_item(Item=item)

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "message": "Log entry created",
                "id": log_id,
                "dateTime": date_time,
            }
        ),
    }
