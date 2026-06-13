from flask import Blueprint, render_template, request, redirect, url_for, flash
from initdb import get_db_connection
from decorators import login_required, roles_required

# Назва блюпринту тепер 'product'
product_bp = Blueprint('product', __name__, url_prefix='/product')

# Перегляд — усі товари, пошук за категорією та назвою
@product_bp.route('/')
@login_required
@roles_required('Manager', 'Cashier')
def list_products():
    category_id = request.args.get('category', '').strip()
    search = request.args.get('search', '').strip()

    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM Category ORDER BY category_name').fetchall()

    query = '''
        SELECT p.*, c.category_name FROM Product p
        JOIN Category c ON p.category_number = c.category_number
        WHERE 1=1
    '''
    params = []

    if category_id:
        query += ' AND p.category_number = ?'
        params.append(category_id)

    if search:
        query += ' AND LOWER(p.product_name) LIKE LOWER(?)'
        params.append(f'%{search}%')

    query += ' ORDER BY p.product_name'

    products = conn.execute(query, params).fetchall()
    conn.close()

    return render_template('product/list.html',
                           products=products,
                           categories=categories,
                           selected_category=category_id,
                           search=search)


# Додавання товару — лише менеджер
@product_bp.route('/add', methods=['GET', 'POST'])
@login_required
@roles_required('Manager')
def add_product():
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM Category ORDER BY category_name').fetchall()

    if request.method == 'POST':
        try:
            conn.execute('''
                INSERT INTO Product (id_product, category_number, product_name, characteristics)
                VALUES (?, ?, ?, ?)
            ''', (
                request.form.get('id_product'),
                request.form.get('category_number'),
                request.form.get('product_name'),
                request.form.get('characteristics') or None
            ))
            conn.commit()
            flash("Товар додано!", "success")
            return redirect(url_for('product.list_products'))
        except Exception as e:
            flash(f"Помилка: {str(e)}", "danger")
        finally:
            conn.close()
    else:
        conn.close()

    return render_template('product/add.html', categories=categories)


# Редагування товару — лише менеджер
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
        return redirect(url_for('product.list_products'))

    if request.method == 'POST':
        try:
            conn.execute('''
                UPDATE Product SET
                    category_number = ?, product_name = ?, characteristics = ?
                WHERE id_product = ?
            ''', (
                request.form.get('category_number'),
                request.form.get('product_name'),
                request.form.get('characteristics') or None,
                id_product
            ))
            conn.commit()
            flash("Товар оновлено!", "success")
            return redirect(url_for('product.list_products'))
        except Exception as e:
            flash(f"Помилка: {str(e)}", "danger")
        finally:
            conn.close()

    conn.close()
    return render_template('product/edit.html', product=product, categories=categories)


# Видалення товару — лише менеджер
@product_bp.route('/delete/<int:id_product>', methods=['POST'])
@login_required
@roles_required('Manager')
def delete_product(id_product):
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM Product WHERE id_product = ?', (id_product,))
        conn.commit()
        flash("Товар видалено!", "success")
    except Exception as e:
        flash("Неможливо видалити товар: він використовується у замовленнях або інших записах.", "danger")
    finally:
        conn.close()
    return redirect(url_for('product.list_products'))