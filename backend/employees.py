# employees.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash
from initdb import get_db_connection
from decorators import login_required, roles_required
from datetime import date
import sqlite3

employees_bp = Blueprint('employees', __name__, url_prefix='/employees')


# Перегляд списку працівників
@employees_bp.route('/')
@login_required
@roles_required('Manager')
def list_employees():
    role = request.args.get('role', '')
    search = request.args.get('search', '').strip()

    query = "SELECT * FROM Employee WHERE 1=1"
    params = []

    if role:
        query += " AND empl_role = ?"
        params.append(role)

    if search:
        query += " AND LOWER(empl_surname) LIKE LOWER(?)"
        params.append(f'%{search}%')

    query += " ORDER BY empl_surname"

    conn = get_db_connection()
    employees = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('employees/list.html',
                           employees=employees, role=role, search=search)




@employees_bp.route('/add', methods=['GET', 'POST'])
@login_required
@roles_required('Manager')
def add_employee():
    if request.method == 'POST':
        error, values = _validate_employee_form(request.form)
        if error:
            flash(error, "danger")
            return render_template('employees/add.html')

        conn = get_db_connection()
        last_empl = conn.execute("SELECT id_employee FROM Employee ORDER BY id_employee DESC LIMIT 1").fetchone()
        new_id = f"E{int(last_empl['id_employee'][1:]) + 1}" if last_empl else "E100"

        try:
            conn.execute('''INSERT INTO Employee VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''', 
                         (new_id, 
                          request.form.get('empl_surname'), 
                          request.form.get('empl_name'), 
                          request.form.get('empl_patronymic'), 
                          request.form.get('empl_role'), 
                          values['salary'],
                          values['birth'],
                          values['start'],  # Використовуємо перевірене значення
                          values['phone'],
                          request.form.get('city'), 
                          request.form.get('street'), 
                          request.form.get('zip_code'), 
                          generate_password_hash(request.form.get('password'))))
            conn.commit()
            flash(f"Працівника додано! ID: {new_id}", "success")
            return redirect(url_for('employees.list_employees'))
        except Exception as e:
            conn.rollback()
            flash(f"Помилка: {str(e)}", "danger")
        finally:
            conn.close()
            
    return render_template('employees/add.html')

@employees_bp.route('/view/<id_employee>')
@login_required
@roles_required('Manager')
def view_employee(id_employee):
    if session.get('role') != 'Manager' and session.get('user_id') != id_employee:
        flash("Ви не маєте доступу до чужого профілю", "danger")
        return redirect(url_for('auth.dashboard'))
    conn = get_db_connection()
    emp = conn.execute('SELECT * FROM Employee WHERE id_employee = ?', (id_employee,)).fetchone()
    conn.close()
    
    if not emp:
        flash("Працівника не знайдено!", "danger")
        return redirect(url_for('employees.list_employees'))
        
    return render_template('employees/profile.html', employee=emp)


# Перегляд власного профілю працівника
@employees_bp.route('/profile')
@login_required
@roles_required('Cashier', 'Manager')
def profile():
    conn = get_db_connection()
    employee = conn.execute(
        'SELECT * FROM Employee WHERE id_employee = ?', (session['user_id'],)
    ).fetchone()
    conn.close()

    if not employee:
        flash("Дані не знайдено!", "danger")
        return redirect(url_for('auth.dashboard'))

    return render_template('employees/profile.html', employee=employee)

