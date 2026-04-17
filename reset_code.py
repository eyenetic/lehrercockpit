"""
Notfall-Reset: Setzt den Zugangscode eines Users auf einen bekannten Wert.
Auf dem Server ausführen: python reset_code.py

Voraussetzung: DATABASE_URL muss als Umgebungsvariable gesetzt sein.
"""
import sys
import os

# Projektroot im Pfad
sys.path.insert(0, os.path.dirname(__file__))

from backend.db import db_connection
from backend.auth.access_code import hash_code, get_code_prefix

# ── Konfiguration ──────────────────────────────────────────────────────────
# Den gewünschten neuen Code hier eintragen (mind. 6 Zeichen):
NEW_CODE = "lehrer123"
# ──────────────────────────────────────────────────────────────────────────

def list_users(conn):
    rows = conn.execute(
        "SELECT id, first_name, last_name, is_admin FROM users ORDER BY id"
    ).fetchall()
    print("\nAlle Users:")
    for row in rows:
        print(f"  ID {row[0]}: {row[1]} {row[2]} {'[ADMIN]' if row[3] else ''}")
    return rows

def reset_code(conn, user_id: int, new_code: str):
    code_hash = hash_code(new_code)
    code_prefix = get_code_prefix(new_code)
    conn.execute(
        """INSERT INTO user_access_codes (user_id, code_hash, code_prefix)
           VALUES (%s, %s, %s)
           ON CONFLICT (user_id) DO UPDATE
               SET code_hash = EXCLUDED.code_hash,
                   code_prefix = EXCLUDED.code_prefix""",
        (user_id, code_hash, code_prefix),
    )
    # Alle Sessions des Users invalidieren
    conn.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
    print(f"\n✓ Code für User-ID {user_id} wurde zurückgesetzt.")
    print(f"  Neuer Code: {new_code}")
    print(f"  Bitte nach dem Login sofort ändern!\n")

if __name__ == "__main__":
    with db_connection() as conn:
        users = list_users(conn)

        if len(sys.argv) > 1:
            user_id = int(sys.argv[1])
        else:
            user_id = int(input("\nUser-ID eingeben: "))

        reset_code(conn, user_id, NEW_CODE)
