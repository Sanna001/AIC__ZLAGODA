from flask import Blueprint, render_template, request, redirect, url_for, flash
from backend.initdb import get_db_connection
from decorators import login_required, roles_required

category_bp = Blueprint('category', __name__, url_prefix='/category')


# Вимога 8 (Manager): усі категорії за назвою
# Доступно і менеджеру, і касиру
@category_bp.route('/')
@login_required
@roles_required('Manager', 'Cashier')
def list_categories():
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM Category ORDER BY category_name').fetchall()
    conn.close()
    return render_template('category/list.html', categories=categories)


# Вимога 1 (Manager): додати категорію
@category_bp.route('/add', methods=['GET', 'POST'])
@login_required
@roles_required('Manager')
def add_category():
    if request.method == 'POST':
        name = request.form.get('category_name', '').strip()
        if not name:
            flash("Назва категорії не може бути порожньою!", "danger")
            return render_template('category/add.html')

        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO Category (category_name) VALUES (?)', (name,))
            conn.commit()
            flash("Категорію успішно додано!", "success")
            return redirect(url_for('category.list_categories'))
        except Exception as e:
            flash(f"Помилка: {str(e)}", "danger")
        finally:
            conn.close()

    return render_template('category/add.html')


# Вимога 2 (Manager): редагувати категорію
@category_bp.route('/edit/<int:category_number>', methods=['GET', 'POST'])
@login_required
@roles_required('Manager')
def edit_category(category_number):
    conn = get_db_connection()
    category = conn.execute(
        'SELECT * FROM Category WHERE category_number = ?', (category_number,)
    ).fetchone()

    if not category:
        conn.close()
        flash("Категорію не знайдено!", "danger")
        return redirect(url_for('category.list_categories'))

    if request.method == 'POST':
        name = request.form.get('category_name', '').strip()
        if not name:
            flash("Назва категорії не може бути порожньою!", "danger")
            conn.close()
            return render_template('category/edit.html', category=category)
        try:
            conn.execute(
                'UPDATE Category SET category_name = ? WHERE category_number = ?',
                (name, category_number)
            )
            conn.commit()
            flash("Категорію успішно оновлено!", "success")
            return redirect(url_for('category.list_categories'))
        except Exception as e:
            flash(f"Помилка: {str(e)}", "danger")
        finally:
            conn.close()

    conn.close()
    return render_template('category/edit.html', category=category)


# Вимога 3 (Manager): видалити категорію
@category_bp.route('/delete/<int:category_number>', methods=['POST'])
@login_required
@roles_required('Manager')
def delete_category(category_number):
    conn = get_db_connection()
    try:
        # Спочатку видаляємо всі товари, що належать цій категорії
        conn.execute('DELETE FROM Product WHERE category_number = ?', (category_number,))
        # Тепер видаляємо саму категорію
        conn.execute('DELETE FROM Category WHERE category_number = ?', (category_number,))
        conn.commit()
        flash("Категорію та всі пов'язані з нею товари успішно видалено!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Помилка при видаленні: {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('category.list_categories'))