from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash
from initdb import get_db_connection
from decorators import login_required, roles_required
from datetime import date
import sqlite3

employees_bp = Blueprint('employees', __name__, url_prefix='/employees')

# перегляд списку працівників 
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
                          values['start'],
                          values['phone'],
                          request.form.get('city'), 
                          request.form.get('street'), 
                          request.form.get('zip_code'), 
                          generate_password_hash(request.form.get('password'))))
            conn.commit()
            flash(f"Employee added successfully! ID: {new_id}", "success")
            return redirect(url_for('employees.list_employees'))
        except Exception as e:
            conn.rollback()
            flash(f"Error: {str(e)}", "danger")
        finally:
            conn.close()
            
    return render_template('employees/add.html')

@employees_bp.route('/view/<id_employee>')
@login_required
@roles_required('Manager')
def view_employee(id_employee):
    if session.get('role') != 'Manager' and session.get('user_id') != id_employee:
        flash("You do not have permission to view this profile", "danger")
        return redirect(url_for('auth.dashboard'))
    conn = get_db_connection()
    emp = conn.execute('SELECT * FROM Employee WHERE id_employee = ?', (id_employee,)).fetchone()
    conn.close()
    
    if not emp:
        flash("Employee not found!", "danger")
        return redirect(url_for('employees.list_employees'))
        
    return render_template('employees/profile.html', employee=emp)

# перегляд свого профілю
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
        flash("Data not found!", "danger")
        return redirect(url_for('auth.dashboard'))

    return render_template('employees/profile.html', employee=employee)

def _validate_employee_form(form):
    """Returns (error_message, parsed_values) or (None, parsed_values)"""
    
    birth = form.get('date_of_birth', '')
    try:
        birth_date = date.fromisoformat(birth)
        today = date.today()
        age = today.year - birth_date.year - (
            (today.month, today.day) < (birth_date.month, birth_date.day)
        )
        if age < 18:
            return "Employee age cannot be less than 18 years!", None
    except ValueError:
        return "Invalid date of birth format!", None

    start_date_str = form.get('date_of_start', '')
    try:
        start_date = date.fromisoformat(start_date_str)
        if start_date > date.today():
            return "Hire date cannot be in the future!", None
    except ValueError:
        return "Invalid hire date format!", None
    
    phone = form.get('phone_number', '').strip()
    if len(phone) > 13:
        return "Phone number cannot exceed 13 characters!", None
    if not phone.startswith('+'):
        return "Phone number must start with '+'!", None

    salary = form.get('salary', 0)
    try:
        salary = float(salary)
    except ValueError:
        return "Invalid salary format!", None
    if salary < 0:
        return "Salary cannot be negative!", None

    return None, {
        'birth': birth,
        'start': start_date_str,
        'phone': phone,
        'salary': salary
    }

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
        flash("Employee not found!", "danger")
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
                values['start'],
                values['phone'],
                request.form.get('city'),
                request.form.get('street'),
                request.form.get('zip_code'),
                id_employee
            ))
            conn.commit()
            flash("Employee data updated!", "success")
            return redirect(url_for('employees.list_employees'))
        except Exception as e:
            conn.rollback()
            flash(f"Database error: {str(e)}", "danger")
        finally:
            conn.close()

    conn.close()
    return render_template('employees/edit.html', employee=employee)

@employees_bp.route('/delete/<id_employee>', methods=['POST'])
@login_required
@roles_required('Manager')
def delete_employee(id_employee):
    if session.get('user_id') == id_employee:
        flash("You cannot fire yourself!", "danger")
        return redirect(url_for('employees.list_employees'))

    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM Employee WHERE id_employee = ?', (id_employee,))
        conn.commit()
        flash("Employee deleted successfully.", "success")
    except Exception as e:
        flash(f"Cannot delete (possible records in receipts): {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('employees.list_employees'))

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
            flash(f"Employee with surname '{surname}' not found!", "warning")

    return render_template('employees/find_contact.html', employee=employee, surname=surname)