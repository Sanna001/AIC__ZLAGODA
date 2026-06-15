from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from backend.initdb import get_db_connection
from decorators import login_required, roles_required
from datetime import date
import datetime

check_bp = Blueprint('check', __name__, url_prefix='/check')


# =========================================================================
# ПЕРЕГЛЯД АРХІВУ ЧЕКІВ (Вимоги для Менеджера та Касира)
# =========================================================================
@check_bp.route('/')
@login_required
def list_checks():
    # Параметри з форми пошуку
    date_from = request.args.get('date_from', date.today().strftime('%Y-%m-%d'))
    date_to = request.args.get('date_to', date.today().strftime('%Y-%m-%d'))
    cashier_id = request.args.get('cashier_id', '')

    conn = get_db_connection()
    
    # Базовий запит
    query = "SELECT cb.*, e.empl_surname FROM Check_bill cb JOIN Employee e ON cb.id_employee = e.id_employee WHERE 1=1"
    params = []

    # Обмеження ролей
    if session.get('role') == 'Cashier':
        query += " AND cb.id_employee = ?"
        params.append(session['user_id'])
    elif session.get('role') == 'Manager' and cashier_id:
        query += " AND cb.id_employee = ?"
        params.append(cashier_id)

    # Фільтр по датах
    query += " AND DATE(cb.print_date) BETWEEN DATE(?) AND DATE(?)"
    params.extend([date_from, date_to])
    
    # Отримання списку чеків
    query_list = query + " ORDER BY cb.print_date DESC"
    checks = conn.execute(query_list, params).fetchall()

    # Розрахунок суми (безпечний спосіб)
    sum_query = "SELECT SUM(sum_total) FROM Check_bill cb WHERE 1=1"
    # Потрібно продублювати фільтри для запиту суми, бо використання .replace() 
    # з попереднім запитом може бути ненадійним через JOIN
    sum_params = []
    if session.get('role') == 'Cashier':
        sum_query += " AND id_employee = ?"
        sum_params.append(session['user_id'])
    elif session.get('role') == 'Manager' and cashier_id:
        sum_query += " AND id_employee = ?"
        sum_params.append(cashier_id)
    sum_query += " AND DATE(print_date) BETWEEN DATE(?) AND DATE(?)"
    sum_params.extend([date_from, date_to])
    
    total_result = conn.execute(sum_query, sum_params).fetchone()
    total_sum = total_result[0] if total_result and total_result[0] else 0

    # Касири
    cashiers = conn.execute("SELECT id_employee, empl_surname FROM Employee WHERE empl_role = 'Cashier'").fetchall()
    
    conn.close()
    return render_template('check/list.html', 
                           checks=checks, 
                           total_sum=total_sum, 
                           date_from=date_from, 
                           date_to=date_to,
                           cashiers=cashiers)

# =========================================================================
# ДОДАТКОВО: Чеки касира за сьогодні (Вимога для Cashier)
# =========================================================================
@check_bp.route('/my-today')
@login_required
@roles_required('Cashier')
def my_checks_today():
    today_str = date.today().strftime('%Y-%m-%d')
    conn = get_db_connection()
    
    # Вибираємо чеки лише поточного касира за сьогодні
    checks = conn.execute('''
        SELECT cb.*, e.empl_surname 
        FROM Check_bill cb 
        JOIN Employee e ON cb.id_employee = e.id_employee 
        WHERE cb.id_employee = ? AND DATE(cb.print_date) = DATE(?)
        ORDER BY cb.print_date DESC
    ''', (session['user_id'], today_str)).fetchall()
    
    conn.close()
    # Використовуємо той самий шаблон списку, передаючи відфільтровані дані
    return render_template('check/list.html', checks=checks, cashiers=[])


# =========================================================================
# ДОДАТКОВО: Чеки касира за період (Вимога для Cashier)
# =========================================================================
@check_bp.route('/my-period')
@login_required
@roles_required('Cashier')
def my_checks():
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    query = '''
        SELECT cb.*, e.empl_surname 
        FROM Check_bill cb 
        JOIN Employee e ON cb.id_employee = e.id_employee 
        WHERE cb.id_employee = ?
    '''
    params = [session['user_id']]

    if date_from:
        query += " AND DATE(cb.print_date) >= DATE(?)"
        params.append(date_from)
    if date_to:
        query += " AND DATE(cb.print_date) <= DATE(?)"
        params.append(date_to)

    query += " ORDER BY cb.print_date DESC"

    conn = get_db_connection()
    checks = conn.execute(query, params).fetchall()
    conn.close()

    return render_template('check/list.html', checks=checks, cashiers=[])

