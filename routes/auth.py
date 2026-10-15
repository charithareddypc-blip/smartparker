from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import check_password_hash
from database import execute_query

auth_bp = Blueprint('auth', __name__)

def admin_required(f):
    """Decorator to protect admin routes from unauthorized access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_id'):
            flash('Please log in with administrator credentials to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page and authentication handler."""
    if session.get('admin_id'):
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Both username and password are required.', 'danger')
            return render_template('login.html', username=username)

        admin = execute_query(
            "SELECT * FROM admins WHERE username = %s OR email = %s",
            (username, username),
            fetch='one'
        )

        if admin and check_password_hash(admin['password_hash'], password):
            if not admin.get('is_active', 1):
                flash('This administrator account has been deactivated.', 'danger')
                return render_template('login.html', username=username)

            # Set session parameters
            session.clear()
            session['admin_id'] = admin['id']
            session['admin_user'] = admin['username']
            session['admin_name'] = admin['full_name']
            session.permanent = True
            
            flash(f"Welcome back, {admin['full_name']}! You have signed in successfully.", 'success')
            next_url = request.args.get('next') or url_for('dashboard.index')
            return redirect(next_url)
        else:
            flash('Invalid username or password. Please try again.', 'danger')
            return render_template('login.html', username=username)

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    """Log out admin and clear session."""
    session.clear()
    flash('You have been securely signed out.', 'info')
    return redirect(url_for('auth.login'))
