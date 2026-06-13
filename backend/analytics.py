# analytics.py
from flask import Blueprint, render_template, request
from initdb import get_db_connection
from decorators import login_required, roles_required

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')


# Вимога 21 (Manager): загальна кількість одиниць товару, проданого за період
@analytics_bp.route('/product_sales')
@login_required
@roles_required('Manager')
def product_sales_volume():
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    upc = request.args.get('upc', '').strip()
    result = None

    conn = get_db_connection()
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


# Вимога 4 (Manager): друк звітів по всіх сутностях
@analytics_bp.route('/print/<report_type>')
@login_required
@roles_required('Manager')
def print_report(report_type):
    from flask import flash, redirect, url_for

    allowed = ['employees', 'customers', 'categories', 'products',
               'store_products', 'checks']
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
    return render_template('analytics/report_print.html',
                           report_type=report_type,
                           data=data)