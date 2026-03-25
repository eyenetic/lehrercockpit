#!/usr/bin/env python3
"""
scripts/backfill_encryption.py

Migrates existing plaintext module config values to Fernet-encrypted storage.

USAGE:
    python scripts/backfill_encryption.py [--dry-run] [--verbose]

    Or as a module:
    python -m scripts.backfill_encryption [--dry-run] [--verbose]

REQUIREMENTS:
    - DATABASE_URL must be set (PostgreSQL connection string)
    - ENCRYPTION_KEY must be set (valid Fernet key)

    Generate a key:
      python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

SAFETY:
    - Idempotent: already-encrypted values (starting with 'enc:') are skipped
    - Dry-run mode: shows what would change without writing anything
    - Performs a round-trip verification before each write:
        encrypt → decrypt → assert equals original
    - Does not touch configs with no sensitive fields (no password/secret/token/credential keys)
    - Safe to re-run: encrypt_config() skips already-encrypted values

WHAT IT DOES:
    1. Loads all rows from user_module_configs
    2. For each row: calls decrypt_config() (pass-through for plaintext) then encrypt_config()
    3. If the result differs from the original: this row needs updating
    4. In dry-run: just prints what would change
    5. In live mode: UPDATE user_module_configs SET config_data = %s WHERE id = %s
    6. Reports a summary: X rows processed, Y rows updated, Z rows skipped

EXIT CODES:
    0 - success
    1 - missing environment variables or configuration error
    2 - database connection error
    3 - unexpected error during backfill
"""
from __future__ import annotations

import argparse
import os
import sys


def _check_env() -> None:
    """Exit with a clear error message if required env vars are not set."""
    missing = []
    if not os.environ.get("DATABASE_URL", "").strip():
        missing.append("DATABASE_URL")
    if not os.environ.get("ENCRYPTION_KEY", "").strip():
        missing.append("ENCRYPTION_KEY")
    if missing:
        print(
            f"[backfill] ERROR: Required environment variable(s) not set: {', '.join(missing)}",
            file=sys.stderr,
        )
        print(
            "[backfill] Set DATABASE_URL (PostgreSQL connection string) and "
            "ENCRYPTION_KEY (Fernet key) before running this script.",
            file=sys.stderr,
        )
        sys.exit(1)


def _is_any_sensitive_plaintext(config: dict) -> bool:
    """Return True if any sensitive field in config is stored in plaintext (not 'enc:' prefix)."""
    _SENSITIVE_PATTERNS = ("password", "secret", "token", "credential")
    _ENC_PREFIX = "enc:"
    for key, value in config.items():
        key_lower = key.lower()
        if any(pat in key_lower for pat in _SENSITIVE_PATTERNS):
            if isinstance(value, str) and value and not value.startswith(_ENC_PREFIX):
                return True
    return False


