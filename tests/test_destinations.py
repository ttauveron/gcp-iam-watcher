from lib.destinations.base import Destination, IamChangeEvent
from lib.destinations.composite import CompositeDestination


def test_fanout_calls_all(monkeypatch):
    called = []

    class D(Destination):
        def __init__(self, name): self.name = name

        def send(self, e): called.append(self.name)

    comp = CompositeDestination([D("a"), D("b"), D("c")])
    comp.send(
        IamChangeEvent(
            resource_type="",
            resource_name="",
            resource_display="",
            actor="",
            source="",
            timestamp="",
            logs_url="",
            raw={},
            changes=[],
        )
    )

    assert called == ["a", "b", "c"]
