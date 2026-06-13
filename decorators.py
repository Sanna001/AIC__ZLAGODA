from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(f):
    """Декоратор перевіряє, чи користувач взагалі увійшов в систему"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Спочатку увійдіть у систему!", "danger")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*allowed_roles):
    """Декоратор перевіряє, чи відповідає роль користувача дозволеній"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] not in allowed_roles:
                flash("У вас немає доступу до цієї сторінки!", "danger")
                return redirect(url_for('auth.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator