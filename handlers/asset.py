import logging
import re
from typing import Dict, Any, List, Optional, Tuple, Set

from lib.destinations.base import ChangeGroup, IamChangeEvent
from lib.destinations.factory import make_destination
from lib.gcp import crm_client
from lib.logs_url import build_log_url, logs_query_activity

IGNORED_ASSET_TYPES = {"storage.googleapis.com/Bucket"}


def _cond_key(cond: Optional[Dict[str, Any]]) -> Tuple:
    """Stable, comparable key for a condition dict (None → unique sentinel)."""
    if not cond:
        return ("∅",)  # unconditional
    # Use a minimal normalized tuple; adjust fields if you care about more.
    return ("cond", cond.get("expression"), cond.get("title"), cond.get("description"))


def _compute_deltas(asset_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    asset = (asset_json.get("asset") or {})
    prior = (asset_json.get("priorAsset") or {})

    new_bindings: List[Dict[str, Any]] = (asset.get("iamPolicy", {}) or {}).get("bindings", []) or []
    old_bindings: List[Dict[str, Any]] = (prior.get("iamPolicy", {}) or {}).get("bindings", []) or []

    # Index old by (role, cond_key) -> set(members)
    old_index: Dict[Tuple[str, Tuple], Set[str]] = {}
    for ob in old_bindings:
        role = ob.get("role")
        if not role:
            continue
        ck = _cond_key(ob.get("condition"))
        members = set(ob.get("members", []) or [])
        old_index[(role, ck)] = members

    deltas: List[Dict[str, Any]] = []

    # Compare new against old with the same (role, condition)
    for nb in new_bindings:
        role = nb.get("role")
        if not role:
            continue
        cond = nb.get("condition")
        ck = _cond_key(cond)

        new_members = set(nb.get("members", []) or [])
        if not new_members:
            continue  # nothing to report

        prev_members = old_index.get((role, ck), set())
        added = sorted(new_members - prev_members)

        if (role, ck) not in old_index:
            # No prior binding for this (role, condition) → report the whole binding (legacy behavior)
            deltas.append({
                "role": role,
                "members": sorted(new_members),
                "condition": cond,
                "change": "members_added",
            })
        elif added:
            # Same (role, condition) existed → report only newly added members
            deltas.append({
                "role": role,
                "members": added,
                "condition": cond,
                "change": "members_added",
            })
        # else: no net additions for this (role, condition) → no delta

    return deltas


def process_feeds(msg: Dict[str, Any]) -> None:
    asset = msg.get("asset") or {}
    asset_type = asset.get("assetType")
    if not asset or not asset_type:
        logging.debug("No asset payload; skip.")
        return
    if asset_type in IGNORED_ASSET_TYPES:
        logging.info("Skipping asset type: %s", asset_type)
        return

    deltas = _compute_deltas(msg)
    if not deltas:
        return

    asset_name = asset.get("name", "unknown")
    ancestors = asset.get("ancestors", []) or []
    ancestor_name = ancestors[0] if ancestors else ""
    update_time = asset.get("updateTime", "")

    resource_type, resource_id, resource_display = "project", "", "Unknown"
    try:
        crm = crm_client()
        if ancestor_name.startswith("projects/"):
            proj = crm.projects().get(name=ancestor_name).execute()
            resource_type = "project"
            resource_id = proj["projectId"]
            resource_display = proj["projectId"]
        elif ancestor_name.startswith("folders/"):
            fld = crm.folders().get(name=ancestor_name).execute()
            resource_type = "folder"
            resource_id = fld.get("name", ancestor_name).split("/")[-1]
            resource_display = f'{fld.get("displayName", ancestor_name)} (*folder-level*)'
        elif ancestor_name.startswith("organizations/"):
            org = crm.organizations().get(name=ancestor_name).execute()
            resource_type = "organization"
            resource_id = org.get("name", ancestor_name).split("/")[-1]
            resource_display = f'{org.get("displayName", ancestor_name)} (*organization-level*)'
        else:
            resource_id = ancestor_name
            resource_display = "Unknown"
    except Exception as e:
        logging.warning("CRM lookup failed (%s). Falling back to raw ancestor.", e)
        resource_id = ancestor_name
        resource_display = "Unknown"

    service_name = re.sub(r"^/*([^/]+)/.*", r"\1", asset_type)
    resource_name = resource_id if "cloudresourcemanager.googleapis.com" in asset_name else asset_name.split("/")[-1]
    query = logs_query_activity(service_name, resource_name)
    scope_key = "organizationId" if resource_type == "organization" else resource_type
    url = build_log_url(query, update_time, scope_key, resource_id)

    groups: List[ChangeGroup] = []

    for b in deltas:
        b["members"] = [
            member for member in b["members"]
            if not any(s in member for s in ["projectEditor", "projectOwner", "projectViewer"])
        ]
        if len(b["members"]) == 0:
            continue

        groups.append(ChangeGroup(
            event_type="binding_added" if b["change"] == "members_added" else "binding_removed",
            role=b.get("role"),
            condition=b.get("condition"),
            members=b.get("members"),
        ))

    if groups:
        evt = IamChangeEvent(
            resource_type=asset_type,
            resource_name=asset_name,
            resource_display=resource_display,
            actor=None,
            source="asset-feed",
            timestamp=update_time,
            logs_url=url,
            raw=msg,
            changes=groups,
        )
        dest = make_destination()
        dest.send(evt)
