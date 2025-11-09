from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from db import with_db, rows_to_dict_list
from utility.security import require_role

bp = Blueprint("admin", __name__)

@bp.route('/admin')
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

@bp.route('/admin/inventory-report', methods=['GET', 'POST'])
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
