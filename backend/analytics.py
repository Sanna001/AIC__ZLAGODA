from flask import Blueprint, render_template, request, flash, redirect, url_for
from backend.initdb import get_db_connection
from decorators import login_required, roles_required

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')

# Загальна кількість одиниць певного товару, проданого за період
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


# Фінансові звіти та чеки 
@analytics_bp.route('/financial_report')
@login_required
@roles_required('Manager')
def financial_report():
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    cashier_id = request.args.get('cashier_id', '').strip() 

    conn = get_db_connection()
    
    cashiers = conn.execute('''
        SELECT id_employee, empl_surname, empl_name 
        FROM Employee WHERE empl_role = 'Cashier'
        ORDER BY empl_surname
    ''').fetchall()

    checks = []
    total_revenue = 0

    if date_from and date_to:
        where_clause = "WHERE DATE(cb.print_date) BETWEEN DATE(?) AND DATE(?)"
        params = [date_from, date_to]

        if cashier_id:
            where_clause += " AND cb.id_employee = ?"
            params.append(cashier_id)
       
        checks_query = f'''
            SELECT cb.check_number, cb.print_date, cb.sum_total, cb.vat,
                   e.empl_surname, e.empl_name
            FROM Check_bill cb
            JOIN Employee e ON cb.id_employee = e.id_employee
            {where_clause}
            ORDER BY cb.print_date DESC
        '''
        checks = conn.execute(checks_query, params).fetchall()

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


# Друк звітів 
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
    if report_type == 'products':
        # Зчитуємо фільтри з URL
        search_name = request.args.get('search_name', '').strip()
        category_id = request.args.get('category_id', '')

        query = '''
            SELECT p.*, c.category_name FROM Product p
            JOIN Category c ON p.category_number = c.category_number
            WHERE 1=1
        '''
        params = []

        if category_id:
            query += " AND p.category_number = ?"
            params.append(category_id)
        
        if search_name:
            query += " AND LOWER(p.product_name) LIKE LOWER(?)"
            params.append(f'%{search_name}%')

        query += " ORDER BY p.product_name"
        data = conn.execute(query, params).fetchall()
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