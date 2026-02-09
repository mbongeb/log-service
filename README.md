# Log Service

A serverless log ingestion and retrieval service built on AWS, deployed via AWS CDK (Python).

## Architecture

```
┌──────────┐  POST   ┌────────────────┐         ┌───────────┐
│  Client  │────────▶│ Ingest Lambda  │────────▶│           │
└──────────┘         └────────────────┘  PutItem │ DynamoDB  │
                      (Function URL)             │ LogTable  │
┌──────────┐  GET    ┌────────────────┐         │           │
│  Client  │────────▶│ ReadRecent λ   │────────▶│  (GSI:    │
└──────────┘         └────────────────┘  Query   │ DateTime) │
                      (Function URL)             └───────────┘
```

**Components:**
- **DynamoDB** — `LogTable` with `DateTimeIndex` GSI for time-sorted queries (PAY_PER_REQUEST)
- **Ingest Lambda** — validates and stores log entries via HTTP POST
- **Read Recent Lambda** — retrieves the 100 most recent log entries via HTTP GET
- **Lambda Function URLs** — direct HTTP endpoints (no API Gateway)

## Log Entry Format

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "dateTime": "2026-02-09T21:50:20.846154+00:00",
  "severity": "info | warning | error",
  "message": "Your log message here"
}
```

- `id` — auto-generated UUID if not provided
- `dateTime` — auto-set to current UTC time if not provided
- `severity` — **required**, one of: `info`, `warning`, `error`
- `message` — **required**, free-text log content

## Prerequisites

- Python 3.12+
- Node.js 20+ (for AWS CDK CLI)
- AWS CLI configured with appropriate credentials
- AWS CDK CLI (`npm install -g aws-cdk`)

## Local Development

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Synthesize CloudFormation template (validates stack)
cdk synth

# View pending changes
cdk diff --profile <your-profile>

# Deploy
cdk deploy --profile <your-profile>

# Destroy
cdk destroy --profile <your-profile>
```

## CI/CD

Automated via GitHub Actions:

| Trigger | Workflow | Action |
|---------|----------|--------|
| PR to `main` | `ci.yml` | `cdk synth` + `cdk diff` (posts diff as PR comment) |
| Push to `main` | `deploy.yml` | `cdk deploy` to production |

**Credential security:** AWS authentication uses OIDC federation — GitHub Actions assumes an IAM role directly. No static AWS keys are stored as secrets.

## Branching Strategy

Trunk-based development with conventional commits:

- `main` — production; deploys on merge
- `feat/<slug>` — new features
- `fix/<slug>` — bug fixes
- `chore/<slug>` — maintenance/infra
- `refactor/<slug>` — restructuring

Commit format: `type(scope): description`

## Database Design Decision

**DynamoDB** was chosen over RDS/Aurora for the following reasons:

- Fully serverless — no VPC, no connection pooling, no cold-start delays
- Native IAM-based Lambda integration — no password management
- PAY_PER_REQUEST billing — scales to zero cost when idle
- Millisecond read/write latency
- GSI with fixed partition key (`LogType=LOG`) enables efficient "latest 100" queries via `ScanIndexForward=False`

**Trade-off:** A single-partition GSI can become a hot partition at very high write volumes (>1000 WCU/s). For production scale, consider sharding the partition key by time bucket.
