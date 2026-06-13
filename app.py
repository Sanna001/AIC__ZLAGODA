from flask import Flask, redirect, url_for, session
from authorization import auth_bp  
from backend.category import categories_bp
app.register_blueprint(categories_bp)

app = Flask(__name__)

app.secret_key = 'zlagoda_secret_key_2026' 

app.register_blueprint(auth_bp, url_prefix='/auth')

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('auth.dashboard'))
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    app.run(debug=True)