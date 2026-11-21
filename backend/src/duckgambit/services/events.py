"""The event log: append, read and wait for more (ADR-0002).

The store is the source of truth. Live streaming is "read what is new, then wait to be
told there is more", so replay and live watching are the same code path and a client
that reconnects with its last cursor misses nothing.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from duckgambit.domain.events import Event
from duckgambit.services.ports import Clock, Store
from duckgambit.services.records import Envelope

MAX_PAGE = 500


def iso(clock: Clock) -> str:
    return clock.now().strftime("%Y-%m-%dT%H:%M:%SZ")


class EventLog:
    def __init__(self, store: Store, clock: Clock) -> None:
        self._store = store
        self._clock = clock
        self._waiters: set[asyncio.Event] = set()
        self.version = 0  # bumped on every notify, so a reader can tell it missed one

    def append(self, stream: str, events: Sequence[Event]) -> list[Envelope]:
        """Blocking append. Call inside `store.atomic()` to commit with other writes,
        then call `notify()` from the event loop once the transaction has committed."""
        payload = [(event.type, event.data()) for event in events]
        return self._store.events.append(stream, payload, iso(self._clock))

    def notify(self) -> None:
        self.version += 1
        for waiter in self._waiters:
            waiter.set()

    async def publish(self, stream: str, events: Sequence[Event]) -> list[Envelope]:
        envelopes = await asyncio.to_thread(self.append, stream, events)
        self.notify()
        return envelopes

    async def read(self, streams: Sequence[str], after: int, limit: int = 200) -> list[Envelope]:
        limit = max(1, min(MAX_PAGE, limit))
        return await asyncio.to_thread(self._store.events.read, list(streams), after, limit)

    async def wait(self, seen_version: int, max_wait: float) -> bool:
        """Wait until something is appended after `seen_version` (True) or `max_wait` seconds pass.

        Read `version` before reading events and pass it here: an append that lands between
        the read and the wait is then noticed immediately instead of after the timeout.
        """
        if self.version != seen_version:
            return True
        waiter = asyncio.Event()
        self._waiters.add(waiter)
        try:
            await asyncio.wait_for(waiter.wait(), max_wait)
            return True
        except TimeoutError:
            return False
        finally:
            self._waiters.discard(waiter)
