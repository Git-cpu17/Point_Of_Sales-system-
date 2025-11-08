from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from flask_cors import CORS
import os
import pyodbc
import traceback, sys
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
            traceback.print_exc()
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

@app.get("/reports")
@with_db
def reports(cursor, conn):
    role = session.get('role')
    if role not in ('employee', 'admin'):
        return redirect(url_for('login'))

    cursor.execute("SELECT DepartmentID, Name FROM Department ORDER BY Name")
    departments = [{'DepartmentID': r[0], 'Name': r[1]} for r in cursor.fetchall()]

    cursor.execute("""
        SELECT
            EmployeeID,
            COALESCE(
              NULLIF(LTRIM(RTRIM(
                COALESCE(FirstName,'') + ' ' + COALESCE(LastName,'')
              )), ''),
              Username
            ) AS Name
        FROM Employee
        ORDER BY Name
    """)
    employees = [{'EmployeeID': r[0], 'Name': r[1]} for r in cursor.fetchall()]

    return render_template(
        'reports.html',
        departments=departments,
        employees=employees
    )

DETAIL_TABLE = "SalesTransactionDetail"
DETAIL_UNIT_PRICE_COL = "UnitPrice"

@app.post("/reports/query")
@with_db
def reports_query(cursor, conn):
    p = (request.get_json() or {})
    date_from    = p.get("date_from") or None
    date_to      = p.get("date_to")   or None
    departmentId = p.get("department_id") or None
    employeeId   = p.get("employee_id")   or None
    group_by     = (p.get("group_by") or "product").lower()
    try:
        min_qty = int(p.get("min_qty") or 0)
    except Exception:
        min_qty = 0

    if group_by == "department":
        select_dim = "d.DepartmentID AS DimID, d.Name AS DimName"
        group_dim  = "d.DepartmentID, d.Name"
        dim_label  = "Department"
    elif group_by == "employee":
        select_dim = """e.EmployeeID AS DimID,
                        COALESCE(NULLIF(LTRIM(RTRIM(e.FirstName + ' ' + e.LastName)), ''), e.Username) AS DimName"""
        group_dim  = "e.EmployeeID, COALESCE(NULLIF(LTRIM(RTRIM(e.FirstName + ' ' + e.LastName)), ''), e.Username)"
        dim_label  = "Employee"
    else:
        select_dim = "p.ProductID AS DimID, p.Name AS DimName"
        group_dim  = "p.ProductID, p.Name"
        dim_label  = "Product"

    sql = f"""
    SELECT
        {select_dim},
        SUM(sd.Quantity)                          AS UnitsSold,
        SUM(sd.Quantity * sd.{DETAIL_UNIT_PRICE_COL}) AS GrossRevenue,
        AVG(NULLIF(sd.{DETAIL_UNIT_PRICE_COL},0)) AS AvgUnitPrice,
        COUNT(DISTINCT st.TransactionID)          AS NumOrders
    FROM SalesTransaction AS st
    JOIN {DETAIL_TABLE} AS sd
         ON sd.TransactionID = st.TransactionID
    JOIN Product AS p
         ON p.ProductID = sd.ProductID
    LEFT JOIN Department AS d
         ON d.DepartmentID = p.DepartmentID
    LEFT JOIN Employee AS e
         ON e.EmployeeID = st.EmployeeID
    WHERE 1=1
    """

    params = []

    if date_from:
        sql += " AND st.TransactionDate >= ?"
        params.append(date_from)

    if date_to:
        sql += " AND st.TransactionDate < DATEADD(day, 1, ?)"
        params.append(date_to)

    if departmentId:
        sql += " AND p.DepartmentID = ?"
        params.append(departmentId)

    if employeeId:
        sql += " AND st.EmployeeID = ?"
        params.append(employeeId)

    sql += f" GROUP BY {group_dim}"

    if min_qty > 0:
        sql += " HAVING SUM(sd.Quantity) >= ?"
        params.append(min_qty)

    sql += f" ORDER BY DimName"

    cursor.execute(sql, params)
    rows = cursor.fetchall()

    cols = [c[0] for c in cursor.description]
    data = [dict(zip(cols, r)) for r in rows]

    totals = {
        "UnitsSold": sum(r.get("UnitsSold", 0) or 0 for r in data),
        "GrossRevenue": sum((r.get("GrossRevenue", 0) or 0) for r in data),
        "NumOrders": sum((r.get("NumOrders", 0) or 0) for r in data),
    }

    return render_template(
        "partials/report_table.html",
        rows=data,
        dim_label=dim_label,
        totals=totals
    )

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