# =========================================================================
# АНАЛІТИКА ТА ГЕНЕРАЦІЯ ЗВІТІВ ПО ЧЕКАХ (Вимоги 18, 19, 20)
# =========================================================================
# Додайте цей маршрут для звіту (Вимоги 17-20)
import sqlite3

@check_bp.route('/generate_report')
@login_required
@roles_required('Manager', 'Cashier')
def generate_report():
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    cashier_id = request.args.get('cashier_id')

    conn = get_db_connection()
    # Встановлюємо row_factory для зручної роботи зі словниками
    conn.row_factory = sqlite3.Row 
    
    query = """
        SELECT cb.*, e.empl_surname 
        FROM Check_bill cb 
        JOIN Employee e ON cb.id_employee = e.id_employee 
        WHERE DATE(cb.print_date) BETWEEN DATE(?) AND DATE(?)
    """
    params = [date_from, date_to]

    # Касир може бачити лише власні чеки
    if session.get('role') == 'Cashier':
        query += " AND cb.id_employee = ?"
        params.append(session['user_id'])
    elif cashier_id:
        query += " AND cb.id_employee = ?"
        params.append(cashier_id)

    checks_rows = conn.execute(query + " ORDER BY cb.print_date DESC", params).fetchall()

    report_data = []
    for chk in checks_rows:
        # Отримуємо товари для кожного чека
        items = conn.execute('''
            SELECT p.product_name, s.product_number, s.selling_price 
            FROM Sale s
            JOIN Store_Product sp ON s.UPC = sp.UPC
            JOIN Product p ON sp.id_product = p.id_product
            WHERE s.check_number = ?
        ''', (chk['check_number'],)).fetchall()
        
        # Перетворюємо результати в звичайні словники (dict)
        report_data.append({
            'check': dict(chk), 
            'products': [dict(item) for item in items]
        })

    # Розрахунок загальної суми
    sum_query = "SELECT SUM(sum_total) FROM Check_bill WHERE DATE(print_date) BETWEEN DATE(?) AND DATE(?)"
    sum_params = [date_from, date_to]
    if cashier_id:
        sum_query += " AND id_employee = ?"
        sum_params.append(cashier_id)
    
    total_revenue = conn.execute(sum_query, sum_params).fetchone()[0] or 0
    conn.close()

    return render_template('check/manager_report.html', 
                           report_data=report_data, 
                           total_revenue=total_revenue,
                           date_from=date_from, date_to=date_to)

