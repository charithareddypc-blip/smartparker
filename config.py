import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration class."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'smart-parking-secret-key-default-2026')
    
    # MySQL Database Settings
    DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_NAME = os.getenv('DB_NAME', 'smart_parking_db')
    
    # Application Timezone
    TIMEZONE = os.getenv('TIMEZONE', 'Asia/Kolkata')
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Application Mode
    DEBUG = os.getenv('FLASK_DEBUG', '1') == '1'
    TESTING = False

class TestingConfig(Config):
    """Testing configuration class."""
    TESTING = True
    DEBUG = False
    DB_NAME = 'smart_parking_test_db'
