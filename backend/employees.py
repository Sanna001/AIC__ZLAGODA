# employees.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash
from initdb import get_db_connection
from decorators import login_required, roles_required
from datetime import date
import sqlite3

employees_bp = Blueprint('employees', __name__, url_prefix='/employees')


# Вимоги 5, 6, 11 (Manager): список, фільтр за роллю, пошук за прізвищем
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

# У файлі employees.py
@employees_bp.route('/view/<id_employee>')
@login_required
@roles_required('Manager')
def view_employee(id_employee):
    conn = get_db_connection()
    # Отримуємо дані конкретного працівника за його ID
    emp = conn.execute('SELECT * FROM Employee WHERE id_employee = ?', (id_employee,)).fetchone()
    conn.close()
    
    if not emp:
        flash("Працівника не знайдено!", "danger")
        return redirect(url_for('employees.list_employees'))
        
    # Використовуємо той самий шаблон profile.html
    return render_template('employees/profile.html', employee=emp)

# Вимога 15 (Cashier): інформація про себе
@employees_bp.route('/profile')
@login_required
@roles_required('Cashier', 'Manager')
def profile():
    from flask import session
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

    phone = form.get('phone_number', '').strip()
    if len(phone) > 13:
        return "Номер телефону не може перевищувати 13 символів!", None

    salary = form.get('salary', 0)
    try:
        salary = float(salary)
    except ValueError:
        return "Невірний формат зарплати!", None
    if salary < 0:
        return "Зарплата не може бути від'ємною!", None

    return None, {
        'birth': birth,
        'phone': phone,
        'salary': salary
    }

@employees_bp.route('/add', methods=['GET', 'POST'])
@login_required
@roles_required('Manager')
def add_employee():
    if request.method == 'POST':
        # 1. Перевіряємо дані через вашу валідаційну функцію
        error, values = _validate_employee_form(request.form)
        if error:
            flash(error, "danger")
            return render_template('employees/add.html')

        # 2. З'єднуємось з БД
        conn = get_db_connection()
        
        # 3. ГЕНЕРАЦІЯ ID (Тут ми визначаємо новий ID)
        last_empl = conn.execute("SELECT id_employee FROM Employee ORDER BY id_employee DESC LIMIT 1").fetchone()
        
        if last_empl:
            # last_empl['id_employee'] це, наприклад, 'E102'. [1:] відрізає 'E' -> '102'
            last_num = int(last_empl['id_employee'][1:]) 
            new_id = f"E{last_num + 1}"
        else:
            new_id = "E100" # Якщо таблиця порожня

        # 4. Вставка в базу
        try:
            conn.execute('''
                INSERT INTO Employee (id_employee, empl_surname, empl_name, empl_patronymic, 
                                      empl_role, salary, date_of_birth, date_of_start, 
                                      phone_number, city, street, zip_code, password_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                new_id, 
                request.form.get('empl_surname'),
                request.form.get('empl_name'),
                request.form.get('empl_patronymic') or None,
                request.form.get('empl_role'),
                values['salary'],
                values['birth'],
                request.form.get('date_of_start'),
                values['phone'],
                request.form.get('city'),
                request.form.get('street'),
                request.form.get('zip_code'),
                generate_password_hash(request.form.get('password'))
            ))
            conn.commit()
            flash(f"Працівника успішно додано! Присвоєно ID: {new_id}", "success")
            return redirect(url_for('employees.list_employees'))
        except Exception as e:
            conn.rollback()
            flash(f"Помилка: {str(e)}", "danger")
        finally:
            conn.close()

    return render_template('employees/add.html')


# Вимога 2 (Manager): редагувати працівника
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
        error, values = _validate_employee_form(request.form)
        if error:
            flash(error, "danger")
            conn.close()
            return render_template('employees/edit.html', employee=employee)

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
                values['salary'],
                values['birth'],
                request.form.get('date_of_start'),
                values['phone'],
                request.form.get('city'),
                request.form.get('street'),
                request.form.get('zip_code'),
                id_employee
            ))
            conn.commit()
            flash("Дані працівника оновлено!", "success")
            return redirect(url_for('employees.list_employees'))
        except Exception as e:
            flash(f"Помилка: {str(e)}", "danger")
        finally:
            conn.close()

    conn.close()
    return render_template('employees/edit.html', employee=employee)


# Вимога 3 (Manager): видалити (деактивувати) працівника
# Видалення працівника (у вашому employees.py)
@employees_bp.route('/delete/<id_employee>', methods=['POST'])
@login_required
@roles_required('Manager')
def delete_employee(id_employee):
    # Захист: менеджер не може видалити самого себе
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


# Вимога 11 (Manager): за прізвищем знайти телефон та адресу
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