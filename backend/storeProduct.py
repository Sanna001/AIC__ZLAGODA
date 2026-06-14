from flask import Blueprint, render_template, request, redirect, url_for, flash
from initdb import get_db_connection
from decorators import login_required, roles_required

# Назва блюпринту та префікс
store_product_bp = Blueprint('store_product', __name__, url_prefix='/store_product')


# Перегляд товарів у магазині
@store_product_bp.route('/')
@login_required
@roles_required('Manager', 'Cashier')
def list_store_products():
    promo_filter = request.args.get('promo', '').strip()  # '0', '1' або ''
    sort_by = request.args.get('sort', 'name')

    sort_map = {
        'name': 'p.product_name',
        'quantity': 'sp.products_number'
    }
    order = sort_map.get(sort_by, 'p.product_name')

    query = f'''
        SELECT sp.UPC, sp.UPC_prom, p.product_name, p.characteristics,
               sp.selling_price, sp.products_number, sp.promotional_product
        FROM Store_Product sp
        JOIN Product p ON sp.id_product = p.id_product
        WHERE 1=1
    '''
    params = []

    if promo_filter in ('0', '1'):
        query += ' AND sp.promotional_product = ?'
        params.append(int(promo_filter))

    query += f' ORDER BY {order}'

    conn = get_db_connection()
    store_products = conn.execute(query, params).fetchall()
    conn.close()

    return render_template('store_product/list.html',
                           store_products=store_products,
                           promo_filter=promo_filter,
                           sort_by=sort_by)


# Пошук товарів
@store_product_bp.route('/search')
@login_required
@roles_required('Manager', 'Cashier')
def search_products():
    search = request.args.get('search', '').strip()
    category_id = request.args.get('category', '').strip()

    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM Category ORDER BY category_name').fetchall()

    query = '''
        SELECT sp.UPC, p.product_name, p.characteristics,
               sp.selling_price, sp.products_number,
               sp.promotional_product, c.category_name
        FROM Store_Product sp
        JOIN Product p ON sp.id_product = p.id_product
        JOIN Category c ON p.category_number = c.category_number
        WHERE 1=1
    '''
    params = []

    if search:
        query += ' AND LOWER(p.product_name) LIKE LOWER(?)'
        params.append(f'%{search}%')

    if category_id:
        query += ' AND p.category_number = ?'
        params.append(category_id)

    query += ' ORDER BY p.product_name'

    products = conn.execute(query, params).fetchall()
    conn.close()

    return render_template('store_product/search.html',
                           products=products,
                           categories=categories,
                           search=search,
                           selected_category=category_id)


# Акційні товари
@store_product_bp.route('/promotional')
@login_required
@roles_required('Manager', 'Cashier')
def view_promotional():
    return _promo_view(is_promo=1)


# Неакційні товари
@store_product_bp.route('/non_promotional')
@login_required
@roles_required('Manager', 'Cashier')
def view_non_promotional():
    return _promo_view(is_promo=0)


def _promo_view(is_promo):
    sort_by = request.args.get('sort', 'name')
    sort_map = {'name': 'p.product_name', 'quantity': 'sp.products_number'}
    order = sort_map.get(sort_by, 'p.product_name')

    conn = get_db_connection()
    products = conn.execute(f'''
        SELECT sp.UPC, p.product_name, sp.selling_price, sp.products_number
        FROM Store_Product sp
        JOIN Product p ON sp.id_product = p.id_product
        WHERE sp.promotional_product = ?
        ORDER BY {order}
    ''', (is_promo,)).fetchall()
    conn.close()

    return render_template('store_product/promotional.html',
                           products=products,
                           is_promo=bool(is_promo),
                           sort_by=sort_by)


# Пошук за UPC
@store_product_bp.route('/search_upc')
@login_required
@roles_required('Manager', 'Cashier')
def search_by_upc():
    upc = request.args.get('upc', '').strip()
    product = None
    if upc:
        conn = get_db_connection()
        product = conn.execute('''
            SELECT sp.UPC, p.product_name, p.characteristics,
                   sp.selling_price, sp.products_number, sp.promotional_product
            FROM Store_Product sp
            JOIN Product p ON sp.id_product = p.id_product
            WHERE sp.UPC = ?
        ''', (upc,)).fetchone()
        conn.close()
        if not product:
            flash(f"Товар з UPC '{upc}' не знайдено!", "warning")
    return render_template('store_product/search_upc.html', product=product, upc=upc)


