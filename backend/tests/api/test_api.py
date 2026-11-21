import time

import pytest
from fastapi.testclient import TestClient

from conftest import CountingIds, FixedClock
from duckgambit.api.app import create_app
from duckgambit.api.container import build_container

from .conftest import BASE_URL, BULLET_ARENA, V1, hatch, make_settings, wait_for_job


def assert_problem(response, status, code):
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["status"] == status
    assert body["code"] == code
    assert body["title"]
    return body


# ----- system ------------------------------------------------------------------------


def test_health_reports_versions_and_readiness(client):
    body = client.get(f"{V1}/health").json()

    assert body["status"] == "ok"
    assert body["apiVersion"] == "v1"
    assert body["schemaVersion"] >= 1
    assert body["fakeEngine"] is True
    assert body["lichessEnabled"] is False


def test_unknown_routes_and_the_old_unversioned_api_are_problems(client):
    assert_problem(client.get(f"{V1}/nope"), 404, "request.not_found")
    assert_problem(client.get("/api/engines"), 404, "request.not_found")


# ----- ducks -------------------------------------------------------------------------


def test_hatching_returns_a_duck_with_budget_and_a_provisional_rating(client):
    duck = hatch(client, "  Sir   Quackalot ")

    assert duck["name"] == "Sir Quackalot"
    assert duck["growth"] == {
        "stage": "hatchling", "level": 1, "xp": 0, "xpForNextLevel": 100,
        "statBudget": 240, "statCap": 60,
    }  # fmt: skip
    assert duck["eggSeed"] is None
    assert duck["stats"]["calculation"] == 40
    assert duck["rating"] == {
        "value": 1500.0, "deviation": 350.0, "games": 0, "provisional": True, "contextId": None
    }  # fmt: skip
    assert duck["stream"] == f"duck:{duck['id']}"
    assert client.get(f"{V1}/ducks").json() == [duck]
    events = client.get(f"{V1}/events", params={"stream": duck["stream"]}).json()["events"]
    assert [e["type"] for e in events] == ["DuckHatched"]
    assert events[0]["data"]["duckId"] == duck["id"]


def test_an_egg_seed_decides_the_starting_stats_and_is_kept(client):
    first = client.post(f"{V1}/ducks", json={"name": "Egg One", "eggSeed": 42}).json()
    twin = client.post(f"{V1}/ducks", json={"name": "Egg Two", "eggSeed": 42}).json()

    assert first["eggSeed"] == 42
    assert first["stats"] == twin["stats"]
    assert first["stats"] != hatch(client, "No egg")["stats"]
    events = client.get(f"{V1}/events", params={"stream": first["stream"]}).json()["events"]
    assert events[0]["data"]["eggSeed"] == 42


def test_an_egg_cannot_be_combined_with_chosen_stats(client):
    stats = dict.fromkeys(
        ("calculation", "memory", "aggression", "solidity", "creativity", "speed"), 40)  # fmt: skip
    body = {"name": "Both", "eggSeed": 1, "stats": stats}

    assert_problem(client.post(f"{V1}/ducks", json=body), 422, "duck.egg_and_stats")
    too_big = {"name": "Big egg", "eggSeed": 2**53}
    assert_problem(client.post(f"{V1}/ducks", json=too_big), 422, "request.invalid")


def test_the_active_duck_defaults_to_the_oldest_and_can_be_chosen(client):
    assert client.get(f"{V1}/profile").json()["activeDuckId"] is None
    first, second = hatch(client, "First"), hatch(client, "Second")

    profile = client.get(f"{V1}/profile").json()
    assert profile["activeDuckId"] == first["id"]
    assert profile["name"]

    chosen = client.put(f"{V1}/profile/active-duck", json={"duckId": second["id"]})
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["activeDuckId"] == second["id"]
    assert client.get(f"{V1}/profile").json()["activeDuckId"] == second["id"]

    missing = client.put(f"{V1}/profile/active-duck", json={"duckId": "duck_missing"})
    assert_problem(missing, 404, "duck.not_found")
    assert client.get(f"{V1}/profile").json()["activeDuckId"] == second["id"]


def test_domain_rules_come_back_as_problems_with_stable_codes(client):
    over_budget = {"name": "Greedy", "stats": dict.fromkeys(
        ("calculation", "memory", "aggression", "solidity", "creativity", "speed"), 60)}  # fmt: skip

    assert_problem(client.post(f"{V1}/ducks", json=over_budget), 422, "duck.stat_budget_exceeded")
    assert_problem(client.post(f"{V1}/ducks", json={"name": "   "}), 422, "duck.invalid_name")
    assert_problem(client.get(f"{V1}/ducks/duck_missing"), 404, "duck.not_found")


