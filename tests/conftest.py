import base64
import importlib
import json
import pathlib
import types

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    def _load(name: str):
        with open(FIXTURES / name, "r") as f:
            return json.load(f)

    return _load


class FakeCRMProjects:
    def get(self, name):
        # Return a payload shaped like CRM v3 projects().get().execute()
        return types.SimpleNamespace(execute=lambda: {"projectId": "my-proj"})


class FakeCRMFolders:
    def get(self, name):
        return types.SimpleNamespace(execute=lambda: {"name": name, "displayName": "My Folder"})


class FakeCRMOrgs:
    def get(self, name):
        return types.SimpleNamespace(execute=lambda: {"name": name, "displayName": "My Org"})


class FakeCRMClient:
    def projects(self): return FakeCRMProjects()

    def folders(self): return FakeCRMFolders()

    def organizations(self): return FakeCRMOrgs()


def import_main_with_stubs(monkeypatch):
    # Ensure env vars are present for the module under test
    monkeypatch.setenv("SLACK_TOKEN", "x-test-token")
    monkeypatch.setenv("SLACK_CHANNEL", "#test-temp")
    monkeypatch.setenv("LOG_LEVEL", "ERROR")  # keep test output quiet

    # Stub discovery.build BEFORE importing the module (it builds crm at import time)
    import googleapiclient.discovery as discovery
    monkeypatch.setattr(discovery, "build", lambda *a, **k: FakeCRMClient())

    # Now import or reload your module (assuming filename is main.py)
    import main
    return importlib.reload(main)


class FakeEvent:
    """Minimal CloudEvent-like wrapper your handler expects."""

    def __init__(self, payload):
        self.data = {"message": {"data": base64.b64encode(json.dumps(payload).encode())}}


class DummyResp:
    def __init__(self, code=200, ok=True):
        self.status_code = code
        self._ok = ok
        self.text = "ok"
        self.headers = {}

    def json(self): return {"ok": self._ok}
