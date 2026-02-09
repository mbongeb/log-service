#!/usr/bin/env python3
import aws_cdk as cdk
from log_service.log_service_stack import LogServiceStack

app = cdk.App()
LogServiceStack(
    app,
    "LogServiceStack",
    env=cdk.Environment(region="us-west-2"),
)
app.synth()
