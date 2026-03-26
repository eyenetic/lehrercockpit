#!/usr/bin/env python3
"""
scripts/admin_recovery.py

Operator-only admin access recovery tool.

SECURITY:
- Requires DATABASE_URL environment variable (server/Render access only)
- Does NOT expose any HTTP endpoint
- Prints access code once to stdout — operator must save it securely
- All operations are logged to audit_log table

USAGE:
    python3 scripts/admin_recovery.py --list
    python3 scripts/admin_recovery.py --rotate-admin <user_id>
    python3 scripts/admin_recovery.py --ensure-bootstrap-admin

RENDER USAGE:
    In Render dashboard → Shell:
    python3 scripts/admin_recovery.py --list
"""
from __future__ import annotations

import argparse
import os
import sys


def _check_env() -> None:
    """Exit with a clear error message if DATABASE_URL is not set."""
    if not os.environ.get("DATABASE_URL", "").strip():
        print(
            "[recovery] ERROR: DATABASE_URL environment variable is not set.",
            file=sys.stderr,
        )
        print(
            "[recovery] This script requires direct database access. "
            "Run it from the Render Shell or a server with DATABASE_URL configured.",
            file=sys.stderr,
        )
        sys.exit(1)


def _print_access_code_banner(user_id: int, display_name: str, plain_code: str) -> None:
    """Print the new plaintext access code exactly once in a clear format."""
    print(
        f"\n{'=' * 60}\n"
        f"[RECOVERY] Zugangscode für Admin-User rotiert.\n"
        f"[RECOVERY] User-ID: {user_id} | Name: {display_name}\n"
        f"[RECOVERY] Neuer Zugangscode: {plain_code}\n"
        f"[RECOVERY] Bitte diesen Code sofort sichern!\n"
        f"[RECOVERY] Er wird NICHT erneut angezeigt.\n"
        f"{'=' * 60}\n",
        flush=True,
    )


