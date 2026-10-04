"""Shared fixtures keep tests isolated from the user's saved route history."""

import pytest


@pytest.fixture
def temporary_history_database(tmp_path, monkeypatch):
    """Use a fresh SQLite file for each test instead of data/shadownav.sqlite3."""
    import database.db as history_db

    test_database_path = tmp_path / "test_history.sqlite3"
    monkeypatch.setattr(history_db, "DATABASE_PATH", test_database_path)
    history_db.initialize_database()
    return history_db


@pytest.fixture
def client(temporary_history_database):
    """Create Flask's in-process test client without starting a web server."""
    import app as app_module

    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()
