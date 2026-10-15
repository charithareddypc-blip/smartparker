import os
import sqlite3
import re
import logging
from contextlib import contextmanager
from flask import g, current_app
from config import Config

logger = logging.getLogger(__name__)

# Try importing mysql.connector
try:
    import mysql.connector
    from mysql.connector import errorcode, pooling
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    logger.warning("mysql-connector-python is not installed. Running in fallback mode.")

_mysql_pool = None
_db_mode = None  # 'mysql' or 'sqlite'
SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'smart_parking_local.db')

def check_mysql_connection():
    """Verify if MySQL server is reachable with configured credentials."""
    if not MYSQL_AVAILABLE:
        return False
    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            connection_timeout=2
        )
        if conn.is_connected():
            conn.close()
            return True
        return False
    except Exception as e:
        logger.info(f"MySQL connection check note: {e}")
        return False

def get_db_mode():
    """Determine database mode: 'mysql' if server is reachable, else 'sqlite'."""
    global _db_mode
    if _db_mode is None:
        force_mode = os.getenv('DB_FORCE_MODE')
        if force_mode:
            _db_mode = force_mode.lower()
        elif check_mysql_connection():
            _db_mode = 'mysql'
        else:
            _db_mode = 'sqlite'
            logger.info("Using local database engine (zero-config mode). MySQL is ready to connect once started.")
    return _db_mode

def set_db_mode(mode):
    """Explicitly set DB mode (useful for testing)."""
    global _db_mode
    _db_mode = mode

def get_mysql_connection():
    """Get a MySQL connection from pool or direct."""
    global _mysql_pool
    if _mysql_pool is None:
        try:
            _mysql_pool = pooling.MySQLConnectionPool(
                pool_name="parking_pool",
                pool_size=5,
                pool_reset_session=True,
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME,
                autocommit=False
            )
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_BAD_DB_ERROR:
                # Database doesn't exist yet, connect without db to create it
                temp_conn = mysql.connector.connect(
                    host=Config.DB_HOST,
                    port=Config.DB_PORT,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD
                )
                cursor = temp_conn.cursor()
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                cursor.close()
                temp_conn.close()
                # Retry pool
                _mysql_pool = pooling.MySQLConnectionPool(
                    pool_name="parking_pool",
                    pool_size=5,
                    pool_reset_session=True,
                    host=Config.DB_HOST,
                    port=Config.DB_PORT,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD,
                    database=Config.DB_NAME,
                    autocommit=False
                )
            else:
                raise err
    return _mysql_pool.get_connection()

def get_sqlite_connection(db_path=None):
    """Get SQLite connection for testing/demo fallback."""
    path = db_path or SQLITE_DB_PATH
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def get_db():
    """Get active database connection stored in Flask application context."""
    if 'db' not in g:
        mode = get_db_mode()
        if mode == 'mysql':
            try:
                g.db = get_mysql_connection()
                g.db_mode = 'mysql'
            except Exception as e:
                logger.error(f"Failed to connect to MySQL, falling back to SQLite: {e}")
                g.db = get_sqlite_connection()
                g.db_mode = 'sqlite'
        else:
            g.db = get_sqlite_connection()
            g.db_mode = 'sqlite'
    return g.db

def close_db(e=None):
    """Close active database connection at end of request."""
    db = g.pop('db', None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass

def dict_from_row(cursor, row):
    """Convert cursor row to dictionary."""
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if isinstance(row, sqlite3.Row):
        return dict(row)
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))