# Додати товар у магазин
@store_product_bp.route('/add', methods=['GET', 'POST'])
@login_required
@roles_required('Manager')
def add_store_product():
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM Product ORDER BY product_name').fetchall()
    if request.method == 'POST':
        try:
            selling_price = float(request.form.get('selling_price', 0))
            products_number = int(request.form.get('products_number', 0))
            if selling_price < 0 or products_number < 0:
                raise ValueError("Значення не можуть бути від'ємними")
            
            conn.execute('INSERT INTO Store_Product VALUES (?, ?, ?, ?, ?, ?)', (
                request.form.get('UPC'), request.form.get('UPC_prom'),
                request.form.get('id_product'), selling_price,
                products_number, int(request.form.get('promotional_product', 0))
            ))
            conn.commit()
            flash("Товар у магазині додано!", "success")
            return redirect(url_for('store_product.list_store_products'))
        except Exception as e:
            flash(f"Помилка: {str(e)}", "danger")
        finally:
            conn.close()
    conn.close()
    return render_template('store_product/add.html', products=products)


# Редагувати товар у магазині
@store_product_bp.route('/edit/<upc>', methods=['GET', 'POST'])
@login_required
@roles_required('Manager')
def edit_store_product(upc):
    conn = get_db_connection()
    store_product = conn.execute('SELECT * FROM Store_Product WHERE UPC = ?', (upc,)).fetchone()
    products = conn.execute('SELECT * FROM Product ORDER BY product_name').fetchall()

    if not store_product:
        conn.close()
        flash("Товар не знайдено!", "danger")
        return redirect(url_for('store_product.list_store_products'))

    if request.method == 'POST':
        try:
            selling_price = float(request.form.get('selling_price', 0))
            products_number = int(request.form.get('products_number', 0))
            is_promo = int(request.form.get('promotional_product', 0))
            new_upc_prom = request.form.get('UPC_prom') or None
            
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE Store_Product SET UPC_prom = ?, id_product = ?, selling_price = ?,
                    products_number = ?, promotional_product = ? WHERE UPC = ?
            ''', (new_upc_prom, request.form.get('id_product'), selling_price, products_number, is_promo, upc))

            if new_upc_prom:
                linked = cursor.execute('SELECT promotional_product FROM Store_Product WHERE UPC = ?', (new_upc_prom,)).fetchone()
                if linked:
                    price_update = round(selling_price * 0.8, 2) if is_promo == 0 else round(selling_price / 0.8, 2)
                    cursor.execute('UPDATE Store_Product SET selling_price = ? WHERE UPC = ?', (price_update, new_upc_prom))

            conn.commit()
            flash("Товар оновлено!", "success")
            return redirect(url_for('store_product.list_store_products'))
        except Exception as e:
            conn.rollback()
            flash(f"Помилка: {str(e)}", "danger")
        finally:
            conn.close()
    conn.close()
    return render_template('store_product/edit.html', store_product=store_product, products=products)


# Видалення
@store_product_bp.route('/delete/<upc>', methods=['POST'])
@login_required
@roles_required('Manager')
def delete_store_product(upc):
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM Store_Product WHERE UPC = ?', (upc,))
        conn.commit()
        flash("Товар видалено!", "success")
    except Exception as e:
        flash("Неможливо видалити: товар присутній у чеках.", "danger")
    finally:
        conn.close()
    return redirect(url_for('store_product.list_store_products'))


@store_product_bp.route('/add', methods=['GET', 'POST'])
@login_required
@roles_required('Manager')
def add_store_product():
    conn = get_db_connection()
    # Отримуємо тільки ті товари, які вже є в каталозі
    products = conn.execute('SELECT * FROM Product ORDER BY product_name').fetchall()
    
    if request.method == 'POST':
        try:
            id_product = request.form.get('id_product')
            selling_price = float(request.form.get('selling_price', 0))
            products_number = int(request.form.get('products_number', 0))
            
            # ВАЛИДАЦІЯ: товар не може мати кількість 0 на полиці
            if products_number <= 0:
                raise ValueError("Кількість товару на полиці має бути більшою за 0!")
            
            # Перевірка: чи існує такий ID в таблиці Product
            exists = conn.execute('SELECT 1 FROM Product WHERE id_product = ?', (id_product,)).fetchone()
            if not exists:
                raise ValueError("Вибраний товар не існує в основному каталозі!")

            conn.execute('INSERT INTO Store_Product (UPC, id_product, selling_price, products_number, promotional_product) VALUES (?, ?, ?, ?, ?)', 
                         (request.form.get('UPC'), id_product, selling_price, products_number, int(request.form.get('promotional_product', 0))))
            
            conn.commit()
            flash("Товар успішно виставлено на полицю!", "success")
            return redirect(url_for('store_product.list_store_products'))
        except Exception as e:
            flash(f"Помилка: {str(e)}", "danger")
        finally:
            conn.close()
            
    return render_template('store_product/add.html', products=products)