from flask import Blueprint, render_template, request, redirect, url_for, flash
from initdb import get_db_connection
from decorators import login_required, roles_required

# Назва блюпринту та префікс шляху
customer_card_bp = Blueprint('customer_card', __name__, url_prefix='/customer_card')

# Перегляд клієнтів
@customer_card_bp.route('/')
@login_required
@roles_required('Manager', 'Cashier')
def list_customers():
    search = request.args.get('search', '').strip()
    percent_filter = request.args.get('percent', '').strip()

    query = "SELECT * FROM Customer_Card WHERE 1=1"
    params = []

    if search:
        query += " AND LOWER(cust_surname) LIKE LOWER(?)"
        params.append(f'%{search}%')

    if percent_filter:
        query += " AND percent = ?"
        params.append(percent_filter)

    query += " ORDER BY cust_surname"

    conn = get_db_connection()
    customers = conn.execute(query, params).fetchall()
    conn.close()

    return render_template('customer_card/list.html',
                           customers=customers,
                           search=search,
                           percent_filter=percent_filter)


def _validate_customer_form(form):
    phone = form.get('phone_number', '').strip()
    if len(phone) > 13:
        return "Номер телефону не може перевищувати 13 символів!", None

    percent_raw = form.get('percent', 0)
    try:
        percent = int(percent_raw)
    except ValueError:
        return "Невірний формат відсотку!", None

    if percent < 0 or percent > 100:
        return "Відсоток має бути від 0 до 100!", None

    return None, {'phone': phone, 'percent': percent}


# Додати клієнта
@customer_card_bp.route('/add', methods=['GET', 'POST'])
@login_required
@roles_required('Manager', 'Cashier')
def add_customer():
    if request.method == 'POST':
        error, values = _validate_customer_form(request.form)
        if error:
            flash(error, "danger")
            return render_template('customer_card/add.html')

        conn = get_db_connection()
        try:
            conn.execute('''
                INSERT INTO Customer_Card
                (card_number, cust_surname, cust_name, cust_patronymic,
                 phone_number, city, street, zip_code, percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                request.form.get('card_number'),
                request.form.get('cust_surname'),
                request.form.get('cust_name'),
                request.form.get('cust_patronymic') or None,
                values['phone'],
                request.form.get('city') or None,
                request.form.get('street') or None,
                request.form.get('zip_code') or None,
                values['percent']
            ))
            conn.commit()
            flash("Клієнта додано!", "success")
            return redirect(url_for('customer_card.list_customers'))
        except Exception as e:
            flash("Помилка: картка з таким номером вже існує.", "danger")
        finally:
            conn.close()

    return render_template('customer_card/add.html')


# Редагувати клієнта
@customer_card_bp.route('/edit/<card_number>', methods=['GET', 'POST'])
@login_required
@roles_required('Manager', 'Cashier')
def edit_customer(card_number):
    conn = get_db_connection()
    customer = conn.execute(
        'SELECT * FROM Customer_Card WHERE card_number = ?', (card_number,)
    ).fetchone()

    if not customer:
        conn.close()
        flash("Клієнта не знайдено!", "danger")
        return redirect(url_for('customer_card.list_customers'))

    if request.method == 'POST':
        error, values = _validate_customer_form(request.form)
        if error:
            flash(error, "danger")
            conn.close()
            return render_template('customer_card/edit.html', customer=customer)

        try:
            conn.execute('''
                UPDATE Customer_Card SET
                    cust_surname = ?, cust_name = ?, cust_patronymic = ?,
                    phone_number = ?, city = ?, street = ?, zip_code = ?, percent = ?
                WHERE card_number = ?
            ''', (
                request.form.get('cust_surname'),
                request.form.get('cust_name'),
                request.form.get('cust_patronymic') or None,
                values['phone'],
                request.form.get('city') or None,
                request.form.get('street') or None,
                request.form.get('zip_code') or None,
                values['percent'],
                card_number
            ))
            conn.commit()
            flash("Дані клієнта оновлено!", "success")
            return redirect(url_for('customer_card.list_customers'))
        except Exception as e:
            flash(f"Помилка: {str(e)}", "danger")
        finally:
            conn.close()

    conn.close()
    return render_template('customer_card/edit.html', customer=customer)


# Видалити клієнта (тільки менеджер)
@customer_card_bp.route('/delete/<card_number>', methods=['POST'])
@login_required
@roles_required('Manager')
def delete_customer(card_number):
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM Customer_Card WHERE card_number = ?', (card_number,))
        conn.commit()
        flash("Клієнта видалено!", "success")
    except Exception as e:
        flash(f"Помилка видалення: {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('customer_card.list_customers'))