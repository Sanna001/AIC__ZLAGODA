# analytics.py
from flask import Blueprint, render_template, request, flash, redirect, url_for
from backend.initdb import get_db_connection
from decorators import login_required, roles_required

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')


# ==========================================
# ВИМОГА 21: Загальна кількість одиниць певного товару, проданого за період
# ==========================================
@analytics_bp.route('/product_sales')
@login_required
@roles_required('Manager')
def product_sales_volume():
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    upc = request.args.get('upc', '').strip()
    result = None

    conn = get_db_connection()
    # Отримуємо список товарів для випадаючого списку (фільтру)
    store_products = conn.execute('''
        SELECT sp.UPC, p.product_name FROM Store_Product sp
        JOIN Product p ON sp.id_product = p.id_product
        ORDER BY p.product_name
    ''').fetchall()

    if upc and date_from and date_to:
        result = conn.execute('''
            SELECT SUM(s.product_number) AS total_sold
            FROM Sale s
            JOIN Check_bill cb ON s.check_number = cb.check_number
            WHERE s.UPC = ?
              AND DATE(cb.print_date) BETWEEN DATE(?) AND DATE(?)
        ''', (upc, date_from, date_to)).fetchone()

    conn.close()
    return render_template('analytics/product_sales.html',
                           store_products=store_products,
                           result=result,
                           upc=upc,
                           date_from=date_from,
                           date_to=date_to)


# ==========================================
# ВИМОГИ 17, 18, 19, 20: Фінансові звіти та чеки (усі або конкретний касир) за період
# ==========================================
@analytics_bp.route('/financial_report')
@login_required
@roles_required('Manager')
def financial_report():
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    cashier_id = request.args.get('cashier_id', '').strip() # Порожньо = усі касири

    conn = get_db_connection()
    
    # Витягуємо список касирів для фільтрації в інтерфейсі
    cashiers = conn.execute('''
        SELECT id_employee, empl_surname, empl_name 
        FROM Employee WHERE empl_role = 'Cashier'
        ORDER BY empl_surname
    ''').fetchall()

    checks = []
    total_revenue = 0

    if date_from and date_to:
        # Базова SQL умова для фільтрації дат
        where_clause = "WHERE DATE(cb.print_date) BETWEEN DATE(?) AND DATE(?)"
        params = [date_from, date_to]

        # Якщо обрано конкретного касира (Вимоги 17 та 19)
        if cashier_id:
            where_clause += " AND cb.id_employee = ?"
            params.append(cashier_id)
        # Якщо cashier_id порожній — шукає по усіх касирах (Вимоги 18 та 20)

        # 1. Отримуємо інформацію про чеки (Вимога 17 та 18)
        checks_query = f'''
            SELECT cb.check_number, cb.print_date, cb.sum_total, cb.vat,
                   e.empl_surname, e.empl_name
            FROM Check_bill cb
            JOIN Employee e ON cb.id_employee = e.id_employee
            {where_clause}
            ORDER BY cb.print_date DESC
        '''
        checks = conn.execute(checks_query, params).fetchall()

        # 2. Визначаємо загальну суму проданих товарів з цих чеків (Вимога 19 та 20)
        sum_query = f"SELECT SUM(cb.sum_total) FROM Check_bill cb {where_clause}"
        total_revenue = conn.execute(sum_query, params).fetchone()[0] or 0

    conn.close()
    return render_template('analytics/financial_report.html',
                           checks=checks,
                           cashiers=cashiers,
                           selected_cashier=cashier_id,
                           date_from=date_from,
                           date_to=date_to,
                           total_revenue=round(total_revenue, 2))


# ==========================================
# Вимога 4 (Manager): Друк звітів по всіх сутностях
# ==========================================
@analytics_bp.route('/print/<report_type>')
@login_required
@roles_required('Manager')
def print_report(report_type):
    allowed = ['employees', 'customers', 'categories', 'products', 'store_products', 'checks']
    if report_type not in allowed:
        flash("Невідомий тип звіту!", "danger")
        return redirect(url_for('auth.dashboard'))

    conn = get_db_connection()
    data = None

    if report_type == 'employees':
        data = conn.execute('SELECT * FROM Employee ORDER BY empl_surname').fetchall()
    elif report_type == 'customers':
        data = conn.execute('SELECT * FROM Customer_Card ORDER BY cust_surname').fetchall()
    elif report_type == 'categories':
        data = conn.execute('SELECT * FROM Category ORDER BY category_name').fetchall()
    elif report_type == 'products':
        data = conn.execute('''
            SELECT p.*, c.category_name FROM Product p
            JOIN Category c ON p.category_number = c.category_number
            ORDER BY p.product_name
        ''').fetchall()
    elif report_type == 'store_products':
        data = conn.execute('''
            SELECT sp.*, p.product_name FROM Store_Product sp
            JOIN Product p ON sp.id_product = p.id_product
            ORDER BY p.product_name
        ''').fetchall()
    elif report_type == 'checks':
        data = conn.execute('''
            SELECT cb.*, e.empl_surname FROM Check_bill cb
            JOIN Employee e ON cb.id_employee = e.id_employee
            ORDER BY cb.print_date DESC
        ''').fetchall()

    conn.close()
    return render_template('analytics/report_print.html', report_type=report_type, data=data)