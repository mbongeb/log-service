"""Read Recent Lambda – returns the 100 most recent log entries.

Logging strategy (per alexwlchan.net/2018/error-logging-in-lambdas):
The incoming event is only logged when the handler raises an exception,
keeping CloudWatch costs down during normal operation.
"""

import json
import logging
import os

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ["TABLE_NAME"]
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

INDEX_NAME = "DateTimeIndex"


def handler(event, context):
    """Lambda Function URL handler for reading recent logs."""
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
    # Only accept GET requests
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    if method != "GET":
        return {
            "statusCode": 405,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": f"Method {method} not allowed. Use GET."}),
        }

    # Query the GSI for the 100 most recent log entries.
    # LogType="LOG" is the fixed partition key; ScanIndexForward=False
    # returns items in descending DateTime order (newest first).
    response = table.query(
        IndexName=INDEX_NAME,
        KeyConditionExpression=Key("LogType").eq("LOG"),
        ScanIndexForward=False,
        Limit=100,
    )

    items = response.get("Items", [])

    # Shape the response to match the specified log entry format
    logs = [
        {
            "id": item["LogID"],
            "dateTime": item["DateTime"],
            "severity": item["Severity"],
            "message": item["Message"],
        }
        for item in items
    ]

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"count": len(logs), "logs": logs}),
    }
