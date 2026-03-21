from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass
class MailSettings:
    local_source: str
    local_mailbox: str
    local_account: str
    host: str
    port: int
    username: str
    password: str
    folder: str
    use_ssl: bool
    max_messages: int

    @property
    def imap_configured(self) -> bool:
        return bool(self.host and self.username and self.password)

    @property
    def apple_mail_enabled(self) -> bool:
        return self.local_source.lower() == "apple_mail"

    @property
    def configured(self) -> bool:
        return self.apple_mail_enabled or self.imap_configured


@dataclass
class ItslearningSettings:
    base_url: str
    username: str
    password: str
    max_updates: int

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    @property
    def native_login_configured(self) -> bool:
        return bool(self.base_url and self.username and self.password)


@dataclass
class AppSettings:
    teacher_name: str
    school_name: str
    mail: MailSettings
    itslearning: ItslearningSettings
    schoolportal_url: str
    webuntis_base_url: str
    webuntis_ical_url: str
    orgaplan_pdf_url: str
    classwork_plan_url: str
    classwork_gsheets_csv_url: str

    @property
    def itslearning_base_url(self) -> str:
        return self.itslearning.base_url


def _env_flag(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError:
        return default


def load_settings() -> AppSettings:
    _load_local_env_file()

    mail_settings = MailSettings(
        local_source=os.getenv("MAIL_LOCAL_SOURCE", "").strip(),
        local_mailbox=os.getenv("MAIL_LOCAL_MAILBOX", "INBOX").strip() or "INBOX",
        local_account=os.getenv("MAIL_LOCAL_ACCOUNT", "").strip(),
        host=os.getenv("MAIL_IMAP_HOST", "").strip(),
        port=_env_int("MAIL_IMAP_PORT", 993),
        username=os.getenv("MAIL_USERNAME", "").strip(),
        password=os.getenv("MAIL_PASSWORD", "").strip(),
        folder=os.getenv("MAIL_FOLDER", "INBOX").strip() or "INBOX",
        use_ssl=_env_flag("MAIL_USE_SSL", True),
        max_messages=_env_int("MAIL_MAX_MESSAGES", 8),
    )
    itslearning_settings = ItslearningSettings(
        base_url=os.getenv("ITSLEARNING_BASE_URL", "").strip(),
        username=os.getenv("ITSLEARNING_USERNAME", "").strip(),
        password=os.getenv("ITSLEARNING_PASSWORD", "").strip(),
        max_updates=_env_int("ITSLEARNING_MAX_UPDATES", 6),
    )

    return AppSettings(
        teacher_name=os.getenv("TEACHER_NAME", "").strip(),
        school_name=os.getenv("SCHOOL_NAME", "Stadtteilschule Nord").strip() or "Stadtteilschule Nord",
        mail=mail_settings,
        itslearning=itslearning_settings,
        schoolportal_url=os.getenv("SCHOOLPORTAL_URL", "https://schulportal.berlin.de").strip(),
        webuntis_base_url=os.getenv("WEBUNTIS_BASE_URL", "").strip(),
        webuntis_ical_url=os.getenv("WEBUNTIS_ICAL_URL", "").strip(),
        orgaplan_pdf_url=os.getenv("ORGAPLAN_PDF_URL", "").strip(),
        classwork_plan_url=os.getenv("CLASSWORK_PLAN_URL", "").strip(),
        classwork_gsheets_csv_url=os.getenv("CLASSWORK_GSHEETS_CSV_URL", "").strip(),
    )


def _load_local_env_file() -> None:
    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env.local"

    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            os.environ[key] = value
