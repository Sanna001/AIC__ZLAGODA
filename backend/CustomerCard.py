from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from backend.initdb import get_db_connection
from decorators import login_required, roles_required

# ВИПРАВЛЕНО: назва блюпринту збігається з тим, що в app.py
customer_card_bp = Blueprint('customer_card', __name__, url_prefix='/customers')


# Вимоги 3, 7 (Cashier) / Вимоги 7, 12 (Manager):
# Сортує за прізвищем. Менеджер фільтрує за відсотком, касир шукає за прізвищем
@customer_card_bp.route('/')
@login_required
def manage_customers():
    percent = request.args.get('percent', '')
    search = request.args.get('search', '').strip()

    query = "SELECT * FROM Customer_Card WHERE 1=1"
    params = []

    if percent:
        query += " AND percent = ?"
        params.append(int(percent))
    if search:
        query += " AND LOWER(cust_surname) LIKE LOWER(?)"
        params.append(f'%{search}%')

    query += " ORDER BY cust_surname"

    conn = get_db_connection()
    customers = conn.execute(query, params).fetchall()
    conn.close()

    if session['role'] == 'Manager':
        return render_template('customer/customers.html',
                               customers=customers, percent=percent, search=search)
    return render_template('customer/customers.html', customers=customers, search=search)


# Вимога 1 (Manager) / Вимога 8 (Cashier): додати клієнта
# Вимога 1 (Manager) / Вимога 8 (Cashier): додати клієнта
@customer_card_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    if request.method == 'POST':
        # card_number більше не беремо з request.form!
        surname = request.form.get('cust_surname', '').strip()
        name = request.form.get('cust_name', '').strip()
        patronymic = request.form.get('cust_patronymic', '').strip() or None
        phone = request.form.get('phone_number', '').strip()
        city = request.form.get('city', '').strip() or None
        street = request.form.get('street', '').strip() or None
        zip_code = request.form.get('zip_code', '').strip() or None
        percent = request.form.get('percent', '0')

        # Валідація
        if len(phone) > 13:
            flash("Номер телефону не може перевищувати 13 символів!", "danger")
            return render_template('customer/add_customer.html')
        try:
            percent_val = int(percent)
            if percent_val < 0 or percent_val > 100:
                raise ValueError
        except ValueError:
            flash("Відсоток має бути цілим числом від 0 до 100!", "danger")
            return render_template('customer/add_customer.html')

        conn = get_db_connection()
        
        # --- ЛОГІКА АВТОГЕНЕРАЦІЇ КАРТКИ ---
        last_card = conn.execute("SELECT card_number FROM Customer_Card ORDER BY card_number DESC LIMIT 1").fetchone()
        if last_card:
            # CC100 -> беремо з 2-го символу (індекс 2)
            last_num = int(last_card['card_number'][2:])
            new_card_number = f"CC{last_num + 1}"
        else:
            new_card_number = "CC100"

        try:
            conn.execute('''
                INSERT INTO Customer_Card
                    (card_number, cust_surname, cust_name, cust_patronymic,
                     phone_number, city, street, zip_code, percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (new_card_number, surname, name, patronymic,
                  phone, city, street, zip_code, percent_val))
            conn.commit()
            flash(f"Картку клієнта успішно створено! Номер: {new_card_number}", "success")
            return redirect(url_for('customer_card.manage_customers'))
        except Exception as e:
            conn.rollback()
            flash(f"Помилка створення картки: {str(e)}", "danger")
        finally:
            conn.close()

    return render_template('customer/add_customer.html')

# Вимога 2 (Manager) / Вимога 8 (Cashier): редагувати клієнта
@customer_card_bp.route('/edit/<card_id>', methods=['GET', 'POST'])
@login_required
def edit_customer(card_id):
    conn = get_db_connection()
    cust = conn.execute(
        'SELECT * FROM Customer_Card WHERE card_number = ?', (card_id,)
    ).fetchone()

    if not cust:
        conn.close()
        flash("Клієнта не знайдено!", "danger")
        return redirect(url_for('customer_card.manage_customers'))

    if request.method == 'POST':
        surname = request.form.get('cust_surname', '').strip()
        name = request.form.get('cust_name', '').strip()
        patronymic = request.form.get('cust_patronymic', '').strip() or None
        phone = request.form.get('phone_number', '').strip()
        city = request.form.get('city', '').strip() or None
        street = request.form.get('street', '').strip() or None
        zip_code = request.form.get('zip_code', '').strip() or None
        percent = request.form.get('percent', '0')

        # Валідація
        if len(phone) > 13:
            flash("Номер телефону не може перевищувати 13 символів!", "danger")
            conn.close()
            return render_template('customer/edit_customer.html', customer=cust)
        try:
            percent_val = int(percent)
            if percent_val < 0 or percent_val > 100:
                raise ValueError
        except ValueError:
            flash("Відсоток має бути цілим числом від 0 до 100!", "danger")
            conn.close()
            return render_template('customer/edit_customer.html', customer=cust)

        try:
            conn.execute('''
                UPDATE Customer_Card
                SET cust_surname=?, cust_name=?, cust_patronymic=?, phone_number=?,
                    city=?, street=?, zip_code=?, percent=?
                WHERE card_number=?
            ''', (surname, name, patronymic, phone,
                  city, street, zip_code, percent_val, card_id))
            conn.commit()
            flash("Дані клієнта успішно оновлено!", "success")
            return redirect(url_for('customer_card.manage_customers'))
        except Exception as e:
            conn.rollback()
            flash(f"Помилка оновлення: {str(e)}", "danger")
        finally:
            conn.close()

    conn.close()
    return render_template('customer/edit_customer.html', customer=cust)


# Вимога 3 (Manager): видалити клієнта
@customer_card_bp.route('/delete/<card_id>', methods=['POST'])
@login_required
@roles_required('Manager')
def delete_customer(card_id):
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM Customer_Card WHERE card_number = ?', (card_id,))
        conn.commit()
        flash("Картку клієнта видалено!", "success")
    except Exception:
        conn.rollback()
        flash("Неможливо видалити картку клієнта, яка фігурує в наявних чеках!", "danger")
    finally:
        conn.close()
    return redirect(url_for('customer_card.manage_customers'))