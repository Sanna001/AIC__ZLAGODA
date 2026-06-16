from flask import Blueprint, render_template, request, redirect, url_for, flash
from initdb import get_db_connection
from decorators import login_required, roles_required

store_product_bp = Blueprint('store_product', __name__, url_prefix='/store_product')

@store_product_bp.route('/')
@login_required
@roles_required('Manager', 'Cashier')
def list_store_products():
    promo_filter = request.args.get('promo', '').strip()  
    sort_by = request.args.get('sort', 'name')

    if promo_filter == '1':
        page_title = "Promotional Products in Store"
    elif promo_filter == '0':
        page_title = "Regular Products in Store"
    else:
        page_title = "All Products in Store"

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
                           sort_by=sort_by,
                           page_title=page_title) 


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
    title = "Promotional Products" if is_promo == 1 else "Regular Products"
    return render_template('store_product/promotional.html',
                           products=products,
                           is_promo=bool(is_promo),
                           sort_by=sort_by,
                           page_title=title)


# Пошук за UPC
@store_product_bp.route('/search_upc', methods=['GET'])
@login_required
@roles_required('Manager', 'Cashier')
def search_by_upc():
    # Отримуємо код UPC з параметрів GET-запиту форми
    upc = request.args.get('upc', '').strip()
    product = None

    if upc:
        conn = get_db_connection()
        try:
            # Запит шукає товар на полиці (Store_Product) та підтягує його назву й характеристики з таблиці Product
            query = '''
                SELECT sp.UPC, sp.selling_price, sp.products_number, sp.promotional_product,
                       p.product_name, p.characteristics
                FROM Store_Product sp
                JOIN Product p ON sp.id_product = p.id_product
                WHERE sp.UPC = ?
            '''
            product = conn.execute(query, (upc,)).fetchone()
        except Exception as e:
            flash(f"Database error: {str(e)}", "danger")
        finally:
            conn.close()
    return render_template('store_product/sesrch_upc.html', product=product, upc=upc)

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
        flash("Product not found!", "danger")
        return redirect(url_for('store_product.list_store_products'))

    if request.method == 'POST':
        try:
            form_price = float(request.form.get('selling_price', 0))
            products_number = int(request.form.get('products_number', 0))
            new_is_promo = int(request.form.get('promotional_product', 0))
            new_upc_prom = request.form.get('UPC_prom', '').strip() or None
            
            # --- ВИПРАВЛЕННЯ: Перевірка існування UPC_prom ---
            if new_upc_prom:
                check_exists = conn.execute('SELECT 1 FROM Store_Product WHERE UPC = ?', (new_upc_prom,)).fetchone()
                if not check_exists:
                    raise ValueError(f"Linked UPC '{new_upc_prom}' does not exist in the store!")
            
            old_is_promo = store_product['promotional_product']
            final_price = form_price
            
            if old_is_promo == 0 and new_is_promo == 1:
                final_price = round(form_price * 0.8, 2)
            elif old_is_promo == 1 and new_is_promo == 0:
                final_price = round(form_price / 0.8, 2)

            cursor = conn.cursor()
            cursor.execute('''
                UPDATE Store_Product SET UPC_prom = ?, id_product = ?, selling_price = ?,
                    products_number = ?, promotional_product = ? WHERE UPC = ?
            ''', (new_upc_prom, request.form.get('id_product'), final_price, products_number, new_is_promo, upc))

            # ... далі ваш код оновлення цін ...
            conn.commit()
            flash("Product updated successfully!", "success")
            return redirect(url_for('store_product.list_store_products'))
            
        except ValueError as ve:
            flash(str(ve), "danger") # Покаже помилку користувачу, замість падіння БД
        except Exception as e:
            conn.rollback()
            flash(f"Database error: {str(e)}", "danger")
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
        flash("Product deleted successfully!", "success")
    except Exception as e:
        flash("Cannot delete: product is present in checks.", "danger")
    finally:
        conn.close()
    return redirect(url_for('store_product.list_store_products'))


# Додавання товару на полицю
@store_product_bp.route('/add', methods=['GET', 'POST'])
@login_required
@roles_required('Manager')
def add_store_product():
    conn = get_db_connection()
    
    # Отримуємо список товарів для вибору в формі
    products = conn.execute('SELECT * FROM Product ORDER BY product_name').fetchall()
    
    # Генерація наступного UPC (якщо база не порожня)
    last_product = conn.execute("SELECT UPC FROM Store_Product ORDER BY UPC DESC LIMIT 1").fetchone()
    if last_product:
        try:
            last_num = int(last_product['UPC'][3:])
            new_upc = f"UPC{last_num + 1:04d}"
        except (ValueError, IndexError):
            new_upc = "UPC0001"
    else:
        new_upc = "UPC0001"

    if request.method == 'POST':
        try:
            upc = request.form.get('UPC', '').strip() 
            id_product = request.form.get('id_product')
            selling_price = float(request.form.get('selling_price', 0))
            products_number = int(request.form.get('products_number', 0))
            is_promo = int(request.form.get('promotional_product', 0))
            
            if not id_product:
                raise ValueError("Product ID is required!")
            if products_number <= 0:
                raise ValueError("Quantity must be greater than 0!")
            if selling_price < 0:
                raise ValueError("Price cannot be negative!")

            exists = conn.execute('SELECT 1 FROM Product WHERE id_product = ?', (id_product,)).fetchone()
            if not exists:
                raise ValueError("Selected product does not exist in the catalog!")

            exists_upc = conn.execute('SELECT 1 FROM Store_Product WHERE UPC = ?', (upc,)).fetchone()
            if exists_upc:
                raise ValueError(f"Product with UPC '{upc}' already exists!")

            if is_promo == 1:
                selling_price = round(selling_price * 0.8, 2)
            
            conn.execute('''
                INSERT INTO Store_Product (UPC, id_product, selling_price, products_number, promotional_product) 
                VALUES (?, ?, ?, ?, ?)
            ''', (upc, id_product, selling_price, products_number, is_promo))
            
            conn.commit()
            flash("Product added to shelf successfully!", "success")
            return redirect(url_for('store_product.list_store_products'))
            
        except ValueError as ve:
            flash(str(ve), "danger")
        except Exception as e:
            conn.rollback()
            flash(f"Database error: {str(e)}", "danger")
        finally:
            conn.close()
            
    conn.close() 
    return render_template('store_product/add.html', products=products, new_upc=new_upc)