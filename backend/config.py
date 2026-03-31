from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

# ── SaaS / Deployment environment variables ───────────────────────────────────
# These are read once at import time and used throughout the application.

LEHRERCOCKPIT_ENV = os.environ.get("LEHRERCOCKPIT_ENV", "development")
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "http://localhost:3000")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
API_URL = os.environ.get("API_URL", "http://localhost:5000")
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "")  # Fernet key for module config encryption

# Login rate limiting — ENV-configurable thresholds
# Set LOGIN_RATE_LIMIT_MAX and LOGIN_RATE_LIMIT_WINDOW_SECONDS in your deployment ENV to tune.
LOGIN_RATE_LIMIT_MAX = int(os.environ.get("LOGIN_RATE_LIMIT_MAX", "10"))
LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "900"))
LOGIN_RATE_LIMIT_MAX_PER_MINUTE = int(os.environ.get("LOGIN_RATE_LIMIT_MAX_PER_MINUTE", "5"))


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
class NextcloudSettings:
    base_url: str
    username: str
    password: str
    workspace_url: str
    q1q2_url: str
    q3q4_url: str
    link_1_label: str
    link_1_url: str
    link_2_label: str
    link_2_url: str
    link_3_label: str
    link_3_url: str

    @property
    def configured(self) -> bool:
        return bool(
            self.base_url
            or self.workspace_url
            or self.q1q2_url
            or self.q3q4_url
            or self.link_1_url
            or self.link_2_url
            or self.link_3_url
        )

    @property
    def login_configured(self) -> bool:
        return bool(self.base_url and self.username and self.password)

    @property
    def workspace_links(self) -> list[dict[str, str]]:
        links = []
        for index, (label, url) in enumerate(
            [
                (self.link_1_label, self.link_1_url),
                (self.link_2_label, self.link_2_url),
                (self.link_3_label, self.link_3_url),
            ],
            start=1,
        ):
            if url.strip():
                links.append(
                    {
                        "id": f"custom-{index}",
                        "label": (label or f"Arbeitslink {index}").strip(),
                        "url": url.strip(),
                    }
                )
        return links


@dataclass
class AppSettings:
    teacher_name: str
    school_name: str
    mail: MailSettings
    itslearning: ItslearningSettings
    nextcloud: NextcloudSettings
    schoolportal_url: str
    webuntis_base_url: str
    webuntis_ical_url: str
    orgaplan_pdf_url: str
    classwork_plan_url: str
    classwork_plan_local_path: str

    @property
    def itslearning_base_url(self) -> str:
        return self.itslearning.base_url

    @property
    def nextcloud_base_url(self) -> str:
        return self.nextcloud.base_url


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
    project_root = Path(__file__).resolve().parent.parent

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
        max_messages=_env_int("MAIL_MAX_MESSAGES", 12),
    )
    itslearning_settings = ItslearningSettings(
        base_url=os.getenv("ITSLEARNING_BASE_URL", "").strip(),
        username=os.getenv("ITSLEARNING_USERNAME", "").strip(),
        password=os.getenv("ITSLEARNING_PASSWORD", "").strip(),
        max_updates=_env_int("ITSLEARNING_MAX_UPDATES", 6),
    )
    nextcloud_settings = NextcloudSettings(
        base_url=os.getenv("NEXTCLOUD_BASE_URL", "https://nextcloud-g2.b-sz-heos.logoip.de").strip(),
        username=os.getenv("NEXTCLOUD_USERNAME", "").strip(),
        password=os.getenv("NEXTCLOUD_PASSWORD", "").strip(),
        workspace_url=os.getenv("NEXTCLOUD_WORKSPACE_URL", "https://nextcloud-g2.b-sz-heos.logoip.de/index.php/apps/files/").strip(),
        q1q2_url=os.getenv("NEXTCLOUD_Q1Q2_URL", "https://nextcloud-g2.b-sz-heos.logoip.de/index.php/f/4008901").strip(),
        q3q4_url=os.getenv("NEXTCLOUD_Q3Q4_URL", "https://nextcloud-g2.b-sz-heos.logoip.de/index.php/f/4008900").strip(),
        link_1_label=os.getenv("NEXTCLOUD_LINK_1_LABEL", "").strip(),
        link_1_url=os.getenv("NEXTCLOUD_LINK_1_URL", "").strip(),
        link_2_label=os.getenv("NEXTCLOUD_LINK_2_LABEL", "").strip(),
        link_2_url=os.getenv("NEXTCLOUD_LINK_2_URL", "").strip(),
        link_3_label=os.getenv("NEXTCLOUD_LINK_3_LABEL", "").strip(),
        link_3_url=os.getenv("NEXTCLOUD_LINK_3_URL", "").strip(),
    )

    return AppSettings(
        teacher_name=os.getenv("TEACHER_NAME", "").strip(),
        school_name=os.getenv("SCHOOL_NAME", "Stadtteilschule Nord").strip() or "Stadtteilschule Nord",
        mail=mail_settings,
        itslearning=itslearning_settings,
        nextcloud=nextcloud_settings,
        schoolportal_url=os.getenv("SCHOOLPORTAL_URL", "https://schulportal.berlin.de").strip(),
        webuntis_base_url=os.getenv("WEBUNTIS_BASE_URL", "").strip(),
        webuntis_ical_url=os.getenv("WEBUNTIS_ICAL_URL", "").strip(),
        orgaplan_pdf_url=os.getenv("ORGAPLAN_PDF_URL", "").strip(),
        classwork_plan_url=os.getenv("CLASSWORK_PLAN_URL", "").strip(),
        classwork_plan_local_path=os.getenv(
            "CLASSWORK_PLAN_LOCAL_PATH",
            str(project_root / "data" / "classwork-plan-local.xlsx"),
        ).strip(),
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
