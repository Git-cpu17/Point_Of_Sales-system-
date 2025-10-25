from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import pyodbc
from functools import wraps

app = Flask(__name__)

# Allow requests from any origin
CORS(app)

# Database credentials (read only from environment variables)
DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_NAME = os.environ.get('DB_NAME')

# Optional: fail early if any are missing
if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
    raise RuntimeError("Database credentials are not fully set in environment variables.")

# -----------------------------
# Database connection
# -----------------------------
def get_db_connection():
    try:
        print("Attempting to connect to Azure SQL Database...")
        conn_str = (
            "Driver={ODBC Driver 18 for SQL Server};"
            f"Server=tcp:{DB_HOST},1433;"
            f"Database={DB_NAME};"
            f"Uid={DB_USER};"
            f"Pwd={DB_PASSWORD};"
            "Encrypt=yes;"
            "TrustServerCertificate=yes;"
            "Connection Timeout=30;"
        )
        conn = pyodbc.connect(conn_str)
        print("Connection successful!")
        return conn
    except Exception as e:
        print("Error while connecting to SQL Server:", e)
        raise e

# Helper to convert cursor results to list of dicts
def rows_to_dict_list(cursor):
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

# -----------------------------
# Decorator to manage DB connections
# -----------------------------
def with_db(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            return f(cursor, conn, *args, **kwargs)
        except Exception as e:
            print("DB error:", e)
            return jsonify({"message": "Database error"}), 500
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    return decorated

# -----------------------------
# Routes
# -----------------------------
@app.route('/')
@with_db
def home(cursor, conn):
    cursor.execute("SELECT * FROM product")
    products = rows_to_dict_list(cursor)

    cursor.execute("SELECT * FROM department")
    departments = rows_to_dict_list(cursor)

    return render_template('index.html', products=products, departments=departments)


@app.route("/api/status", methods=["GET"])
def status():
    return jsonify({"message": "Flask API is running and connected to Azure SQL!"})


@app.route("/products", methods=["GET"])
@with_db
def get_products(cursor, conn):
    cursor.execute("""
        SELECT product_id, name, description, price, quantity_in_stock, barcode, department_id
        FROM product WHERE hidden = 0
    """)
    rows = rows_to_dict_list(cursor)
    return jsonify(rows)


@app.route("/add", methods=["POST"])
@with_db
def add_product(cursor, conn):
    data = request.get_json() or {}
    query = """
        INSERT INTO product (name, description, price, barcode, quantity_in_stock, department_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    cursor.execute(query, (
        data.get('name'),
        data.get('description', ''),
        data.get('price', 0),
        data.get('barcode', ''),
        data.get('quantity_in_stock', 0),
        data.get('department_id')
    ))
    conn.commit()
    return jsonify({"message": "Product added successfully"}), 201


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json() or {}
        user_id = data.get('user_id')
        password = data.get('password')

        if not user_id or not password:
            return jsonify({"success": False, "message": "Missing credentials"}), 400

        @with_db
        def check_credentials(cursor, conn):
            cursor.execute("SELECT * FROM administrator WHERE username = ? AND password = ?", (user_id, password))
            admin = cursor.fetchone()

            cursor.execute("SELECT * FROM employee WHERE username = ? AND password = ?", (user_id, password))
            emp = cursor.fetchone()

            cursor.execute("SELECT * FROM customer WHERE username = ? AND password = ?", (user_id, password))
            cust = cursor.fetchone()

            if admin:
                return jsonify({"success": True, "role": "admin", "redirectUrl": "/admin"})
            elif emp:
                return jsonify({"success": True, "role": "employee", "redirectUrl": "/employee"})
            elif cust:
                return jsonify({"success": True, "role": "customer", "redirectUrl": "/customer"})
            else:
                return jsonify({"success": False, "message": "Invalid ID or Password"}), 401

        return check_credentials()

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json() or {}
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        phone = data.get('phone')
        username = data.get('username')

        if not name or not email or not password or not username:
            return jsonify({"success": False, "message": "Missing required fields"}), 400

        @with_db
        def do_register(cursor, conn):
            # Check email
            cursor.execute("SELECT * FROM customer WHERE email = ?", (email,))
            if cursor.fetchone():
                return jsonify({"success": False, "message": "Email already registered"}), 409

            # Check username
            cursor.execute("SELECT * FROM customer WHERE username = ?", (username,))
            if cursor.fetchone():
                return jsonify({"success": False, "message": "Username already taken"}), 409

            # Insert new record
            insert_query = """
                INSERT INTO customer (username, name, phone, email, password)
                VALUES (?, ?, ?, ?, ?)
            """
            cursor.execute(insert_query, (username, name, phone, email, password))
            conn.commit()
            return jsonify({"success": True, "message": "Registration successful!"}), 201

        return do_register()

    return render_template('register.html')


@app.route('/admin')
@with_db
def admin_dashboard(cursor, conn):
    cursor.execute("SELECT * FROM administrator")
    admins = rows_to_dict_list(cursor)

    cursor.execute("SELECT * FROM employee")
    employees = rows_to_dict_list(cursor)

    return render_template('admin_dashboard.html', admins=admins, employees=employees)


@app.route('/employee')
@with_db
def employee_dashboard(cursor, conn):
    cursor.execute("SELECT * FROM employee")
    employees = rows_to_dict_list(cursor)
    return render_template('employee_dashboard.html', employees=employees)


@app.route('/customer')
@with_db
def customer_dashboard(cursor, conn):
    cursor.execute("SELECT * FROM customer")
    customers = rows_to_dict_list(cursor)
    return render_template('customer_dashboard.html', customers=customers)


@app.route('/department')
@with_db
def department_dashboard(cursor, conn):
    cursor.execute("SELECT * FROM department")
    departments = rows_to_dict_list(cursor)
    return render_template('department_dashboard.html', departments=departments)


@app.route('/transactions')
@with_db
def get_transactions(cursor, conn):
    base_query = """
        SELECT t.*, e.name AS employee_name, c.name AS customer_name
        FROM transaction t
        JOIN employee e ON t.employee_id = e.employee_id
        JOIN customer c ON t.customer_id = c.customer_id
    """
    filters = []
    params = []

    if request.args.get('employee'):
        filters.append("e.name LIKE ?")
        params.append(f"%{request.args['employee']}%")
    if request.args.get('payment_method'):
        filters.append("t.payment_method = ?")
        params.append(request.args['payment_method'])

    if filters:
        base_query += " WHERE " + " AND ".join(filters)

    if request.args.get('sort_by') == 'date':
        base_query += " ORDER BY t.transaction_date DESC"
    elif request.args.get('sort_by') == 'amount':
        base_query += " ORDER BY t.total_amount DESC"

    cursor.execute(base_query, params)
    transactions = rows_to_dict_list(cursor)
    return jsonify(transactions)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
