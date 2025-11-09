from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from flask_cors import CORS
from db import with_db, rows_to_dict_list, get_db_connection
import os
import traceback, sys

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get('SECRET_KEY')




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

@app.post("/reports/query")
@with_db
def report_query(cur, _conn):
    payload = request.get_json(force=True) or {}
    date_from = (payload.get("date_from") or "").strip() or None
    date_to   = (payload.get("date_to") or "").strip() or None
    dept_id   = (payload.get("department_id") or "").strip() or None
    emp_id    = (payload.get("employee_id") or "").strip() or None
    group_by  = (payload.get("group_by") or "product").strip().lower()
    try:
        min_qty = int(payload.get("min_qty") or 0)
    except Exception:
        min_qty = 0

    if group_by == "department":
        select_dim = "d.DepartmentID AS DimID, d.Name AS DimName"
        group_dim  = "d.DepartmentID, d.Name"
    elif group_by == "employee":
        select_dim = (
            "e.EmployeeID AS DimID, "
            "COALESCE(NULLIF(LTRIM(RTRIM(e.FirstName + ' ' + e.LastName)), ''), e.Username) AS DimName"
        )
        group_dim  = "e.EmployeeID, COALESCE(NULLIF(LTRIM(RTRIM(e.FirstName + ' ' + e.LastName)), ''), e.Username)"
    else:
        select_dim = "p.ProductID AS DimID, p.Name AS DimName"
        group_dim  = "p.ProductID, p.Name"

    sql = f"""
    SELECT
        {select_dim},
        SUM(sd.Quantity) AS UnitsSold,
        SUM(CAST(sd.Quantity AS DECIMAL(18,4)) * CAST(sd.UnitPrice AS DECIMAL(18,4))) AS GrossRevenue
    FROM SalesTransaction AS st
    JOIN SalesTransactionDetail AS sd
        ON sd.TransactionID = st.TransactionID
    JOIN Products AS p
        ON p.ProductID = sd.ProductID
    LEFT JOIN Departments AS d
        ON d.DepartmentID = p.DepartmentID
    LEFT JOIN Employees AS e
        ON e.EmployeeID = st.EmployeeID
    WHERE 1 = 1
    """

    params = []

    if date_from and date_to:
        sql += " AND st.TransactionDate >= ? AND st.TransactionDate < DATEADD(day, 1, ?)"
        params.extend([date_from, date_to])
    elif date_from:
        sql += " AND st.TransactionDate >= ?"
        params.append(date_from)
    elif date_to:
        sql += " AND st.TransactionDate < DATEADD(day, 1, ?)"
        params.append(date_to)

    if dept_id:
        sql += " AND p.DepartmentID = ?"
        params.append(dept_id)

    if emp_id:
        sql += " AND st.EmployeeID = ?"
        params.append(emp_id)

    sql += f"""
    GROUP BY {group_dim}
    HAVING SUM(sd.Quantity) >= ?
    ORDER BY GrossRevenue DESC, UnitsSold DESC
    """
    params.append(min_qty)

    cur.execute(sql, params)
    rows = cur.fetchall()
    cols = [c[0] for c in cur.description]
    data = [dict(zip(cols, r)) for r in rows]
    return jsonify({"ok": True, "data": data})

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
