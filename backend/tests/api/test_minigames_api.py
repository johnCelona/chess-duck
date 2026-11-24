from __future__ import annotations

from .conftest import V1


def test_minigames_list_start_and_play(client):
    listed = client.get(f"{V1}/minigames").json()
    assert len(listed) >= 10
    for info in listed:
        body = {"kind": info["id"], "seed": 7}
        first, again = (client.post(f"{V1}/minigame-runs", json=body).json() for _ in range(2))
        assert {**first, "id": ""} == {**again, "id": ""}

        moves, choices = first["moves"], first["choices"]
        action = (
            {"type": "move", "value": moves[0]}
            if moves
            else {"type": "choice", "value": choices[0]["id"]}
        )
        after = client.post(f"{V1}/minigame-runs/{first['id']}/actions", json=action)
        assert after.status_code == 200, after.text
        assert after.json()["version"] == 1


def test_bad_minigame_requests_are_problems(client):
    assert client.post(f"{V1}/minigame-runs", json={"kind": "nope"}).status_code == 422
    missing = client.post(f"{V1}/minigame-runs/mini_x/actions", json={"type": "next"})
    assert missing.status_code == 404
    run = client.post(f"{V1}/minigame-runs", json={"kind": "lily-pads"}).json()
    bad = client.post(
        f"{V1}/minigame-runs/{run['id']}/actions", json={"type": "move", "value": "a1a1"}
    )
    assert bad.json()["code"] == "minigame.action"
