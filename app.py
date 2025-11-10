from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from flask_cors import CORS
from datetime import datetime
from db import with_db, rows_to_dict_list, get_db_connection
import os
import traceback, sys

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get('SECRET_KEY')

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
                SELECT SUM(td.Quantity * p.Price)
                FROM Transaction_Details td
                JOIN Product p ON p.ProductID = td.ProductID
                WHERE td.TransactionID = ?
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
            td.ProductID,
            p.Name,
            td.Quantity,
            p.Price              AS UnitPrice,
            (td.Quantity * p.Price) AS Subtotal
        FROM Transaction_Details td
        JOIN Product p ON p.ProductID = td.ProductID
        WHERE td.TransactionID = ?
        ORDER BY td.ProductID
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
    cursor.execute("SELECT DepartmentID, Name FROM Department")
    departments = rows_to_dict_list(cursor)

    if request.method == 'POST':
        department_id = request.form.get('department')
        min_price = request.form.get('min_price')
        max_price = request.form.get('max_price')
        stock_status = request.form.get('stock_status')

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
        elif role == 'employee':
            cursor.execute("SELECT Name FROM Employee WHERE EmployeeID = ?", (session['user_id'],))
            record = cursor.fetchone()
            if record:
                user = {'Name': record[0], 'role': 'employee'}

    # You can fetch cart items here if needed

    return render_template('bag.html', user=user)

@app.post("/checkout")
@with_db
def checkout(cursor, conn):
    payload = request.get_json(silent=True) or {}
    items = payload.get("items") or []
    if not items:
        return jsonify({"message": "No items to checkout."}), 400

    clean = []
    for it in items:
        try:
            pid = int(it.get("product_id"))
            qty = int(it.get("quantity"))
        except Exception:
            return jsonify({"message": f"Invalid item: {it}"}), 400
        if pid <= 0 or qty <= 0:
            return jsonify({"message": f"Invalid item: {it}"}), 400
        clean.append((pid, qty))

    role = session.get('role')
    cust_id = session.get('user_id') if role == 'customer' else None
    emp_id  = session.get('user_id') if role == 'employee' else None

    if cust_id is None and emp_id is None:
        return jsonify({"message": "Login required to checkout."}), 401

    autocommit_backup = conn.autocommit
    conn.autocommit = False
    try:
        grand_total = 0.0
        line_items = []

        for pid, qty in clean:
            cursor.execute("""
                SELECT TOP 1 ProductID, Price, QuantityInStock
                FROM Product WITH (UPDLOCK, ROWLOCK)
                WHERE ProductID = ?
            """, (pid,))
            row = cursor.fetchone()
            if not row:
                conn.rollback(); conn.autocommit = autocommit_backup
                return jsonify({"message": f"Product {pid} not found."}), 404

            _, price, stock = row
            stock = stock or 0
            if stock < qty:
                conn.rollback(); conn.autocommit = autocommit_backup
                return jsonify({"message": f"Insufficient stock for ProductID {pid}. In stock: {stock}, requested: {qty}"}), 409

            subtotal = float(price) * qty
            grand_total += subtotal
            line_items.append((pid, qty, float(price), subtotal))

        cursor.execute("""
             INSERT INTO SalesTransaction (
                 CustomerID, EmployeeID, TransactionDate, TotalAmount, PaymentMethod, OrderStatus
             )
             VALUES (?, ?, GETDATE(), ?, ?, ?)
         """, (cust_id, emp_id, grand_total, 'Cash', 'Completed'))

         cursor.execute("SELECT CAST(SCOPE_IDENTITY() AS INT)")
         new_tid = cursor.fetchone()[0]

        for pid, qty, price, subtotal in line_items:
            cursor.execute("""
                INSERT INTO Transaction_Details (TransactionID, ProductID, Quantity, Price)
                VALUES (?, ?, ?, ?)
            """, (new_tid, pid, qty, price))
            cursor.execute("""
                UPDATE Product
                SET QuantityInStock = QuantityInStock - ?
                WHERE ProductID = ?
            """, (qty, pid))

        conn.commit()
        conn.autocommit = autocommit_backup
        return jsonify({"transaction_id": new_tid, "total_amount": grand_total}), 201

    except Exception as e:
        print("DB error (/checkout):", e)
        traceback.print_exc()
        conn.rollback()
        conn.autocommit = autocommit_backup
        return jsonify({"message": f"Database error: {str(e)}"}), 500
        
@app.route('/logout')
def logout():
    # Clear all session data
    session.clear()
    # Redirect user back to login page
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
