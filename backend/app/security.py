from typing import Iterable

import chess.engine


MAX_THREADS = 8
MAX_HASH_MB = 1024
MAX_NODES = 5_000_000
MAX_DEPTH = 100
MAX_TIME_MS = 60_000
MAX_MULTIPV = 10

ALLOWED_OPTIONS = {
    "Threads",
    "Hash",
    "MultiPV",
    "Skill Level",
    "UCI_LimitStrength",
    "UCI_Elo",
    "UCI_ShowWDL",
}

BLOCKED_OPTIONS = {
    "EvalFile",
    "EvalFileSmall",
    "SyzygyPath",
    "NumaPolicy",
    "Debug Log File",
}


def advertised_limit(
    option_name: str,
    value: object,
    advertised: dict[str, dict[str, object]],
) -> object:
    if option_name not in ALLOWED_OPTIONS or option_name in BLOCKED_OPTIONS:
        raise ValueError(f"Engine option is not user-settable: {option_name}")
    if option_name not in advertised:
        raise ValueError(f"Engine does not advertise option: {option_name}")

    option = advertised[option_name]
    kind = option["type"]
    if kind in {"spin", "check", "combo"}:
        if kind == "check":
            if isinstance(value, bool):
                return value
            if isinstance(value, str) and value.lower() in {"true", "false"}:
                return value.lower() == "true"
            raise ValueError(f"{option_name} must be true or false")

        if kind == "combo":
            choices = option["choices"] or []
            if value not in choices:
                raise ValueError(f"{option_name} must be one of {choices}")
            return value

        numeric = int(value)
        minimum = int(option["min"]) if option["min"] is not None else None
        maximum = int(option["max"]) if option["max"] is not None else None
        numeric = max(numeric, minimum) if minimum is not None else numeric
        numeric = min(numeric, maximum) if maximum is not None else numeric
        if option_name == "Threads":
            numeric = min(numeric, MAX_THREADS)
        if option_name == "Hash":
            numeric = min(numeric, MAX_HASH_MB)
        if option_name == "MultiPV":
            numeric = min(numeric, MAX_MULTIPV)
        return numeric
    raise ValueError(f"Unsupported engine option type: {kind}")


def validate_limit(limit_type: str, value: int) -> chess.engine.Limit:
    if limit_type == "nodes":
        if value > MAX_NODES:
            raise ValueError(f"nodes cannot exceed {MAX_NODES}")
        return chess.engine.Limit(nodes=value)
    if limit_type == "depth":
        if value > MAX_DEPTH:
            raise ValueError(f"depth cannot exceed {MAX_DEPTH}")
        return chess.engine.Limit(depth=value)
    if limit_type == "time":
        if value > MAX_TIME_MS:
            raise ValueError(f"time cannot exceed {MAX_TIME_MS}")
        return chess.engine.Limit(time=value / 1000)
    raise ValueError("limit.type must be nodes, depth, or time")
