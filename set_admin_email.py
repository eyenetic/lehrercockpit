#!/usr/bin/env python3
"""
set_admin_email.py — E-Mail-Adresse für einen User setzen.

Einmalig auf dem Server ausführen:
    python set_admin_email.py

Benötigt die gleichen Umgebungsvariablen wie die Haupt-App (DATABASE_URL etc.).
"""
import sys
import os

# Projekt-Root zum Pfad hinzufügen
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.db import db_connection
from backend.users.user_store import get_all_users, update_user


def main():
    print("=== E-Mail-Adresse setzen ===\n")

    with db_connection() as conn:
        users = get_all_users(conn)

        if not users:
            print("Keine User gefunden.")
            return

        print("Verfügbare User:")
        for u in users:
            admin_mark = " [Admin]" if u.is_admin else ""
            email_info = f" <{u.email}>" if u.email else " (keine E-Mail)"
            print(f"  [{u.id}] {u.full_name}{admin_mark}{email_info}")

        print()
        try:
            user_id = int(input("User-ID wählen: ").strip())
        except ValueError:
            print("Ungültige ID.")
            return

        user = next((u for u in users if u.id == user_id), None)
        if not user:
            print(f"User {user_id} nicht gefunden.")
            return

        current = f" (aktuell: {user.email})" if user.email else ""
        new_email = input(f"Neue E-Mail-Adresse für {user.full_name}{current}: ").strip()

        if not new_email or "@" not in new_email:
            print("Ungültige E-Mail-Adresse.")
            return

        update_user(conn, user_id, email=new_email)
        print(f"\n✅ E-Mail für {user.full_name} auf '{new_email}' gesetzt.")
        print("Ab sofort kann dieser User über 'Code vergessen?' auf der Login-Seite einen Reset anfordern.")


if __name__ == "__main__":
    main()
