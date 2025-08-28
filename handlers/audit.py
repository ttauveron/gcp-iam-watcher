import logging
import re
from collections import defaultdict
from typing import Any, Dict, List

from lib.destinations.base import ChangeGroup, IamChangeEvent
from lib.destinations.factory import make_destination
from lib.logs_url import build_log_url, logs_query_bucket_adds


def process_audit_logs(msg: Dict[str, Any]) -> None:
    """GCS Admin Activity audit log handler — includes raw condition dicts like asset feed."""
    pp = msg.get("protoPayload", {}) or {}
    res = msg.get("resource", {}) or {}
    labels = res.get("labels", {}) or {}

    if not (
            pp.get("serviceName") == "storage.googleapis.com"
            and pp.get("methodName") == "storage.setIamPermissions"
            and res.get("type") == "gcs_bucket"
    ):
        logging.debug("Not a GCS SetIamPolicy event.")
        return

    # Keep only ADD binding deltas
    deltas = (pp.get("serviceData", {}).get("policyDelta", {}).get("bindingDeltas", []) or [])
    adds = [d for d in deltas if d.get("action") == "ADD"]
    if not adds:
        logging.info("Bucket IAM change has no ADD actions; skipping notify.")
        return

    bucket = labels.get("bucket_name")
    if not bucket:
        rn = pp.get("resourceName", "")
        m = re.search(r"/buckets/([^/]+)$", rn)
        bucket = m.group(1) if m else rn or "unknown-bucket"

    project_id = labels.get("project_id", "unknown-project")
    actor = pp.get("authenticationInfo", {}).get("principalEmail", "unknown")
    ts = msg.get("timestamp") or ""
    url = build_log_url(logs_query_bucket_adds(bucket), ts, "project", project_id)

    groups: List[ChangeGroup] = []
    role_members = defaultdict(list)

    for d in adds:
        role = d.get("role", "unknown-role")
        condition = str(d.get("condition"))
        member = d.get("member", "unknown-member")
        role_members[(role, condition)].append(member)

    for (role, condition), members in role_members.items():
        groups.append(ChangeGroup(
            event_type="binding_added",
            role=role,
            condition=condition,
            members=members
        ))

    if groups:
        evt = IamChangeEvent(
            resource_type="storage.googleapis.com/Bucket",
            resource_name=bucket,
            resource_display=project_id,
            actor=actor,
            source="audit-logs",
            timestamp=ts,
            logs_url=url,
            raw=msg,
            changes=groups,
        )
        dest = make_destination()
        dest.send(evt)