# =========================================================================
# ВИМОГА 7 (Cashier): СТВОРЕННЯ НОВОГО ЧЕКУ ЗАМОВЛЕННЯ
# =========================================================================
@check_bp.route('/create', methods=['GET', 'POST'])
@login_required
@roles_required('Cashier')
def create_check():
    conn = get_db_connection()

    if request.method == 'POST':
        card_number = request.form.get('card_number') or None
        items = request.form.getlist('items')  # очікується масив рядків виду "UPC:кількість"

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
                    raise Exception("Невірний формат товару у формі!")
                
                upc, quantity = parts[0].strip(), parts[1].strip()
                qty = int(quantity)
                if qty <= 0:
                    raise Exception(f"Кількість товару з UPC {upc} має бути більше 0!")

                prod = cursor.execute(
                    'SELECT selling_price, products_number FROM Store_Product WHERE UPC = ?',
                    (upc,)
                ).fetchone()

                if not prod or prod['products_number'] < qty:
                    raise Exception(f"Недостатньо товару з UPC {upc} на полицях супермаркету!")

                price = prod['selling_price']
                item_total = price * qty
                total_sum += item_total
                sale_items.append((upc, qty, price))

            # Перевірка та отримання знижки за дисконтною карткою клієнта
            discount = 0
            if card_number:
                card = cursor.execute('SELECT percent FROM Customer_Card WHERE card_number = ?', (card_number,)).fetchone()
                if card:
                    discount = card['percent']

            # Розрахунок кінцевої вартості (ПДВ 20% вже закладено у вартість selling_price)
            final_total = round(total_sum * (1 - discount / 100.0), 2)
            vat = round(final_total * 0.20, 2)

            # Генерація унікального номера чека за поточною мілісекундою/часом
            check_number = "CH" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")

            cursor.execute('''
                INSERT INTO Check_bill (check_number, id_employee, card_number, print_date, sum_total, vat)
                VALUES (?, ?, ?, datetime('now', 'localtime'), ?, ?)
            ''', (check_number, session['user_id'], card_number, final_total, vat))

            for upc, qty, price in sale_items:
                # Фіксація продажу в таблиці Sale
                cursor.execute('''
                    INSERT INTO Sale (UPC, check_number, product_number, selling_price)
                    VALUES (?, ?, ?, ?)
                ''', (upc, check_number, qty, price))

                # Списання залишків продукту з торгового залу
                cursor.execute('''
                    UPDATE Store_Product
                    SET products_number = products_number - ?
                    WHERE UPC = ?
                ''', (qty, upc))

            conn.commit()
            flash(f"Чек {check_number} успішно створено на суму {final_total} грн!", "success")
            return redirect(url_for('check.list_checks'))
            
        except Exception as e:
            conn.rollback()
            flash(f"Помилка оформлення чеку: {str(e)}", "danger")
            return redirect(url_for('check.create_check'))
        finally:
            conn.close()

    # GET-запит: Формування даних для інтерфейсу касира
    store_products = conn.execute('''
        SELECT sp.UPC, p.product_name, sp.selling_price, sp.products_number
        FROM Store_Product sp
        JOIN Product p ON sp.id_product = p.id_product
        WHERE sp.products_number > 0
        ORDER BY p.product_name
    ''').fetchall()
    
    cards = conn.execute('SELECT card_number, cust_surname, cust_name FROM Customer_Card ORDER BY cust_surname').fetchall()
    conn.close()

    return render_template('check/create_check.html', store_products=store_products, cards=cards)


# =========================================================================
# ПЕРЕГЛЯД ДЕТАЛЕЙ КОНКРЕТНОГО ЧЕКУ
# =========================================================================
# Додайте цей маршрут у check.py
# Додайте цей код у ваш check.py
@check_bp.route('/<check_number>')
@login_required
def view_check(check_number):
    conn = get_db_connection()
    # Отримуємо дані чека з інформацією про касира
    check = conn.execute('''
        SELECT cb.*, e.empl_surname 
        FROM Check_bill cb 
        JOIN Employee e ON cb.id_employee = e.id_employee 
        WHERE cb.check_number = ?
    ''', (check_number,)).fetchone()
    
    # Отримуємо товари, що були в чеку
    items = conn.execute('''
        SELECT s.*, p.product_name, sp.selling_price
        FROM Sale s
        JOIN Store_Product sp ON s.UPC = sp.UPC
        JOIN Product p ON sp.id_product = p.id_product
        WHERE s.check_number = ?
    ''', (check_number,)).fetchall()
    
    conn.close()
    
    if not check:
        flash("Чек не знайдено!", "danger")
        return redirect(url_for('check.list_checks'))

    # Касир може переглядати лише власні чеки
    if session.get('role') == 'Cashier' and check['id_employee'] != session['user_id']:
        flash("У вас немає доступу до цього чеку!", "danger")
        return redirect(url_for('check.list_checks'))
        
    return render_template('check/view_check.html', check=check, items=items)
# =========================================================================
# ВИМОГА 3 (Manager): СКАСУВАННЯ ЧЕКУ З ПОВЕРНЕННЯМ ТОВАРІВ НА ПОЛИЦІ
# =========================================================================
@check_bp.route('/delete/<check_number>', methods=['POST'])
@login_required
@roles_required('Manager')
def delete_check(check_number):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 1. Отримуємо список товарів та їх кількість з чеку, що скасовується
        items_to_return = cursor.execute(
            'SELECT UPC, product_number FROM Sale WHERE check_number = ?',
            (check_number,)
        ).fetchall()

        # 2. Повертаємо кількість товарів назад до Store_Product
        for item in items_to_return:
            cursor.execute('''
                UPDATE Store_Product
                SET products_number = products_number + ?
                WHERE UPC = ?
            ''', (item['product_number'], item['UPC']))

        # 3. Видаляємо чек (завдяки ON DELETE CASCADE у базі даних, записи зі Sale видаляться автоматично)
        cursor.execute('DELETE FROM Check_bill WHERE check_number = ?', (check_number,))
        
        conn.commit()
        flash(f"Чек {check_number} скасовано, товари повернуто в торговий зал!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Помилка видалення: {str(e)}", "danger")
    finally:
        conn.close()
        
    return redirect(url_for('check.list_checks'))

