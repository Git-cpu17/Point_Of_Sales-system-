from flask import Flask, render_template, request, redirect, url_for
from config import Config
import os
import mysql.connector

app = Flask(__name__)
CORS(app, origins=["https://git-cpu17.github.io"])  # Allows frontend from GitHub Pages to call this API

# Connect to Azure MySQL
db = mysql.connector.connect(
    host="posapp.mysql.database.azure.com",
    user="CloudSA0d30306e",
    password="Azure123456*",
    database="PosApp"
)

# Reflect tables if they already exist in Azure MySQL
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print("Database connection issue:", e)


# -----------------------------
# Routes
# -----------------------------
@app.route('/')
def home():
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM product")
    products = cursor.fetchall()

    cursor.execute("SELECT * FROM department")
    departments = cursor.fetchall()

    return render_template('index.html', products=products, departments=departments)

@app.route("/api/status", methods=["GET"])
def status():
    return jsonify({"message": "Flask API is running on Azure!"})

#---
#debug
  

@app.route("/api/products", methods=["GET"])
def get_products():
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT product_id, name, description, price, quantity_in_stock, barcode, department_id FROM product WHERE hidden = FALSE")
    rows = cursor.fetchall()
    return jsonify(rows)

@app.route("/api/add", methods=["POST"])
def add_product():
    data = request.json
    cursor = db.cursor()
    query = """
        INSERT INTO product (name, description, price, barcode, quantity_in_stock, department_id)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    cursor.execute(query, (
        data['name'],
        data.get('description', ''),
        data['price'],
        data.get('barcode', ''),
        data.get('quantity_in_stock', 0),
        data.get('department_id')
    ))
    db.commit()
    return jsonify({"message": "Product added successfully"}), 201



#------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form['user_id']
        password = request.form['password']
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM administrator WHERE username = %s AND password = %s", (user_id, password))
        admin = cursor.fetchone()

        cursor.execute("SELECT * FROM employee WHERE username = %s AND password = %s", (user_id, password))
        emp = cursor.fetchone()

        cursor.execute("SELECT * FROM customer WHERE email = %s AND password = %s", (user_id, password))
        cust = cursor.fetchone()

        if admin:
            return redirect(url_for('admin_dashboard'))
        elif emp:
            return redirect(url_for('employee_dashboard'))
        elif cust:
            return redirect(url_for('customer_dashboard'))
        else:
            return render_template('login.html', error='Invalid ID or Password')
    return render_template('login.html')
@app.route('/admin')
def admin_dashboard():
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM administrator")
    admins = cursor.fetchall()

    cursor.execute("SELECT * FROM employee")
    employees = cursor.fetchall()

    return render_template('admin_dashboard.html', admins=admins, employees=employees)
@app.route('/employee')
def employee_dashboard():
    employees = Employee.query.all()
    return render_template('employee_dashboard.html', employees=employees)

@app.route('/customer')
def customer_dashboard():
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM customer")
    customers = cursor.fetchall()
    return render_template('customer_dashboard.html', customers=customers)
@app.route('/department')
def department_dashboard():
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM employee")
    employees = cursor.fetchall()
    return render_template('employee_dashboard.html', employees=employees)
@app.route('/transactions')
def get_transactions():
    cursor = db.cursor(dictionary=True)
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

    transactions = query.all()
    return jsonify([tx.to_dict() for tx in transactions])


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Azure injects PORT dynamically
    app.run(host='0.0.0.0', port=port)
    
