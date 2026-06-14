from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from backend.initdb import get_db_connection
from decorators import login_required

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        surname = request.form.get('surname', '').strip()
        name = request.form.get('name', '').strip()
        patronymic = request.form.get('patronymic', '').strip()
        password = request.form.get('password', '')

        conn = get_db_connection()
        user = conn.execute("""
            SELECT * FROM Employee 
            WHERE LOWER(empl_surname) = LOWER(?) 
              AND LOWER(empl_name) = LOWER(?) 
              AND LOWER(empl_patronymic) = LOWER(?)
        """, (surname, name, patronymic)).fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id_employee']
            session['user_name'] = f"{user['empl_name']} {user['empl_surname']}"
            session['role'] = user['empl_role']
            return redirect(url_for('auth.dashboard'))
        else:
            flash("Невірні дані або пароль!", "danger")

    return render_template('login.html')

@auth_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', role=session['role'], name=session['user_name'])

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))