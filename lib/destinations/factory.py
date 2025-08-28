import os
from typing import Dict, List

from .base import IamChangeEvent, Destination
from .composite import CompositeDestination
from .email_dest import EmailDestination
from .slack_dest import SlackDestination

REGISTRY = {
    "slack": SlackDestination,
    "email": EmailDestination,
}


def _csv(name: str, default: str = "") -> List[str]:
    raw = os.getenv(name, default)
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


def parse_filters(prefix: str) -> Dict[str, List[str]]:
    # Example envs:
    # DEST_SLACK_EVENT_TYPES=binding_added,binding_removed
    # DEST_SLACK_ROLES=roles/storage.admin
    # DEST_SLACK_RESOURCE_TYPES=storage.googleapis.com/Bucket
    return {
        "event_types": _csv(f"{prefix}_EVENT_TYPES"),
        "roles": _csv(f"{prefix}_ROLES"),
        "resource_types": _csv(f"{prefix}_RESOURCE_TYPES"),
    }


def make_single_destination(kind: str) -> Destination:
    cls = REGISTRY[kind]
    inst = cls()

    # Optional: decorate with a filter wrapper if any filters are set
    filters = parse_filters(f"DEST_{kind.upper()}")
    if any(filters.values()):
        inst = _FilterWrapper(inst, **filters)
    return inst


class _FilterWrapper(Destination):
    def __init__(self, inner: Destination, event_types: List[str], roles: List[str], resource_types: List[str]):
        self.inner = inner
        self.event_types = set(event_types)
        self.roles = set(roles)
        self.resource_types = set(resource_types)

    def send(self, event: IamChangeEvent) -> None:
        if self.event_types and event.event_type not in self.event_types:
            return
        if self.roles and (event.role or "") not in self.roles:
            return
        if self.resource_types and (event.resource_type or "") not in self.resource_types:
            return
        self.inner.send(event)


def make_destination() -> Destination:
    # New: multiple destinations
    types = _csv("DEST_TYPES", os.getenv("DEST_TYPE", "slack"))
    if len(types) == 1:
        return make_single_destination(types[0])

    sinks = [make_single_destination(t) for t in types]
    return CompositeDestination(sinks)