@app.route('/customer/orders')
@with_db
def customer_orders(cursor, conn):
    if 'user_id' not in session or session.get('role') != 'customer':
        return redirect(url_for('login'))

    customer_id = session['user_id']

    cursor.execute("""
        SELECT
            st.TransactionID,
            st.TransactionDate,
            COALESCE(st.TotalAmount, 0)   AS TotalAmount,
            COALESCE(st.OrderStatus, '')  AS OrderStatus,
            COALESCE(st.PaymentMethod, '') AS PaymentMethod,
            COALESCE(st.OrderDiscount, 0) AS OrderDiscount,
            COALESCE(st.ShippingAddress, '') AS ShippingAddress
        FROM SalesTransaction AS st
        WHERE st.CustomerID = ?
        ORDER BY st.TransactionDate DESC
    """, (customer_id,))
    cols = [c[0] for c in cursor.description]
    orders = [dict(zip(cols, r)) for r in cursor.fetchall()]

    for o in orders:
        if not o['TotalAmount']:
            cursor.execute("""
                SELECT SUM(tp.Quantity * p.Price)
                FROM TransactionProduct tp
                JOIN Product p ON p.ProductID = tp.ProductID
                WHERE tp.TransactionID = ?
            """, (o['TransactionID'],))
            o['TotalAmount'] = float(cursor.fetchone()[0] or 0)

    return render_template('customer_orders.html', orders=orders)

@app.route('/customer/orders/<int:transaction_id>')
@with_db
def customer_order_detail(cursor, conn, transaction_id):
    if 'user_id' not in session or session.get('role') != 'customer':
        return redirect(url_for('login'))

    customer_id = session['user_id']

    cursor.execute("""
        SELECT
            st.TransactionID,
            st.TransactionDate,
            COALESCE(st.TotalAmount, 0)     AS TotalAmount,
            COALESCE(st.OrderStatus, '')    AS OrderStatus,
            COALESCE(st.PaymentMethod, '')  AS PaymentMethod,
            COALESCE(st.OrderDiscount, 0)   AS OrderDiscount,
            COALESCE(st.ShippingAddress, '') AS ShippingAddress,
            st.EmployeeID,
            st.CustomerID
        FROM SalesTransaction st
        WHERE st.TransactionID = ? AND st.CustomerID = ?
    """, (transaction_id, customer_id))
    row = cursor.fetchone()
    if not row:
        return render_template('customer_order_detail.html', order=None, items=[])

    cols = [c[0] for c in cursor.description]
    order = dict(zip(cols, row))

    cursor.execute("""
        SELECT
            tp.ProductID,
            p.Name,
            tp.Quantity,
            p.Price                                    AS UnitPrice,
            (tp.Quantity * p.Price)                         AS Subtotal
        FROM TransactionProduct tp
        JOIN Product p ON p.ProductID = tp.ProductID
        WHERE tp.TransactionID = ?
        ORDER BY tp.ProductID
    """, (transaction_id,))
    item_cols = [c[0] for c in cursor.description]
    items = [dict(zip(item_cols, r)) for r in cursor.fetchall()]

    if not order['TotalAmount']:
        gross = sum((it['Subtotal'] or 0) for it in items)
        order['TotalAmount'] = float(gross - (order.get('OrderDiscount') or 0))

    return render_template('customer_order_detail.html', order=order, items=items)
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
