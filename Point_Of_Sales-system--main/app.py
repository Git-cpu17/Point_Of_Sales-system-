from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from flask_cors import CORS
from datetime import datetime

import os
import pyodbc
from functools import wraps

app = Flask(__name__)
CORS(app)

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

        # Azure SQL sometimes expects username@servername in some contexts; keep original credentials usage
        db_user = f"{DB_USER}@{DB_HOST.split('.')[0]}"

        conn_str = (
            "Driver={ODBC Driver 18 for SQL Server};"
            f"Server={DB_HOST},1433;"
            f"Database={DB_NAME};"
            f"Uid={DB_USER};"
            f"Pwd={DB_PASSWORD};"
            "Encrypt=yes;"
            "TrustServerCertificate=no;"
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
            if conn is None:
                raise RuntimeError("Failed to connect to database.")
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
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'role' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def role_required(roles):
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'role' not in session or session['role'] not in roles:
                return jsonify({"message": "Access denied"}), 403
            return f(*args, **kwargs)
        return decorated
    return wrapper

# -----------------------------
# Routes
# -----------------------------
@app.route('/')
@with_db
def home(cursor, conn):
    # Public route: anyone can see products and departments
    cursor.execute("SELECT * FROM Product")
    products = rows_to_dict_list(cursor)
    cursor.execute("SELECT * FROM Department")
    departments = rows_to_dict_list(cursor)
    return render_template('index.html', products=products, departments=departments)

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


# Admin-facing Add Product page (GET -> form, POST -> insert and redirect)
@app.route('/add_product', methods=['GET', 'POST'])
@with_db
def add_product_page(cursor, conn):
    if request.method == 'POST':
        # Collect form values (names in form should match these keys)
        name = request.form.get('name')
        description = request.form.get('description', '')
        price = request.form.get('price') or 0
        barcode = request.form.get('barcode', '')
        quantity = request.form.get('quantity') or 0
        department_id = request.form.get('department_id') or None

        try:
            cursor.execute("""
                INSERT INTO Product (Name, Description, Price, Barcode, QuantityInStock, DepartmentID)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, description, price, barcode, int(quantity), department_id))
            conn.commit()
        except Exception as e:
            print("Error inserting product:", e)
            # Return the form again with an error message (simple approach)
            return render_template('add_product.html', error="Could not add product. Check server logs."), 500

        return redirect(url_for('admin_dashboard'))

    # GET -> render blank form
    # Optionally provide departments for a select dropdown
    cursor.execute("SELECT DepartmentID, Name FROM Department ORDER BY Name")
    departments = rows_to_dict_list(cursor)
    return render_template('add_product.html', departments=departments)


@app.route('/login', methods=['GET', 'POST'])
@with_db
def login():
    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form or {}
        user_id = data.get('user_id') or data.get('username') or ''
        password = data.get('password') or ''

        if not user_id or not password:
            return jsonify({"success": False, "message": "Missing credentials"}), 400

        
        def check_credentials(cursor, conn):
            cursor.execute("SELECT * FROM Administrator WHERE Username = ? AND Password = ?", (user_id, password))
            admin = cursor.fetchone()

            cursor.execute("SELECT * FROM Employee WHERE Username = ? AND Password = ?", (user_id, password))
            emp = cursor.fetchone()

            cursor.execute("SELECT * FROM Customer WHERE username = ? AND password = ?", (user_id, password))
            cust = cursor.fetchone()

            if admin:
                return jsonify({"success": True, "role": "admin", "redirectUrl": "/admin"})
            elif emp:
                return jsonify({"success": True, "role": "employee", "redirectUrl": "/employee"})
            elif cust:
                return jsonify({"success": True, "role": "customer", "redirectUrl": "/customer"})
            else:
                return jsonify({"success": False, "message": "Invalid ID or Password"}), 401

        return check_credentials(cursor, conn)

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
@login_required
@role_required(['admin'])
@with_db
def admin_dashboard(cursor, conn):
    # Admin-only: manage admins and employees
    cursor.execute("SELECT * FROM Administrator")
    admins = rows_to_dict_list(cursor)
    cursor.execute("SELECT * FROM Employee")
    employees = rows_to_dict_list(cursor)
    return render_template('admin_dashboard.html', admins=admins, employees=employees)

# -----------------------------
# Employee Routes
# -----------------------------
@app.route('/employee')
@login_required
@role_required(['employee'])
@with_db
def employee_dashboard(cursor, conn):
    # Employee-only: dashboard showing employee info
    cursor.execute("SELECT * FROM Employee")
    employees = rows_to_dict_list(cursor)
    # Provide current date for template
    current_date = datetime.now().strftime("%A, %B %d, %Y")
    return render_template('employee_dashboard.html', employees=employees, current_date=current_date)

@app.route('/customer')
@login_required
@role_required(['customer'])
@with_db
def customer_dashboard(cursor, conn):
    # Customer-only: view own dashboard
    try:
        query = "SELECT * FROM Customer"
        print("Running query:", query)
        cursor.execute(query)
        customers = rows_to_dict_list(cursor)
        # For customer dashboard we typically show the logged-in customer's info.
        # Here we pass a single example or the first customer for the template.
        customer_data = customers[0] if customers else {"Name": "Customer", "member_since": "2024"}
        return render_template('customer_dashboard.html', customer=customer_data)
    except Exception as e:
        print("Error fetching customers:", e)
        raise

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

@app.route('/bag', endpoint='bag_page')
@login_required
@role_required(['admin','employee','customer'])
def bag():
    # Shared: accessible by all roles
    return render_template('bag.html')

#route for triggering the low stock products
@app.route('/update_stock', methods=['POST'])
@login_required
@role_required(['admin','employee'])
@with_db
def update_stock(cursor, conn):
    # Admin+Employee: update product quantity (fires triggers)
    data = request.get_json()
    cursor.execute("""
        UPDATE Product
        SET QuantityInStock = ?
        WHERE ProductID = ?
    """, (data['new_stock'], data['product_id']))
    conn.commit()  # 🔥 This will fire trg_low_stock_reorder_alert
    return jsonify({"message": "Stock updated successfully"}), 200

#Update the price base on seasonal demand
@app.route('/apply_sales', methods=['POST'])
@login_required
@role_required(['admin'])
@with_db
def apply_sales(cursor, conn):
    # Admin-only: apply holiday/seasonal sales
    cursor.execute("EXEC ApplyHolidaySales")  # if you wrap your SQL in a stored procedure
    conn.commit()
    return jsonify({"message": "Sales prices updated"}), 200

@app.route('/reports')
@login_required
@role_required(['employee','admin'])
@with_db
def reports(cursor, conn):
    # Admin+Employee: view reports
    role = session.get('role')
    if role not in ('employee', 'admin'):
        return redirect(url_for('login'))

    cursor.execute("SELECT DepartmentID, Name FROM Department ORDER BY Name")
    departments = [{'DepartmentID': r[0], 'Name': r[1]} for r in cursor.fetchall()]

    cursor.execute("""
        SELECT
            EmployeeID,
            COALESCE(NULLIF(LTRIM(RTRIM(Name)), ''), Username) AS Name
        FROM Employee
        ORDER BY Name
    """)
    employees = [{'EmployeeID': r[0], 'Name': r[1]} for r in cursor.fetchall()]

    return render_template(
        'reports.html',
        departments=departments,
        employees=employees
    )

def _iso_date(s):
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None
@login_required
@role_required(['employee','admin'])
@with_db
@app.post("/reports/query")
@with_db
def reports_query(cur, conn):
    payload = (request.get_json(silent=True) or request.form.to_dict() or {})

    date_from = _iso_date(payload.get("date_from") or payload.get("from") or payload.get("dateFrom"))
    date_to   = _iso_date(payload.get("date_to")   or payload.get("to")   or payload.get("dateTo"))
    group_by  = (payload.get("group_by") or payload.get("groupBy") or "product").strip().lower()
    department = payload.get("department") or payload.get("department_id")
    employee   = payload.get("employee") or payload.get("employee_id")

    try:
        min_units = int(payload.get("min_units") or payload.get("minUnits") or 0)
    except (TypeError, ValueError):
        min_units = 0

    if not date_from:
        date_from = "1900-01-01"
    if not date_to:
        date_to = "2100-12-31"

    dept_val = None if (not department or str(department).lower() == "all") else int(department)
    emp_val  = None if (not employee   or str(employee).lower()   == "all") else int(employee)
    try:
        min_val = None if (not min_units or int(min_units) <= 0) else int(min_units)
    except Exception:
        min_val = None

    if group_by == "product":
        select_dim = "p.ProductID AS DimID, p.Name AS DimName"
        group_dim  = "p.ProductID, p.Name"
    elif group_by == "department":
        select_dim = "d.DepartmentID AS DimID, d.Name AS DimName"
        group_dim  = "d.DepartmentID, d.Name"
    elif group_by == "employee":
        select_dim = "e.EmployeeID AS DimID, COALESCE(NULLIF(LTRIM(RTRIM(e.Name)), ''), e.Username) AS DimName"
        group_dim  = "e.EmployeeID, COALESCE(NULLIF(LTRIM(RTRIM(e.Name)), ''), e.Username)"
    else:
        select_dim = "p.ProductID AS DimID, p.Name AS DimName"
        group_dim  = "p.ProductID, p.Name"

    sql_parts = [
        "SELECT",
        f"  {select_dim},",
        "  SUM(td.Quantity) AS UnitsSold,",
        "  SUM(CAST(td.Quantity * p.Price AS DECIMAL(18,4))) AS GrossRevenue",
        "FROM SalesTransaction AS st",
        "JOIN Transaction_Details AS td ON td.TransactionID = st.TransactionID",
        "JOIN Product AS p              ON p.ProductID       = td.ProductID",
        "LEFT JOIN Department_Product AS dp ON dp.ProductID   = p.ProductID",
        "LEFT JOIN Department AS d          ON d.DepartmentID = dp.DepartmentID",
        "LEFT JOIN Employee  AS e           ON e.EmployeeID   = st.EmployeeID",
        "WHERE st.TransactionDate >= ?",
        "  AND st.TransactionDate < DATEADD(day, 1, ?)",
        "  AND ( ? IS NULL OR d.DepartmentID = ? )",
        "  AND ( ? IS NULL OR e.EmployeeID   = ? )",
        f"GROUP BY {group_dim}",
        "HAVING ( ? IS NULL OR SUM(td.Quantity) >= ? )",
        f"ORDER BY {group_dim}",
    ]
    
    sql = "\n".join(sql_parts)
    
    params = [
        date_from, date_to,
        dept_val, dept_val,
        emp_val,  emp_val,
        min_val,  min_val
    ]

    try:
        cur.execute(sql, params)
        rows = cur.fetchall()
    except Exception as e:
        print("DB error in /reports/query:", e)
        return "Could not load report. Please check parameter values and try again.", 500

    html = [
        '<table class="report-table">',
        '<thead><tr><th>Group</th><th>Units Sold</th><th>Gross Revenue</th></tr></thead>',
        '<tbody>'
    ]
    
    for r in rows:
        dim_name = r[1]
        units    = int(r[2] or 0)
        revenue  = float(r[3] or 0.0)
        html.append(f"<tr><td>{dim_name}</td><td>{units}</td><td>${revenue:,.2f}</td></tr>")
    html.append("</tbody></table>")

    return "".join(html), 200, {"Content-Type": "text/html; charset=utf-8"}

# --- Placeholder pages for links used by templates (render templates)
@app.route('/restock', methods=['GET', 'POST'])
@login_required
@role_required(['admin','employee'])
@with_db
def restock(cursor, conn):
    # Admin+Employee: restock products
    return render_template('restock.html')

@app.route('/update_prices')
@login_required
@role_required(['admin'])
@with_db
def update_prices(cursor, conn):
    # Admin-only: update seasonal prices
    return render_template('update_prices.html')

@app.route('/order', methods=['GET', 'POST'])
@login_required
@role_required(['admin','employee'])
@with_db
def order(cursor, conn):
    # Admin+Employee: view or create orders
    return render_template('order.html')

@app.route('/transactions')
@login_required
@role_required(['admin'])
@with_db
def transaction(cursor, conn):
    # Admin-only: view all transactions
    return render_template('transaction.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
