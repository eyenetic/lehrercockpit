"""Tests für backend/modules/module_registry.py – benötigt echte DB-Connection."""
import os
import pytest


@pytest.fixture
def db_conn():
    """Erstellt eine Test-DB-Connection mit Transaction-Rollback."""
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        pytest.skip("DATABASE_URL nicht gesetzt")
    import psycopg
    conn = psycopg.connect(db_url)
    from backend.migrations import run_migrations
    run_migrations(conn)
    conn.commit()
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture
def test_user(db_conn):
    """Erstellt einen Test-User."""
    from backend.users.user_store import create_user
    return create_user(db_conn, "Module", "TestUser")


@pytest.mark.db
def test_get_all_modules(db_conn):
    """Nach Migrations: mindestens 7 Module vorhanden."""
    from backend.modules.module_registry import get_all_modules
    modules = get_all_modules(db_conn)
    assert len(modules) >= 7


@pytest.mark.db
def test_module_ids_present(db_conn):
    """itslearning, nextcloud, webuntis, orgaplan, klassenarbeitsplan, noten, mail vorhanden."""
    from backend.modules.module_registry import get_all_modules
    modules = get_all_modules(db_conn)
    module_ids = {m.id for m in modules}
    expected_ids = {
        "itslearning",
        "nextcloud",
        "webuntis",
        "orgaplan",
        "klassenarbeitsplan",
        "noten",
        "mail",
    }
    for expected_id in expected_ids:
        assert expected_id in module_ids, f"Modul '{expected_id}' fehlt. Vorhanden: {module_ids}"


@pytest.mark.db
def test_get_module_by_id(db_conn):
    """Bekannte ID → Module-Objekt."""
    from backend.modules.module_registry import get_module_by_id
    module = get_module_by_id(db_conn, "itslearning")
    assert module is not None
    assert module.id == "itslearning"
    assert module.display_name


@pytest.mark.db
def test_get_module_by_id_unknown(db_conn):
    """Unbekannte ID → None."""
    from backend.modules.module_registry import get_module_by_id
    result = get_module_by_id(db_conn, "nicht_vorhanden_xyz")
    assert result is None


@pytest.mark.db
def test_initialize_user_modules(db_conn, test_user):
    """Für neuen User: UserModule-Einträge werden erstellt."""
    from backend.modules.module_registry import initialize_user_modules, get_user_modules
    initialize_user_modules(db_conn, test_user.id)
    user_modules = get_user_modules(db_conn, test_user.id)
    assert len(user_modules) >= 7


@pytest.mark.db
def test_initialize_user_modules_idempotent(db_conn, test_user):
    """Zweimal aufrufen → keine Duplikate."""
    from backend.modules.module_registry import initialize_user_modules, get_user_modules
    initialize_user_modules(db_conn, test_user.id)
    count_first = len(get_user_modules(db_conn, test_user.id))

    initialize_user_modules(db_conn, test_user.id)
    count_second = len(get_user_modules(db_conn, test_user.id))

    assert count_first == count_second


@pytest.mark.db
def test_get_user_modules(db_conn, test_user):
    """User-Module werden geladen."""
    from backend.modules.module_registry import initialize_user_modules, get_user_modules, UserModule
    initialize_user_modules(db_conn, test_user.id)
    modules = get_user_modules(db_conn, test_user.id)
    assert all(isinstance(m, UserModule) for m in modules)
    assert all(m.user_id == test_user.id for m in modules)


@pytest.mark.db
def test_update_visibility(db_conn, test_user):
    """is_visible kann geändert werden."""
    from backend.modules.module_registry import (
        initialize_user_modules,
        get_user_modules,
        update_user_module_visibility,
    )
    initialize_user_modules(db_conn, test_user.id)
    modules = get_user_modules(db_conn, test_user.id)
    assert modules, "Keine Module vorhanden"

    first_module_id = modules[0].module_id
    original_visible = modules[0].is_visible
    new_visible = not original_visible

    result = update_user_module_visibility(db_conn, test_user.id, first_module_id, new_visible)
    assert result is True

    updated = get_user_modules(db_conn, test_user.id)
    updated_module = next(m for m in updated if m.module_id == first_module_id)
    assert updated_module.is_visible == new_visible


