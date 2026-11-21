import pytest

from app.security import advertised_limit, validate_limit


ADVERTISED = {
    "Threads": {"type": "spin", "default": 1, "min": 1, "max": 512, "choices": None},
    "Hash": {"type": "spin", "default": 16, "min": 1, "max": 131072, "choices": None},
    "MultiPV": {"type": "spin", "default": 1, "min": 1, "max": 256, "choices": None},
    "UCI_LimitStrength": {"type": "check", "default": False, "min": 0, "max": 1, "choices": None},
    "UCI_Elo": {"type": "spin", "default": 1350, "min": 1320, "max": 3150, "choices": None},
}


def test_option_values_are_clamped():
    assert advertised_limit("Threads", 999, ADVERTISED) == 8
    assert advertised_limit("Hash", 0, ADVERTISED) == 1
    assert advertised_limit("MultiPV", 500, ADVERTISED) == 10


def test_blocked_option_is_rejected():
    with pytest.raises(ValueError):
        advertised_limit("EvalFile", "evil.nnue", ADVERTISED)


@pytest.mark.parametrize(
    ("limit_type", "value"),
    [("nodes", 5_000_001), ("depth", 101), ("time", 60_001)],
)
def test_server_limit_caps(limit_type, value):
    with pytest.raises(ValueError):
        validate_limit(limit_type, value)
