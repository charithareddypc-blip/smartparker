import os
import sys
import argparse
from werkzeug.security import generate_password_hash
from database import (
    get_db_mode, 
    init_mysql_from_schema, 
    init_sqlite_schema, 
    execute_query, 
    check_mysql_connection
)
from config import Config

def init_database(mode=None):
    """Initialize database tables and initial sample data."""
    if mode is None:
        mode = get_db_mode()
    
    print(f"[*] Initializing database in mode: {mode.upper()}...")
    if mode == 'mysql':
        if not check_mysql_connection():
            print(f"[!] Error: Cannot connect to MySQL server at {Config.DB_HOST}:{Config.DB_PORT} as '{Config.DB_USER}'.")
            print("    Please ensure your MySQL service is started (e.g. via XAMPP, WAMP, or Windows Services).")
            return False
        success, message = init_mysql_from_schema()
        print(f"[*] {message}")
        return success
    else:
        init_sqlite_schema()
        print("[*] Local database initialized successfully with sample parking areas, slots, and bookings.")
        return True

def create_admin(username, email, password, full_name="Administrator"):
    """Create or update an administrator account with hashed password."""
    password_hash = generate_password_hash(password)
    
    # Check if admin username exists
    existing = execute_query(
        "SELECT id FROM admins WHERE username = %s OR email = %s",
        (username, email),
        fetch='one'
    )
    
    if existing:
        execute_query(
            "UPDATE admins SET password_hash = %s, full_name = %s, email = %s WHERE id = %s",
            (password_hash, full_name, email, existing['id']),
            commit=True
        )
        print(f"[+] Administrator '{username}' password successfully updated.")
    else:
        execute_query(
            "INSERT INTO admins (username, email, password_hash, full_name) VALUES (%s, %s, %s, %s)",
            (username, email, password_hash, full_name),
            commit=True
        )
        print(f"[+] Administrator '{username}' successfully created.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Smart Parking Management System - Database Initializer")
    parser.add_argument('--mode', choices=['mysql', 'sqlite', 'auto'], default='auto', help="Database target engine")
    parser.add_argument('--create-admin', action='store_true', help="Prompt to create a new administrator account")
    parser.add_argument('--username', default=None, help="Admin username")
    parser.add_argument('--password', default=None, help="Admin password")
    parser.add_argument('--email', default=None, help="Admin email")
    parser.add_argument('--name', default="Administrator", help="Admin display name")

    args = parser.parse_args()
    
    target_mode = None if args.mode == 'auto' else args.mode
    init_database(target_mode)
    
    if args.create_admin:
        username = args.username or input("Enter Admin Username: ").strip()
        email = args.email or input("Enter Admin Email: ").strip()
        password = args.password or input("Enter Admin Password: ").strip()
        name = args.name or input("Enter Admin Full Name: ").strip()
        create_admin(username, email, password, name)
    else:
        print("[*] Default Admin Credentials: Username: admin | Password: Admin@123")
