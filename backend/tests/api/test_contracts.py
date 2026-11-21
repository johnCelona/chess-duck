"""Contract tests (ADR-0002, ADR-0012): the committed schemas are the source of truth."""

import json
from pathlib import Path

from duckgambit.api.schemas.events import EVENT_ADAPTER, wire_event_types
from duckgambit.cli.main import contract_documents
from duckgambit.domain import events as domain_events

from .conftest import BULLET_ARENA, V1, hatch, wait_for_job

CONTRACTS = Path(__file__).resolve().parents[3] / "contracts"

# Events with a schema and domain code whose services are built in later milestones.
NOT_EMITTED_YET = {"LessonCompleted", "KnowledgeAdded", "DuckLeveledUp"}


def all_domain_event_types() -> set[str]:
    return {
        cls.type
        for cls in vars(domain_events).values()
        if isinstance(cls, type)
        and issubclass(cls, domain_events.Event)
        and cls is not domain_events.Event
    }


def test_committed_contracts_match_the_code():
    """If this fails, run `npm run gen` and commit the result: a contract change is a diff."""
    for name, text in contract_documents().items():
        committed = (CONTRACTS / name).read_text(encoding="utf-8")
        assert committed == text, f"contracts/{name} is out of date; run `npm run gen`"


def test_every_domain_event_has_a_wire_schema_and_nothing_extra():
    assert wire_event_types() == all_domain_event_types()


def test_every_route_is_versioned_typed_and_named():
    document = json.loads(contract_documents()["openapi.json"])

    assert document["openapi"].startswith("3.1")
    operation_ids = []
    for path, methods in document["paths"].items():
        assert path.startswith("/api/v1/"), path
        for method, operation in methods.items():
            operation_ids.append(operation["operationId"])
            assert "default" in operation["responses"], f"{method} {path} lacks the Problem schema"
            ok = next(r for code, r in operation["responses"].items() if code.startswith("2"))
            schema = next(iter(ok["content"].values())).get("schema", {})
            assert schema, f"{method} {path} has no response schema"
    assert len(operation_ids) == len(set(operation_ids))
    assert all(op[0].islower() and op.isalnum() for op in operation_ids)


def test_wire_names_are_camel_case():
    document = json.loads(contract_documents()["openapi.json"])

    for name, schema in document["components"]["schemas"].items():
        for prop in schema.get("properties", {}):
            assert "_" not in prop, f"{name}.{prop} is not camelCase"


def test_no_schema_offers_raw_uci_or_wall_clock_limits():
    text = contract_documents()["openapi.json"].lower()

    for forbidden in ("movetime", "uci_elo", "skill level", "evalfile", "syzygypath", "rawcommand"):
        assert forbidden not in text


def test_real_event_streams_validate_against_the_published_event_schema(client):
    a, b = hatch(client, "A"), hatch(client, "B")
    match = client.post(
        f"{V1}/matches", json={"duckIds": [a["id"], b["id"]], "arena": BULLET_ARENA}
    ).json()
    wait_for_job(client, match["jobId"])
    streams = [match["stream"], a["stream"], b["stream"], f"job:{match['jobId']}"]

    events = client.get(f"{V1}/events", params={"stream": streams, "limit": 500}).json()["events"]

    seen = {event["type"] for event in events}
    assert seen == all_domain_event_types() - NOT_EMITTED_YET
    for event in events:
        # Round trip through the same schema clients are generated from.
        parsed = EVENT_ADAPTER.validate_python(event)
        assert json.loads(EVENT_ADAPTER.dump_json(parsed, by_alias=True)) == event
