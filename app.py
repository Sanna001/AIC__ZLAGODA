from flask import Flask, redirect, url_for, session
from authorization import auth_bp  
from backend.category import category_bp 
from backend.employees import employees_bp
from backend.product import product_bp
from backend.storeProduct import store_product_bp
from backend.CustomerCard import customer_card_bp
from backend.check import check_bp
from backend.analytics import analytics_bp

# 1. Спершу створюємо екземпляр Flask
app = Flask(__name__)
app.secret_key = 'zlagoda_secret_key_2026' 

# 2. Тепер реєструємо всі блюпринти
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(employees_bp)
app.register_blueprint(category_bp) 
app.register_blueprint(product_bp)
app.register_blueprint(store_product_bp)
app.register_blueprint(customer_card_bp)
app.register_blueprint(check_bp)
app.register_blueprint(analytics_bp)

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('auth.dashboard'))
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    app.run(debug=True)