@pytest.mark.db
def test_update_module_order(db_conn, test_user):
    """sort_order wird gesetzt."""
    from backend.modules.module_registry import (
        initialize_user_modules,
        get_user_modules,
        update_user_module_order,
    )
    initialize_user_modules(db_conn, test_user.id)
    modules = get_user_modules(db_conn, test_user.id)
    assert modules, "Keine Module vorhanden"

    first_module_id = modules[0].module_id
    new_order = [{"module_id": first_module_id, "sort_order": 99}]
    update_user_module_order(db_conn, test_user.id, new_order)

    updated = get_user_modules(db_conn, test_user.id)
    updated_module = next((m for m in updated if m.module_id == first_module_id), None)
    assert updated_module is not None
    assert updated_module.sort_order == 99


@pytest.mark.db
def test_save_and_load_module_config(db_conn, test_user):
    """Config gespeichert und wieder geladen."""
    from backend.modules.module_registry import (
        initialize_user_modules,
        save_user_module_config,
        get_user_module_config,
    )
    initialize_user_modules(db_conn, test_user.id)
    config = {"username": "teacher1", "server": "itslearning.example.com"}
    save_user_module_config(db_conn, test_user.id, "itslearning", config)

    loaded = get_user_module_config(db_conn, test_user.id, "itslearning")
    assert loaded == config


@pytest.mark.db
def test_save_config_sets_is_configured(db_conn, test_user):
    """Nach Save: is_configured = True."""
    from backend.modules.module_registry import (
        initialize_user_modules,
        save_user_module_config,
        get_user_modules,
    )
    initialize_user_modules(db_conn, test_user.id)
    save_user_module_config(db_conn, test_user.id, "itslearning", {"key": "value"})

    modules = get_user_modules(db_conn, test_user.id)
    itslearning_module = next((m for m in modules if m.module_id == "itslearning"), None)
    assert itslearning_module is not None
    assert itslearning_module.is_configured is True


# ── Additional gap-filling tests ──────────────────────────────────────────────

@pytest.mark.db
def test_all_six_expected_modules_exist(db_conn):
    """webuntis, itslearning, nextcloud, orgaplan, klassenarbeitsplan, noten, mail alle vorhanden."""
    from backend.modules.module_registry import get_all_modules
    modules = get_all_modules(db_conn)
    module_ids = {m.id for m in modules}
    expected = {
        "webuntis",
        "itslearning",
        "nextcloud",
        "orgaplan",
        "klassenarbeitsplan",
        "noten",
        "mail",
    }
    for mid in expected:
        assert mid in module_ids, f"Erwartetes Modul '{mid}' fehlt. Vorhanden: {module_ids}"


@pytest.mark.db
def test_mail_module_default_visible_is_false(db_conn):
    """mail-Modul hat default_visible=False."""
    from backend.modules.module_registry import get_module_by_id
    mail = get_module_by_id(db_conn, "mail")
    assert mail is not None
    assert mail.default_visible is False, (
        f"mail.default_visible sollte False sein, ist aber: {mail.default_visible}"
    )


@pytest.mark.db
def test_mail_module_type_is_local(db_conn):
    """mail-Modul hat module_type='local'."""
    from backend.modules.module_registry import get_module_by_id
    mail = get_module_by_id(db_conn, "mail")
    assert mail is not None
    assert mail.module_type == "local", (
        f"mail.module_type sollte 'local' sein, ist aber: {mail.module_type!r}"
    )


@pytest.mark.db
def test_orgaplan_is_central_type(db_conn):
    """orgaplan-Modul hat module_type='central'."""
    from backend.modules.module_registry import get_module_by_id
    module = get_module_by_id(db_conn, "orgaplan")
    assert module is not None
    assert module.module_type == "central"


@pytest.mark.db
def test_klassenarbeitsplan_is_central_type(db_conn):
    """klassenarbeitsplan-Modul hat module_type='central'."""
    from backend.modules.module_registry import get_module_by_id
    module = get_module_by_id(db_conn, "klassenarbeitsplan")
    assert module is not None
    assert module.module_type == "central"


@pytest.mark.db
def test_webuntis_is_individual_type(db_conn):
    """webuntis-Modul hat module_type='individual'."""
    from backend.modules.module_registry import get_module_by_id
    module = get_module_by_id(db_conn, "webuntis")
    assert module is not None
    assert module.module_type == "individual"


@pytest.mark.db
def test_itslearning_is_individual_type(db_conn):
    """itslearning-Modul hat module_type='individual'."""
    from backend.modules.module_registry import get_module_by_id
    module = get_module_by_id(db_conn, "itslearning")
    assert module is not None
    assert module.module_type == "individual"


