from __future__ import annotations

import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from conftest import CountingIds, FixedClock
from duckgambit.api.app import create_app
from duckgambit.api.container import build_container
from duckgambit.settings import Settings

BASE_URL = "http://127.0.0.1:8000"
V1 = "/api/v1"


def make_settings(tmp_path, **overrides) -> Settings:
    values = {"env": "test", "data_dir": tmp_path / "data", "fake_engine": True, "_env_file": None}
    return Settings(**{**values, **overrides})


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    container = build_container(make_settings(tmp_path), clock=FixedClock(), ids=CountingIds())
    with TestClient(create_app(container=container), base_url=BASE_URL) as test_client:
        yield test_client


def wait_for_job(client: TestClient, job_id: str, timeout: float = 20.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"{V1}/jobs/{job_id}").json()
        if job["state"] not in {"queued", "running"}:
            return job
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not finish")


def hatch(client: TestClient, name: str, **stats) -> dict:
    body: dict = {"name": name}
    if stats:
        base = dict.fromkeys(
            ("calculation", "memory", "aggression", "solidity", "creativity", "speed"), 40
        )
        body["stats"] = {**base, **stats}
    response = client.post(f"{V1}/ducks", json=body)
    assert response.status_code == 201, response.text
    return response.json()


BULLET_ARENA = {
    "engine": {"id": "fake"},
    "limit": {
        "type": "virtual-clock",
        "timeControl": {"baseSeconds": 60, "incrementSeconds": 0},
        "virtualNps": 200000,
    },
    "seed": 20261121,
    "multiPV": 5,
    "maxPlies": 40,
}
