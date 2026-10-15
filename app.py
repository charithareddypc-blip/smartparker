import os
from datetime import datetime
from flask import Flask, render_template, session, request, abort
from config import Config
from database import close_db, get_db_mode, init_sqlite_schema, check_mysql_connection, init_mysql_from_schema

# Import route blueprints
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.parking import parking_bp
from routes.reservations import reservations_bp
from routes.payments import payments_bp
from routes.occupancy import occupancy_bp
from routes.customers import customers_bp

def create_app(config_class=Config):
    """Application factory for Smart Parking Management System."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Teardown application context to close DB connection
    app.teardown_appcontext(close_db)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(parking_bp)
    app.register_blueprint(reservations_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(occupancy_bp)
    app.register_blueprint(customers_bp)

    # Custom Jinja2 Template Filters
    @app.template_filter('currency')
    def format_currency(value):
        try:
            return f"${float(value):,.2f}"
        except (ValueError, TypeError):
            return "$0.00"

    @app.template_filter('datetime')
    def format_datetime(value, format_str='%b %d, %Y %I:%M %p'):
        if not value:
            return '—'
        if isinstance(value, str):
            try:
                # Handle ISO or standard SQL string
                clean = value.replace('T', ' ')[:19]
                value = datetime.strptime(clean, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return value
        if isinstance(value, datetime):
            return value.strftime(format_str)
        return str(value)

    @app.template_filter('status_badge')
    def status_badge(status):
        badges = {
            'available': 'bg-success',
            'reserved': 'bg-warning text-dark',
            'active': 'bg-primary',
            'occupied': 'bg-danger',
            'completed': 'bg-secondary',
            'cancelled': 'bg-dark',
            'maintenance': 'bg-secondary',
            'paid': 'bg-success',
            'pending': 'bg-warning text-dark',
            'failed': 'bg-danger',
            'refunded': 'bg-info text-dark'
        }
        return badges.get(str(status).lower(), 'bg-secondary')

    # Global Context Processor
    @app.context_processor
    def inject_globals():
        return {
            'current_year': datetime.now().year,
            'logged_admin': session.get('admin_name', 'Administrator'),
            'admin_username': session.get('admin_user')
        }

    # Error Handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('error.html', error_code=404, message="The requested resource or page was not found."), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('error.html', error_code=500, message="An internal server error occurred. Please contact the administrator."), 500

    # Initialize Database Schema if not already initialized
    with app.app_context():
        mode = get_db_mode()
        if mode == 'sqlite':
            init_sqlite_schema()
        elif mode == 'mysql' and check_mysql_connection():
            # Test schema initialization
            try:
                init_mysql_from_schema()
            except Exception:
                pass

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', '1') == '1'
    print(f"\n{'='*60}")
    print("  SMART PARKING MANAGEMENT SYSTEM")
    print(f"  Starting Development Server on http://127.0.0.1:{port}")
    print(f"  Admin Login: http://127.0.0.1:{port}/login")
    print(f"  Default Credentials: admin / Admin@123")
    print(f"{'='*60}\n")
    app.run(host='0.0.0.0', port=port, debug=debug)
