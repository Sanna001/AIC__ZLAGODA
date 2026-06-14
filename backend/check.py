from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from backend.initdb import get_db_connection
from decorators import login_required, roles_required

check_bp = Blueprint('check', __name__, url_prefix='/check')


# Вимога 7 (Cashier): створення чеку
@check_bp.route('/create', methods=['GET', 'POST'])
@login_required
@roles_required('Cashier')
def create_check():
    conn = get_db_connection()

    if request.method == 'POST':
        card_number = request.form.get('card_number') or None
        items = request.form.getlist('items')  # формат "UPC:кількість"

        if not items:
            flash("Додайте хоча б один товар до чеку!", "danger")
            conn.close()
            return redirect(url_for('check.create_check'))

        cursor = conn.cursor()
        try:
            total_sum = 0
            sale_items = []

            for item in items:
                parts = item.split(':')
                if len(parts) != 2:
                    raise Exception("Невірний формат товару!")
                upc, quantity = parts[0].strip(), parts[1].strip()
                qty = int(quantity)
                if qty <= 0:
                    raise Exception(f"Кількість товару {upc} має бути більше 0!")

                prod = cursor.execute(
                    'SELECT selling_price, products_number FROM Store_Product WHERE UPC = ?',
                    (upc,)
                ).fetchone()

                if not prod:
                    raise Exception(f"Товар з UPC {upc} не знайдено!")
                if prod['products_number'] < qty:
                    raise Exception(
                        f"Недостатньо товару {upc}: є {prod['products_number']}, потрібно {qty}!"
                    )

                total_sum += prod['selling_price'] * qty
                sale_items.append((upc, qty, prod['selling_price']))

            # Знижка за картою клієнта
            if card_number:
                card = cursor.execute(
                    'SELECT percent FROM Customer_Card WHERE card_number = ?',
                    (card_number,)
                ).fetchone()
                if card:
                    discount = card['percent'] / 100
                    total_sum = total_sum * (1 - discount)
                else:
                    flash("Вказану дисконтну картку не знайдено. Чек оформлено без знижки.", "warning")
                    card_number = None

            vat = round(total_sum * 0.2, 2)
            total_sum = round(total_sum, 2)

            # Генерація унікального номера чека
            max_check = cursor.execute(
                "SELECT check_number FROM Check_bill ORDER BY check_number DESC LIMIT 1"
            ).fetchone()
            if max_check:
                try:
                    last_num = int(max_check['check_number'].replace('CH', ''))
                    check_number = f"CH{last_num + 1}"
                except ValueError:
                    check_number = "CH1001"
            else:
                check_number = "CH1001"

            cursor.execute('''
                INSERT INTO Check_bill (check_number, id_employee, card_number, print_date, sum_total, vat)
                VALUES (?, ?, ?, datetime('now', 'localtime'), ?, ?)
            ''', (check_number, session['user_id'], card_number, total_sum, vat))

            for upc, qty, price in sale_items:
                cursor.execute('''
                    INSERT INTO Sale (UPC, check_number, product_number, selling_price)
                    VALUES (?, ?, ?, ?)
                ''', (upc, check_number, qty, price))
                cursor.execute(
                    "UPDATE Store_Product SET products_number = products_number - ? WHERE UPC = ?",
                    (qty, upc)
                )
                cursor.execute('DELETE FROM Store_Product WHERE products_number <= 0')

            conn.commit()
            flash(f"Чек {check_number} успішно створено! Сума: {total_sum} грн.", "success")
            return redirect(url_for('check.view_check', check_number=check_number))

        except Exception as e:
            conn.rollback()
            flash(f"Помилка: {str(e)}", "danger")
            return redirect(url_for('check.create_check'))
        finally:
            conn.close()

    # GET — форма створення чеку
    store_products = conn.execute('''
        SELECT sp.UPC, p.product_name, sp.selling_price, sp.products_number
        FROM Store_Product sp
        JOIN Product p ON sp.id_product = p.id_product
        WHERE sp.products_number > 0
        ORDER BY p.product_name
    ''').fetchall()

    customers = conn.execute(
        'SELECT card_number, cust_surname, cust_name, percent FROM Customer_Card ORDER BY cust_surname'
    ).fetchall()

    conn.close()
    return render_template('check/create.html',
                           store_products=store_products,
                           customers=customers)


