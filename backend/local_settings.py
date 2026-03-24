from __future__ import annotations

import base64
from pathlib import Path


ITSLEARNING_KEYS = (
    "ITSLEARNING_BASE_URL",
    "ITSLEARNING_USERNAME",
    "ITSLEARNING_PASSWORD",
    "ITSLEARNING_MAX_UPDATES",
)

NEXTCLOUD_KEYS = (
    "NEXTCLOUD_BASE_URL",
    "NEXTCLOUD_USERNAME",
    "NEXTCLOUD_PASSWORD",
    "NEXTCLOUD_WORKSPACE_URL",
    "NEXTCLOUD_Q1Q2_URL",
    "NEXTCLOUD_Q3Q4_URL",
    "NEXTCLOUD_LINK_1_LABEL",
    "NEXTCLOUD_LINK_1_URL",
    "NEXTCLOUD_LINK_2_LABEL",
    "NEXTCLOUD_LINK_2_URL",
    "NEXTCLOUD_LINK_3_LABEL",
    "NEXTCLOUD_LINK_3_URL",
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


def save_nextcloud_settings(
    env_path: Path,
    *,
    base_url: str,
    username: str,
    password: str,
    workspace_url: str,
    q1q2_url: str,
    q3q4_url: str,
    link_1_label: str = "",
    link_1_url: str = "",
    link_2_label: str = "",
    link_2_url: str = "",
    link_3_label: str = "",
    link_3_url: str = "",
) -> None:
    updates = {
        "NEXTCLOUD_BASE_URL": base_url.strip(),
        "NEXTCLOUD_USERNAME": username.strip(),
        "NEXTCLOUD_PASSWORD": password.strip(),
        "NEXTCLOUD_WORKSPACE_URL": workspace_url.strip(),
        "NEXTCLOUD_Q1Q2_URL": q1q2_url.strip(),
        "NEXTCLOUD_Q3Q4_URL": q3q4_url.strip(),
        "NEXTCLOUD_LINK_1_LABEL": link_1_label.strip(),
        "NEXTCLOUD_LINK_1_URL": link_1_url.strip(),
        "NEXTCLOUD_LINK_2_LABEL": link_2_label.strip(),
        "NEXTCLOUD_LINK_2_URL": link_2_url.strip(),
        "NEXTCLOUD_LINK_3_LABEL": link_3_label.strip(),
        "NEXTCLOUD_LINK_3_URL": link_3_url.strip(),
    }
    _upsert_env_values(env_path, updates)


def save_classwork_file(target_path: Path, *, filename: str, content_base64: str) -> None:
    normalized_name = filename.strip().lower()
    if not normalized_name.endswith((".xlsx", ".xlsm")):
        raise ValueError("Bitte eine XLSX- oder XLSM-Datei auswaehlen.")

    try:
        file_bytes = base64.b64decode(content_base64, validate=True)
    except Exception as exc:
        raise ValueError("Dateiinhalt konnte nicht gelesen werden.") from exc

    if not file_bytes:
        raise ValueError("Die ausgewaehlte Datei ist leer.")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(file_bytes)


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