def cmd_list() -> None:
    """List all admin users (is_admin=TRUE) and whether they have an access code.

    Phase 13: queries by is_admin=TRUE (not role='admin') to include teacher+admin users.
    Exit code 0 if admins found, 1 if no admins exist.
    """
    from backend.db import db_connection

    try:
        with db_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, first_name, last_name, role, is_active, created_at, is_admin
                FROM users
                WHERE is_admin = TRUE
                ORDER BY id
                """
            ).fetchall()

            if not rows:
                print("[recovery] Keine Admin-User gefunden.", flush=True)
                sys.exit(1)

            print(f"\n[recovery] {len(rows)} Admin-User gefunden:\n", flush=True)
            print(
                f"{'ID':<6} {'Vorname':<15} {'Nachname':<20} {'Rolle':<10} "
                f"{'is_admin':<10} {'Aktiv':<8} {'Hat Code':<10} {'Erstellt am'}",
                flush=True,
            )
            print("-" * 100, flush=True)

            for row in rows:
                user_id = row[0]
                first_name = row[1] if row[1] else ""
                last_name = row[2] if row[2] else ""
                role = row[3]
                is_active = row[4]
                created_at = row[5]
                is_admin_flag = row[6]

                # Check if they have an access code
                code_row = conn.execute(
                    "SELECT COUNT(*) FROM user_access_codes WHERE user_id = %s",
                    (user_id,),
                ).fetchone()
                has_code = (code_row[0] > 0) if code_row else False

                created_str = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "?"
                active_str = "Ja" if is_active else "Nein"
                code_str = "Ja" if has_code else "NEIN"
                admin_str = "Ja" if is_admin_flag else "Nein"

                print(
                    f"{user_id:<6} {first_name:<15} {last_name:<20} {role:<10} "
                    f"{admin_str:<10} {active_str:<8} {code_str:<10} {created_str}",
                    flush=True,
                )

            print("", flush=True)

    except SystemExit:
        raise
    except Exception as exc:
        print(
            f"[recovery] ERROR: Fehler beim Laden der Admin-User: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)


def cmd_rotate_admin(user_id_str: str) -> None:
    """Rotate the access code for an existing admin user.

    Args:
        user_id_str: User ID as string (will be validated as integer).
    """
    # Validate user_id is an integer
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        print(
            f"[recovery] ERROR: Ungültige User-ID '{user_id_str}' — muss eine Ganzzahl sein.",
            file=sys.stderr,
        )
        sys.exit(1)

    from backend.db import db_connection
    from backend.auth.access_code import generate_code, hash_code, get_code_prefix
    from backend.users.user_store import set_access_code
    from backend.migrations import log_audit_event

    try:
        with db_connection() as conn:
            # Query the user — must exist AND have is_admin=TRUE
            row = conn.execute(
                """
                SELECT id, first_name, last_name, role, is_active, is_admin
                FROM users
                WHERE id = %s
                """,
                (user_id,),
            ).fetchone()

            if row is None:
                print(
                    f"[recovery] ERROR: User mit ID {user_id} nicht gefunden.",
                    file=sys.stderr,
                )
                sys.exit(1)

            is_admin_flag = row[5] if len(row) > 5 else False
            role = row[3]
            # Phase 13: check is_admin flag (not role) for admin authorization
            # Also accept legacy role='admin' for backward compat
            if not is_admin_flag and role != "admin":
                print(
                    f"[recovery] ERROR: User {user_id} ist kein Admin "
                    f"(is_admin=False, role='{role}'). "
                    f"Nur Admin-User können mit --rotate-admin rotiert werden.",
                    file=sys.stderr,
                )
                sys.exit(1)

            first_name = row[1] or ""
            last_name = row[2] or ""
            display_name = f"{first_name} {last_name}".strip() or f"User #{user_id}"

            # Generate new access code
            plain_code = generate_code()
            code_hash = hash_code(plain_code)
            prefix = get_code_prefix(plain_code)

            # Store the hashed code
            set_access_code(conn, user_id, code_hash, code_prefix=prefix)

            # Log audit event
            log_audit_event(
                conn,
                "admin_code_rotated_by_operator",
                user_id=user_id,
                details={"method": "cli_recovery"},
            )

        # Print code ONLY after successful DB commit (outside db_connection context)
        _print_access_code_banner(user_id, display_name, plain_code)

    except SystemExit:
        raise
    except Exception as exc:
        print(
            f"[recovery] ERROR: Fehler beim Rotieren des Admin-Codes: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)


def cmd_ensure_bootstrap_admin() -> None:
    """Ensure at least one admin user exists.

    If admins exist: print their count and exit 0.
    If no admin exists: create one and print the access code.
    """
    from backend.db import db_connection
    from backend.users.user_service import create_teacher
    from backend.migrations import log_audit_event

    try:
        with db_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM users WHERE is_admin = TRUE"
            ).fetchone()
            admin_count = row[0] if row else 0

            if admin_count > 0:
                print(
                    f"[RECOVERY] Es existieren bereits {admin_count} Admin-User(s). "
                    f"Verwende --list und --rotate-admin.",
                    flush=True,
                )
                return

            # No admin exists: create one
            # Phase 13: canonical form is role='teacher' + is_admin=True
            user, plain_code = create_teacher(conn, "Recovery", "Admin", role="teacher", is_admin=True)

            # Log audit event
            log_audit_event(
                conn,
                "bootstrap_admin_created_by_operator",
                user_id=user.id,
                details={"method": "cli_recovery"},
            )

        # Print code ONLY after successful DB commit
        _print_access_code_banner(user.id, user.full_name, plain_code)

    except SystemExit:
        raise
    except Exception as exc:
        print(
            f"[recovery] ERROR: Fehler beim Erstellen des Bootstrap-Admins: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Operator-only admin access recovery tool. "
            "Requires DATABASE_URL to be set (Render Shell or server SSH access)."
        )
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--list",
        action="store_true",
        help="List all admin users and whether they have an access code configured.",
    )
    group.add_argument(
        "--rotate-admin",
        metavar="USER_ID",
        help="Generate a new access code for the admin user with the given ID.",
    )
    group.add_argument(
        "--ensure-bootstrap-admin",
        action="store_true",
        help="Create a recovery admin if no admin user exists; otherwise list existing admins.",
    )

    args = parser.parse_args()

    _check_env()

    if args.list:
        cmd_list()
    elif args.rotate_admin is not None:
        cmd_rotate_admin(args.rotate_admin)
    elif args.ensure_bootstrap_admin:
        cmd_ensure_bootstrap_admin()


if __name__ == "__main__":
    main()
