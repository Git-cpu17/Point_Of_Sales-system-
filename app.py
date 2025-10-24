from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_cors import CORS
import os
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)

# Allow only your GitHub Pages origin
CORS(app, resources={r"/*": {"origins": "https://git-cpu17.github.io"}})

# Read DB credentials from environment variables (recommended)
DB_HOST = os.environ.get('DB_HOST', 'posapp.mysql.database.azure.com')
DB_USER = os.environ.get('DB_USER', 'CloudSA0d30306e')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'Azure123456*')
DB_NAME = os.environ.get('DB_NAME', 'PosApp')

def get_db_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

# -----------------------------
# Routes (API + server-rendered)
# -----------------------------
@app.route('/')
def home():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM product")
        products = cursor.fetchall()

        cursor.execute("SELECT * FROM department")
        departments = cursor.fetchall()
    except Error as e:
        print("DB error:", e)
        products, departments = [], []
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

    return render_template('index.html', products=products, departments=departments)

@app.route("/api/status", methods=["GET"])
def status():
    return jsonify({"message": "Flask API is running on Azure!"})

# JSON API endpoint matching the frontend's expectation
@app.route("/products", methods=["GET"])
def get_products():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT product_id, name, description, price, quantity_in_stock, barcode, department_id FROM product WHERE hidden = FALSE")
        rows = cursor.fetchall()
        return jsonify(rows)
    except Error as e:
        print("DB error:", e)
        return jsonify([]), 500
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

@app.route("/add", methods=["POST"])
def add_product():
    data = request.get_json() or {}
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO product (name, description, price, barcode, quantity_in_stock, department_id)
            VALUES (%s, %s, %s, %s, %s, %s)
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
    except Error as e:
        print("DB error:", e)
        return jsonify({"message": "DB error"}), 500
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

# Login: accept JSON POST (suitable for your JS client)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json() or {}
        user_id = data.get('user_id')
        password = data.get('password')
        if not user_id or not password:
            return jsonify({"success": False, "message": "Missing credentials"}), 400

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT * FROM administrator WHERE username = %s AND password = %s", (user_id, password))
            admin = cursor.fetchone()

            cursor.execute("SELECT * FROM employee WHERE username = %s AND password = %s", (user_id, password))
            emp = cursor.fetchone()

            cursor.execute("SELECT * FROM customer WHERE email = %s AND password = %s", (user_id, password))
            cust = cursor.fetchone()

            if admin:
                return jsonify({"success": True, "role": "admin", "redirectUrl": "/admin"})
            elif emp:
                return jsonify({"success": True, "role": "employee", "redirectUrl": "/employee"})
            elif cust:
                return jsonify({"success": True, "role": "customer", "redirectUrl": "/customer"})
            else:
                return jsonify({"success": False, "message": "Invalid ID or Password"}), 401
        except Error as e:
            print("DB error:", e)
            return jsonify({"success": False, "message": "Server error"}), 500
        finally:
            try:
                cursor.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass

    # GET: render login page for browsers visiting the login URL
    return render_template('login.html')

@app.route('/admin')
def admin_dashboard():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM administrator")
        admins = cursor.fetchall()

        cursor.execute("SELECT * FROM employee")
        employees = cursor.fetchall()
    except Error as e:
        print("DB error:", e)
        admins, employees = [], []
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

    return render_template('admin_dashboard.html', admins=admins, employees=employees)

@app.route('/employee')
def employee_dashboard():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM employee")
        employees = cursor.fetchall()
    except Error as e:
        print("DB error:", e)
        employees = []
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

    return render_template('employee_dashboard.html', employees=employees)

@app.route('/customer')
def customer_dashboard():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM customer")
        customers = cursor.fetchall()
    except Error as e:
        print("DB error:", e)
        customers = []
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

    return render_template('customer_dashboard.html', customers=customers)

@app.route('/department')
def department_dashboard():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM department")
        departments = cursor.fetchall()
    except Error as e:
        print("DB error:", e)
        departments = []
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

    return render_template('department_dashboard.html', departments=departments)

@app.route('/transactions')
def get_transactions():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        base_query = """
            SELECT t.*, e.name AS employee_name, c.name AS customer_name
            FROM transaction t
            JOIN employee e ON t.employee_id = e.employee_id
            JOIN customer c ON t.customer_id = c.customer_id
        """
        filters = []
        params = []

        if request.args.get('employee'):
            filters.append("e.name LIKE %s")
            params.append(f"%{request.args['employee']}%")
        if request.args.get('payment_method'):
            filters.append("t.payment_method = %s")
            params.append(request.args['payment_method'])

        if filters:
            base_query += " WHERE " + " AND ".join(filters)

        if request.args.get('sort_by') == 'date':
            base_query += " ORDER BY t.transaction_date DESC"
        elif request.args.get('sort_by') == 'amount':
            base_query += " ORDER BY t.total_amount DESC"

        cursor.execute(base_query, params)
        transactions = cursor.fetchall()
        return jsonify(transactions)
    except Error as e:
        print("DB error:", e)
        return jsonify([]), 500
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Azure injects PORT dynamically
    app.run(host='0.0.0.0', port=port)
