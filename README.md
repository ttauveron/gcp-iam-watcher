# GCP IAM Watcher (Cloud Function)

`gcp-iam-watcher` is a Google Cloud Function that monitors IAM policy changes across your GCP projects.
It listens to Cloud Asset Inventory feeds and Audit Logs, detects role grants, and sends real-time alerts to your chosen destinations (Slack, email, etc.).

---

## Development

### Requirements

Install runtime dependencies only:

```bash
pip install -r requirements.txt
````

Install everything for local development (tests, lint, type-checks):

```
pip install -r requirements-dev.txt
```

#### Test Locally

```
export SLACK_TOKEN=xoxb-xxxxxxr
export SLACK_CHANNEL=#my_channel
python main.py ./tests/fixtures/asset_project.json
```

### Cloud Setup Example

Create a topic named "iam-changes-feed"

```
projects/MY_PROJECT/topics/iam-changes-feed
```

#### Asset Feed

Create the asset feeds at the organization level :

```bash
gcloud asset feeds create iam-policy-feed --organization=ORG_NUM --content-type=iam-policy --asset-types=".*" --pubsub-topic=projects/MY_PROJECT/topics/iam-changes-feed
```

Create service identity for Cloud Assets:

```
gcloud beta services identity create --service=cloudasset.googleapis.com --project=MY_PROJECT
```

That command should return :

```
Service identity created: service-888721688705@gcp-sa-cloudasset.iam.gserviceaccount.com
```

This service account should automatically be granted `roles/cloudasset.serviceAgent` at the project level, which include
topic publish permission.

Create a cloud function named "iam-changes-notifier" subscribing to the topic's
events. (https://cloud.google.com/run/docs/triggering/pubsub-triggers)
It notably requires to grant invoker permission to the event arc service account on the cloud function.

Grant `roles/browser` to the cloud function's service account at the organization-level in order to resolve
project/folder names from their ID.

#### Log Sink

Since Asset feed doesn't have priorAssetState values for the Bucket resource, we'll need to get that information from
audit logs in order to compute the permission grants deltas.

Create an organization-level Log Sink only for bucket IAM changes and pointing to the previously created topic :

```
protoPayload.methodName="storage.setIamPermissions"
protoPayload.serviceName="storage.googleapis.com"
resource.type="gcs_bucket"
protoPayload.serviceData.policyDelta.bindingDeltas.action="ADD"
```

Then grant `roles/pubsub.publisher` on the topic to the GCP service account
`service-org-MY_ORG_NUMBER@gcp-sa-logging.iam.gserviceaccount.com` so that the Log Sink can forward logs to the topic.

#### Deploy the cloud function

From the root of this repository:

```
gcloud run deploy gcp-iam-watcher --region=MY_REGION --source=.
```

## Running Tests

### From the command line

Run all tests:

```bash
pytest
```

## Using Multiple Destinations (Fan-Out)

This notifier can send the **same IAM change** to **many outputs** (Slack + SIEM + Email, etc.) in one run.
Set a comma-separated list in `DEST_TYPES` and provide env vars for each chosen destination.

* If `DEST_TYPES` is **unset**, it defaults to `slack`.
* Each destination validates **only its own** env vars. Nothing Slack-specific is required unless Slack is selected.

### Quick examples

**Slack only (default):**

```bash
# DEST_TYPES defaults to "slack"
SLACK_CHANNEL=#mychannel
SLACK_TOKEN=xoxb-xxxxx
```

**Slack + Email:**

```bash
DEST_TYPES=slack,email
SLACK_CHANNEL=#mychannel
SLACK_TOKEN=xoxb-xxxxxx

SMTP_EMAIL_FROM=info@example.com
SMTP_EMAIL_TO=bob@example.com
SMTP_HOST=smtp.eu.mailgun.org
SMTP_PASS=xxxxxxxxxxxxxx
SMTP_PORT=587
SMTP_USER=user@example.com
```

## Environment Variables by Destination

### Common

| Var          | Default | Purpose                                             |
|--------------|--------:|-----------------------------------------------------|
| `DEST_TYPES` | `slack` | Comma-separated list of destinations: `slack,email` |
| `LOG_LEVEL`  |  `INFO` | Python log level (`DEBUG`, `INFO`, …)               |

### Slack

Two ways to send messages: **webhook** or **token+channel**.

| Var                 |             Required | Notes                                |
|---------------------|---------------------:|--------------------------------------|
| `SLACK_WEBHOOK_URL` |     if using webhook | Easiest path; no token needed        |
| `SLACK_TOKEN`       | if not using webhook | Bot/User token (Bearer)              |
| `SLACK_CHANNEL`     | if not using webhook | Channel ID or name (e.g., `#alerts`) |

### Email (SMTP)

| Var          | Required | Notes                                               |
|--------------|---------:|-----------------------------------------------------|
| `SMTP_HOST`  |       ✔︎ | e.g., `smtp.sendgrid.net`                           |
| `SMTP_PORT`  |       25 | e.g., 587                                           |
| `SMTP_USER`  |        – | optional; if set with `SMTP_PASS`, TLS+AUTH is used |
| `SMTP_PASS`  |        – | optional                                            |
| `EMAIL_FROM` |       ✔︎ | Sender                                              |
| `EMAIL_TO`   |       ✔︎ | Recipient (single address)                          |

## How to Add a New Destination

Adding a destination is straightforward. Each destination decides how to **format** and **fan-out** the data. The core
code sends a **neutral event**:

```python
# IamChangeEvent with grouped changes (keeps role↔members↔condition together)
@dataclass
class ChangeGroup:
    event_type: str              # "binding_added" | "binding_removed"
    role: Optional[str]
    condition: Optional[str]
    members: List[str]

@dataclass
class IamChangeEvent:
    resource_type: str
    resource_name: str           # full resource name
    project_id: Optional[str]
    actor: Optional[str]         # who made the change (audit logs)
    source: str                  # "asset-feed" | "audit-log"
    timestamp: str               # ISO8601
    logs_url: Optional[str]
    raw: Dict[str, Any]          # original message
    changes: List[ChangeGroup]
```

### 1) Create a destination class

Create `lib/destinations/<your_dest>_dest.py`:

```python
import os, requests
from lib.destinations.destination import Destination
from lib.destinations.base import IamChangeEvent
from lib.destinations.utils import iter_atomic  # helper to explode groups → (role,member,cond)


class MyDestDestination(Destination):
    def __init__(self):
        # validate only what you need; raise if missing
        self.endpoint = os.environ["MYDEST_ENDPOINT"]

    def send(self, e: IamChangeEvent) -> None:
# build the payload
```

Use `slack_dest.py` or `email_dest.py` as an example.

### 2) Register it

Add to the registry in `lib/destinations/factory.py`:

```python
from .mydest_dest import MyDestDestination

REGISTRY = {
    "slack": SlackDestination,
    "email": EmailDestination,
    "mydest": MyDestDestination,  # ← new
}
```

Now users can enable it with:

```bash
DEST_TYPES=slack,mydest
MYDEST_ENDPOINT=https://example/api/ingest
```