def execute_query(sql, params=None, fetch=None, commit=False):
    """
    Execute SQL query with parameters and return results.
    - sql: SQL string with %s placeholders
    - params: tuple or list of parameters
    - fetch: 'one', 'all', or None
    - commit: whether to commit the transaction
    """
    conn = get_db()
    mode = getattr(g, 'db_mode', get_db_mode())
    params = params or ()
    
    if mode == 'mysql':
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(sql, params)
            if commit:
                conn.commit()
            if fetch == 'one':
                res = cursor.fetchone()
                return res
            elif fetch == 'all':
                res = cursor.fetchall()
                return res
            else:
                return cursor.lastrowid
        except Exception as e:
            if commit:
                conn.rollback()
            raise e
        finally:
            cursor.close()
    else:
        # SQLite mode: convert %s to ? and adjust minor function syntax if needed
        sqlite_sql = sql.replace('%s', '?')
        # Replace NOW() with CURRENT_TIMESTAMP if needed
        sqlite_sql = re.sub(r'\bNOW\(\)', 'CURRENT_TIMESTAMP', sqlite_sql, flags=re.IGNORECASE)
        # Format datetime objects as strings for SQLite
        sqlite_params = []
        for p in params:
            if hasattr(p, 'strftime'):
                sqlite_params.append(p.strftime('%Y-%m-%d %H:%M:%S'))
            else:
                sqlite_params.append(p)
        cursor = conn.cursor()
        try:
            cursor.execute(sqlite_sql, tuple(sqlite_params))
            if commit:
                conn.commit()
            if fetch == 'one':
                row = cursor.fetchone()
                return dict(row) if row else None
            elif fetch == 'all':
                rows = cursor.fetchall()
                return [dict(r) for r in rows]
            else:
                return cursor.lastrowid
        except Exception as e:
            if commit:
                conn.rollback()
            raise e
        finally:
            cursor.close()

@contextmanager
def transaction():
    """Transactional context manager that commits on success or rolls back on error."""
    conn = get_db()
    mode = getattr(g, 'db_mode', get_db_mode())
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e