# Вимога 9 (Cashier): чеки касира за сьогодні
@check_bp.route('/my/today')
@login_required
@roles_required('Cashier')
def my_checks_today():
    conn = get_db_connection()
    checks = conn.execute('''
        SELECT * FROM Check_bill
        WHERE id_employee = ?
          AND DATE(print_date) = DATE('now', 'localtime')
        ORDER BY print_date DESC
    ''', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('check/my_checks.html', checks=checks, period="сьогодні")


# Вимога 10 (Cashier): чеки касира за обраний період
@check_bp.route('/my')
@login_required
@roles_required('Cashier')
def my_checks():
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    conn = get_db_connection()

    if date_from and date_to:
        checks = conn.execute('''
            SELECT * FROM Check_bill
            WHERE id_employee = ?
              AND DATE(print_date) BETWEEN DATE(?) AND DATE(?)
            ORDER BY print_date DESC
        ''', (session['user_id'], date_from, date_to)).fetchall()
    else:
        checks = conn.execute('''
            SELECT * FROM Check_bill
            WHERE id_employee = ?
            ORDER BY print_date DESC
        ''', (session['user_id'],)).fetchall()

    conn.close()
    return render_template('check/my_checks.html',
                           checks=checks,
                           date_from=date_from,
                           date_to=date_to,
                           period="за обраний період")


# Вимоги 11 (Cashier) / 17, 18 (Manager): перегляд деталей чека
@check_bp.route('/<check_number>')
@login_required
@roles_required('Manager', 'Cashier')
def view_check(check_number):
    conn = get_db_connection()

    if session['role'] == 'Cashier':
        check = conn.execute('''
            SELECT cb.*, cc.cust_surname, cc.cust_name, cc.percent
            FROM Check_bill cb
            LEFT JOIN Customer_Card cc ON cb.card_number = cc.card_number
            WHERE cb.check_number = ? AND cb.id_employee = ?
        ''', (check_number, session['user_id'])).fetchone()
        # ВИПРАВЛЕНО: правильний endpoint
        redirect_endpoint = 'check.my_checks'
    else:
        check = conn.execute('''
            SELECT cb.*, e.empl_surname, e.empl_name,
                   cc.cust_surname, cc.cust_name, cc.percent
            FROM Check_bill cb
            JOIN Employee e ON cb.id_employee = e.id_employee
            LEFT JOIN Customer_Card cc ON cb.card_number = cc.card_number
            WHERE cb.check_number = ?
        ''', (check_number,)).fetchone()
        # ВИПРАВЛЕНО: звіти тепер в analytics
        redirect_endpoint = 'analytics.financial_report'

    if not check:
        conn.close()
        flash("Чек не знайдено або доступ заборонено!", "danger")
        return redirect(url_for(redirect_endpoint))

    items = conn.execute('''
        SELECT s.UPC, p.product_name, s.product_number, s.selling_price,
               (s.product_number * s.selling_price) AS item_total
        FROM Sale s
        JOIN Store_Product sp ON s.UPC = sp.UPC
        JOIN Product p ON sp.id_product = p.id_product
        WHERE s.check_number = ?
    ''', (check_number,)).fetchall()

    conn.close()
    return render_template('check/view_check.html', check=check, items=items)


# Вимога 3 (Manager): видалення чеку з поверненням товарів
@check_bp.route('/delete/<check_number>', methods=['POST'])
@login_required
@roles_required('Manager')
def delete_check(check_number):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Повертаємо товари на полиці перед видаленням
        items_to_return = cursor.execute(
            'SELECT UPC, product_number FROM Sale WHERE check_number = ?',
            (check_number,)
        ).fetchall()

        for item in items_to_return:
            cursor.execute('''
                UPDATE Store_Product
                SET products_number = products_number + ?
                WHERE UPC = ?
            ''', (item['product_number'], item['UPC']))

        cursor.execute('DELETE FROM Check_bill WHERE check_number = ?', (check_number,))
        conn.commit()
        flash(f"Чек {check_number} скасовано, товари повернуто в торговий зал!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Помилка видалення: {str(e)}", "danger")
    finally:
        conn.close()
    # ВИПРАВЛЕНО: правильний endpoint
    return redirect(url_for('analytics.financial_report'))