import base64
import json

from config import Config


def make_event(payload_bytes: bytes):
    # Helper that takes raw bytes (already base64-able)
    return type("E", (), {"data": {"message": {"data": base64.b64encode(payload_bytes)}}})()


def make_event_raw_base64_str(bad_base64: str):
    # Helper that injects a raw (possibly invalid) base64 string directly
    return type("E", (), {"data": {"message": {"data": bad_base64}}})()


def test_non_json_message_logged_and_acked(monkeypatch, caplog):
    import importlib
    m = importlib.import_module("main")

    # Replace cfg to avoid env dependency
    monkeypatch.setattr(m, "cfg", Config(dest_types="slack,email", log_level=20))

    # Stub handlers so we detect accidental routing
    monkeypatch.setattr(m, "process_feeds",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not be called")))
    monkeypatch.setattr(m, "process_audit_logs",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not be called")))

    caplog.clear()
    caplog.set_level("WARNING")

    # Payload decodes fine but is not JSON
    event = make_event(b"this is not json")
    m.hello_pubsub(event)

    # Assert a warning was logged and no exception raised
    assert any("Non-JSON Pub/Sub message" in r.message for r in caplog.records)


def test_unrecognized_schema_logged(monkeypatch, caplog):
    import importlib
    m = importlib.import_module("main")
    monkeypatch.setattr(m, "cfg", Config(dest_types="slack,email", log_level=20))

    # No asset, no audit → should warn and return
    caplog.clear()
    caplog.set_level("WARNING")

    payload = {"some": "random", "fields": 123}
    event = type("E", (), {"data": {"message": {"data": base64.b64encode(json.dumps(payload).encode())}}})()
    m.hello_pubsub(event)

    assert any("Unrecognized message format" in r.message for r in caplog.records)
