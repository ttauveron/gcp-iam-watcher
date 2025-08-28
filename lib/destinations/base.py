from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ChangeGroup:
    event_type: str  # "binding_added" | "binding_removed"
    role: Optional[str]
    condition: Optional[str]
    members: List[str]  # all members for (role, condition)


@dataclass
class IamChangeEvent:
    # Shared context
    resource_type: str
    resource_name: str
    resource_display: str
    actor: Optional[str]  # who made the change (audit logs)
    source: str  # "asset-feed" | "audit-log"
    timestamp: str  # ISO8601
    logs_url: Optional[str]
    raw: Dict[str, Any]

    # Grouped changes
    changes: List[ChangeGroup]


class Destination(ABC):
    @abstractmethod
    def send(self, event: IamChangeEvent) -> None:
        ...
