import os
import sys
# Ensure application root is in python search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import tempfile
import sqlite3
from app import create_app
from database import init_sqlite_schema, set_db_mode


@pytest.fixture(scope='session')
def app():
    """Create and configure a testing Flask application instance with an isolated database."""
    import database
    test_db_fd, test_db_path = tempfile.mkstemp(suffix='.db')
    os.close(test_db_fd)
    database.SQLITE_DB_PATH = test_db_path
    database.set_db_mode('sqlite')

    test_app = create_app()
    test_app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key-12345',
        'WTF_CSRF_ENABLED': False
    })
    
    with test_app.app_context():
        database.init_sqlite_schema()
        
    yield test_app

    # Cleanup temporary test database
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except Exception:
            pass

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def auth_client(app, client):
    """A test client with an authenticated admin session."""
    with client.session_transaction() as sess:
        sess['admin_id'] = 1
        sess['admin_user'] = 'admin'
        sess['admin_name'] = 'System Administrator'
    return client