def test_malformed_requests_list_the_offending_fields(client):
    body = assert_problem(
        client.post(f"{V1}/ducks", json={"nam": "typo", "stats": {"calculation": "many"}}),
        422,
        "request.invalid",
    )

    locations = {error["location"] for error in body["errors"]}
    assert "body.name" in locations
    assert "body.nam" in locations  # unknown fields are rejected, not ignored


@pytest.mark.parametrize("duck_id", ["..", "%2e%2e", "..%5c..", "A", "a" * 65, "a b"])
def test_ids_that_are_not_ids_never_reach_a_handler(client, duck_id):
    response = client.get(f"{V1}/ducks/{duck_id}")

    assert response.status_code in {404, 422}
    assert response.json()["code"] in {"request.invalid", "request.not_found"}


def test_a_duck_file_round_trips_into_a_new_duck(client):
    original = hatch(client, "Traveller", aggression=60, solidity=20)

    exported = client.get(f"{V1}/ducks/{original['id']}/export")
    assert "attachment" in exported.headers["content-disposition"]
    data = exported.json()
    assert data["format"] == "duck-gambit.duck"

    imported = client.post(f"{V1}/ducks/imports", json=data)

    assert imported.status_code == 201, imported.text
    copy = imported.json()
    assert copy["id"] != original["id"]
    assert copy["origin"] == original["id"]
    assert (copy["name"], copy["stats"]) == (original["name"], original["stats"])


def test_a_tampered_duck_file_is_refused(client):
    data = client.get(f"{V1}/ducks/{hatch(client, 'Honest')['id']}/export").json()
    data["duck"]["stats"]["calculation"] = 100

    assert_problem(client.post(f"{V1}/ducks/imports", json=data), 422, "duck.stat_out_of_range")


# ----- engines -----------------------------------------------------------------------


def test_engines_are_listed_without_any_filesystem_path(client):
    engines = client.get(f"{V1}/engines").json()

    assert [(e["id"], e["status"]) for e in engines] == [("fake", "installed")]
    assert not any("binary" in key.lower() or "path" in key.lower() for key in engines[0])


def test_test_engine_returns_lines_with_san_for_a_rule_free_client(client):
    response = client.post(f"{V1}/engines/fake/analyses", json={"nodes": 5000, "multiPV": 2})

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["lines"]) == 2
    assert {"move", "san", "cp", "mate", "wdl", "pv"} <= set(body["lines"][0])


def test_analysis_limits_are_enforced(client):
    for bad in ({"nodes": 10**9}, {"multiPV": 99}, {"movetime": 1000}, {"fen": "not a fen"}):
        response = client.post(f"{V1}/engines/fake/analyses", json=bad)
        assert response.status_code == 422, bad
    assert_problem(client.post(f"{V1}/engines/nope/analyses", json={}), 404, "engine.not_found")


def test_only_hash_is_user_settable_and_no_string_option_ever_is(client):
    options = client.get(f"{V1}/engines/fake/options").json()

    assert [o["name"] for o in options if o["userSettable"]] == ["Hash"]


def test_engine_profiles_are_validated_and_stored(client):
    profile = {"name": "Casual", "nodes": 50000, "multiPV": 3, "hashMb": 16}

    assert client.put(f"{V1}/engines/fake/profiles", json=profile).json() == profile
    assert client.get(f"{V1}/engines/fake/profiles").json() == [profile]
    extra = {**profile, "options": {"Debug Log File": "C:/x.log"}}
    assert client.put(f"{V1}/engines/fake/profiles", json=extra).status_code == 422
    assert_problem(
        client.put(f"{V1}/engines/fake/profiles", json={**profile, "name": "../x"}),
        400,
        "engine.profile_name",
    )


# ----- matches and jobs --------------------------------------------------------------


def test_a_match_can_be_cancelled_and_resumed_through_the_api(client):
    a, b = hatch(client, "A"), hatch(client, "B")
    arena = {**BULLET_ARENA, "games": 6, "maxPlies": 60}
    match = client.post(
        f"{V1}/matches", json={"duckIds": [a["id"], b["id"]], "arena": arena}
    ).json()

    time.sleep(0.2)
    cancelled = client.put(f"{V1}/jobs/{match['jobId']}/cancellation", json={})
    assert cancelled.status_code == 200, cancelled.text
    job = wait_for_job(client, match["jobId"])
    assert job["state"] == "cancelled"
    assert job["done"] < 6
    assert client.get(f"{V1}/matches/{match['id']}").json()["state"] == "cancelled"

    resumed = client.put(f"{V1}/matches/{match['id']}/resumption", json={})
    assert resumed.status_code == 200, resumed.text
    assert wait_for_job(client, match["jobId"], timeout=60)["state"] == "succeeded"
    finished = client.get(f"{V1}/matches/{match['id']}").json()
    assert finished["state"] == "finished"
    assert sum(s["points"] for s in finished["scores"]) == 6.0
    assert_problem(
        client.put(f"{V1}/matches/{match['id']}/resumption", json={}), 409, "match.finished"
    )


