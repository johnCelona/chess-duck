import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILES_ROOT = ROOT / "config" / "profiles"


def list_profiles(engine_id: str) -> list[dict]:
    engine_dir = PROFILES_ROOT / engine_id
    if not engine_dir.exists():
        return []
    profiles = []
    for path in sorted(engine_dir.glob("*.json")):
        profiles.append(json.loads(path.read_text(encoding="utf-8")))
    return profiles


def save_profile(engine_id: str, name: str, payload: dict) -> dict:
    engine_dir = PROFILES_ROOT / engine_id
    engine_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(
        character for character in name if character.isalnum() or character in "-_ "
    ).strip()
    if not safe_name:
        raise ValueError("Profile name is required")
    profile = {"name": safe_name, **payload}
    path = engine_dir / f"{safe_name.lower().replace(' ', '-')}.json"
    path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return profile
