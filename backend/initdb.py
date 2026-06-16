import sqlite3
import os
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '..', 'zlagoda.db')


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def setup_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # підтримку Foreign Keys в SQLite
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Категорії
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Category(
        category_number INTEGER PRIMARY KEY AUTOINCREMENT,
        category_name TEXT NOT NULL 
    );
    ''')

    # Товари
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Product(
        id_product INTEGER PRIMARY KEY,
        category_number INTEGER NOT NULL,
        product_name TEXT NOT NULL, 
        characteristics TEXT,
        FOREIGN KEY (category_number) REFERENCES Category(category_number)
            ON UPDATE CASCADE ON DELETE NO ACTION
    );
    ''')

    # Працівники
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Employee(
        id_employee TEXT PRIMARY KEY,
        empl_surname TEXT NOT NULL,
        empl_name TEXT NOT NULL,
        empl_patronymic TEXT,
        empl_role TEXT NOT NULL, 
        salary REAL NOT NULL CHECK(salary >= 0),
        date_of_birth TEXT NOT NULL,
        date_of_start TEXT NOT NULL,
        phone_number TEXT NOT NULL CHECK(length(phone_number) <= 13),
        city TEXT NOT NULL,
        street TEXT NOT NULL,
        zip_code TEXT NOT NULL,
        password_hash TEXT NOT NULL
    );
    ''')

    # Картки клієнтів 
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Customer_Card(
        card_number TEXT PRIMARY KEY,
        cust_surname TEXT NOT NULL,
        cust_name TEXT NOT NULL,
        cust_patronymic TEXT,
        phone_number TEXT NOT NULL CHECK(length(phone_number) <= 13),
        city TEXT,
        street TEXT,
        zip_code TEXT,
        percent INTEGER NOT NULL CHECK(percent >= 0 AND percent <= 100)
    );
    ''')

    # Чеки 
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Check_bill(
        check_number TEXT PRIMARY KEY,
        id_employee TEXT NOT NULL,
        card_number TEXT, 
        print_date TEXT NOT NULL,
        sum_total REAL NOT NULL CHECK(sum_total >= 0),
        vat REAL NOT NULL CHECK(vat >= 0),
        FOREIGN KEY (id_employee) REFERENCES Employee(id_employee)
            ON UPDATE CASCADE ON DELETE NO ACTION,
        FOREIGN KEY (card_number) REFERENCES Customer_Card(card_number)
            ON UPDATE CASCADE ON DELETE NO ACTION
    );
    ''')

    # 6. Товари у магазині
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Store_Product(
        UPC TEXT PRIMARY KEY,
        UPC_prom TEXT,
        id_product INTEGER NOT NULL,
        selling_price REAL NOT NULL CHECK(selling_price >= 0),
        products_number INTEGER NOT NULL CHECK(products_number >= 0),
        promotional_product INTEGER NOT NULL CHECK(promotional_product IN (0, 1)),
        FOREIGN KEY (UPC_prom) REFERENCES Store_Product(UPC)
            ON UPDATE CASCADE ON DELETE SET NULL,
        FOREIGN KEY (id_product) REFERENCES Product(id_product)
            ON UPDATE CASCADE ON DELETE NO ACTION
    );
    ''')

    # 7. Продажі
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Sale(
        UPC TEXT NOT NULL,
        check_number TEXT NOT NULL,
        product_number INTEGER NOT NULL CHECK(product_number > 0),
        selling_price REAL NOT NULL CHECK(selling_price >= 0),
        PRIMARY KEY (UPC, check_number), 
        FOREIGN KEY (UPC) REFERENCES Store_Product(UPC)
            ON UPDATE CASCADE ON DELETE NO ACTION,
        FOREIGN KEY (check_number) REFERENCES Check_bill(check_number)
            ON UPDATE CASCADE ON DELETE CASCADE
    );
    ''')

    
    manager_password = generate_password_hash("boss_zlagoda")  
    cashier_password = generate_password_hash("cashier_pass")

    cursor.execute("INSERT INTO Category VALUES (1, 'Beverages')")
    cursor.execute("INSERT INTO Category VALUES (2, 'Fruits')")
    cursor.execute("INSERT INTO Category VALUES (3, 'Vegetables')")
    cursor.execute("INSERT INTO Category VALUES (4, 'Dairy')")
    cursor.execute("INSERT INTO Category VALUES (5, 'Bakery')")
    cursor.execute("INSERT INTO Category VALUES (6, 'Sweets')")


    cursor.execute("INSERT INTO Product VALUES (1001, 1, 'Pepsi zero', 'Pepsi without sugar 500ml')")
    cursor.execute("INSERT INTO Product VALUES (1002, 2, 'Dragon-fruit', 'Sweet')")
    cursor.execute("INSERT INTO Product VALUES (1003, 3, 'Baby-carrot', 'baby carrot big pack 700g')")
    cursor.execute("INSERT INTO Product VALUES (1004, 4, 'Mozzarella', 'italian')")
    cursor.execute("INSERT INTO Product VALUES (1005, 5, 'Сroissant', 'with almond cream')")
    cursor.execute("INSERT INTO Product VALUES (1006, 5, 'Сroissant', 'with strawberry jam')")
    cursor.execute("INSERT INTO Product VALUES (1007, 6, 'Lollipop', 'big pepsi-flavored with gum inside')")
    cursor.execute("INSERT INTO Product VALUES (1008, 4, 'Milk', 'lactose-free, 1 liter')")
    cursor.execute("INSERT INTO Product VALUES (1009, 1, 'Orange Juice', 'orange fresh juice without sugar, 1 liter')")
    cursor.execute("INSERT INTO Product VALUES (1010, 6, 'Chocolate bar', 'sweet, cocoa-based, can be milk')")
    cursor.execute("INSERT INTO Product VALUES (1011, 6, 'Marshmallow', 'big, pink, 100g')")
    cursor.execute("INSERT INTO Product VALUES (1012, 2, 'Avocado', 'big')")
    cursor.execute("INSERT INTO Product VALUES (1013, 1, 'Herbal tea', 'cold, caffeine-free, 500ml')")

    cursor.execute("INSERT INTO Employee VALUES ('E100', 'Gevalo', 'Liza', 'Romanivna', 'Manager', 45000, '2000-09-09', '2024-10-01', '+380973349688', 'Kyiv', 'Johna McCana 31a', '31045', ?)", (manager_password,))
    cursor.execute("INSERT INTO Employee VALUES ('E101', 'Vus', 'Sofia', 'Oleksiivna', 'Cashier', 20000, '1999-06-02', '2025-05-12', '+380975550310', 'Kyiv', 'Velyka Vasylkivska 67', '31065', ?)", (cashier_password,))
    cursor.execute("INSERT INTO Employee VALUES ('E102', 'Bybis', 'Pavlo', 'Oleksandrovich', 'Cashier', 20000, '1998-01-09', '2025-03-12', '+380981237088', 'Kyiv', 'Velyka Vasylkivska 12', '31065', ?)", (cashier_password,))
   
    cursor.execute("INSERT INTO Customer_Card VALUES ('CC100', 'Afanasieva', 'Maria', 'Mykolaivna', '+380970543673', 'Kyiv', 'Tarasa Shevchenka 12B', '31021', 5)")
    cursor.execute("INSERT INTO Customer_Card VALUES ('CC101', 'Pavelko', 'Olha', 'Ivanivna', '+380665445123', 'Kyiv', 'Ioana Pavla2 11', '31034', 10)")

    cursor.execute("INSERT INTO Check_bill VALUES ('CH1000', 'E101', 'CC100', '2026-06-11', 103.2, 17.2)")
    cursor.execute("INSERT INTO Check_bill VALUES ('CH1001', 'E101', 'CC101', '2026-06-12', 294, 49)")

    cursor.execute("INSERT INTO Store_Product VALUES ('UPC0001', NULL, 1001, 43, 12, 0)")
    cursor.execute("INSERT INTO Store_Product VALUES ('UPC0002', NULL, 1002, 150, 15, 0)")
    cursor.execute("INSERT INTO Store_Product VALUES ('UPC0003', NULL, 1003, 95, 30, 0)")

    cursor.execute("INSERT INTO Sale VALUES ('UPC0001', 'CH1000', 2, 43)")
    cursor.execute("INSERT INTO Sale VALUES ('UPC0002', 'CH1001', 1, 150)")
    cursor.execute("INSERT INTO Sale VALUES ('UPC0003', 'CH1001', 1, 95)")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    setup_database()