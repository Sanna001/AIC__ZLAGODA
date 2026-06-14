from flask import Blueprint, render_template, request, redirect, url_for, flash
from backend.initdb import get_db_connection
from decorators import login_required, roles_required

product_bp = Blueprint('product', __name__, url_prefix='/products')


# Вимоги 9, 13 (Manager) / Вимога 1 (Cashier): товари за назвою, фільтр за категорією
@product_bp.route('/')
@login_required
def manage_products():
    cat_filter = request.args.get('category_id', '')

    query = '''
        SELECT p.*, c.category_name FROM Product p
        JOIN Category c ON p.category_number = c.category_number
    '''
    params = []
    if cat_filter:
        query += " WHERE p.category_number = ?"
        params.append(cat_filter)
    query += " ORDER BY p.product_name"

    conn = get_db_connection()
    products = conn.execute(query, params).fetchall()
    categories = conn.execute('SELECT * FROM Category ORDER BY category_name').fetchall()
    conn.close()
    return render_template('product/list.html',
                           products=products,
                           categories=categories,
                           cat_filter=cat_filter)


# Вимога 1 (Manager): додати товар
@product_bp.route('/add', methods=['GET', 'POST'])
@login_required
@roles_required('Manager')
def add_product():
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM Category ORDER BY category_name').fetchall()

    if request.method == 'POST':
        cat_num = request.form.get('category_number', '').strip()
        name = request.form.get('product_name', '').strip()
        chars = request.form.get('characteristics', '').strip() or None

        if not cat_num or not name:
            flash("Заповніть усі обов'язкові поля!", "danger")
            conn.close()
            return render_template('product/add.html', categories=categories)

        try:
            # SQL автоматично призначить ID, якщо ви вкажете тільки потрібні стовпці
            conn.execute(
                'INSERT INTO Product (category_number, product_name, characteristics) VALUES (?, ?, ?)',
                (int(cat_num), name, chars)
            )
            conn.commit()
            flash("Товар успішно додано!", "success")
            return redirect(url_for('product.manage_products'))
        except Exception as e:
            conn.rollback()
            flash(f"Помилка: {str(e)}", "danger")
        finally:
            conn.close()

    conn.close()
    return render_template('product/add.html', categories=categories)


# Вимога 2 (Manager): редагувати товар
@product_bp.route('/edit/<int:id_product>', methods=['GET', 'POST'])
@login_required
@roles_required('Manager')
def edit_product(id_product):
    conn = get_db_connection()
    product = conn.execute(
        'SELECT * FROM Product WHERE id_product = ?', (id_product,)
    ).fetchone()
    categories = conn.execute('SELECT * FROM Category ORDER BY category_name').fetchall()

    if not product:
        conn.close()
        flash("Товар не знайдено!", "danger")
        return redirect(url_for('product.manage_products'))

    if request.method == 'POST':
        cat_num = request.form.get('category_number', '').strip()
        name = request.form.get('product_name', '').strip()
        chars = request.form.get('characteristics', '').strip() or None

        if not cat_num or not name:
            flash("Заповніть усі обов'язкові поля!", "danger")
            conn.close()
            return render_template('product/edit.html', product=product, categories=categories)

        try:
            conn.execute('''
                UPDATE Product
                SET category_number = ?, product_name = ?, characteristics = ?
                WHERE id_product = ?
            ''', (int(cat_num), name, chars, id_product))
            conn.commit()
            flash("Товар успішно оновлено!", "success")
            return redirect(url_for('product.manage_products'))
        except Exception as e:
            conn.rollback()
            flash(f"Помилка: {str(e)}", "danger")
        finally:
            conn.close()

    conn.close()
    return render_template('product/edit.html', product=product, categories=categories)


# Вимога 3 (Manager): видалити товар
@product_bp.route('/delete/<int:id_product>', methods=['POST'])
@login_required
@roles_required('Manager')
def delete_product(id_product):
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM Product WHERE id_product = ?', (id_product,))
        conn.commit()
        flash("Товар успішно видалено!", "success")
    except Exception:
        conn.rollback()
        flash("Неможливо видалити товар, який присутній у магазині або чеках!", "danger")
    finally:
        conn.close()
    return redirect(url_for('product.manage_products'))