"""Log Service CDK Stack.

Creates a DynamoDB table with a GSI for time-based queries,
two Lambda functions (ingest + read_recent) with Function URLs,
and the necessary IAM permissions.
"""

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
)
from constructs import Construct


class LogServiceStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------------------------------------------------------------
        # DynamoDB Table
        # ---------------------------------------------------------------
        log_table = dynamodb.Table(
            self,
            "LogTable",
            table_name="LogTable",
            partition_key=dynamodb.Attribute(
                name="LogID", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # GSI for querying the most recent logs sorted by DateTime.
        # LogType is always "LOG" — a fixed partition key that collects
        # all entries so we can sort by DateTime across the whole table.
        log_table.add_global_secondary_index(
            index_name="DateTimeIndex",
            partition_key=dynamodb.Attribute(
                name="LogType", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="DateTime", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # ---------------------------------------------------------------
        # Ingest Lambda
        # ---------------------------------------------------------------
        ingest_fn = lambda_.Function(
            self,
            "IngestFunction",
            function_name="log-service-ingest",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/ingest"),
            environment={
                "TABLE_NAME": log_table.table_name,
            },
            timeout=Duration.seconds(10),
            memory_size=128,
        )

        # Grant the ingest function write access to the table
        log_table.grant_write_data(ingest_fn)

        # Function URL (public, no auth for demo purposes)
        ingest_url = ingest_fn.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE,
        )

        # ---------------------------------------------------------------
        # Read Recent Lambda
        # ---------------------------------------------------------------
        read_recent_fn = lambda_.Function(
            self,
            "ReadRecentFunction",
            function_name="log-service-read-recent",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/read_recent"),
            environment={
                "TABLE_NAME": log_table.table_name,
            },
            timeout=Duration.seconds(10),
            memory_size=128,
        )

        # Grant the read function read access to the table
        log_table.grant_read_data(read_recent_fn)

        # Function URL (public, no auth for demo purposes)
        read_recent_url = read_recent_fn.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE,
        )

        # ---------------------------------------------------------------
        # Outputs
        # ---------------------------------------------------------------
        CfnOutput(self, "IngestFunctionUrl", value=ingest_url.url)
        CfnOutput(self, "ReadRecentFunctionUrl", value=read_recent_url.url)
        CfnOutput(self, "DynamoDBTableName", value=log_table.table_name)
