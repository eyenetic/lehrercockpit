"""
Bootstrap-Admin: Stellt sicher dass mindestens ein Admin-User existiert.
Wird beim App-Start aufgerufen. Idempotent — führt nichts aus wenn bereits
ein Admin vorhanden ist.

Sicherheits-Härtungen (Phase 8b):
- PostgreSQL advisory lock verhindert TOCTOU-Race bei mehreren Worker-Prozessen.
- Audit-Log-Eintrag nach Bootstrap-Erstellung.
- system_settings-Flag 'bootstrap_pending_rotation' für Admin-Panel-Banner.
- system_settings-Flag 'bootstrap_completed_at' für Audit-Trail.
"""
from datetime import datetime


def ensure_bootstrap_admin() -> None:
    """Erstellt einen Bootstrap-Admin falls noch kein Admin-User existiert.

    Gibt den Klartext-Zugangscode einmalig auf stdout aus (erscheint in
    Render-Logs beim ersten Deploy). Der Code wird NUR gehasht gespeichert.

    Sicher bei jedem App-Start aufrufbar — kehrt sofort zurück wenn bereits
    ein Admin vorhanden ist.

    Verwendet einen PostgreSQL advisory lock um TOCTOU-Races bei mehreren
    gunicorn-Workern zu verhindern.
    """
    from backend.db import db_connection
    from backend.users.user_service import create_teacher
    from backend.migrations import log_audit_event
    from backend.admin.admin_service import set_system_setting

    try:
        with db_connection() as conn:
            # Acquire session-level advisory lock to prevent concurrent bootstrap
            conn.execute("SELECT pg_advisory_lock(12345678)")
            try:
                row = conn.execute(
                    "SELECT COUNT(*) FROM users WHERE role = 'admin'"
                ).fetchone()
                if row and row[0] > 0:
                    return  # Admin already exists — nothing to do

                # No admin exists: create Bootstrap Admin
                user, plain_code = create_teacher(conn, "Bootstrap", "Admin", role="admin")

                # Log audit event
                log_audit_event(
                    conn,
                    "bootstrap_created",
                    user_id=user.id,
                    details={"note": "See server logs for initial access code"},
                )

                # Store bootstrap completion timestamp and rotation flag
                set_system_setting(
                    conn,
                    "bootstrap_completed_at",
                    datetime.utcnow().isoformat(),
                )
                set_system_setting(
                    conn,
                    "bootstrap_pending_rotation",
                    "true",
                )

                print(
                    f"\n{'=' * 60}\n"
                    f"[BOOTSTRAP] Erster Admin-User wurde erstellt.\n"
                    f"[BOOTSTRAP] User-ID: {user.id} | Name: {user.full_name}\n"
                    f"[BOOTSTRAP] Zugangscode (EINMALIG - SOFORT SICHERN):\n"
                    f"[BOOTSTRAP] {plain_code}\n"
                    f"[BOOTSTRAP] WICHTIG: Diesen Code nach dem ersten Login\n"
                    f"[BOOTSTRAP] im Admin-Panel rotieren!\n"
                    f"{'=' * 60}\n",
                    flush=True,
                )

            finally:
                conn.execute("SELECT pg_advisory_unlock(12345678)")

    except Exception as exc:
        print(f"[BOOTSTRAP] Fehler beim Admin-Bootstrap: {type(exc).__name__}: {exc}", flush=True)