# =========================================================================
# ВИМОГА: Пошук чеку за номером (для Касира)
# =========================================================================
@check_bp.route('/search-by-number')
@login_required
@roles_required('Cashier')
def search_check_by_number():
    check_number = request.args.get('check_number', '').strip()

    if not check_number:
        flash("Введіть номер чеку для пошуку.", "warning")
        return redirect(url_for('check.list_checks'))

    conn = get_db_connection()
    check = conn.execute('''
        SELECT cb.*, e.empl_surname
        FROM Check_bill cb
        JOIN Employee e ON cb.id_employee = e.id_employee
        WHERE cb.check_number = ?
    ''', (check_number,)).fetchone()
    conn.close()

    if not check:
        flash(f"Чек з номером «{check_number}» не знайдено.", "danger")
        return redirect(url_for('check.list_checks'))

    # Касир може шукати лише власні чеки
    if check['id_employee'] != session['user_id']:
        flash("У вас немає доступу до цього чеку.", "danger")
        return redirect(url_for('check.list_checks'))

    return redirect(url_for('check.view_check', check_number=check_number))


@check_bp.route('/cashier-sales-report')
@login_required
@roles_required('Manager')
def cashier_sales_report():
    date_from = request.args.get('date_from', date.today().strftime('%Y-%m-%d'))
    date_to = request.args.get('date_to', date.today().strftime('%Y-%m-%d'))
    cashier_id = request.args.get('cashier_id', '')

    conn = get_db_connection()
    cashiers = conn.execute(
        "SELECT id_employee, empl_surname, empl_name FROM Employee WHERE empl_role = 'Cashier'"
    ).fetchall()

    report = None
    cashier_info = None

    if cashier_id:
        # Загальна сума по касиру за період
        report = conn.execute('''
            SELECT 
                COUNT(cb.check_number) AS checks_count,
                SUM(cb.sum_total)      AS total_sum,
                SUM(cb.vat)            AS total_vat
            FROM Check_bill cb
            WHERE cb.id_employee = ?
              AND DATE(cb.print_date) BETWEEN DATE(?) AND DATE(?)
        ''', (cashier_id, date_from, date_to)).fetchone()

        # Деталізація по товарах
        products = conn.execute('''
            SELECT 
                p.product_name,
                SUM(s.product_number)  AS total_qty,
                SUM(s.product_number * s.selling_price) AS total_price
            FROM Sale s
            JOIN Check_bill cb ON s.check_number = cb.check_number
            JOIN Store_Product sp ON s.UPC = sp.UPC
            JOIN Product p ON sp.id_product = p.id_product
            WHERE cb.id_employee = ?
              AND DATE(cb.print_date) BETWEEN DATE(?) AND DATE(?)
            GROUP BY p.product_name
            ORDER BY total_price DESC
        ''', (cashier_id, date_from, date_to)).fetchall()

        cashier_info = conn.execute(
            "SELECT empl_surname, empl_name FROM Employee WHERE id_employee = ?",
            (cashier_id,)
        ).fetchone()
    else:
        products = []

    conn.close()
    return render_template('check/cashier_sales_report.html',
                           cashiers=cashiers,
                           cashier_info=cashier_info,
                           report=report,
                           products=products,
                           date_from=date_from,
                           date_to=date_to,
                           cashier_id=cashier_id)

# Додайте цей код у backend/check.py
@check_bp.route('/all_cashiers_report', methods=['GET'])
@login_required
@roles_required('Manager')
def all_cashiers_report():
    conn = get_db_connection()
    # Тут має бути ваш SQL-запит для звіту по всіх касирах
    # Наприклад:
    report = conn.execute('''
        SELECT e.empl_surname, SUM(cb.sum_total) as total_sales
        FROM Check_bill cb
        JOIN Employee e ON cb.id_employee = e.id_employee
        GROUP BY e.id_employee
    ''').fetchall()
    conn.close()
    
    return render_template('check/all_cashiers_report.html', report=report)