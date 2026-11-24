"""The one end-to-end smoke test: hatch two ducks, play a bullet match, stream it, get the PGN.

The PGN and the match's event stream are golden files: anything a player can see in a
result must not change by accident. If a change is intended, re-run with
`--update-golden`, review the diff, and bump DECISION_LAYER_VERSION if a move changed.
"""

import json
from pathlib import Path

import pytest

from .conftest import BULLET_ARENA, V1, hatch, wait_for_job

GOLDEN = Path(__file__).resolve().parents[1] / "golden"


def check_golden(name: str, actual: str, update: bool) -> None:
    path = GOLDEN / name
    if update:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(actual, encoding="utf-8", newline="\n")
        return
    assert path.is_file(), f"Missing golden file {name}; run pytest --update-golden"
    assert actual == path.read_text(encoding="utf-8"), (
        f"{name} changed. If that is intended, run pytest --update-golden and review the diff."
    )


def play_bullet_match(client):
    bold = hatch(client, "Sir Quackalot", aggression=60, solidity=20)
    calm = hatch(client, "Bill the Solid", solidity=60, aggression=20, creativity=10, speed=60)
    created = client.post(
        f"{V1}/matches", json={"duckIds": [bold["id"], calm["id"]], "arena": BULLET_ARENA}
    )
    assert created.status_code == 201, created.text
    match = created.json()
    job = wait_for_job(client, match["jobId"])
    assert job["state"] == "succeeded", job
    return bold, calm, client.get(f"{V1}/matches/{match['id']}").json()


def test_hatch_play_watch_and_download(client, request):
    update = request.config.getoption("--update-golden")
    bold, calm, match = play_bullet_match(client)

    assert match["state"] == "finished"
    assert sum(score["points"] for score in match["scores"]) == 1.0

    # The game is saved with per-move metadata and a downloadable PGN.
    games = client.get(f"{V1}/matches/{match['id']}/games").json()
    assert len(games) == 1
    game = games[0]
    moves = client.get(f"{V1}/games/{game['id']}/moves").json()
    assert moves and {"uci", "san", "source", "thinkMs", "clockMs", "fenAfter"} <= set(moves[0])
    pgn = client.get(f"{V1}/games/{game['id']}/pgn")
    assert pgn.headers["content-type"].startswith("application/x-chess-pgn")
    assert "attachment" in pgn.headers["content-disposition"]
    check_golden("walking_skeleton.pgn", pgn.text, update)

    # The event stream replays the match; `data` is deterministic, the envelope's clock is not.
    page = client.get(f"{V1}/events", params={"stream": match["stream"], "limit": 500}).json()
    stable = [
        {"stream": e["stream"], "seq": e["seq"], "type": e["type"], "data": e["data"]}
        for e in page["events"]
    ]
    assert stable[0]["type"] == "MatchCreated"
    assert stable[-1]["type"] == "MatchFinished"
    lines = "".join(json.dumps(event, sort_keys=True) + "\n" for event in stable)
    check_golden("walking_skeleton.events.jsonl", lines, update)

    # The ducks now show a measured, still provisional rating.
    for duck in (bold, calm):
        rating = client.get(f"{V1}/ducks/{duck['id']}").json()["rating"]
        assert rating["games"] == 1
        assert rating["provisional"] is True
        assert rating["contextId"] == match["contextId"]


def test_sse_stream_carries_the_same_events_with_resumable_ids(client):
    _, _, match = play_bullet_match(client)
    page = client.get(f"{V1}/events", params={"stream": match["stream"], "limit": 500}).json()

    response = client.get(
        f"{V1}/events/stream", params={"stream": match["stream"], "follow": "false"}
    )

    assert response.headers["content-type"].startswith("text/event-stream")
    messages = [block for block in response.text.split("\n\n") if block.startswith("id:")]
    assert len(messages) == len(page["events"])
    first = dict(line.split(": ", 1) for line in messages[0].split("\n"))
    assert first["event"] == "MatchCreated"
    assert json.loads(first["data"]) == page["events"][0]

    # Reconnecting with Last-Event-ID resumes after that event.
    cut = page["events"][4]["cursor"]
    resumed = client.get(
        f"{V1}/events/stream",
        params={"stream": match["stream"], "follow": "false"},
        headers={"Last-Event-ID": str(cut)},
    )
    resumed_ids = [
        int(block.split("\n")[0].removeprefix("id: "))
        for block in resumed.text.split("\n\n")
        if block.startswith("id:")
    ]
    assert resumed_ids == [e["cursor"] for e in page["events"][5:]]


def test_event_pages_can_be_walked_with_the_cursor(client):
    _, _, match = play_bullet_match(client)
    collected, cursor = [], 0

    while True:
        page = client.get(
            f"{V1}/events", params={"stream": match["stream"], "after": cursor, "limit": 7}
        ).json()
        if not page["events"]:
            break
        collected += page["events"]
        cursor = page["nextCursor"]

    assert [e["seq"] for e in collected] == list(range(1, len(collected) + 1))


@pytest.mark.parametrize("stream", ["match:..", "file:x", "match:" + "a" * 80])
def test_stream_names_are_validated(client, stream):
    response = client.get(f"{V1}/events", params={"stream": stream})

    assert response.status_code == 422
    assert response.json()["code"] == "request.invalid"
