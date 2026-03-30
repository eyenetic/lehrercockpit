"""
Datenbank-Migrationen für Multi-User-Architektur.
Führt alle Migrationen idempotent aus.
"""


def run_migrations(conn) -> None:
    """Führt alle Schema-Migrationen idempotent aus.

    Erstellt alle notwendigen Tabellen für die Multi-User-Architektur
    und fügt Seed-Daten für die Modul-Registry ein.

    Args:
        conn: psycopg3 DB-Verbindung (wird nicht committed hier).
    """
    # ── Bestehende app_state-Tabelle (aus persistence.py) ─────────────────────
    from backend.persistence import store
    store.init_schema()

    # ── users ──────────────────────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          SERIAL PRIMARY KEY,
            first_name  TEXT NOT NULL,
            last_name   TEXT NOT NULL,
            role        TEXT NOT NULL DEFAULT 'teacher' CHECK (role IN ('admin', 'teacher')),
            is_active   BOOLEAN NOT NULL DEFAULT TRUE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ── user_access_codes ──────────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_access_codes (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            code_hash   TEXT NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id)
        )
    """)

    # ── sessions ───────────────────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at  TIMESTAMPTZ NOT NULL,
            last_seen   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ── modules ────────────────────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS modules (
            id              TEXT PRIMARY KEY,
            display_name    TEXT NOT NULL,
            description     TEXT NOT NULL DEFAULT '',
            module_type     TEXT NOT NULL DEFAULT 'individual'
                            CHECK (module_type IN ('individual', 'central', 'local')),
            is_enabled      BOOLEAN NOT NULL DEFAULT TRUE,
            default_visible BOOLEAN NOT NULL DEFAULT TRUE,
            default_order   INTEGER NOT NULL DEFAULT 100,
            requires_config BOOLEAN NOT NULL DEFAULT FALSE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ── user_modules ───────────────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_modules (
            id            SERIAL PRIMARY KEY,
            user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            module_id     TEXT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
            is_visible    BOOLEAN NOT NULL DEFAULT TRUE,
            sort_order    INTEGER NOT NULL DEFAULT 100,
            is_configured BOOLEAN NOT NULL DEFAULT FALSE,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, module_id)
        )
    """)

    # ── user_module_configs ────────────────────────────────────────────────────
    # SICHERHEITSHINWEIS: Credentials werden aktuell im Klartext gespeichert.
    # Für Produktion: Verschlüsselung mit AES-256 empfohlen (siehe architecture.md)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_module_configs (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            module_id   TEXT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
            config_data JSONB NOT NULL DEFAULT '{}',
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, module_id)
        )
    """)

    # ── system_settings ────────────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key         TEXT PRIMARY KEY,
            value       JSONB NOT NULL DEFAULT '{}',
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ── Indizes ────────────────────────────────────────────────────────────────
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_sessions_expires_at
            ON sessions (expires_at)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_sessions_user_id
            ON sessions (user_id)
    """)

    # ── Seed-Daten: Modul-Registry ─────────────────────────────────────────────
    modules_seed = [
        # (id, display_name, description, module_type, is_enabled, default_visible, default_order, requires_config)
        ("itslearning",       "itslearning Lernplattform", "", "individual", True,  True,  10,  True),
        ("nextcloud",         "Nextcloud",                 "", "individual", True,  True,  20,  False),
        ("webuntis",          "WebUntis Stundenplan",      "", "individual", True,  True,  30,  True),
        ("orgaplan",          "Orgaplan",                  "", "central",    True,  True,  40,  False),
        ("klassenarbeitsplan","Klassenarbeitsplan",         "", "central",    True,  True,  50,  False),
        ("noten",             "Noten",                     "", "individual", True,  True,  60,  False),
        ("mail",              "Dienstmail (lokal)",         "", "local",      True,  False, 70,  False),
    ]

    for (mid, display_name, description, module_type, is_enabled,
         default_visible, default_order, requires_config) in modules_seed:
        conn.execute(
            """
            INSERT INTO modules
                (id, display_name, description, module_type, is_enabled,
                 default_visible, default_order, requires_config)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (mid, display_name, description, module_type, is_enabled,
             default_visible, default_order, requires_config),
        )

    # ── audit_log ───────────────────────────────────────────────────────────────
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id          SERIAL PRIMARY KEY,
                event_type  VARCHAR(64) NOT NULL,
                user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
                ip_address  VARCHAR(64),
                details     JSONB DEFAULT '{}',
                created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_log_user_id
                ON audit_log(user_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_log_event_type
                ON audit_log(event_type)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_log_created_at
                ON audit_log(created_at)
        """)
    except Exception as _audit_exc:
        print(f"[migrations] audit_log migration skipped (already applied?): {_audit_exc}", flush=True)

    # ── grades (per-user, Phase 9b) ──────────────────────────────────────────────
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS grades (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                class_name  VARCHAR(64) NOT NULL,
                subject     VARCHAR(128),
                grade_value VARCHAR(32) NOT NULL,
                grade_date  DATE,
                note        TEXT DEFAULT '',
                created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_grades_user_id
                ON grades(user_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_grades_class_name
                ON grades(user_id, class_name)
        """)
    except Exception as _grades_exc:
        print(f"[migrations] grades migration skipped (already applied?): {_grades_exc}", flush=True)

    # ── class_notes (per-user, Phase 9b) ─────────────────────────────────────────
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS class_notes (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                class_name  VARCHAR(64) NOT NULL,
                note_text   TEXT DEFAULT '',
                created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(user_id, class_name)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_class_notes_user_id
                ON class_notes(user_id)
        """)
    except Exception as _notes_exc:
        print(f"[migrations] class_notes migration skipped (already applied?): {_notes_exc}", flush=True)

    # ── code_prefix optimisation (Phase 9c) ──────────────────────────────────────
    try:
        conn.execute("""
            ALTER TABLE user_access_codes
                ADD COLUMN IF NOT EXISTS code_prefix VARCHAR(8)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_access_codes_prefix
                ON user_access_codes(code_prefix)
                WHERE code_prefix IS NOT NULL
        """)
    except Exception as _prefix_exc:
        print(f"[migrations] code_prefix migration skipped (already applied?): {_prefix_exc}", flush=True)

    # ── is_admin flag (Phase 13) ──────────────────────────────────────────────
    # Separates authorization flag from the identity `role` field.
    # Backfills existing admin-role users so they keep admin access after migration.
    try:
        conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE
        """)
        conn.execute("""
            UPDATE users SET is_admin = TRUE WHERE role = 'admin' AND is_admin = FALSE
        """)
    except Exception as _is_admin_exc:
        print(f"[migrations] is_admin migration skipped (already applied?): {_is_admin_exc}", flush=True)

    print("[migrations] Alle Migrationen erfolgreich ausgeführt.", flush=True)


def _migrate_seed_today_modules(conn) -> None:
    """Seed-Migration Phase 14: Neue zentrale Heute-Module und app_title-Setting.

    Idempotent via ON CONFLICT DO NOTHING.
    """
    conn.execute("""
        INSERT INTO modules (id, display_name, description, module_type, is_enabled, default_visible, default_order, requires_config)
        VALUES
          ('tagesbriefing', 'Tagesbriefing', 'Tageszusammenfassung und aktuelle Hinweise', 'central', TRUE, TRUE, 1, FALSE),
          ('zugaenge', 'Zugänge', 'Schnellzugriff auf externe Systeme', 'central', TRUE, TRUE, 2, FALSE),
          ('wichtige-termine', 'Wichtige Termine', 'Schulkalender-Termine aus dem Schulportal', 'central', TRUE, FALSE, 90, FALSE)
        ON CONFLICT (id) DO NOTHING
    """)
    conn.execute("""
        INSERT INTO system_settings (key, value)
        VALUES ('app_title', '"Lehrercockpit"')
        ON CONFLICT (key) DO NOTHING
    """)
    print("[migrations] Phase 14: Heute-Module und app_title geseedet.", flush=True)


def run_all_migrations() -> None:
    """Führt alle Migrationen aus. Wird bei App-Start aufgerufen wenn DATABASE_URL gesetzt."""
    from .db import db_connection
    with db_connection() as conn:
        run_migrations(conn)
        _migrate_seed_today_modules(conn)


def log_audit_event(
    conn,
    event_type: str,
    user_id=None,
    ip_address=None,
    details=None,
) -> None:
    """Schreibt ein Audit-Log-Ereignis in die audit_log-Tabelle.

    Fehler beim Schreiben werden geloggt aber nicht weitergeworfen,
    damit ein Audit-Log-Fehler niemals den eigentlichen Request abbricht.

    Args:
        conn: psycopg3 DB-Verbindung.
        event_type: Ereignistyp (z.B. 'login_success', 'login_failure', 'bootstrap_created').
        user_id: ID des betroffenen Users (optional).
        ip_address: IP-Adresse des Clients (optional).
        details: Zusätzliche Infos als dict (optional).
    """
    import json as _json
    import psycopg.types.json as _pjson

    if details is None:
        details = {}

    try:
        conn.execute(
            """
            INSERT INTO audit_log (event_type, user_id, ip_address, details)
            VALUES (%s, %s, %s, %s)
            """,
            (event_type, user_id, ip_address, _pjson.Jsonb(details)),
        )
    except Exception as exc:
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "[audit] Failed to write audit log event '%s': %s", event_type, exc
        )
