from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
import os
import pyodbc
from functools import wraps

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get('SECRET_KEY')

# Database credentials
DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_NAME = os.environ.get('DB_NAME')

if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
    raise RuntimeError("Database credentials are not fully set in environment variables.")

# -----------------------------
# Database connection
# -----------------------------
def get_db_connection():
    try:
        print(f"Attempting to connect to DB at {DB_HOST}...")
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
        print(f"Error while connecting to SQL Server: {str(e)}")
        return None

def rows_to_dict_list(cursor):
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

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
    cursor.execute("SELECT * FROM Product")
    products = rows_to_dict_list(cursor)
    cursor.execute("SELECT * FROM Department")
    departments = rows_to_dict_list(cursor)

    user = None
    role = session.get('role')

    if role == 'customer':
        cursor.execute("SELECT Name FROM Customer WHERE CustomerID = ?", (session['user_id'],))
        record = cursor.fetchone()
        if record:
            user = {'Name': record[0], 'role': 'customer'}

    elif role == 'admin':
        cursor.execute("SELECT Name FROM Administrator WHERE AdminID = ?", (session['user_id'],))
        record = cursor.fetchone()
        if record:
            user = {'Name': record[0], 'role': 'admin'}

    elif role == 'employee':
        cursor.execute("SELECT Name FROM Employee WHERE EmployeeID = ?", (session['user_id'],))
        record = cursor.fetchone()
        if record:
            user = {'Name': record[0], 'role': 'employee'}

    return render_template('index.html', products=products, departments=departments, user=user)

@app.route("/api/status", methods=["GET"])
def status():
    return jsonify({"message": "Flask API is running and connected to Azure SQL!"})

@app.route("/products", methods=["GET"])
@with_db
def get_products(cursor, conn):
    cursor.execute("""
        SELECT ProductID, Name, Description, Price, QuantityInStock, Barcode, DepartmentID
        FROM Product
    """)
    rows = rows_to_dict_list(cursor)
    return jsonify(rows)

@app.route("/add", methods=["POST"])
@with_db
def add_product(cursor, conn):
    data = request.get_json() or {}
    query = """
        INSERT INTO Product (Name, Description, Price, Barcode, QuantityInStock, DepartmentID)
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
        data = request.get_json(silent=True) or request.form or {}
        user_id = data.get('user_id') or data.get('username') or ''
        password = data.get('password') or ''

        if not user_id or not password:
            return jsonify({"success": False, "message": "Missing credentials"}), 400

        @with_db
        def check_credentials(cursor, conn):
            cursor.execute("SELECT * FROM Administrator WHERE Username = ? AND Password = ?", (user_id, password))
            admin = cursor.fetchone()

            cursor.execute("SELECT * FROM Employee WHERE Username = ? AND Password = ?", (user_id, password))
            emp = cursor.fetchone()

            cursor.execute("SELECT * FROM Customer WHERE username = ? AND password = ?", (user_id, password))
            cust = cursor.fetchone()

            if admin:
                session['user_id'] = admin[0]
                session['role'] = 'admin'
                return jsonify({"success": True, "role": "admin", "redirectUrl": "/admin"})

            elif emp:
                session['user_id'] = emp[0]
                session['role'] = 'employee'
                return jsonify({"success": True, "role": "employee", "redirectUrl": "/employee"})

            elif cust:
                session['user_id'] = cust[0]
                session['role'] = 'customer'
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
            cursor.execute("SELECT * FROM Customer WHERE Email = ?", (email,))
            if cursor.fetchone():
                return jsonify({"success": False, "message": "Email already registered"}), 409

            cursor.execute("SELECT * FROM Customer WHERE username = ?", (username,))
            if cursor.fetchone():
                return jsonify({"success": False, "message": "Username already taken"}), 409

            insert_query = """
                INSERT INTO Customer (username, Name, Phone, Email, password)
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
    # Stats
    cursor.execute("SELECT COUNT(*) FROM Product")
    total_products = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Customer")
    total_customers = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(TotalAmount) FROM SalesTransaction WHERE CAST(TransactionDate AS DATE) = CAST(GETDATE() AS DATE)")
    todays_revenue = cursor.fetchone()[0] or 0

    # Orders today
    cursor.execute("SELECT COUNT(*) FROM SalesTransaction WHERE CAST(TransactionDate AS DATE) = CAST(GETDATE() AS DATE)")
    orders_today = cursor.fetchone()[0] or 0

    # Employee list
    cursor.execute("SELECT EmployeeID, Name, Email, DepartmentID FROM Employee")
    employees = rows_to_dict_list(cursor)

    # Get admin name from session
    admin_name = "Admin"  # default fallback
    if 'user_id' in session and session.get('role') == 'admin':
        cursor.execute("SELECT Name FROM Administrator WHERE AdminID = ?", (session['user_id'],))
        record = cursor.fetchone()
        if record:
            admin_name = record[0]

    return render_template(
        'admin_dashboard.html',
        total_products=total_products,
        total_customers=total_customers,
        todays_revenue=todays_revenue,
        orders_today=orders_today,
        employees=employees,
        admin_name=admin_name
    )

@app.route('/employee')
@with_db
def employee_dashboard(cursor, conn):
    if 'user_id' not in session or session.get('role') != 'employee':
        return redirect(url_for('login'))

    # Fetch logged-in employee info
    cursor.execute("SELECT EmployeeID, Name FROM Employee WHERE EmployeeID = ?", (session['user_id'],))
    record = cursor.fetchone()
    user = None
    if record:
        user = {'Name': record[1], 'role': 'employee'}  # record[1] = Name

    # Fetch all employees (if needed for dashboard)
    cursor.execute("SELECT * FROM Employee")
    employees = rows_to_dict_list(cursor)

    return render_template('employee_dashboard.html', employees=employees, user=user)

