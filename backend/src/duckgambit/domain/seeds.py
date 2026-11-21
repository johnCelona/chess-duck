"""Seed derivation and seeded draws.

Every random choice gets its own generator derived from (seed, labels), so a single
decision can be replayed without replaying everything before it (ADR-0005).
Only integer arithmetic touches the outcome, so results match on every platform.
"""

from __future__ import annotations

import hashlib
import random


def derive_seed(seed: int, *labels: object) -> int:
    text = ":".join([str(seed), *(str(label) for label in labels)])
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def rng_for(seed: int, *labels: object) -> random.Random:
    return random.Random(derive_seed(seed, *labels))


def draw_below(rng: random.Random, total: int) -> int:
    """Uniform integer in [0, total) using only integer arithmetic."""
    if total <= 0:
        raise ValueError("total must be positive")
    return (rng.getrandbits(53) * total) >> 53


def pick_weighted(rng: random.Random, weights: list[int]) -> int:
    """Index chosen with probability proportional to its integer weight."""
    total = sum(weights)
    target = draw_below(rng, total)
    running = 0
    for index, weight in enumerate(weights):
        running += weight
        if target < running:
            return index
    return len(weights) - 1
