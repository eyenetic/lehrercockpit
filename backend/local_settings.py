from __future__ import annotations

from pathlib import Path


ITSLEARNING_KEYS = (
    "ITSLEARNING_BASE_URL",
    "ITSLEARNING_USERNAME",
    "ITSLEARNING_PASSWORD",
    "ITSLEARNING_MAX_UPDATES",
)


def save_itslearning_settings(
    env_path: Path,
    *,
    base_url: str,
    username: str,
    password: str,
    max_updates: int = 6,
) -> None:
    updates = {
        "ITSLEARNING_BASE_URL": base_url.strip(),
        "ITSLEARNING_USERNAME": username.strip(),
        "ITSLEARNING_PASSWORD": password.strip(),
        "ITSLEARNING_MAX_UPDATES": str(max(1, min(max_updates, 12))),
    }
    _upsert_env_values(env_path, updates)


def _upsert_env_values(env_path: Path, updates: dict[str, str]) -> None:
    existing_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    remaining = dict(updates)
    rendered: list[str] = []

    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            rendered.append(line)
            continue

        key, _value = line.split("=", 1)
        normalized_key = key.strip()
        if normalized_key in remaining:
            rendered.append(f"{normalized_key}={remaining.pop(normalized_key)}")
        else:
            rendered.append(line)

    for key, value in remaining.items():
        rendered.append(f"{key}={value}")

    env_path.write_text("\n".join(rendered).rstrip() + "\n", encoding="utf-8")
