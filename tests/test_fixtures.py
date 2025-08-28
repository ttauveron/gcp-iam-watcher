from tests.conftest import DummyResp, import_main_with_stubs, FakeEvent


def test_audit_posts_only_on_add(monkeypatch, load_fixture):
    m = import_main_with_stubs(monkeypatch)

    sent = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent["body"] = json
        return DummyResp()

    monkeypatch.setattr("requests.post", fake_post)

    audit_add = load_fixture("audit_bucket_iam_add.json")
    m.hello_pubsub(FakeEvent(audit_add))
    assert "New Role Grant" in sent["body"]["text"]
    assert "r" in sent["body"]["text"] and "m" in sent["body"]["text"]

    # Now ensure no post when no ADDs
    calls = {"n": 0}

    def fake_post_no(*a, **k):
        calls["n"] += 1
        return DummyResp()

    monkeypatch.setattr("requests.post", fake_post_no)

    audit_remove = load_fixture("audit_bucket_iam_no_add.json")

    m.hello_pubsub(FakeEvent(audit_remove))
    assert calls["n"] == 0


def test_asset_posts(monkeypatch, load_fixture):
    m = import_main_with_stubs(monkeypatch)
    sent = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent["body"] = json
        return DummyResp()

    monkeypatch.setattr("requests.post", fake_post)
    payload_add = load_fixture("asset_project.json")

    m.hello_pubsub(FakeEvent(payload_add))

    assert "New Role Grant" in sent["body"]["text"]
    assert "r" in sent["body"]["text"] and "m" in sent["body"]["text"]

    sent = {}
    payload_no_add = load_fixture("asset_project_no_add.json")
    m.hello_pubsub(FakeEvent(payload_no_add))
    assert not sent
