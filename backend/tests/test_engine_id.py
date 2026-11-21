import pytest
from fastapi.testclient import TestClient

import app.main as main


@pytest.fixture
def client(monkeypatch):
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(main, "remove_engine", lambda engine_id: calls.append(("remove", engine_id)))
    monkeypatch.setattr(main, "list_profiles", lambda engine_id: calls.append(("list", engine_id)) or [])
    monkeypatch.setattr(
        main, "save_profile", lambda engine_id, name, payload: calls.append(("save", engine_id)) or {}
    )
    test_client = TestClient(main.app)
    test_client.calls = calls
    return test_client


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("DELETE", "/api/engines/%2e%2e"),
        ("DELETE", "/api/engines/..%5c.."),
        ("DELETE", "/api/engines/Stockfish"),
        ("DELETE", "/api/engines/not-in-manifest"),
        ("GET", "/api/engines/%2e%2e/profiles"),
        ("POST", "/api/engines/%2e%2e/profiles"),
    ],
)
def test_engine_id_outside_the_manifest_never_reaches_the_filesystem(client, method, path):
    response = client.request(method, path, json={"name": "x", "settings": {}})

    assert response.status_code in {404, 422}
    assert client.calls == []


def test_manifest_engine_id_is_accepted(client):
    response = client.delete("/api/engines/stockfish")

    assert response.status_code == 200
    assert client.calls == [("remove", "stockfish")]
