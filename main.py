import base64
import json
import logging
import sys
from typing import Dict, Any

import functions_framework

from config import load_config
from handlers.asset import process_feeds
from handlers.audit import process_audit_logs

cfg = load_config()
logging.basicConfig(level=cfg.log_level)


def _is_asset(msg: Dict[str, Any]) -> bool:
    return isinstance(msg.get("asset"), dict)


def _is_gcs_iam_audit(msg: Dict[str, Any]) -> bool:
    pp = msg.get("protoPayload", {})
    res = msg.get("resource", {})
    return (
            pp.get("methodName") == "storage.setIamPermissions"
            and pp.get("serviceName") == "storage.googleapis.com"
            and res.get("type") == "gcs_bucket"
    )


@functions_framework.cloud_event
def hello_pubsub(event):
    raw = base64.b64decode(event.data["message"]["data"])

    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        logging.warning("Non-JSON Pub/Sub message received; ignoring. Payload=%r", raw[:200])
        return  # ack and drop

    try:
        if _is_asset(msg):
            process_feeds(msg)
            return
        if _is_gcs_iam_audit(msg):
            process_audit_logs(msg)
            return

        logging.warning("Unrecognized message format; ignoring.")
    except Exception as e:
        # Re-raise only for transient/unknown errors to trigger retry
        logging.exception("Unhandled error; will retry: %s", e)
        raise


if __name__ == "__main__":
    # usage: python main.py ./payload.json
    path = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/audit_bucket_iam_add.json"
    payload = json.load(open(path, "r", encoding="utf-8"))

    envelope = {
        "message": {
            "data": base64.b64encode(json.dumps(payload).encode()).decode(),
            "attributes": {},
            "messageId": "local",
            "publishTime": "1970-01-01T00:00:00Z",
        },
        "subscription": "local-sub",
    }


    class _CE:  # tiny CloudEvent shim with .data
        def __init__(self, d): self.data = d


    hello_pubsub(_CE(envelope))