from flask import session, redirect, url_for, render_template

@app.route('/customer')
@with_db
def customer_dashboard(cursor, conn):
    try:
        # Require login
        if 'user_id' not in session or session.get('role') != 'customer':
            return redirect(url_for('login'))

        customer_id = session['user_id']

        # Fetch customer info
        cursor.execute("SELECT * FROM Customer WHERE CustomerID = ?", (customer_id,))
        record = cursor.fetchone()
        if not record:
            return redirect(url_for('login'))
        columns = [col[0] for col in cursor.description]
        customer = dict(zip(columns, record))

        # Fetch customer orders
        cursor.execute("""
            SELECT 
                t.TransactionID,
                t.TransactionDate,
                t.TotalAmount,
                t.OrderStatus,
                SUM(td.Quantity) AS ItemCount
            FROM SalesTransaction t
            JOIN Transaction_Details td ON t.TransactionID = td.TransactionID
            WHERE t.CustomerID = ?
            GROUP BY t.TransactionID, t.TransactionDate, t.TotalAmount, t.OrderStatus
            ORDER BY t.TransactionDate DESC
        """, (customer_id,))
        orders = rows_to_dict_list(cursor)


        # <<< Place optional quick stats queries here >>>
        cursor.execute("SELECT SUM(OrderDiscount) FROM SalesTransaction WHERE CustomerID = ?", (customer_id,))
        total_saved = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM SalesTransaction WHERE CustomerID = ?", (customer_id,))
        total_orders = cursor.fetchone()[0] or 0

        return render_template(
            'customer_dashboard.html',
            customer=customer,
            orders=orders,
            total_saved=total_saved,
            total_orders=total_orders,
        )
    
    except Exception as e:
        print("Error fetching customer dashboard:", e)
        return render_template('error.html', message="Error loading dashboard")

@app.route('/department')
@with_db
def department(cursor, conn):
    cursor.execute("SELECT * FROM Department")
    departments = rows_to_dict_list(cursor)
    return render_template('department_dashboard.html', departments=departments)

@app.route('/transactions')
@with_db
def get_transactions(cursor, conn):
    base_query = """
        SELECT t.TransactionID, t.TransactionDate, t.TotalAmount, t.EmployeeID, t.CustomerID, t.PaymentMethod,
               e.Name AS EmployeeName, c.Name AS CustomerName
        FROM SalesTransaction t
        JOIN Employee e ON t.EmployeeID = e.EmployeeID
        JOIN Customer c ON t.CustomerID = c.CustomerID
    """
    filters = []
    params = []

    if request.args.get('employee'):
        filters.append("e.Name LIKE ?")
        params.append(f"%{request.args['employee']}%")
    if request.args.get('payment_method'):
        filters.append("t.PaymentMethod = ?")
        params.append(request.args['payment_method'])

    if filters:
        base_query += " WHERE " + " AND ".join(filters)

    if request.args.get('sort_by') == 'date':
        base_query += " ORDER BY t.TransactionDate DESC"
    elif request.args.get('sort_by') == 'amount':
        base_query += " ORDER BY t.TotalAmount DESC"

    cursor.execute(base_query, params)
    transactions = rows_to_dict_list(cursor)
    return jsonify(transactions)

@app.route('/admin/inventory-report', methods=['GET', 'POST'])
@with_db
def inventory_report(cursor, conn):
    # Get list of departments for the dropdown
    cursor.execute("SELECT DepartmentID, Name FROM Department")
    departments = rows_to_dict_list(cursor)

    if request.method == 'POST':
        # Get filter values from the form
        department_id = request.form.get('department')
        min_price = request.form.get('min_price')
        max_price = request.form.get('max_price')
        stock_status = request.form.get('stock_status')

        # Build query dynamically based on filters
        query = "SELECT * FROM Inventory WHERE 1=1"
        params = []

        if department_id and department_id != "all":
            query += " AND DepartmentID = ?"
            params.append(department_id)
        if min_price:
            query += " AND Price >= ?"
            params.append(min_price)
        if max_price:
            query += " AND Price <= ?"
            params.append(max_price)
        if stock_status and stock_status != "all":
            query += " AND StockStatus = ?"
            params.append(stock_status)

        cursor.execute(query, params)
        inventory_data = rows_to_dict_list(cursor)

        return render_template('admin_inventory_report.html', 
                               departments=departments, 
                               inventory=inventory_data,
                               filters=request.form)
    
    # GET request -> show empty form
    return render_template('admin_inventory_report.html', 
                           departments=departments, 
                           inventory=[], 
                           filters={})

@app.route('/bag', endpoint='bag_page')
@with_db
def bag(cursor, conn):
    user = None
    if 'user_id' in session:
        role = session.get('role')
        if role == 'customer':
            cursor.execute("SELECT Name FROM Customer WHERE CustomerID = ?", (session['user_id'],))
            record = cursor.fetchone()
            if record:
                user = {'Name': record[0], 'role': 'customer'}
        elif role == 'admin':
            cursor.execute("SELECT Name FROM Administrator WHERE AdminID = ?", (session['user_id'],))
            record = cursor.fetchone()
            if record:
                user = {'Name': record[0], 'role': 'admin'}
        elif role == 'employee':  # <-- add this
            cursor.execute("SELECT Name FROM Employee WHERE EmployeeID = ?", (session['user_id'],))
            record = cursor.fetchone()
            if record:
                user = {'Name': record[0], 'role': 'employee'}

    # You can fetch cart items here if needed

    return render_template('bag.html', user=user)

@app.route('/logout')
def logout():
    # Clear all session data
    session.clear()
    # Redirect user back to login page
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