def init_sqlite_schema(conn=None):
    """Initialize SQLite database with equivalent schema and sample data."""
    close_after = False
    if conn is None:
        conn = get_sqlite_connection()
        close_after = True
        
    cursor = conn.cursor()
    cursor.executescript('''
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS vehicles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        license_plate TEXT NOT NULL UNIQUE,
        vehicle_type TEXT DEFAULT 'Sedan',
        make_model TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS parking_areas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        area_code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        floor_level TEXT NOT NULL,
        total_slots INTEGER DEFAULT 0,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS parking_slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        area_id INTEGER NOT NULL,
        slot_number TEXT NOT NULL,
        slot_type TEXT NOT NULL DEFAULT 'regular',
        hourly_rate REAL NOT NULL DEFAULT 5.00,
        status TEXT NOT NULL DEFAULT 'available',
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (area_id) REFERENCES parking_areas(id) ON DELETE RESTRICT,
        UNIQUE (area_id, slot_number)
    );

    CREATE TABLE IF NOT EXISTS reservations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reservation_code TEXT NOT NULL UNIQUE,
        customer_id INTEGER NOT NULL,
        vehicle_id INTEGER NOT NULL,
        slot_id INTEGER NOT NULL,
        start_time DATETIME NOT NULL,
        end_time DATETIME NOT NULL,
        duration_hours REAL NOT NULL,
        estimated_amount REAL NOT NULL,
        actual_amount REAL DEFAULT NULL,
        booking_status TEXT NOT NULL DEFAULT 'reserved',
        payment_status TEXT NOT NULL DEFAULT 'pending',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT,
        FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE RESTRICT,
        FOREIGN KEY (slot_id) REFERENCES parking_slots(id) ON DELETE RESTRICT
    );

    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reservation_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        payment_method TEXT NOT NULL DEFAULT 'demo_gateway',
        transaction_ref TEXT NOT NULL UNIQUE,
        payment_status TEXT NOT NULL DEFAULT 'pending',
        notes TEXT,
        paid_at DATETIME DEFAULT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (reservation_id) REFERENCES reservations(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS parking_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reservation_id INTEGER DEFAULT NULL,
        slot_id INTEGER NOT NULL,
        vehicle_id INTEGER NOT NULL,
        check_in_time DATETIME NOT NULL,
        check_out_time DATETIME DEFAULT NULL,
        actual_duration_hours REAL DEFAULT NULL,
        initial_fee REAL NOT NULL,
        final_fee REAL DEFAULT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (reservation_id) REFERENCES reservations(id) ON DELETE SET NULL,
        FOREIGN KEY (slot_id) REFERENCES parking_slots(id) ON DELETE RESTRICT,
        FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE RESTRICT
    );

    CREATE TABLE IF NOT EXISTS occupancy_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slot_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        details TEXT NOT NULL,
        logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (slot_id) REFERENCES parking_slots(id) ON DELETE CASCADE
    );
    ''')
    conn.commit()

    # Seed initial data if admins table is empty
    check_admin = cursor.execute("SELECT COUNT(*) as cnt FROM admins").fetchone()
    if check_admin[0] == 0:
        cursor.execute('''
        INSERT INTO admins (username, email, password_hash, full_name)
        VALUES ('admin', 'admin@smartparking.local', 'scrypt:32768:8:1$yLgX7n2K8M$93f9efdd8829be7bc2b95c8793b8fbd46399a9b60dafb6047da0344405391d1ea173beae20485a0cbb029ae4ea1ec1cb14b09b52a1d2f09d3b14643717243916', 'System Administrator')
        ''')
        
        cursor.executescript('''
        INSERT OR IGNORE INTO parking_areas (id, area_code, name, floor_level, total_slots, description) VALUES
        (1, 'AREA-G', 'Ground Level North Wing', 'Ground Floor', 6, 'Convenient ground-level parking with EV charging and quick exit'),
        (2, 'AREA-F1', 'Level 1 South Wing', '1st Floor', 6, 'Standard covered bays with wide access lanes'),
        (3, 'AREA-B1', 'Basement Executive Bay', 'Basement 1', 6, 'Climate-controlled basement parking with priority accessible spaces');

        INSERT OR IGNORE INTO parking_slots (id, area_id, slot_number, slot_type, hourly_rate, status) VALUES
        (1, 1, 'G-01', 'ev', 8.00, 'available'),
        (2, 1, 'G-02', 'ev', 8.00, 'occupied'),
        (3, 1, 'G-03', 'accessible', 5.00, 'available'),
        (4, 1, 'G-04', 'accessible', 5.00, 'reserved'),
        (5, 1, 'G-05', 'regular', 6.00, 'available'),
        (6, 1, 'G-06', 'compact', 4.50, 'available'),
        (7, 2, 'F1-01', 'regular', 5.00, 'occupied'),
        (8, 2, 'F1-02', 'regular', 5.00, 'available'),
        (9, 2, 'F1-03', 'regular', 5.00, 'available'),
        (10, 2, 'F1-04', 'compact', 4.00, 'available'),
        (11, 2, 'F1-05', 'compact', 4.00, 'reserved'),
        (12, 2, 'F1-06', 'regular', 5.00, 'available'),
        (13, 3, 'B1-01', 'accessible', 6.00, 'available'),
        (14, 3, 'B1-02', 'regular', 6.50, 'available'),
        (15, 3, 'B1-03', 'regular', 6.50, 'occupied'),
        (16, 3, 'B1-04', 'ev', 9.00, 'available'),
        (17, 3, 'B1-05', 'regular', 6.50, 'available'),
        (18, 3, 'B1-06', 'compact', 5.00, 'available');

        INSERT OR IGNORE INTO customers (id, full_name, email, phone) VALUES
        (1, 'Alexander Wright', 'alex.wright@example.com', '+1-555-0192'),
        (2, 'Sophia Martinez', 'sophia.m@example.com', '+1-555-0143'),
        (3, 'David Chen', 'david.chen@example.com', '+1-555-0188'),
        (4, 'Emma Watson', 'emma.w@example.com', '+1-555-0164'),
        (5, 'Marcus Johnson', 'marcus.j@example.com', '+1-555-0177');

        INSERT OR IGNORE INTO vehicles (id, customer_id, license_plate, vehicle_type, make_model) VALUES
        (1, 1, 'NYC-8921', 'EV', 'Tesla Model 3'),
        (2, 2, 'CA-4298', 'Sedan', 'Toyota Camry'),
        (3, 3, 'TX-1044', 'SUV', 'Honda CR-V'),
        (4, 4, 'FL-6733', 'Compact', 'Mini Cooper'),
        (5, 5, 'WA-5512', 'SUV', 'Ford Explorer');

        INSERT OR IGNORE INTO reservations (id, reservation_code, customer_id, vehicle_id, slot_id, start_time, end_time, duration_hours, estimated_amount, actual_amount, booking_status, payment_status, notes) VALUES
        (1, 'RES-2026-1001', 1, 1, 2, datetime('now', '-2 hours'), datetime('now', '+2 hours'), 4.0, 32.00, 32.00, 'active', 'paid', 'Checked in at North EV Gate'),
        (2, 'RES-2026-1002', 2, 2, 4, datetime('now', '+1 hours'), datetime('now', '+5 hours'), 4.0, 20.00, NULL, 'reserved', 'paid', 'Upcoming reservation, confirmed'),
        (3, 'RES-2026-1003', 3, 3, 7, datetime('now', '-3 hours'), datetime('now', '+1 hours'), 4.0, 20.00, 20.00, 'active', 'paid', 'Early morning commuter check-in'),
        (4, 'RES-2026-1004', 4, 4, 11, datetime('now', '+2 hours'), datetime('now', '+6 hours'), 4.0, 16.00, NULL, 'reserved', 'pending', 'Awaiting payment confirmation'),
        (5, 'RES-2026-1005', 5, 5, 15, datetime('now', '-1 hours'), datetime('now', '+3 hours'), 4.0, 26.00, 26.00, 'active', 'paid', 'Executive meeting parking');

        INSERT OR IGNORE INTO payments (id, reservation_id, amount, payment_method, transaction_ref, payment_status, notes, paid_at) VALUES
        (1, 1, 32.00, 'demo_card', 'TXN-20261015-8911', 'paid', 'Simulated Visa Card Payment', datetime('now', '-2 hours')),
        (2, 2, 20.00, 'demo_upi', 'TXN-20261015-4420', 'paid', 'Simulated UPI QuickPay', datetime('now', '-1 hours')),
        (3, 3, 20.00, 'demo_card', 'TXN-20261015-9932', 'paid', 'Simulated MasterCard Payment', datetime('now', '-3 hours')),
        (4, 5, 26.00, 'demo_cash', 'TXN-20261015-1105', 'paid', 'Cash collected at entrance desk', datetime('now', '-1 hours'));

        INSERT OR IGNORE INTO parking_sessions (id, reservation_id, slot_id, vehicle_id, check_in_time, initial_fee, status, notes) VALUES
        (1, 1, 2, 1, datetime('now', '-2 hours'), 32.00, 'active', 'Checked in at North EV Gate'),
        (2, 3, 7, 3, datetime('now', '-3 hours'), 20.00, 'active', 'Checked in at Level 1 Boom Barrier'),
        (3, 5, 15, 5, datetime('now', '-1 hours'), 26.00, 'active', 'Executive basement bay check-in');

        INSERT OR IGNORE INTO occupancy_logs (slot_id, event_type, details, logged_at) VALUES
        (2, 'check_in', 'Vehicle NYC-8921 checked into Slot G-02', datetime('now', '-2 hours')),
        (4, 'reservation_hold', 'Reservation RES-2026-1002 placed on Slot G-04', datetime('now', '-1 hours')),
        (7, 'check_in', 'Vehicle TX-1044 checked into Slot F1-01', datetime('now', '-3 hours')),
        (11, 'reservation_hold', 'Reservation RES-2026-1004 placed on Slot F1-05', datetime('now', '-30 minutes')),
        (15, 'check_in', 'Vehicle WA-5512 checked into Slot B1-03', datetime('now', '-1 hours'));
        ''')
        conn.commit()

    if close_after:
        conn.close()