def test_match_requests_are_validated(client):
    a, b = hatch(client, "A"), hatch(client, "B")
    body = {"duckIds": [a["id"], b["id"]], "arena": BULLET_ARENA}

    threads = {**body, "arena": {**BULLET_ARENA, "engine": {"id": "fake", "threads": 4}}}
    assert client.post(f"{V1}/matches", json=threads).status_code == 422
    wall_clock = {**body, "arena": {**BULLET_ARENA, "limit": {"type": "time", "value": 1000}}}
    assert client.post(f"{V1}/matches", json=wall_clock).status_code == 422
    assert_problem(
        client.post(f"{V1}/matches", json={**body, "duckIds": [a["id"], a["id"]]}),
        400,
        "match.same_duck",
    )
    assert_problem(
        client.post(f"{V1}/matches", json={**body, "duckIds": [a["id"], "duck_missing"]}),
        404,
        "duck.not_found",
    )
    assert client.get(f"{V1}/matches").json() == []


def test_pgn_is_not_available_until_the_game_is_finished(client):
    assert_problem(client.get(f"{V1}/games/game_missing/pgn"), 404, "game.not_found")


def test_nodes_limit_matches_work_too(client):
    a, b = hatch(client, "A"), hatch(client, "B")
    arena = {
        "engine": {"id": "fake"},
        "limit": {"type": "nodes", "value": 2000},
        "seed": 5,
        "maxPlies": 10,
    }

    match = client.post(
        f"{V1}/matches", json={"duckIds": [a["id"], b["id"]], "arena": arena}
    ).json()

    assert wait_for_job(client, match["jobId"])["state"] == "succeeded"
    assert match["arena"]["limit"] == {"type": "nodes", "value": 2000}
    game = client.get(f"{V1}/matches/{match['id']}/games").json()[0]
    assert '[TimeControl "-"]' in client.get(f"{V1}/games/{game['id']}/pgn").text


# ----- the request boundary (ADR-0011) -----------------------------------------------


def test_requests_for_another_host_name_are_refused(client):
    response = client.get(f"{V1}/health", headers={"Host": "evil.example"})

    assert_problem(response, 403, "request.host_not_allowed")


@pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost:5173", "[::1]:8000"])
def test_loopback_host_names_are_accepted_on_any_port(client, host):
    assert client.get(f"{V1}/health", headers={"Host": host}).status_code == 200


def test_cross_site_requests_are_refused_but_same_origin_ones_pass(client):
    foreign = client.get(f"{V1}/ducks", headers={"Origin": "https://evil.example"})
    assert_problem(foreign, 403, "request.origin_not_allowed")

    same = client.get(f"{V1}/ducks", headers={"Origin": "http://127.0.0.1:8000"})
    assert same.status_code == 200
    proxied = client.get(
        f"{V1}/ducks", headers={"Host": "localhost:5173", "Origin": "http://localhost:5173"}
    )
    assert proxied.status_code == 200


def test_state_changing_requests_must_be_json(client):
    form = client.post(f"{V1}/ducks", content="name=x", headers={"Content-Type": "text/plain"})
    assert_problem(form, 415, "request.json_required")

    bodyless = client.put(f"{V1}/engines/fake/installation")
    assert_problem(bodyless, 415, "request.json_required")


def test_oversized_bodies_are_refused_before_parsing(client):
    response = client.post(
        f"{V1}/ducks/imports",
        content=b"x",
        headers={"Content-Type": "application/json", "Content-Length": str(50 * 1024 * 1024)},
    )

    assert response.status_code in {400, 413}


def test_a_launch_token_is_required_when_configured(tmp_path):
    settings = make_settings(tmp_path, api_token="s3cret-launch-token")
    container = build_container(settings, clock=FixedClock(), ids=CountingIds())
    with TestClient(create_app(container=container), base_url=BASE_URL) as client:
        assert_problem(client.get(f"{V1}/health"), 401, "request.unauthorised")
        wrong = client.get(f"{V1}/health", headers={"Authorization": "Bearer nope"})
        assert_problem(wrong, 401, "request.unauthorised")
        right = client.get(f"{V1}/health", headers={"Authorization": "Bearer s3cret-launch-token"})
        assert right.status_code == 200


def test_listening_beyond_loopback_without_a_token_is_refused(tmp_path):
    with pytest.raises(RuntimeError, match="DG_API_TOKEN"):
        create_app(make_settings(tmp_path, host="0.0.0.0"))


def test_internal_errors_do_not_leak_details(client, monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("secret path C:/Users/someone/token.txt")

    monkeypatch.setattr(client.app.state.container.ducks, "all", boom)
    quiet = TestClient(client.app, base_url=BASE_URL, raise_server_exceptions=False)

    body = assert_problem(quiet.get(f"{V1}/ducks"), 500, "internal")

    assert "secret" not in str(body) and "token.txt" not in str(body)
