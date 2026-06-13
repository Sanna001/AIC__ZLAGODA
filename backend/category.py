from flask import Blueprint, render_template, request, redirect, url_for, flash
from initdb import get_db_connection
from decorators import login_required, roles_required

# Назва блюпринту тепер 'category'
category_bp = Blueprint('category', __name__, url_prefix='/category')

# Перегляд — доступно і менеджеру, і касиру
@category_bp.route('/')
@login_required
@roles_required('Manager', 'Cashier')
def list_categories():
    conn = get_db_connection()
    # Таблиця: Category
    categories = conn.execute('SELECT * FROM Category ORDER BY category_name').fetchall()
    conn.close()
    return render_template('category/list.html', categories=categories)

# Додавання — лише менеджер
@category_bp.route('/add', methods=['GET', 'POST'])
@login_required
@roles_required('Manager')
def add_category():
    if request.method == 'POST':
        name = request.form.get('category_name', '').strip()
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO Category (category_name) VALUES (?)', (name,))
            conn.commit()
            flash("Категорію додано!", "success")
            return redirect(url_for('category.list_categories'))
        except Exception as e:
            flash(f"Помилка: {str(e)}", "danger")
        finally:
            conn.close()
    return render_template('category/add.html')

# Редагування — лише менеджер
@category_bp.route('/edit/<int:category_number>', methods=['GET', 'POST'])
@login_required
@roles_required('Manager')
def edit_category(category_number):
    conn = get_db_connection()
    category = conn.execute('SELECT * FROM Category WHERE category_number = ?', (category_number,)).fetchone()
    
    if not category:
        conn.close()
        flash("Категорію не знайдено!", "danger")
        return redirect(url_for('category.list_categories'))

    if request.method == 'POST':
        name = request.form.get('category_name', '').strip()
        conn.execute('UPDATE Category SET category_name = ? WHERE category_number = ?', (name, category_number))
        conn.commit()
        conn.close()
        flash("Категорію оновлено!", "success")
        return redirect(url_for('category.list_categories'))

    conn.close()
    return render_template('category/edit.html', category=category)

# Видалення — лише менеджер
@category_bp.route('/delete/<int:category_number>', methods=['POST'])
@login_required
@roles_required('Manager')
def delete_category(category_number):
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM Category WHERE category_number = ?', (category_number,))
        conn.commit()
        flash("Категорію видалено!", "success")
    except Exception as e:
        flash(f"Помилка видалення: {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('category.list_categories'))