def init_mysql_from_schema():
    """Execute schema.sql on MySQL database."""
    if not MYSQL_AVAILABLE or not check_mysql_connection():
        return False, "MySQL server is not accessible."
    
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')
    if not os.path.exists(schema_path):
        return False, "schema.sql not found."
    
    with open(schema_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # Split statements
    statements = sql_content.split(';')
    conn = mysql.connector.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        multi=True
    )
    cursor = conn.cursor()
    for stmt in statements:
        stmt = stmt.strip()
        if stmt:
            try:
                cursor.execute(stmt)
            except Exception as e:
                logger.warning(f"Error executing statement during schema load: {e}")
    conn.commit()
    cursor.close()
    conn.close()
    return True, "MySQL database initialized from schema.sql successfully."

def get_db_status_info():
    """Returns database connection status for dashboard display."""
    mode = get_db_mode()
    if mode == 'mysql':
        return {
            'mode': 'MySQL Server (Live)',
            'is_mysql': True,
            'host': f"{Config.DB_HOST}:{Config.DB_PORT}",
            'database': Config.DB_NAME,
            'badge_class': 'bg-success'
        }
    else:
        return {
            'mode': 'Local Storage (Demo/Fallback Mode)',
            'is_mysql': False,
            'host': 'SQLite / Local File',
            'database': os.path.basename(SQLITE_DB_PATH),
            'badge_class': 'bg-primary'
        }