@pytest.mark.db
def test_nextcloud_is_individual_type(db_conn):
    """nextcloud-Modul hat module_type='individual'."""
    from backend.modules.module_registry import get_module_by_id
    module = get_module_by_id(db_conn, "nextcloud")
    assert module is not None
    assert module.module_type == "individual"


@pytest.mark.db
def test_is_valid_module_known_module_returns_true(db_conn):
    """is_valid_module(conn, 'webuntis') gibt True zurück."""
    from backend.modules.module_registry import is_valid_module
    result = is_valid_module(db_conn, "webuntis")
    assert result is True


@pytest.mark.db
def test_is_valid_module_unknown_returns_false(db_conn):
    """is_valid_module(conn, 'nonexistent_xyz') gibt False zurück."""
    from backend.modules.module_registry import is_valid_module
    result = is_valid_module(db_conn, "nonexistent_xyz_12345")
    assert result is False


@pytest.mark.db
def test_get_modules_by_type_individual(db_conn):
    """get_modules_by_type(conn, 'individual') gibt nur individual-Module zurück."""
    from backend.modules.module_registry import get_modules_by_type
    modules = get_modules_by_type(db_conn, "individual")
    assert len(modules) > 0
    for m in modules:
        assert m.module_type == "individual", (
            f"Modul '{m.id}' hat Typ '{m.module_type}', erwartet 'individual'"
        )
    # webuntis, itslearning, nextcloud should be in individual modules
    individual_ids = {m.id for m in modules}
    assert "webuntis" in individual_ids
    assert "itslearning" in individual_ids
    assert "nextcloud" in individual_ids


@pytest.mark.db
def test_get_modules_by_type_central(db_conn):
    """get_modules_by_type(conn, 'central') gibt nur central-Module zurück."""
    from backend.modules.module_registry import get_modules_by_type
    modules = get_modules_by_type(db_conn, "central")
    assert len(modules) > 0
    for m in modules:
        assert m.module_type == "central", (
            f"Modul '{m.id}' hat Typ '{m.module_type}', erwartet 'central'"
        )
    central_ids = {m.id for m in modules}
    assert "orgaplan" in central_ids
    assert "klassenarbeitsplan" in central_ids


# ── Encrypted config round-trip tests ─────────────────────────────────────────

@pytest.mark.db
def test_save_and_load_config_with_sensitive_fields_round_trip(db_conn, test_user):
    """save_user_module_config + get_user_module_config round-trip for sensitive fields.

    Regardless of whether ENCRYPTION_KEY is set, the round-trip must return
    the original plaintext values (decrypt_config undoes encrypt_config).
    """
    from backend.modules.module_registry import (
        initialize_user_modules,
        save_user_module_config,
        get_user_module_config,
    )
    initialize_user_modules(db_conn, test_user.id)
    config = {"password": "secret", "username": "itslearning_user"}
    save_user_module_config(db_conn, test_user.id, "itslearning", config)

    loaded = get_user_module_config(db_conn, test_user.id, "itslearning")
    assert loaded["password"] == "secret", (
        f"Expected 'secret', got: {loaded['password']!r}"
    )
    assert loaded["username"] == "itslearning_user"


@pytest.mark.db
def test_raw_db_value_encrypted_when_key_set(db_conn, test_user):
    """When ENCRYPTION_KEY is set, the raw DB value should NOT equal the plaintext.

    Skipped if ENCRYPTION_KEY is not set (encryption disabled).
    """
    if not os.environ.get("ENCRYPTION_KEY", "").strip():
        pytest.skip("ENCRYPTION_KEY not set — encryption disabled, skipping raw-value check")

    from backend.modules.module_registry import (
        initialize_user_modules,
        save_user_module_config,
    )
    initialize_user_modules(db_conn, test_user.id)
    save_user_module_config(db_conn, test_user.id, "itslearning", {"password": "secret"})

    # Read the raw JSONB value directly from the DB
    row = db_conn.execute(
        "SELECT config_data FROM user_module_configs WHERE user_id = %s AND module_id = %s",
        (test_user.id, "itslearning"),
    ).fetchone()
    assert row is not None, "Config row not found in DB"
    raw_config = row[0]  # psycopg3 returns JSONB as Python dict
    raw_password = raw_config.get("password", "")
    assert raw_password != "secret", (
        f"Raw DB value should be encrypted, but got plaintext: {raw_password!r}"
    )
    assert raw_password.startswith("enc:"), (
        f"Expected encrypted value with 'enc:' prefix, got: {raw_password!r}"
    )