def _validate_employee_form(form):
    """Повертає (error_message, parsed_values) або (None, parsed_values)"""
    
    # 1. Обмеження: Вік не менше 18 років
    birth = form.get('date_of_birth', '')
    try:
        birth_date = date.fromisoformat(birth)
        today = date.today()
        age = today.year - birth_date.year - (
            (today.month, today.day) < (birth_date.month, birth_date.day)
        )
        if age < 18:
            return "Вік працівника не може бути менше 18 років!", None
    except ValueError:
        return "Невірний формат дати народження!", None

    # ВАЛІДАЦІЯ ДАТИ НАЙМУ (Виправлені відступи)
    start_date_str = form.get('date_of_start', '')
    try:
        start_date = date.fromisoformat(start_date_str)
        if start_date > date.today():
            return "Дата найму не може бути в майбутньому!", None
    except ValueError:
        return "Невірний формат дати найму!", None
    
    # 2. Обмеження: Довжина номеру телефону
    phone = form.get('phone_number', '').strip()
    if len(phone) > 13:
        return "Номер телефону не може перевищувати 13 символів (включаючи '+')!", None
    if not phone.startswith('+'):
        return "Номер телефону повинен починатися з символу '+'!", None

    # 3. Обмеження: Зарплата
    salary = form.get('salary', 0)
    try:
        salary = float(salary)
    except ValueError:
        return "Невірний формат зарплати!", None
    if salary < 0:
        return "Зарплата не може бути від'ємною!", None

    # ПОВЕРТАЄМО ВСІ ПЕРЕВІРЕНІ ЗНАЧЕННЯ
    return None, {
        'birth': birth,
        'start': start_date_str, # Додано це значення
        'phone': phone,
        'salary': salary
    }


# Додавання працівника менеджерів
# Додавання працівника менеджером
# Редагування працівника (Виправлено використання валідатора)
@employees_bp.route('/edit/<id_employee>', methods=['GET', 'POST'])
@login_required
@roles_required('Manager')
def edit_employee(id_employee):
    conn = get_db_connection()
    employee = conn.execute(
        'SELECT * FROM Employee WHERE id_employee = ?', (id_employee,)
    ).fetchone()

    if not employee:
        conn.close()
        flash("Працівника не знайдено!", "danger")
        return redirect(url_for('employees.list_employees'))

    if request.method == 'POST':
        # 1. Виклик валідації
        error, values = _validate_employee_form(request.form)
        if error:
            flash(error, "danger")
            conn.close()
            return render_template('employees/edit.html', employee=employee)

        # 2. Оновлення з використанням перевірених значень (values)
        try:
            conn.execute('''
                UPDATE Employee SET
                    empl_surname = ?, empl_name = ?, empl_patronymic = ?,
                    empl_role = ?, salary = ?, date_of_birth = ?,
                    date_of_start = ?, phone_number = ?,
                    city = ?, street = ?, zip_code = ?
                WHERE id_employee = ?
            ''', (
                request.form.get('empl_surname'),
                request.form.get('empl_name'),
                request.form.get('empl_patronymic') or None,
                request.form.get('empl_role'),
                values['salary'],        # Перевірене значення
                values['birth'],         # Перевірене значення
                values['start'],         # ТЕПЕР ВИКОРИСТОВУЄТЬСЯ ПЕРЕВІРЕНЕ ЗНАЧЕННЯ
                values['phone'],         # Перевірене значення
                request.form.get('city'),
                request.form.get('street'),
                request.form.get('zip_code'),
                id_employee
            ))
            conn.commit()
            flash("Дані працівника оновлено!", "success")
            return redirect(url_for('employees.list_employees'))
        except Exception as e:
            conn.rollback()
            flash(f"Помилка бази даних: {str(e)}", "danger")
        finally:
            conn.close()

    conn.close()
    return render_template('employees/edit.html', employee=employee)


# Видалення працівника
@employees_bp.route('/delete/<id_employee>', methods=['POST'])
@login_required
@roles_required('Manager')
def delete_employee(id_employee):
    if session.get('user_id') == id_employee:
        flash("Ви не можете звільнити самого себе!", "danger")
        return redirect(url_for('employees.list_employees'))

    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM Employee WHERE id_employee = ?', (id_employee,))
        conn.commit()
        flash("Працівника успішно видалено.", "success")
    except Exception as e:
        flash(f"Неможливо видалити (можливо, є записи в чеках): {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('employees.list_employees'))


# Пошук контактних даних за прізвищем
@employees_bp.route('/find_contact')
@login_required
@roles_required('Manager')
def find_contact():
    surname = request.args.get('surname', '').strip()
    employee = None

    if surname:
        conn = get_db_connection()
        employee = conn.execute('''
            SELECT empl_surname, empl_name, empl_patronymic,
                   phone_number, city, street, zip_code
            FROM Employee
            WHERE LOWER(empl_surname) = LOWER(?)
        ''', (surname,)).fetchone()
        conn.close()

        if not employee:
            flash(f"Працівника з прізвищем '{surname}' не знайдено!", "warning")

    return render_template('employees/find_contact.html', employee=employee, surname=surname)