def backfill(dry_run: bool = False, verbose: bool = False) -> None:
    """Main backfill logic.

    Args:
        dry_run: If True, only print what would change without writing to DB.
        verbose: If True, print details for every row (including skipped ones).
    """
    # Import here so the env check above runs first
    from backend.crypto import encrypt_config, decrypt_config, is_encryption_enabled
    from backend.db import db_connection
    import psycopg.types.json as _pjson

    if not is_encryption_enabled():
        print(
            "[backfill] ERROR: ENCRYPTION_KEY is set but encryption is not enabled. "
            "Ensure the `cryptography` package is installed: pip install cryptography>=42.0.0",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"[backfill] Starting{'  (DRY RUN — no writes)' if dry_run else ''}...")

    rows_processed = 0
    rows_updated = 0
    rows_skipped = 0
    rows_already_encrypted = 0
    rows_no_sensitive = 0

    try:
        with db_connection() as conn:
            rows = conn.execute(
                "SELECT id, user_id, module_id, config_data FROM user_module_configs"
            ).fetchall()

            print(f"[backfill] Found {len(rows)} row(s) in user_module_configs.")

            for row in rows:
                row_id, user_id, module_id, config_data = row[0], row[1], row[2], row[3]
                rows_processed += 1

                # config_data is already a dict when coming from psycopg JSONB
                if not isinstance(config_data, dict):
                    if verbose:
                        print(f"[backfill]   row {row_id} (user={user_id}, module={module_id}): "
                              f"config_data is not a dict ({type(config_data).__name__}), skipping.")
                    rows_skipped += 1
                    continue

                # Check if there are any sensitive fields at all
                if not _is_any_sensitive_plaintext(config_data):
                    # Could be: no sensitive fields, or all are already encrypted
                    _SENSITIVE_PATTERNS = ("password", "secret", "token", "credential")
                    has_any_sensitive = any(
                        any(pat in k.lower() for pat in _SENSITIVE_PATTERNS)
                        for k in config_data.keys()
                    )
                    if not has_any_sensitive:
                        if verbose:
                            print(f"[backfill]   row {row_id} (user={user_id}, module={module_id}): "
                                  f"no sensitive fields, skipping.")
                        rows_no_sensitive += 1
                        rows_skipped += 1
                    else:
                        if verbose:
                            print(f"[backfill]   row {row_id} (user={user_id}, module={module_id}): "
                                  f"all sensitive fields already encrypted, skipping.")
                        rows_already_encrypted += 1
                        rows_skipped += 1
                    continue

                # Step 1: decrypt (pass-through for plaintext, decrypts 'enc:' prefixed values)
                decrypted = decrypt_config(config_data)

                # Step 2: encrypt (will encrypt plaintext sensitive fields, skip already-encrypted)
                encrypted = encrypt_config(decrypted)

                # Step 3: compare — if no change, skip
                if encrypted == config_data:
                    if verbose:
                        print(f"[backfill]   row {row_id} (user={user_id}, module={module_id}): "
                              f"no change after encrypt, skipping.")
                    rows_skipped += 1
                    continue

                # Step 4: verify round-trip before committing
                re_decrypted = decrypt_config(encrypted)
                if re_decrypted != decrypted:
                    print(
                        f"[backfill] ERROR: Round-trip verification FAILED for row {row_id} "
                        f"(user={user_id}, module={module_id}). "
                        f"Aborting — no data written.",
                        file=sys.stderr,
                    )
                    sys.exit(3)

                # Step 5: update or dry-run
                if dry_run:
                    sensitive_keys = [
                        k for k in config_data
                        if any(pat in k.lower() for pat in ("password", "secret", "token", "credential"))
                        and isinstance(config_data[k], str) and config_data[k]
                        and not config_data[k].startswith("enc:")
                    ]
                    print(
                        f"[backfill]   DRY-RUN: would encrypt row {row_id} "
                        f"(user={user_id}, module={module_id}) "
                        f"— plaintext fields: {sensitive_keys}"
                    )
                else:
                    conn.execute(
                        "UPDATE user_module_configs SET config_data = %s, updated_at = NOW() WHERE id = %s",
                        (_pjson.Jsonb(encrypted), row_id),
                    )
                    if verbose:
                        print(f"[backfill]   ✓ encrypted row {row_id} (user={user_id}, module={module_id})")

                rows_updated += 1

    except SystemExit:
        raise
    except Exception as exc:
        print(
            f"[backfill] ERROR: Unexpected failure: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        import traceback
        traceback.print_exc()
        sys.exit(2)

    print()
    print(f"[backfill] {'DRY-RUN ' if dry_run else ''}Summary:")
    print(f"  {rows_processed} rows processed")
    print(f"  {rows_updated} rows {'would be updated' if dry_run else 'updated'}")
    print(f"  {rows_skipped} rows skipped "
          f"({rows_already_encrypted} already encrypted, "
          f"{rows_no_sensitive} no sensitive fields, "
          f"{rows_skipped - rows_already_encrypted - rows_no_sensitive} other)")

    if dry_run:
        print()
        print("[backfill] Dry-run complete. Run without --dry-run to apply changes.")
    else:
        print()
        print("[backfill] Done.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill plaintext module config values to Fernet-encrypted storage. "
            "Requires DATABASE_URL and ENCRYPTION_KEY to be set."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would change without writing to the database.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Print details for every row, including skipped ones.",
    )
    args = parser.parse_args()

    _check_env()
    backfill(dry_run=args.dry_run, verbose=args.verbose)


if __name__ == "__main__":
    main()
