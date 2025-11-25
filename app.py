from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response, flash
from flask_cors import CORS
from datetime import datetime, timedelta, date
from collections import defaultdict
from db import with_db, rows_to_dict_list, get_db_connection
import random
import string
import os
import traceback, sys
import requests

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get('SECRET_KEY','dev_secret_123!@#')

def get_bag_owner_from_session():
    role = session.get('role')
    uid  = session.get('user_id')
    if role == 'customer' and uid:
        return {'CustomerID': uid, 'EmployeeID': None}
    if role == 'employee' and uid:
        return {'CustomerID': None, 'EmployeeID': uid}
    return None

@app.context_processor
@with_db
def inject_bag_count(cursor, conn):
    owner = get_bag_owner_from_session()
    count = 0
    if owner:
        if owner['CustomerID'] is not None:
            cursor.execute("SELECT COALESCE(SUM(Quantity),0) FROM dbo.Bag WHERE CustomerID = ? AND EmployeeID IS NULL", (owner['CustomerID'],))
        else:
            cursor.execute("SELECT COALESCE(SUM(Quantity),0) FROM dbo.Bag WHERE EmployeeID = ? AND CustomerID IS NULL", (owner['EmployeeID'],))
        row = cursor.fetchone()
        count = int(row[0] or 0) if row else 0
    return {'bag_count': count}
    
# -----------------------------
# Routes
# -----------------------------

@app.route('/')
@with_db
def home(cursor, conn):
    # Fetch active products including DepartmentID
    cursor.execute("""
        SELECT ProductID, Name, Description, Price, QuantityInStock, DepartmentID, ImageURL, OnSale
        FROM Product
        WHERE IsActive = 1
    """)
    products = rows_to_dict_list(cursor)

    # Fetch active holiday sale
    cursor.execute("""
        SELECT SaleID, SaleName, StartDate, EndDate, DiscountPercent, DepartmentID, IsActive
        FROM Holiday_Sales
        WHERE IsActive = 1
        AND GETDATE() BETWEEN StartDate AND EndDate
    """)
    holiday_sale = cursor.fetchone()

    sale_info = None
    if holiday_sale:
        sale_info = {
            'SaleID': holiday_sale[0],
            'SaleName': holiday_sale[1],
            'StartDate': holiday_sale[2],
            'EndDate': holiday_sale[3],
            'DiscountPercent': holiday_sale[4],
            'DepartmentID': holiday_sale[5],
            'IsActive': holiday_sale[6]
        }

        # Calculate sale prices for products marked OnSale
        # If DepartmentID is set, only apply to that department
        for product in products:
            if product.get('OnSale'):
                # Check if sale applies to this product's department
                if sale_info['DepartmentID'] is None or product['DepartmentID'] == sale_info['DepartmentID']:
                    original_price = float(product['Price'])
                    discount = float(sale_info['DiscountPercent'])
                    sale_price = original_price * (1 - discount / 100)
                    product['SalePrice'] = round(sale_price, 2)
                    product['OriginalPrice'] = original_price
                    product['Savings'] = round(original_price - sale_price, 2)

    # Fetch all departments
    cursor.execute("SELECT DepartmentID,Name FROM Department")
    departments = rows_to_dict_list(cursor)

    # Determine user info based on role
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
        cursor.execute("SELECT Name FROM Employee WHERE EmployeeID = ? AND IsActive = 1", (session['user_id'],))
        record = cursor.fetchone()
        if record:
            user = {'Name': record[0], 'role': 'employee'}

    # Pass products, departments, and sale info to template
    return render_template('index.html', products=products, departments=departments, user=user, sale_info=sale_info)

@app.route("/api/status", methods=["GET"])
def status():
    return jsonify({"message": "Flask API is running and connected to Azure SQL!"})

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
    cursor.execute("SELECT EmployeeID, Name, Email, DepartmentID FROM Employee WHERE IsActive = 1")
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

@app.route('/admin/products')
@with_db
def manage_products(cursor, conn):
    # Only admins and employees can access
    if 'role' not in session or session['role'] not in ['admin', 'employee']:
        return redirect(url_for('login'))
    
    # Get filter parameters
    search = request.args.get('search', '')
    department = request.args.get('department', '')
    
    # Build query
    query = """
        SELECT 
            p.ProductID,
            p.Name,
            p.Description,
            p.Price,
            p.SalePrice,
            p.OnSale,
            p.QuantityInStock,
            p.Barcode,
            d.Name as DepartmentName,
            p.DepartmentID,
            p.ImageURL
        FROM Product p
        LEFT JOIN Department d ON p.DepartmentID = d.DepartmentID
        WHERE p.IsActive = 1
    """
    params = []
    
    if search:
        query += " AND (p.Name LIKE ? OR p.Description LIKE ? OR p.Barcode LIKE ?)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])
    
    if department:
        query += " AND p.DepartmentID = ?"
        params.append(department)
    
    query += " ORDER BY p.Name"
    
    cursor.execute(query, params)
    products = rows_to_dict_list(cursor)
    
    # Get departments for filter
    cursor.execute("SELECT DepartmentID, Name FROM Department ORDER BY Name")
    departments = rows_to_dict_list(cursor)
    
    return render_template('manage_products.html', 
                          products=products, 
                          departments=departments,
                          search=search,
                          selected_dept=department)

@app.route('/admin/edit-product/<int:product_id>', methods=['GET', 'POST'])
@with_db
def edit_product(cursor, conn, product_id):
    # Access control
    if 'role' not in session or session['role'] not in ['admin', 'employee']:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        data = request.form

        # --- Extract fields ---
        name = (data.get("Name") or "").strip()
        description = data.get("Description") or ""
        price = data.get("Price")
        department_id = data.get("DepartmentID")
        image_url = data.get("ImageURL") or ""
        quantity_in_stock = data.get("QuantityInStock") or 0

        # --- Validation ---
        if not name:
            flash("Product name is required.", "danger")
            return redirect(url_for('edit_product', product_id=product_id))

        try:
            price = float(price)
            if price < 0:
                raise ValueError
        except (TypeError, ValueError):
            flash("Price must be a valid non-negative number.", "danger")
            return redirect(url_for('edit_product', product_id=product_id))

        try:
            department_id = int(department_id)
            if department_id <= 0:
                raise ValueError
        except (TypeError, ValueError):
            flash("Please select a valid department.", "danger")
            return redirect(url_for('edit_product', product_id=product_id))

        try:
            quantity_in_stock = int(quantity_in_stock)
            if quantity_in_stock < 0:
                raise ValueError
        except (TypeError, ValueError):
            flash("Quantity must be a valid non-negative integer.", "danger")
            return redirect(url_for('edit_product', product_id=product_id))

        # --- Handle image generation if missing ---
        if not image_url:
            image_url = generate_product_image(name) or "https://via.placeholder.com/400?text=Product+Image"

        # --- Update the product ---
        cursor.execute("""
            UPDATE Product
            SET Name = ?, Description = ?, Price = ?, DepartmentID = ?, 
                QuantityInStock = ?, ImageURL = ?
            WHERE ProductID = ?
        """, (name, description, price, department_id, quantity_in_stock, image_url, product_id))

        conn.commit()
        flash(f"Product '{name}' updated successfully!", "success")
        return redirect(url_for('manage_products'))

    # --- GET request: load product info ---
    cursor.execute("SELECT * FROM Product WHERE ProductID = ?", (product_id,))
    product = cursor.fetchone()

    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for('manage_products'))

    # Convert to dict
    columns = [col[0] for col in cursor.description]
    product = dict(zip(columns, product))

    # --- Fetch department list for dropdown ---
    cursor.execute("SELECT DepartmentID, Name FROM Department ORDER BY Name")
    departments = rows_to_dict_list(cursor)

    return render_template(
        'edit_product.html',
        product=product,
        departments=departments
    )

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
@with_db
def delete_product(cursor, conn, product_id):
    # Only admins can delete
    if 'role' not in session or session['role'] != 'admin':
        return jsonify({"message": "Unauthorized"}), 403
    
    try:
        # Check if product exists
        cursor.execute("SELECT Name FROM Product WHERE ProductID = ?", (product_id,))
        product = cursor.fetchone()
        
        if not product:
            return jsonify({"message": "Product not found"}), 404
        
        product_name = product[0]
        
        # Soft delete - just mark as inactive
        cursor.execute("UPDATE Product SET IsActive = 0 WHERE ProductID = ?", (product_id,))
        conn.commit()
        
        return jsonify({"message": f"Product '{product_name}' has been deactivated"}), 200
    except Exception as e:
        return jsonify({"message": f"Error deactivating product: {str(e)}"}), 500
        
@app.route('/api/low_stock')
@with_db
def low_stock(cursor, conn):
    if 'user_id' not in session or session.get('role') not in ('admin', 'employee'):
        return jsonify({"error": "Unauthorized"}), 403

    cursor.execute("""
        SELECT ProductID, Name, QuantityInStock, DepartmentID
        FROM Product
        WHERE QuantityInStock < 10
        ORDER BY QuantityInStock ASC
    """)
    items = rows_to_dict_list(cursor)
    return jsonify(items)
@app.route('/api/update_stock', methods=['POST'])
@with_db
def update_stock(cursor, conn):
    if 'user_id' not in session or session.get('role') not in ('admin', 'employee'):
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    pid = data.get('product_id')
    new_stock = data.get('new_stock')

    if pid is None or new_stock is None:
        return jsonify({"error": "Missing fields"}), 400

    try:
        new_stock = int(new_stock)
        if new_stock < 0:
            return jsonify({"error": "Stock cannot be negative"}), 400
    except ValueError:
        return jsonify({"error": "Invalid stock value"}), 400

    cursor.execute("UPDATE Product SET QuantityInStock = ? WHERE ProductID = ?", (new_stock, pid))
    conn.commit()
    return jsonify({"message": "Stock updated successfully"}), 200
@app.route('/apply_sales', methods=['POST'])
@with_db
def apply_sales(cursor, conn):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    try:
        cursor.execute("""
            UPDATE Product
            SET Price = Price * 0.8
        """)
        conn.commit()
        return jsonify({"message": "Seasonal sale prices applied!"}), 200
    except Exception as e:
        print("Error executing sale trigger:", e)
        conn.rollback()
        return jsonify({"error": "Failed to apply sales"}), 500

# Reorder Alerts API endpoints
@app.route('/api/reorder_alerts/count')
@with_db
def get_reorder_alerts_count(cursor, conn):
    if 'user_id' not in session or session.get('role') not in ('admin', 'employee'):
        return jsonify({"error": "Unauthorized"}), 403

    cursor.execute("SELECT COUNT(*) FROM Reorder_Alerts WHERE AlertStatus = 'PENDING'")
    count = cursor.fetchone()[0] or 0
    return jsonify({"count": count})

@app.route('/api/reorder_alerts')
@with_db
def get_reorder_alerts(cursor, conn):
    if 'user_id' not in session or session.get('role') not in ('admin', 'employee'):
        return jsonify({"error": "Unauthorized"}), 403

    cursor.execute("""
        SELECT
            ra.AlertID,
            ra.ProductID,
            ra.ProductName,
            ra.CurrentStock,
            ra.ReorderLevel,
            ra.AlertDate,
            ra.AlertStatus,
            p.Price,
            p.DepartmentID
        FROM Reorder_Alerts ra
        LEFT JOIN Product p ON ra.ProductID = p.ProductID
        WHERE ra.AlertStatus = 'PENDING'
        ORDER BY ra.AlertDate DESC
    """)
    alerts = rows_to_dict_list(cursor)
    return jsonify(alerts)

@app.route('/api/reorder_alerts/<int:alert_id>/restock', methods=['POST'])
@with_db
def restock_product(cursor, conn, alert_id):
    if 'user_id' not in session or session.get('role') not in ('admin', 'employee'):
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    restock_quantity = data.get('quantity')

    if not restock_quantity:
        return jsonify({"error": "Quantity is required"}), 400

    try:
        restock_quantity = int(restock_quantity)
        if restock_quantity <= 0:
            return jsonify({"error": "Quantity must be positive"}), 400
    except ValueError:
        return jsonify({"error": "Invalid quantity"}), 400

    # Get the alert details
    cursor.execute("SELECT ProductID, AlertStatus FROM Reorder_Alerts WHERE AlertID = ?", (alert_id,))
    alert = cursor.fetchone()

    if not alert:
        return jsonify({"error": "Alert not found"}), 404

    if alert[1] != 'PENDING':
        return jsonify({"error": "Alert already processed"}), 400

    product_id = alert[0]

    # Update the product stock
    cursor.execute("""
        UPDATE Product
        SET QuantityInStock = QuantityInStock + ?
        WHERE ProductID = ?
    """, (restock_quantity, product_id))

    # Mark alert as completed
    cursor.execute("""
        UPDATE Reorder_Alerts
        SET AlertStatus = 'COMPLETED'
        WHERE AlertID = ?
    """, (alert_id,))

    conn.commit()

    return jsonify({"message": "Product restocked successfully", "quantity": restock_quantity})

@app.route('/api/reorder_alerts/scan', methods=['POST'])
@with_db
def scan_low_stock(cursor, conn):
    """Scan all products and create alerts for any that are currently low stock but don't have pending alerts"""
    if 'user_id' not in session or session.get('role') not in ('admin', 'employee'):
        return jsonify({"error": "Unauthorized"}), 403

    # Find products that are low stock but don't have pending alerts
    cursor.execute("""
        INSERT INTO Reorder_Alerts (ProductID, ProductName, CurrentStock, ReorderLevel)
        SELECT
            p.ProductID,
            p.Name,
            p.QuantityInStock,
            ISNULL(inv.ReorderLevel, 10) as ReorderLevel
        FROM Product p
        LEFT JOIN Inventory inv ON p.ProductID = inv.ProductID
        WHERE p.QuantityInStock <= ISNULL(inv.ReorderLevel, 10) * 1.2
        AND p.IsActive = 1
        AND NOT EXISTS (
            SELECT 1
            FROM Reorder_Alerts ra
            WHERE ra.ProductID = p.ProductID
            AND ra.AlertStatus = 'PENDING'
        )
    """)

    rows_inserted = cursor.rowcount
    conn.commit()

    return jsonify({
        "message": f"Scan complete. Created {rows_inserted} new alert(s).",
        "alerts_created": rows_inserted
    })

@app.route('/admin/add-product', methods=['GET', 'POST'])
@with_db
def add_product(cursor, conn):
    # Only admins can access
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        data = request.form

        name = (data.get("Name") or "").strip()
        description = data.get("Description") or ""
        price = data.get("Price")
        department_id = data.get("DepartmentID")
        image_url = data.get("ImageURL") or ""

        # --- Validate fields ---
        if not name:
            return jsonify({"success": False, "error": "Product name is required."}), 400
        if price is None or price == "":
            return jsonify({"success": False, "error": "Price is required."}), 400
        try:
            price = float(price)
            if price < 0: raise ValueError
        except ValueError:
            return jsonify({"success": False, "error": "Price must be a non-negative number."}), 400

        try:
            department_id = int(department_id)
            if department_id <= 0: raise ValueError
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Please select a valid department."}), 400

        # --- Generate unique 12-digit barcode ---
        while True:
            barcode = ''.join(random.choices(string.digits, k=12))
            cursor.execute("SELECT 1 FROM Product WHERE Barcode = ?", (barcode,))
            if not cursor.fetchone():
                break

        # --- Ensure image URL is set ---
        if not image_url:
            image_url = generate_product_image(name) or "https://via.placeholder.com/400?text=Product+Image"

        # --- Set initial inventory values ---
        quantity_in_stock = int(data.get("QuantityInStock") or 0)
        reorder_level = int(data.get("ReorderLevel") or 10)  # default reorder level
        quantity_available = quantity_in_stock  # initially same as stock

        # --- Insert product ---
        cursor.execute("""
            INSERT INTO Product
            (Name, Description, Price, DepartmentID, Barcode, QuantityInStock, SalePrice, OnSale, ImageURL)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, description, price, department_id, barcode, quantity_in_stock, None, 0, image_url))
        conn.commit()  # commit first

        # --- Get inserted ProductID by barcode ---
        cursor.execute("SELECT ProductID FROM Product WHERE Barcode = ?", (barcode,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"success": False, "error": "Failed to retrieve inserted ProductID."}), 500
        product_id = row[0]

        # --- Insert into Inventory table ---
        cursor.execute("""
            INSERT INTO Inventory
            (ProductID, QuantityAvailable, ReorderLevel)
            VALUES (?, ?, ?)
        """, (product_id, quantity_available, reorder_level))
        conn.commit()

        # --- Return JSON for AJAX ---
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "success": True,
                "product_name": name,
                "image_url": image_url
            })

        flash(f"Product '{name}' added successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    # GET request -> show form
    cursor.execute("SELECT DepartmentID, Name FROM Department ORDER BY Name")
    departments = rows_to_dict_list(cursor)
    return render_template('add_product.html', departments=departments)

def generate_product_image(product_name: str) -> str:
    """
    Generates or fetches a product image based on the product name.
    Returns the URL of the generated/fetched image.
    """

    # --- Option 1: Fetch a stock image from Unsplash ---
    # You need to get an API key from Unsplash and set it in your environment
    UNSPLASH_ACCESS_KEY = "4YRk506nTWf9lbL1hkJmmXEqG3qtACKUBAWVouGzY5Y"

    if not UNSPLASH_ACCESS_KEY:
        # fallback if no key is set
        return "https://via.placeholder.com/400?text=Product+Image"

    try:
        response = requests.get(
            "https://api.unsplash.com/photos/random",
            params={
                "query": product_name,
                "orientation": "squarish",
                "client_id": UNSPLASH_ACCESS_KEY
            },
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        # return the regular-sized image URL
        return data.get("urls", {}).get("regular") or "https://via.placeholder.com/400?text=Product+Image"
    except Exception as e:
        print("Error fetching image:", e)
        # fallback placeholder if anything fails
        return "https://via.placeholder.com/400?text=Product+Image"

@app.route('/employees')
@with_db
def manage_employees(cursor, conn):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    cursor.execute("SELECT * FROM Employee WHERE IsActive = 1 ORDER BY HireDate DESC")
    employees = rows_to_dict_list(cursor)

    cursor.execute("SELECT DepartmentID, Name FROM Department ORDER BY Name")
    departments = rows_to_dict_list(cursor)

    return render_template('admin_employees.html', employees=employees, departments=departments)

@app.get("/api/employees/<int:emp_id>")
@with_db
def get_employee(cursor, conn, emp_id):
    cursor.execute("""
        SELECT EmployeeID, Name, Phone, Email, JobTitle, HireDate, DepartmentID, AdminID, Username, Password
        FROM Employee
        WHERE EmployeeID = ? AND IsActive = 1
    """, (emp_id,))
    row = cursor.fetchone()
    if not row:
        return jsonify({"message": "Employee not found"}), 404
    columns = [c[0] for c in cursor.description]
    return jsonify(dict(zip(columns, row)))

@app.post("/api/employees/add")
@with_db
def add_employee(cursor, conn):
    if 'role' not in session or session['role'] != 'admin':
        return jsonify({"message": "Unauthorized"}), 403

    data = request.get_json()
    username = data.get("Username")
    department_id = data.get("DepartmentID")
    current_date = datetime.now().strftime("%m/%d/%Y")

    # Check for duplicate username
    cursor.execute("SELECT EmployeeID FROM Employee WHERE Username = ?", (username,))
    if cursor.fetchone():
        return jsonify({"message": f"Username '{username}' already exists."}), 409

    # Check if department already has an active employee
    cursor.execute("""
        SELECT EmployeeID 
        FROM Employee 
        WHERE DepartmentID = ? AND IsActive = 1
    """, (department_id,))
    if cursor.fetchone():
        return jsonify({"message": f"Department already has an active employee."}), 409

    # Insert employee
    cursor.execute("""
        INSERT INTO Employee (Name, Phone, Email, JobTitle, HireDate, DepartmentID, AdminID, Username, Password, IsActive)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (
        data.get("Name"),
        data.get("Phone") or None,
        data.get("Email") or None,
        data.get("JobTitle") or None,
        current_date,
        department_id,
        session.get("user_id"),  # logged-in admin
        data.get("Username"),
        data.get("Password")
    ))
    conn.commit()
    return jsonify({"message": "Employee added successfully!"}), 201

@app.post("/api/employees/edit/<int:emp_id>")
@with_db
def edit_employee(cursor, conn, emp_id):
    data = request.get_json()

    # Fetch current hire date
    cursor.execute("SELECT HireDate FROM Employee WHERE EmployeeID = ?", (emp_id,))
    current_hiredate = cursor.fetchone()[0]

    # If no new hire date provided, keep current
    hiredate = data.get("HireDate") or current_hiredate

    cursor.execute("""
        UPDATE Employee
        SET Name = ?, Phone = ?, Email = ?, JobTitle = ?, HireDate = ?, DepartmentID = ?, Username = ?, Password = ?
        WHERE EmployeeID = ?
    """, (
        data.get("Name"),
        data.get("Phone"),
        data.get("Email"),
        data.get("JobTitle"),
        hiredate,
        data.get("DepartmentID"),
        data.get("Username"),
        data.get("Password"),
        emp_id
    ))
    conn.commit()
    return jsonify({"message": "Employee updated successfully!"}), 200

@app.delete("/api/employees/delete/<int:emp_id>")
@with_db
def delete_employee(cursor, conn, emp_id):
    cursor.execute("UPDATE Employee SET IsActive = 0 WHERE EmployeeID = ?", (emp_id,))
    conn.commit()
    return jsonify({"message": "Employee deleted successfully!"}), 200

@app.route('/employee')
@with_db
def employee_dashboard(cursor, conn):
    user_id = session['user_id']

    # Get employee info
    cursor.execute("SELECT * FROM Employee WHERE EmployeeID = ?", (user_id,))
    user = cursor.fetchone()

    # 1. Number of orders employee processed today
    cursor.execute("""
        SELECT COUNT(*) 
        FROM Transaction_Details
        WHERE EmployeeID = ? AND CAST(datetime AS DATE) = CAST(GETDATE() AS DATE)
    """, (user_id,))
    orders_today = cursor.fetchone()[0]

    # 2. Revenue generated by employee today
    cursor.execute("""
        SELECT SUM(Subtotal) 
        FROM Transaction_Details
        WHERE EmployeeID = ? AND CAST(datetime AS DATE) = CAST(GETDATE() AS DATE)
    """, (user_id,))
    revenue_today = cursor.fetchone()[0] or 0

    # 3. Low-stock products in employee's department
    cursor.execute("""
        SELECT COUNT(*) 
        FROM Inventory i
        JOIN Employee e ON e.DepartmentID = i.DepartmentID
        WHERE e.EmployeeID = ? AND i.QuantityAvailable <= i.ReorderLevel
    """, (user_id,))
    low_stock_products = cursor.fetchone()[0]

    return render_template(
        'employee_dashboard.html',
        user=user,
        current_date=datetime.now().strftime("%A, %B %d, %Y"),
        orders_today=orders_today,
        revenue_today=revenue_today,
        low_stock_products=low_stock_products
    )

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

@app.route('/customer/settings', methods=['GET', 'POST'])
@with_db
def customer_settings(cursor, conn):
    # Require customer login
    if 'user_id' not in session or session.get('role') != 'customer':
        return redirect(url_for('login'))

    customer_id = session['user_id']

    if request.method == 'POST':
        # Handle settings update
        data = request.get_json() or request.form or {}
        name = data.get('name')
        email = data.get('email')
        phone = data.get('phone')
        current_password = data.get('current_password')
        new_password = data.get('new_password')

        if not name or not email:
            return jsonify({"success": False, "message": "Name and email are required"}), 400

        # Verify current customer
        cursor.execute("SELECT password FROM Customer WHERE CustomerID = ?", (customer_id,))
        record = cursor.fetchone()
        if not record:
            return jsonify({"success": False, "message": "Customer not found"}), 404

        # Check if email is already used by another customer
        cursor.execute("SELECT CustomerID FROM Customer WHERE Email = ? AND CustomerID != ?", (email, customer_id))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Email already in use by another account"}), 409

        # Update customer information
        if new_password and current_password:
            # Verify current password
            if record[0] != current_password:
                return jsonify({"success": False, "message": "Current password is incorrect"}), 401

            # Update with new password
            cursor.execute("""
                UPDATE Customer
                SET Name = ?, Email = ?, Phone = ?, password = ?
                WHERE CustomerID = ?
            """, (name, email, phone, new_password, customer_id))
        else:
            # Update without changing password
            cursor.execute("""
                UPDATE Customer
                SET Name = ?, Email = ?, Phone = ?
                WHERE CustomerID = ?
            """, (name, email, phone, customer_id))

        conn.commit()
        return jsonify({"success": True, "message": "Settings updated successfully!"}), 200

    # GET request - fetch customer info
    cursor.execute("SELECT CustomerID, username, Name, Email, Phone FROM Customer WHERE CustomerID = ?", (customer_id,))
    record = cursor.fetchone()
    if not record:
        return redirect(url_for('login'))

    columns = [col[0] for col in cursor.description]
    customer = dict(zip(columns, record))

    return render_template('customer_settings.html', customer=customer)

@app.route('/customer/orders')
@with_db
def customer_orders(cursor, conn):
    if 'user_id' not in session or session.get('role') != 'customer':
        return redirect(url_for('login'))

    customer_id = session['user_id']

    # Fetch orders
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
        # Ensure TotalAmount is set
        if not o['TotalAmount']:
            cursor.execute("""
                SELECT SUM(td.Quantity * p.Price)
                FROM Transaction_Details td
                JOIN Product p ON p.ProductID = td.ProductID
                WHERE td.TransactionID = ?
            """, (o['TransactionID'],))
            o['TotalAmount'] = float(cursor.fetchone()[0] or 0)

        # Fetch first 3 items for inline summary
        cursor.execute("""
            SELECT TOP 3 td.ProductID, p.Name, td.Quantity
            FROM Transaction_Details td
            JOIN Product p ON p.ProductID = td.ProductID
            WHERE td.TransactionID = ?
            ORDER BY td.ProductID
        """, (o['TransactionID'],))
        item_cols = [c[0] for c in cursor.description]
        o['items'] = [dict(zip(item_cols, r)) for r in cursor.fetchall()]

    return render_template('customer_orders.html', orders=orders)

@app.route('/customer/orders/json')
@with_db
def customer_orders_json(cursor, conn):
    if 'user_id' not in session or session.get('role') != 'customer':
        return jsonify({"error": "Unauthorized"}), 401

    customer_id = session['user_id']

    # Get filter parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status = request.args.get('status')
    min_amount = request.args.get('min_amount')
    max_amount = request.args.get('max_amount')
    keyword = request.args.get('keyword', '').strip()

    query = """
        SELECT
            st.TransactionID,
            st.TransactionDate,
            COALESCE(st.TotalAmount, 0) AS TotalAmount,
            COALESCE(st.OrderStatus, '') AS OrderStatus,
            COALESCE(st.PaymentMethod, '') AS PaymentMethod,
            COALESCE(st.OrderDiscount, 0) AS OrderDiscount,
            COALESCE(st.ShippingAddress, '') AS ShippingAddress
        FROM SalesTransaction st
        WHERE st.CustomerID = ?
    """
    params = [customer_id]

    # Dynamic filters
    if start_date:
        query += " AND st.TransactionDate >= ?"
        params.append(start_date)
    if end_date:
        query += " AND st.TransactionDate <= ?"
        params.append(end_date)
    if status:
        query += " AND st.OrderStatus = ?"
        params.append(status)
    if min_amount:
        query += " AND COALESCE(st.TotalAmount,0) >= ?"
        params.append(min_amount)
    if max_amount:
        query += " AND COALESCE(st.TotalAmount,0) <= ?"
        params.append(max_amount)

    query += " ORDER BY st.TransactionDate DESC"

    cursor.execute(query, tuple(params))
    cols = [c[0] for c in cursor.description]
    orders = [dict(zip(cols, r)) for r in cursor.fetchall()]

    # Fetch items for each order and apply keyword filtering
    for o in orders:
        cursor.execute("""
            SELECT td.ProductID, p.Name, td.Quantity, p.Price, (td.Quantity * p.Price) AS Subtotal
            FROM Transaction_Details td
            JOIN Product p ON p.ProductID = td.ProductID
            WHERE td.TransactionID = ?
        """, (o['TransactionID'],))
        item_cols = [c[0] for c in cursor.description]
        items = [dict(zip(item_cols, r)) for r in cursor.fetchall()]

        # Filter items by keyword
        if keyword:
            items = [it for it in items if keyword.lower() in it['Name'].lower()]

        o['items'] = items
        # Recalculate total amount based on filtered items
        o['TotalAmount'] = sum(it['Subtotal'] or 0 for it in items)

    orders = [o for o in orders if o['items']]

    return jsonify(orders)

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

@app.route('/customer/orders/<int:transaction_id>/items')
@with_db
def customer_order_items_json(cursor, conn, transaction_id):
    if 'user_id' not in session or session.get('role') != 'customer':
        return jsonify({"error": "Unauthorized"}), 401

    customer_id = session['user_id']

    # Get items for this transaction
    cursor.execute("""
        SELECT
            td.ProductID,
            p.Name,
            td.Quantity,
            p.Price AS UnitPrice,
            (td.Quantity * p.Price) AS Subtotal
        FROM Transaction_Details td
        JOIN Product p ON p.ProductID = td.ProductID
        JOIN SalesTransaction st ON st.TransactionID = td.TransactionID
        WHERE td.TransactionID = ? AND st.CustomerID = ?
        ORDER BY td.ProductID
    """, (transaction_id, customer_id))

    cols = [c[0] for c in cursor.description]
    items = [dict(zip(cols, r)) for r in cursor.fetchall()]

    return jsonify(items)

@app.route('/department')
@with_db
def department(cursor, conn):
    # Restrict access to admin and employee only
    if 'user_id' not in session or session.get('role') not in ('admin', 'employee'):
        return redirect(url_for('login'))

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

@app.get("/api/bag")
@with_db
def api_get_bag(cursor, conn):
    owner = get_bag_owner_from_session()
    if not owner:
        return jsonify({"message": "Login required"}), 401

    if owner['CustomerID'] is not None:
        cursor.execute("""
            SELECT b.BagID, b.ProductID, p.Name, p.Price, b.Quantity, b.AddedAt
            FROM dbo.Bag b
            JOIN dbo.Product p ON p.ProductID = b.ProductID
            WHERE b.CustomerID = ? AND b.EmployeeID IS NULL
            ORDER BY b.AddedAt DESC
        """, (owner['CustomerID'],))
    else:
        cursor.execute("""
            SELECT b.BagID, b.ProductID, p.Name, p.Price, b.Quantity, b.AddedAt
            FROM dbo.Bag b
            JOIN dbo.Product p ON p.ProductID = b.ProductID
            WHERE b.EmployeeID = ? AND b.CustomerID IS NULL
            ORDER BY b.AddedAt DESC
        """, (owner['EmployeeID'],))

    rows = cursor.fetchall()
    cols = [c[0] for c in cursor.description]
    return jsonify([dict(zip(cols, r)) for r in rows])


@app.post("/api/bag")
@with_db
def api_add_to_bag(cursor, conn):
    payload = request.get_json(silent=True) or {}
    try:
        pid = int(payload.get("product_id") or 0)
        qty = int(payload.get("quantity") or 1)
    except Exception:
        return jsonify({"message": "Bad item"}), 400
    if pid <= 0 or qty <= 0:
        return jsonify({"message": "Bad item"}), 400

    owner = get_bag_owner_from_session()
    if not owner:
        return jsonify({"message": "Login required"}), 401

    if owner['CustomerID'] is not None:
        cursor.execute("""
            MERGE dbo.Bag AS target
            USING (SELECT ? AS CustomerID, ? AS ProductID) AS src
            ON target.CustomerID = src.CustomerID
               AND target.ProductID = src.ProductID
               AND target.EmployeeID IS NULL
            WHEN MATCHED THEN UPDATE SET Quantity = target.Quantity + ?
            WHEN NOT MATCHED THEN
                INSERT (CustomerID, EmployeeID, ProductID, Quantity)
                VALUES (src.CustomerID, NULL, src.ProductID, ?);
        """, (owner['CustomerID'], pid, qty, qty))
    else:
        cursor.execute("""
            MERGE dbo.Bag AS target
            USING (SELECT ? AS EmployeeID, ? AS ProductID) AS src
            ON target.EmployeeID = src.EmployeeID
               AND target.ProductID = src.ProductID
               AND target.CustomerID IS NULL
            WHEN MATCHED THEN UPDATE SET Quantity = target.Quantity + ?
            WHEN NOT MATCHED THEN
                INSERT (CustomerID, EmployeeID, ProductID, Quantity)
                VALUES (NULL, src.EmployeeID, src.ProductID, ?);
        """, (owner['EmployeeID'], pid, qty, qty))

    conn.commit()
    return jsonify({"message": "Added"}), 201


@app.patch("/api/bag/<int:bag_id>")
@with_db
def api_set_bag_qty(cursor, conn, bag_id):
    payload = request.get_json(silent=True) or {}
    try:
        qty = int(payload.get("quantity") or 0)
    except Exception:
        return jsonify({"message": "Bad quantity"}), 400
    if qty < 0:
        return jsonify({"message": "Bad quantity"}), 400

    owner = get_bag_owner_from_session()
    if not owner:
        return jsonify({"message": "Login required"}), 401

    if owner['CustomerID'] is not None:
        cursor.execute("""
            UPDATE dbo.Bag SET Quantity = ?
            WHERE BagID = ? AND CustomerID = ? AND EmployeeID IS NULL
        """, (qty, bag_id, owner['CustomerID']))
    else:
        cursor.execute("""
            UPDATE dbo.Bag SET Quantity = ?
            WHERE BagID = ? AND EmployeeID = ? AND CustomerID IS NULL
        """, (qty, bag_id, owner['EmployeeID']))

    if cursor.rowcount == 0:
        return jsonify({"message": "Not found"}), 404
    conn.commit()
    return jsonify({"message": "Updated"})


@app.delete("/api/bag/<int:bag_id>")
@with_db
def api_delete_bag_item(cursor, conn, bag_id):
    owner = get_bag_owner_from_session()
    if not owner:
        return jsonify({"message": "Login required"}), 401

    if owner['CustomerID'] is not None:
        cursor.execute("""
            DELETE FROM dbo.Bag
            WHERE BagID = ? AND CustomerID = ? AND EmployeeID IS NULL
        """, (bag_id, owner['CustomerID']))
    else:
        cursor.execute("""
            DELETE FROM dbo.Bag
            WHERE BagID = ? AND EmployeeID = ? AND CustomerID IS NULL
        """, (bag_id, owner['EmployeeID']))

    if cursor.rowcount == 0:
        return jsonify({"message": "Not found"}), 404
    conn.commit()
    return jsonify({"message": "Deleted"})

@app.delete("/api/bag")
@with_db
def api_clear_bag(cursor, conn):
    owner = get_bag_owner_from_session()
    if not owner:
        return jsonify({"message": "Login required"}), 401

    if owner['CustomerID'] is not None:
        cursor.execute("DELETE FROM dbo.Bag WHERE CustomerID = ? AND EmployeeID IS NULL",
                       (owner['CustomerID'],))
    else:
        cursor.execute("DELETE FROM dbo.Bag WHERE EmployeeID = ? AND CustomerID IS NULL",
                       (owner['EmployeeID'],))
    conn.commit()
    return jsonify({"message": "Cleared"})

# ---------- Shopping Lists ----------

def _require_customer():
    if session.get('role') != 'customer':
        return None
    return session['user_id']

def _ensure_default_list(cursor, conn, customer_id):
    cursor.execute("SELECT ListID FROM dbo.ShoppingList WHERE CustomerID=? AND IsDefault=1", (customer_id,))
    row = cursor.fetchone()
    if row:
        return int(row[0])

    cursor.execute("""
        INSERT INTO dbo.ShoppingList (CustomerID, Name, IsDefault, CreatedAt)
        OUTPUT Inserted.ListID
        VALUES (?, N'Default', 1, GETDATE())
    """, (customer_id,))
    new_id = int(cursor.fetchone()[0])
    conn.commit()
    return new_id

@app.get('/shopping-lists', endpoint='shopping_lists')
@with_db
def shopping_lists_page(cursor, conn):
    user = None
    if 'user_id' in session:
        role = session.get('role')
        if role == 'customer':
            cursor.execute("SELECT Name FROM Customer WHERE CustomerID=?", (session['user_id'],))
            r = cursor.fetchone()
            if r: user = {'Name': r[0], 'role': 'customer'}
        elif role == 'admin':
            cursor.execute("SELECT Name FROM Administrator WHERE AdminID=?", (session['user_id'],))
            r = cursor.fetchone()
            if r: user = {'Name': r[0], 'role': 'admin'}
        elif role == 'employee':
            cursor.execute("SELECT Name FROM Employee WHERE EmployeeID=?", (session['user_id'],))
            r = cursor.fetchone()
            if r: user = {'Name': r[0], 'role': 'employee'}
    return render_template('shopping_lists.html', user=user)

@app.get('/api/lists')
@with_db
def api_lists_all(cursor, conn):
    cid = _require_customer()
    if not cid: return jsonify({"message":"Login required"}), 401
    _ensure_default_list(cursor, conn, cid)
    cursor.execute("""
        SELECT 
            l.ListID, l.Name, l.IsDefault,
            ISNULL(SUM(i.Quantity), 0) AS ItemCount,
            MIN(l.CreatedAt) AS CreatedAt
        FROM dbo.ShoppingList l
        LEFT JOIN dbo.ShoppingListItem i ON i.ListID = l.ListID
        WHERE l.CustomerID = ?
        GROUP BY l.ListID, l.Name, l.IsDefault
        ORDER BY l.IsDefault DESC, CreatedAt ASC
    """, (cid,))
    return jsonify(rows_to_dict_list(cursor))

@app.post('/api/lists')
@with_db
def api_lists_create(cursor, conn):
    cid = _require_customer()
    if not cid: return jsonify({"message":"Login required"}), 401
    name = (request.get_json(silent=True) or {}).get('name')
    if not name or not str(name).strip():
        return jsonify({"message":"Name required"}), 400
    name = str(name).strip()
    _ensure_default_list(cursor, conn, cid)
    cursor.execute("INSERT INTO dbo.ShoppingList(CustomerID, Name, IsDefault, CreatedAt) VALUES(?, ?, 0, GETDATE())", (cid, name))
    conn.commit()
    return jsonify({"message":"Created"})

@app.delete('/api/lists/<int:list_id>')
@with_db
def api_lists_delete(cursor, conn, list_id):
    cid = _require_customer()
    if not cid: return jsonify({"message":"Login required"}), 401
    cursor.execute("SELECT IsDefault FROM dbo.ShoppingList WHERE ListID=? AND CustomerID=?", (list_id, cid))
    row = cursor.fetchone()
    if not row: return jsonify({"message":"Not found"}), 404
    if row[0]: return jsonify({"message":"Default list cannot be deleted"}), 400
    cursor.execute("DELETE FROM dbo.ShoppingListItem WHERE ListID=?", (list_id,))
    cursor.execute("DELETE FROM dbo.ShoppingList WHERE ListID=? AND CustomerID=?", (list_id, cid))
    conn.commit()
    return jsonify({"message":"Deleted"})

@app.get('/api/lists/<int:list_id>/items')
@with_db
def api_list_items(cursor, conn, list_id):
    cid = _require_customer()
    if not cid: return jsonify({"message":"Login required"}), 401
    cursor.execute("SELECT 1 FROM dbo.ShoppingList WHERE ListID=? AND CustomerID=?", (list_id, cid))
    if not cursor.fetchone(): return jsonify({"message":"Not found"}), 404
    cursor.execute("""
        SELECT i.ProductID, i.Quantity, p.Name, p.Price,
               CONVERT(VARCHAR(19), i.AddedAt, 120) AS AddedAt
        FROM dbo.ShoppingListItem i
        JOIN dbo.Product p ON p.ProductID=i.ProductID
        WHERE i.ListID=?
        ORDER BY i.AddedAt DESC
    """, (list_id,))
    return jsonify(rows_to_dict_list(cursor))

@app.post('/api/lists/<int:list_id>/items')
@with_db
def api_list_items_add(cursor, conn, list_id):
    cid = _require_customer()
    if not cid: return jsonify({"message":"Login required"}), 401
    cursor.execute("SELECT 1 FROM dbo.ShoppingList WHERE ListID=? AND CustomerID=?", (list_id, cid))
    if not cursor.fetchone(): return jsonify({"message":"Not found"}), 404
    body = request.get_json(silent=True) or {}
    try:
        pid = int(body.get('product_id') or 0)
        qty = int(body.get('quantity') or 1)
    except Exception:
        return jsonify({"message":"Bad payload"}), 400
    if pid<=0 or qty<=0: return jsonify({"message":"Bad payload"}), 400
    cursor.execute("""
        MERGE dbo.ShoppingListItem AS t
        USING (VALUES (?, ?, ?)) AS s(ListID, ProductID, Quantity)
        ON (t.ListID = s.ListID AND t.ProductID = s.ProductID)
        WHEN MATCHED THEN
          UPDATE SET Quantity = t.Quantity + s.Quantity, AddedAt = GETDATE()
        WHEN NOT MATCHED THEN
          INSERT (ListID, ProductID, Quantity, AddedAt)
          VALUES (s.ListID, s.ProductID, s.Quantity, GETDATE());
        """, (list_id, pid, qty))
    conn.commit()
    return jsonify({"message":"Added"})

@app.patch('/api/lists/<int:list_id>/items/<int:product_id>')
@with_db
def api_list_items_update(cursor, conn, list_id, product_id):
    cid = _require_customer()
    if not cid: return jsonify({"message":"Login required"}), 401
    cursor.execute("SELECT 1 FROM dbo.ShoppingList WHERE ListID=? AND CustomerID=?", (list_id, cid))
    if not cursor.fetchone(): return jsonify({"message":"Not found"}), 404
    body = request.get_json(silent=True) or {}
    try:
        qty = int(body.get('quantity'))
    except Exception:
        return jsonify({"message":"Bad quantity"}), 400
    if qty <= 0:
        cursor.execute("DELETE FROM dbo.ShoppingListItem WHERE ListID=? AND ProductID=?", (list_id, product_id))
    else:
        cursor.execute("UPDATE dbo.ShoppingListItem SET Quantity=? WHERE ListID=? AND ProductID=?", (qty, list_id, product_id))
    conn.commit()
    return jsonify({"message":"Updated"})

@app.delete('/api/lists/<int:list_id>/items/<int:product_id>')
@with_db
def api_list_items_delete(cursor, conn, list_id, product_id):
    cid = _require_customer()
    if not cid: return jsonify({"message":"Login required"}), 401
    cursor.execute("DELETE FROM dbo.ShoppingListItem WHERE ListID=? AND ProductID=?", (list_id, product_id))
    conn.commit()
    return jsonify({"message":"Removed"})

@app.delete('/api/lists/<int:list_id>/items')
@with_db
def api_list_items_clear(cursor, conn, list_id):
    cid = _require_customer()
    if not cid:
        return jsonify({"message": "Login required"}), 401
    cursor.execute("SELECT 1 FROM dbo.ShoppingList WHERE ListID=? AND CustomerID=?", (list_id, cid))
    if not cursor.fetchone():
        return jsonify({"message": "Not found"}), 404
    cursor.execute("DELETE FROM dbo.ShoppingListItem WHERE ListID=?", (list_id,))
    conn.commit()
    return jsonify({"message": "Cleared"})

@app.post('/api/lists/<int:list_id>/add-to-bag')
@with_db
def api_list_add_to_bag(cursor, conn, list_id):
    cid = _require_customer()
    if not cid:
        return jsonify({"message": "Login required"}), 401

    cursor.execute("SELECT 1 FROM dbo.ShoppingList WHERE ListID=? AND CustomerID=?", (list_id, cid))
    if not cursor.fetchone():
        return jsonify({"message": "Not found"}), 404

    cursor.execute("SELECT COUNT(*) FROM dbo.ShoppingListItem WHERE ListID=?", (list_id,))
    if int(cursor.fetchone()[0]) == 0:
        return jsonify({"message": "List is empty"}), 400

    cursor.execute("""
    MERGE dbo.Bag AS t
    USING (
        SELECT ? AS CustomerID, ProductID, SUM(Quantity) AS Quantity
        FROM dbo.ShoppingListItem
        WHERE ListID = ?
        GROUP BY ProductID
    ) AS s
    ON  t.CustomerID = s.CustomerID AND t.ProductID = s.ProductID
    WHEN MATCHED THEN
        UPDATE SET t.Quantity = t.Quantity + s.Quantity
    WHEN NOT MATCHED THEN
        INSERT (CustomerID, ProductID, Quantity)
        VALUES (s.CustomerID, s.ProductID, s.Quantity);
    """, (cid, list_id))

    cursor.execute("DELETE FROM dbo.ShoppingListItem WHERE ListID=?", (list_id,))

    conn.commit()
    return jsonify({"message": "Added to cart and cleared list"})

#DATA REPORTS theres three of them

@app.route('/employee_report')
@with_db
def employee_report(cursor, conn):
    # Fetch employees with revenue info
    cursor.execute("""
        SELECT 
            e.EmployeeID,
            e.Name,
            d.Name AS DepartmentName,
            e.JobTitle,
            e.HireDate,
            COALESCE(SUM(td.Quantity * p.Price), 0) AS TotalRevenue,
            COUNT(td.TransactionID) AS NumberOfSales,
            COALESCE(SUM(td.Quantity * p.Price)/NULLIF(COUNT(td.TransactionID),0), 0) AS AverageSaleValue
        FROM Employee e
        LEFT JOIN Department d ON e.DepartmentID = d.DepartmentID
        LEFT JOIN Transaction_Details td ON td.EmployeeID = e.EmployeeID
        LEFT JOIN Product p ON p.ProductID = td.ProductID
        WHERE e.IsActive = 1
        GROUP BY e.EmployeeID, e.Name, d.Name, e.JobTitle, e.HireDate
    """)
    employees = rows_to_dict_list(cursor)

    # Calculate average tenure
    total_days = 0
    valid_employees = []

    for e in employees:
        hire = e.get("HireDate")
        hire_date = None

        # Handle different types
        if isinstance(hire, datetime):
            hire_date = hire.date()
        elif isinstance(hire, date):
            hire_date = hire
        elif isinstance(hire, str):
            try:
                hire_date = datetime.strptime(hire[:10], "%Y-%m-%d").date()
            except ValueError:
                hire_date = None

        # Exclude placeholder or invalid dates (before 1901)
        if hire_date and hire_date.year > 1900:
            days_since_hire = (date.today() - hire_date).days
            e["DaysSinceHire"] = days_since_hire
            total_days += days_since_hire
            valid_employees.append(e)
        else:
            e["DaysSinceHire"] = None

    avg_tenure_years = round(total_days / len(valid_employees) / 365, 1) if valid_employees else 0

    # Fetch departments and job titles
    cursor.execute("SELECT Name FROM Department ORDER BY Name")
    departments = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT JobTitle FROM Employee ORDER BY JobTitle")
    job_titles = [row[0] for row in cursor.fetchall() if row[0]]

    return render_template(
        "employee_report.html",
        employees=employees,
        departments=departments,
        job_titles=job_titles,
        avg_tenure_years=avg_tenure_years
    )

@app.post("/api/employee_report")
@with_db
def employee_report_filter(cursor, conn):
    payload = request.get_json() or {}

    department = payload.get("department") or []
    job_title = payload.get("job_title")
    name = payload.get("name")
    hire_date_from = _iso_date(payload.get("hire_date_from"))
    hire_date_to = _iso_date(payload.get("hire_date_to"))

    # Revenue filtering
    revenue_min = payload.get("revenue_min")
    revenue_max = payload.get("revenue_max")
    try:
        revenue_min = float(revenue_min) if revenue_min not in [None, ""] else None
    except ValueError:
        revenue_min = None
    try:
        revenue_max = float(revenue_max) if revenue_max not in [None, ""] else None
    except ValueError:
        revenue_max = None

    # Sorting
    sort_column = payload.get("sort_column")
    sort_order = payload.get("sort_order", "asc").lower()

    allowed_columns = [
        "EmployeeID", "Name", "DepartmentName", "JobTitle",
        "HireDate", "TotalRevenue", "NumberOfSales", "AverageSaleValue"
    ]
    if sort_column not in allowed_columns:
        sort_column = "Name"
    if sort_order not in ["asc", "desc"]:
        sort_order = "asc"

    sql_parts = [
        "SELECT",
        "  e.EmployeeID,",
        "  e.Name,",
        "  d.Name AS DepartmentName,",
        "  e.JobTitle,",
        "  e.HireDate,",
        "  COALESCE(SUM(td.Quantity * p.Price), 0) AS TotalRevenue,",
        "  COUNT(td.TransactionID) AS NumberOfSales,",
        "  COALESCE(SUM(td.Quantity * p.Price)/NULLIF(COUNT(td.TransactionID),0), 0) AS AverageSaleValue",
        "FROM Employee e",
        "LEFT JOIN Department d ON e.DepartmentID = d.DepartmentID",
        "LEFT JOIN Transaction_Details td ON td.EmployeeID = e.EmployeeID",
        "LEFT JOIN Product p ON p.ProductID = td.ProductID",
        "WHERE e.IsActive = 1"
    ]

    params = []

    if department:
        placeholders = ",".join("?" for _ in department)
        sql_parts.append(f"AND d.Name IN ({placeholders})")
        params.extend(department)

    if job_title:
        sql_parts.append("AND e.JobTitle = ?")
        params.append(job_title)
    if name:
        sql_parts.append("AND e.Name LIKE ?")
        params.append(f"%{name}%")
    if hire_date_from:
        sql_parts.append("AND e.HireDate >= ?")
        params.append(hire_date_from)
    if hire_date_to:
        sql_parts.append("AND e.HireDate <= ?")
        params.append(hire_date_to)

    sql_parts.append("GROUP BY e.EmployeeID, e.Name, d.Name, e.JobTitle, e.HireDate")

    # HAVING clause for revenue
    having_clauses = []
    if revenue_min is not None:
        having_clauses.append("COALESCE(SUM(td.Quantity * p.Price), 0) >= ?")
        params.append(revenue_min)
    if revenue_max is not None:
        having_clauses.append("COALESCE(SUM(td.Quantity * p.Price), 0) <= ?")
        params.append(revenue_max)
    if having_clauses:
        sql_parts.append("HAVING " + " AND ".join(having_clauses))

    # Sorting
    sql_parts.append(f"ORDER BY {sort_column} {sort_order.upper()}")

    sql = "\n".join(sql_parts)
    cursor.execute(sql, params)
    rows = cursor.fetchall()

    html = ""
    for r in rows:
        html += "<tr>"
        for val in r:
            if isinstance(val, float):
                html += f"<td>${val:,.2f}</td>"
            elif isinstance(val, datetime):
                html += f"<td>{val.strftime('%Y-%m-%d')}</td>"
            else:
                html += f"<td>{val}</td>"
        html += "</tr>"

    return jsonify({"html": html})

@app.route('/product_report')
@with_db
def product_report(cursor, conn):
    # Fetch products as before
    cursor.execute("""
        SELECT 
            p.ProductID,
            p.Name AS ProductName,
            d.Name AS Department,
            p.Price,
            p.SalePrice,
            i.QuantityAvailable,
            CASE
                WHEN i.QuantityAvailable <= 0 THEN 'Out of Stock'
                WHEN i.QuantityAvailable <= i.ReorderLevel THEN 'Low Stock'
                ELSE 'In Stock'
            END AS StockStatus,
            i.ReorderLevel,
            i.LastRestockDate,
            CASE WHEN p.OnSale = 1 THEN 'Yes' ELSE 'No' END AS OnSale,
            ISNULL(SUM(td.Quantity * td.Price), 0) AS TotalRevenue,
            COUNT(td.TransactionID) AS NumberOfSales
        FROM Product p
        LEFT JOIN Department d ON p.DepartmentID = d.DepartmentID
        LEFT JOIN Inventory i ON p.ProductID = i.ProductID
        LEFT JOIN Transaction_Details td ON td.ProductID = p.ProductID
        GROUP BY 
            p.ProductID, p.Name, d.Name, p.Price, p.SalePrice, 
            i.QuantityAvailable, i.ReorderLevel, i.LastRestockDate, p.OnSale
        ORDER BY p.Name
    """)
    products = rows_to_dict_list(cursor)

    # Fetch all departments for the filter
    cursor.execute("SELECT Name FROM Department ORDER BY Name")
    departments = [row[0] for row in cursor.fetchall()]

    return render_template('product_report.html', products=products, departments=departments)

@app.post("/api/product_report")
@with_db
def product_report_filter(cursor, conn):
    payload = request.get_json() or {}

    department = payload.get("department")
    product_name = payload.get("product_name")
    stock_status = payload.get("stock_status")
    on_sale = payload.get("on_sale")
    min_price = payload.get("min_price")
    max_price = payload.get("max_price")
    qty_min = payload.get("qty_min")
    qty_max = payload.get("qty_max")
    restock_from = payload.get("restock_from")
    restock_to = payload.get("restock_to")

    sort_column = payload.get("sort_column")
    sort_direction = payload.get("sort_direction", "ASC").upper()

    allowed_columns = [
        "ProductID","ProductName","Department","Price","SalePrice",
        "QuantityAvailable","StockStatus","ReorderLevel",
        "LastRestockDate","OnSale","TotalRevenue","NumberOfSales"
    ]

    sql_parts = [
        "SELECT",
        "  p.ProductID,",
        "  p.Name AS ProductName,",
        "  d.Name AS Department,",
        "  p.Price,",
        "  p.SalePrice,",
        "  i.QuantityAvailable,",
        "  CASE",
        "      WHEN i.QuantityAvailable <= 0 THEN 'Out of Stock'",
        "      WHEN i.QuantityAvailable <= i.ReorderLevel THEN 'Low Stock'",
        "      ELSE 'In Stock'",
        "  END AS StockStatus,",
        "  i.ReorderLevel,",
        "  i.LastRestockDate,",
        "  CASE WHEN p.OnSale = 1 THEN 'Yes' ELSE 'No' END AS OnSale,",
        "  COALESCE(SUM(td.Quantity * td.Price), 0) AS TotalRevenue,",
        "  COUNT(td.TransactionID) AS NumberOfSales",
        "FROM Product p",
        "LEFT JOIN Department d ON p.DepartmentID = d.DepartmentID",
        "LEFT JOIN Inventory i ON p.ProductID = i.ProductID",
        "LEFT JOIN Transaction_Details td ON td.ProductID = p.ProductID",
        "WHERE 1=1"
    ]

    params = []

    # Filters
    # if department is a list
    if department:
        if isinstance(department, list):
            placeholders = ", ".join(["?"] * len(department))
            sql_parts.append(f"AND d.Name IN ({placeholders})")
            params.extend(department)
        else:
            sql_parts.append("AND d.Name = ?")
            params.append(department)

    if product_name:
        sql_parts.append("AND p.Name LIKE ?")
        params.append(f"%{product_name}%")

    if stock_status and stock_status.lower() != "all":
        if stock_status.lower() == "in stock":
            sql_parts.append("AND i.QuantityAvailable > i.ReorderLevel")
        elif stock_status.lower() == "low stock":
            sql_parts.append("AND i.QuantityAvailable <= i.ReorderLevel AND i.QuantityAvailable > 0")
        elif stock_status.lower() == "out of stock":
            sql_parts.append("AND i.QuantityAvailable <= 0")

    if on_sale and on_sale.lower() != "all":
        sql_parts.append("AND p.OnSale = ?")
        params.append(1 if on_sale.lower() == "yes" else 0)

    if min_price not in (None, ""):
        sql_parts.append("AND p.Price >= ?")
        params.append(float(min_price))
    if max_price not in (None, ""):
        sql_parts.append("AND p.Price <= ?")
        params.append(float(max_price))

    if qty_min not in (None, ""):
        sql_parts.append("AND i.QuantityAvailable >= ?")
        params.append(int(qty_min))
    if qty_max not in (None, ""):
        sql_parts.append("AND i.QuantityAvailable <= ?")
        params.append(int(qty_max))

    if restock_from not in (None, ""):
        sql_parts.append("AND i.LastRestockDate >= ?")
        params.append(restock_from)
    if restock_to not in (None, ""):
        sql_parts.append("AND i.LastRestockDate <= ?")
        params.append(restock_to)

    # Grouping
    sql_parts.append("""
        GROUP BY 
            p.ProductID, p.Name, d.Name, p.Price, p.SalePrice, 
            i.QuantityAvailable, i.ReorderLevel, i.LastRestockDate, p.OnSale
    """)

    # Sorting
    if sort_column in allowed_columns:
        sort_direction = "DESC" if sort_direction == "DESC" else "ASC"
        sql_parts.append(f"ORDER BY {sort_column} {sort_direction}")
    else:
        sql_parts.append("ORDER BY p.Name ASC")  # default sort

    sql = "\n".join(sql_parts)
    cursor.execute(sql, params)
    rows = cursor.fetchall()

    html = ""
    for r in rows:
        html += "<tr>"
        for val in r:
            if isinstance(val, float):
                html += f"<td>${val:,.2f}</td>"
            elif isinstance(val, datetime):
                html += f"<td>{val.strftime('%Y-%m-%d')}</td>"
            else:
                html += f"<td>{val}</td>"
        html += "</tr>"

    return jsonify({"html": html})

@app.route('/api/product_kpis')
@with_db
def product_kpis(cursor, conn):
    # Top 3 most sold products (by number of sales)
    cursor.execute("""
        SELECT TOP 3 p.Name, COUNT(td.TransactionID) AS NumberOfSales
        FROM Product p
        LEFT JOIN Transaction_Details td ON td.ProductID = p.ProductID
        GROUP BY p.Name
        ORDER BY NumberOfSales DESC
    """)
    top_sold = cursor.fetchall()

    # Bottom 3 slow-moving products (fewest sales, but at least 1 sale)
    cursor.execute("""
        SELECT TOP 3 p.Name, COUNT(td.TransactionID) AS NumberOfSales
        FROM Product p
        LEFT JOIN Transaction_Details td ON td.ProductID = p.ProductID
        GROUP BY p.Name
        HAVING COUNT(td.TransactionID) > 0
        ORDER BY NumberOfSales ASC
    """)
    slow_moving = cursor.fetchall()

    # Products low in stock (QuantityAvailable <= ReorderLevel)
    cursor.execute("""
        SELECT TOP 3 p.Name, i.QuantityAvailable, i.ReorderLevel
        FROM Product p
        JOIN Inventory i ON i.ProductID = p.ProductID
        WHERE i.QuantityAvailable <= i.ReorderLevel
        ORDER BY i.QuantityAvailable ASC
    """)
    low_stock = cursor.fetchall()

    return jsonify({
        "top_sold": [{"name": r[0], "sales": r[1]} for r in top_sold],
        "slow_moving": [{"name": r[0], "sales": r[1]} for r in slow_moving],
        "low_stock": [{"name": r[0], "qty": r[1], "reorder": r[2]} for r in low_stock]
    })

@app.route('/customer_report')
@with_db
def customer_report(cursor, conn):
    cursor.execute("""
        SELECT
            c.CustomerID,
            c.Name,
            c.Email,
            COUNT(DISTINCT st.TransactionID) AS TotalPurchases,
            COALESCE(SUM(st.TotalAmount), 0) AS TotalSpent,
            
            -- Favorite product
            COALESCE((
                SELECT TOP 1 p.Name
                FROM Transaction_Details td2
                JOIN Product p ON td2.ProductID = p.ProductID
                JOIN SalesTransaction st2 ON td2.TransactionID = st2.TransactionID
                WHERE st2.CustomerID = c.CustomerID
                GROUP BY p.ProductID, p.Name
                ORDER BY SUM(td2.Quantity) DESC
            ), 'N/A') AS FavoriteProduct,
            
            -- Recent purchase (correlated subquery)
            COALESCE((
                SELECT TOP 1 CONVERT(VARCHAR, st2.TransactionDate, 23)
                FROM SalesTransaction st2
                WHERE st2.CustomerID = c.CustomerID
                ORDER BY st2.TransactionDate DESC
            ), 'N/A') AS RecentPurchaseDate,
            
            -- Largest single order per customer
            COALESCE((
                SELECT MAX(st2.TotalAmount)
                FROM SalesTransaction st2
                WHERE st2.CustomerID = c.CustomerID
            ), 0) AS LargestSingleOrder,
            
            -- Most purchased category (using Department)
            COALESCE((
                SELECT TOP 1 d.Name
                FROM Transaction_Details td2
                JOIN Product p ON td2.ProductID = p.ProductID
                JOIN Department d ON p.DepartmentID = d.DepartmentID
                JOIN SalesTransaction st2 ON td2.TransactionID = st2.TransactionID
                WHERE st2.CustomerID = c.CustomerID
                GROUP BY d.Name
                ORDER BY SUM(td2.Quantity) DESC
            ), 'N/A') AS MostPurchasedCategory

        FROM Customer c
        LEFT JOIN SalesTransaction st ON c.CustomerID = st.CustomerID
        GROUP BY c.CustomerID, c.Name, c.Email
        ORDER BY c.Name
    """)
    customers = rows_to_dict_list(cursor)

    # Compute overall largest single order across all customers
    overall_largest_order = max(c['LargestSingleOrder'] for c in customers) if customers else 0

    return render_template(
        'customer_report.html',
        customers=customers,
        overall_largest_order=overall_largest_order
    )

@app.post("/api/customer_report")
@with_db
def customer_report_filter(cursor, conn):
    payload = request.get_json() or {}

    customer_name = payload.get("customer_name")
    email = payload.get("email")
    date_from = payload.get("date_from")
    date_to = payload.get("date_to")
    total_spent_min = payload.get("total_spent_min")
    total_spent_max = payload.get("total_spent_max")
    sort_column = payload.get("sort_column")
    sort_direction = payload.get("sort_direction", "asc").upper()
    total_purchases_min = payload.get("total_purchases_min")
    total_purchases_max = payload.get("total_purchases_max")

    sql_parts = [
        "SELECT",
        "  c.CustomerID,",
        "  c.Name,",
        "  c.Email,",
        "  COUNT(DISTINCT st.TransactionID) AS TotalPurchases,",
        "  COALESCE(SUM(st.TotalAmount), 0) AS TotalSpent,",
        "  COALESCE((SELECT TOP 1 p.Name",
        "           FROM Transaction_Details td2",
        "           JOIN Product p ON td2.ProductID = p.ProductID",
        "           JOIN SalesTransaction st2 ON td2.TransactionID = st2.TransactionID",
        "           WHERE st2.CustomerID = c.CustomerID",
        "           GROUP BY p.ProductID, p.Name",
        "           ORDER BY SUM(td2.Quantity) DESC), 'N/A') AS FavoriteProduct,",
        "  COALESCE((SELECT TOP 1 CONVERT(VARCHAR, st2.TransactionDate, 23)",
        "           FROM SalesTransaction st2",
        "           WHERE st2.CustomerID = c.CustomerID",
        "           ORDER BY st2.TransactionDate DESC), 'N/A') AS RecentPurchaseDate,",
        "  COALESCE((SELECT MAX(st2.TotalAmount)",
        "           FROM SalesTransaction st2",
        "           WHERE st2.CustomerID = c.CustomerID), 0) AS LargestSingleOrder,",
        "  COALESCE((SELECT TOP 1 d.Name",
        "           FROM Transaction_Details td2",
        "           JOIN Product p ON td2.ProductID = p.ProductID",
        "           JOIN Department d ON p.DepartmentID = d.DepartmentID",
        "           JOIN SalesTransaction st2 ON td2.TransactionID = st2.TransactionID",
        "           WHERE st2.CustomerID = c.CustomerID",
        "           GROUP BY d.Name",
        "           ORDER BY SUM(td2.Quantity) DESC), 'N/A') AS MostPurchasedCategory",
        "FROM Customer c",
        "LEFT JOIN SalesTransaction st ON c.CustomerID = st.CustomerID",
        "WHERE 1=1"
    ]

    params = []

    if customer_name:
        sql_parts.append("AND c.Name LIKE ?")
        params.append(f"%{customer_name}%")
    if email:
        sql_parts.append("AND c.Email LIKE ?")
        params.append(f"%{email}%")
    if date_from:
        sql_parts.append("AND st.TransactionDate >= ?")
        params.append(date_from)
    if date_to:
        sql_parts.append("AND st.TransactionDate <= ?")
        params.append(date_to)

    sql_parts.append("GROUP BY c.CustomerID, c.Name, c.Email")

    having_conditions = []
    if total_spent_min:
        having_conditions.append("COALESCE(SUM(st.TotalAmount), 0) >= ?")
        params.append(float(total_spent_min))
    if total_spent_max:
        having_conditions.append("COALESCE(SUM(st.TotalAmount), 0) <= ?")
        params.append(float(total_spent_max))
    if total_purchases_min:
        having_conditions.append("COUNT(DISTINCT st.TransactionID) >= ?")
        params.append(int(total_purchases_min))
    if total_purchases_max:
        having_conditions.append("COUNT(DISTINCT st.TransactionID) <= ?")
        params.append(int(total_purchases_max))

    if having_conditions:
        sql_parts.append("HAVING " + " AND ".join(having_conditions))

    allowed_columns = ["CustomerID","Name","Email","TotalPurchases","TotalSpent",
                       "FavoriteProduct","RecentPurchaseDate","LargestSingleOrder","MostPurchasedCategory"]
    if sort_column in allowed_columns:
        direction = "DESC" if sort_direction == "DESC" else "ASC"
        sql_parts.append(f"ORDER BY {sort_column} {direction}")
    else:
        sql_parts.append("ORDER BY c.Name ASC")

    sql = "\n".join(sql_parts)
    cursor.execute(sql, params)
    rows = rows_to_dict_list(cursor)

    html = ""
    for r in rows:
        html += "<tr>"
        html += f"<td>{r['CustomerID'] or 'N/A'}</td>"
        html += f"<td>{r['Name'] or 'N/A'}</td>"
        html += f"<td>{r['Email'] or 'N/A'}</td>"
        html += f"<td>{r['TotalPurchases'] or 0}</td>"
        html += f"<td>${r['TotalSpent']:.2f}</td>"
        html += f"<td>{r['FavoriteProduct'] or 'N/A'}</td>"
        html += f"<td>{r['RecentPurchaseDate'] or 'N/A'}</td>"
        html += f"<td>${r['LargestSingleOrder']:.2f}</td>"
        html += f"<td>{r['MostPurchasedCategory'] or 'N/A'}</td>"
        html += "</tr>"

    return jsonify({"html": html})

@app.route('/revenue_report')
@with_db
def revenue_report(cursor, conn):
    # Fetch initial revenue transactions
    cursor.execute("""
        SELECT st.TransactionID, st.TransactionDate, c.Name AS CustomerName,
            st.PaymentMethod, st.OrderStatus, st.TotalAmount
        FROM SalesTransaction st
        LEFT JOIN Customer c ON st.CustomerID = c.CustomerID
        ORDER BY st.TransactionDate DESC
    """)
    rows = cursor.fetchall()

    transactions = []
    for r in rows:
        transaction_date = r[1]
        if isinstance(transaction_date, str):
            # sometimes already string
            date_str = transaction_date.split("T")[0]
        else:
            date_str = transaction_date.strftime("%Y-%m-%d")

        transactions.append({
            "TransactionID": r[0],
            "TransactionDate": date_str,
            "CustomerName": r[2],
            "PaymentMethod": r[3],
            "OrderStatus": r[4],
            "TotalAmount": r[5]
        })

    # Fetch unique payment methods and order statuses for filters
    cursor.execute("SELECT DISTINCT PaymentMethod FROM SalesTransaction")
    payment_methods = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT OrderStatus FROM SalesTransaction")
    order_statuses = [row[0] for row in cursor.fetchall()]

    # Fetch departments for department filter
    cursor.execute("SELECT Name FROM Department ORDER BY Name")
    departments = [row[0] for row in cursor.fetchall()]

    return render_template(
        'revenue_report.html',
        transactions=transactions,
        payment_methods=payment_methods,
        order_statuses=order_statuses,
        departments=departments
    )

@app.post("/api/revenue_report")
@with_db
def revenue_report_filter(cursor, conn):
    payload = request.get_json() or {}
    start_date = payload.get("start_date")
    end_date = payload.get("end_date")
    payment_method = payload.get("payment_method")
    order_status = payload.get("order_status")

    sql_parts = [
        "SELECT st.TransactionID, st.TransactionDate, c.Name AS CustomerName,",
        "st.PaymentMethod, st.OrderStatus, st.TotalAmount",
        "FROM SalesTransaction st",
        "LEFT JOIN Customer c ON st.CustomerID = c.CustomerID",
        "WHERE 1=1"
    ]
    params = []

    # Filters
    if start_date:
        sql_parts.append("AND st.TransactionDate >= ?")
        params.append(start_date)
    if end_date:
        # Convert to datetime and add 1 day for inclusive comparison
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        sql_parts.append("AND st.TransactionDate < ?")
        params.append(end_dt.strftime("%Y-%m-%d"))
    if payment_method and payment_method.lower() != "all":
        sql_parts.append("AND st.PaymentMethod = ?")
        params.append(payment_method)
    if order_status and order_status.lower() != "all":
        sql_parts.append("AND st.OrderStatus = ?")
        params.append(order_status)

    # Sorting
    sort_column = payload.get("sort_column", "TransactionDate")
    sort_direction = "DESC" if payload.get("sort_direction", "DESC").upper() == "DESC" else "ASC"
    sql_parts.append(f"ORDER BY {sort_column} {sort_direction}")

    sql = "\n".join(sql_parts)
    cursor.execute(sql, params)
    rows = cursor.fetchall()

    # Calculate KPIs
    total_revenue = sum(r[5] for r in rows)
    total_orders = len(rows)
    avg_order_value = total_revenue / total_orders if total_orders else 0

    # Build transactions list
    transactions = []
    for r in rows:
        transaction_date = r[1]
        if isinstance(transaction_date, str):
            transaction_date = datetime.strptime(transaction_date, "%Y-%m-%d")
        transactions.append({
            "TransactionID": r[0],
            "TransactionDate": transaction_date.strftime("%Y-%m-%d"),
            "CustomerName": r[2],
            "PaymentMethod": r[3],
            "OrderStatus": r[4],
            "TotalAmount": r[5]
        })

    return jsonify({
        "transactions": transactions,
        "totalRevenue": total_revenue,
        "totalOrders": total_orders,
        "avgOrderValue": avg_order_value
    })

@app.post("/api/revenue_report_chart")
@with_db
def revenue_report_chart(cursor, conn):
    payload = request.get_json() or {}
    departments = payload.get("departments", [])

    # Default dates
    start_date = payload.get("start_date")
    if not start_date:
        today = datetime.today()
        start_date = datetime(today.year, today.month, 1).date()
    end_date = payload.get("end_date") or datetime.today().date()

    sql_parts = [
        "SELECT d.Name AS Department, CAST(st.TransactionDate AS DATE) AS TransactionDate,",
        "SUM(td.Subtotal) AS Revenue",
        "FROM SalesTransaction st",
        "LEFT JOIN Transaction_Details td ON st.TransactionID = td.TransactionID",
        "LEFT JOIN Product p ON td.ProductID = p.ProductID",
        "LEFT JOIN Department d ON p.DepartmentID = d.DepartmentID",
        "WHERE st.OrderStatus = 'Completed'",
        "AND CAST(st.TransactionDate AS DATE) BETWEEN ? AND ?"
    ]
    params = [start_date, end_date]

    if departments:
        placeholders = ",".join("?" for _ in departments)
        sql_parts.append(f"AND d.Name IN ({placeholders})")
        params.extend(departments)

    sql_parts.append("GROUP BY d.Name, CAST(st.TransactionDate AS DATE)")
    sql_parts.append("ORDER BY TransactionDate ASC")
    sql = "\n".join(sql_parts)

    try:
        cursor.execute(sql, params)
        rows = cursor.fetchall()
    except Exception as e:
        print("DB error:", e)
        return jsonify({"error": str(e)}), 500

    # Build department data
    department_data = defaultdict(lambda: defaultdict(float))
    all_dates = set()
    for dept, date_val, revenue in rows:
        department_data[dept][date_val.strftime("%Y-%m-%d")] += float(revenue)
        all_dates.add(date_val.strftime("%Y-%m-%d"))

    sorted_dates = sorted(all_dates)

    # Build Chart.js datasets
    colors = ["#2ecc71", "#e74c3c", "#3498db", "#9b59b6", "#f1c40f", "#1abc9c", "#e67e22"]
    datasets = []
    for i, (dept, revenue_by_date) in enumerate(department_data.items()):
        data = [revenue_by_date.get(d, 0) for d in sorted_dates]
        datasets.append({
            "department": dept,
            "color": colors[i % len(colors)],
            "data": data
        })

    return jsonify({
        "labels": sorted_dates,
        "datasets": datasets
    })

@app.post("/checkout")
@with_db
def checkout(cursor, conn):
    payload = request.get_json(silent=True) or {}
    items = payload.get("items") or []
    if not items:
        owner = get_bag_owner_from_session()
        if not owner:
            return jsonify({"message": "Login required"}), 401

        if owner['CustomerID'] is not None:
            cursor.execute("""
                SELECT ProductID, Quantity
                FROM dbo.Bag
                WHERE CustomerID = ? AND EmployeeID IS NULL
            """, (owner['CustomerID'],))
        else:
            cursor.execute("""
                SELECT ProductID, Quantity
                FROM dbo.Bag
                WHERE EmployeeID = ? AND CustomerID IS NULL
            """, (owner['EmployeeID'],))

        rows = cursor.fetchall()
        items = [{"product_id": int(r[0]), "quantity": int(r[1])} for r in rows]

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
                CustomerID, TransactionDate, TotalAmount, PaymentMethod, OrderStatus
            )
            OUTPUT INSERTED.TransactionID
            VALUES (?, GETDATE(), ?, ?, ?)
        """, (cust_id, grand_total, 'Cash', 'Completed'))
        new_tid = cursor.fetchone()[0]

        for pid, qty, price, subtotal in line_items:
            cursor.execute("""
                INSERT INTO Transaction_Details (TransactionID, ProductID, Quantity, Price, EmployeeID)
                VALUES (?, ?, ?, ?, ?)
            """, (new_tid, pid, qty, price, emp_id)) 
            cursor.execute("""
                UPDATE Product
                SET QuantityInStock = QuantityInStock - ?
                WHERE ProductID = ?
            """, (qty, pid))

        if cust_id is not None:
            cursor.execute("DELETE FROM dbo.Bag WHERE CustomerID = ? AND EmployeeID IS NULL",
                           (cust_id,))
        elif emp_id is not None:
            cursor.execute("DELETE FROM dbo.Bag WHERE EmployeeID = ? AND CustomerID IS NULL",
                           (emp_id,))

        conn.commit()
        conn.autocommit = autocommit_backup
        return jsonify({"transaction_id": new_tid, "total_amount": grand_total}), 201

    except Exception as e:
        print("DB error (/checkout):", e)
        traceback.print_exc()
        conn.rollback()
        conn.autocommit = autocommit_backup
        return jsonify({"message": f"Database error: {str(e)}"}), 500
@app.route('/api/notifications')
@with_db
def get_notifications(cursor, conn):
    """Get all pending reorder alerts for admins and employees"""
    if 'role' not in session or session.get('role') not in ['admin', 'employee']:
        return jsonify({"message": "Unauthorized"}), 403

    try:
        cursor.execute("""
            SELECT AlertID, ProductID, ProductName, CurrentStock, ReorderLevel, AlertDate, AlertStatus
            FROM Reorder_Alerts
            WHERE AlertStatus = 'PENDING'
            ORDER BY AlertDate DESC
        """)
        alerts = rows_to_dict_list(cursor)

        # Format the notifications
        notifications = []
        for alert in alerts:
            notifications.append({
                'id': alert['AlertID'],
                'type': 'low_stock',
                'productId': alert['ProductID'],
                'productName': alert['ProductName'],
                'currentStock': alert['CurrentStock'],
                'reorderLevel': alert['ReorderLevel'],
                'message': f"Low stock alert: {alert['ProductName']} has only {alert['CurrentStock']} units left (reorder at {alert['ReorderLevel']})",
                'timestamp': alert['AlertDate'].isoformat() if alert['AlertDate'] else None,
                'status': alert['AlertStatus']
            })

        return jsonify({'notifications': notifications, 'count': len(notifications)}), 200
    except Exception as e:
        print(f"Error fetching notifications: {e}")
        traceback.print_exc()
        return jsonify({"message": "Error fetching notifications"}), 500

@app.route('/api/notifications/<int:alert_id>/dismiss', methods=['POST'])
@with_db
def dismiss_notification(cursor, conn, alert_id):
    """Mark a notification as dismissed"""
    if 'role' not in session or session.get('role') not in ['admin', 'employee']:
        return jsonify({"message": "Unauthorized"}), 403

    try:
        cursor.execute("""
            UPDATE Reorder_Alerts
            SET AlertStatus = 'DISMISSED'
            WHERE AlertID = ?
        """, (alert_id,))
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "Notification not found"}), 404

        return jsonify({"message": "Notification dismissed"}), 200
    except Exception as e:
        print(f"Error dismissing notification: {e}")
        return jsonify({"message": "Error dismissing notification"}), 500

@app.route('/api/notifications/dismiss-all', methods=['POST'])
@with_db
def dismiss_all_notifications(cursor, conn):
    """Mark all pending notifications as dismissed"""
    if 'role' not in session or session.get('role') not in ['admin', 'employee']:
        return jsonify({"message": "Unauthorized"}), 403

    try:
        cursor.execute("""
            UPDATE Reorder_Alerts
            SET AlertStatus = 'DISMISSED'
            WHERE AlertStatus = 'PENDING'
        """)
        conn.commit()

        return jsonify({"message": f"{cursor.rowcount} notifications dismissed"}), 200
    except Exception as e:
        print(f"Error dismissing all notifications: {e}")
        return jsonify({"message": "Error dismissing notifications"}), 500

@app.route('/receipts_report')
@with_db
def receipts_report(cursor, conn):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    start_date = request.args.get('date_from') or None
    end_date = request.args.get('date_to') or None
    payment_method = request.args.get('payment_method') or None
    order_status = request.args.get('order_status') or None
    employee_id = request.args.get('employee_id') or None

    sql = """
        SELECT
            st.TransactionID,
            st.TransactionDate,
            COALESCE(c.Name, 'Guest / In-store') AS CustomerName,
            COALESCE(e.Name, 'N/A') AS EmployeeName,
            COALESCE(st.PaymentMethod, '') AS PaymentMethod,
            COALESCE(st.OrderStatus, '') AS OrderStatus,
            COALESCE(st.OrderDiscount, 0) AS OrderDiscount,
            COALESCE(st.TotalAmount, 0) AS TotalAmount,

            -- Line item summary
            COUNT(DISTINCT td.ProductID) AS DistinctItems,
            COALESCE(SUM(td.Quantity), 0) AS TotalUnits
        FROM dbo.SalesTransaction st
        LEFT JOIN dbo.Customer c ON c.CustomerID = st.CustomerID
        LEFT JOIN dbo.Employee e ON e.EmployeeID = (
            SELECT TOP 1 EmployeeID 
            FROM dbo.Transaction_Details 
            WHERE TransactionID = st.TransactionID
        )
        LEFT JOIN dbo.Transaction_Details td ON td.TransactionID = st.TransactionID
        WHERE 1 = 1
    """

    params = []

    if start_date:
        sql += " AND st.TransactionDate >= ?"
        params.append(start_date)

    if end_date:
        sql += " AND st.TransactionDate < DATEADD(day,1,?)"
        params.append(end_date)

    if payment_method:
        sql += " AND st.PaymentMethod = ?"
        params.append(payment_method)

    if order_status:
        sql += " AND st.OrderStatus = ?"
        params.append(order_status)

    if employee_id:
        sql += " AND e.EmployeeID = ?"
        params.append(employee_id)

    sql += """
        GROUP BY
            st.TransactionID,
            st.TransactionDate,
            c.Name,
            e.Name,
            st.PaymentMethod,
            st.OrderStatus,
            st.OrderDiscount,
            st.TotalAmount
        ORDER BY st.TransactionDate DESC
    """

    cursor.execute(sql, tuple(params))
    rows = cursor.fetchall()

    receipts = []
    for r in rows:
        receipts.append({
            "TransactionID": r[0],
            "TransactionDate": r[1].strftime("%Y-%m-%d"),
            "CustomerName": r[2],
            "EmployeeName": r[3],
            "PaymentMethod": r[4],
            "OrderStatus": r[5],
            "OrderDiscount": float(r[6]),
            "TotalAmount": float(r[7]),
            "DistinctItems": int(r[8]),
            "TotalUnits": int(r[9])
        })

    total_revenue = sum(r["TotalAmount"] for r in receipts)
    total_receipts = len(receipts)
    avg_receipt = total_revenue / total_receipts if total_receipts else 0

    cursor.execute("SELECT DISTINCT PaymentMethod FROM dbo.SalesTransaction WHERE PaymentMethod IS NOT NULL")
    payment_methods = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT OrderStatus FROM dbo.SalesTransaction WHERE OrderStatus IS NOT NULL")
    order_statuses = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT EmployeeID, Name FROM dbo.Employee WHERE IsActive = 1 ORDER BY Name")
    employees = [{"EmployeeID": row[0], "Name": row[1]} for row in cursor.fetchall()]

    return render_template(
        'receipts_report.html',
        receipts=receipts,
        total_revenue=total_revenue,
        total_receipts=total_receipts,
        avg_receipt=avg_receipt,
        payment_methods=payment_methods,
        order_statuses=order_statuses,
        employees=employees
    )

@app.route('/api/receipts/<int:transaction_id>')
@with_db
def api_receipt_details(cursor, conn, transaction_id):
    """Return detailed breakdown of a given receipt for admin view."""
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    cursor.execute("""
        SELECT
            st.TransactionID,
            st.TransactionDate,
            COALESCE(c.Name, 'Guest / In-store') AS CustomerName,
            COALESCE(st.PaymentMethod, '') AS PaymentMethod,
            COALESCE(st.OrderStatus, '') AS OrderStatus,
            COALESCE(st.OrderDiscount, 0) AS OrderDiscount,
            COALESCE(st.TotalAmount, 0) AS TotalAmount,
            COALESCE(st.ShippingAddress, '') AS ShippingAddress
        FROM dbo.SalesTransaction st
        LEFT JOIN dbo.Customer c ON c.CustomerID = st.CustomerID
        WHERE st.TransactionID = ?
    """, (transaction_id,))
    header_row = cursor.fetchone()
    if not header_row:
        return jsonify({"error": "Receipt not found"}), 404

    header_cols = [col[0] for col in cursor.description]
    header = dict(zip(header_cols, header_row))

    cursor.execute("""
        SELECT
            td.ProductID,
            p.Name AS ProductName,
            td.Quantity,
            td.Price,
            COALESCE(td.Discount, 0) AS Discount,
            COALESCE(td.Subtotal, td.Price * td.Quantity) AS Subtotal,
            COALESCE(e.Name, 'N/A') AS EmployeeName
        FROM dbo.Transaction_Details td
        JOIN dbo.Product p ON p.ProductID = td.ProductID
        LEFT JOIN dbo.Employee e ON e.EmployeeID = td.EmployeeID
        WHERE td.TransactionID = ?
        ORDER BY p.Name
    """, (transaction_id,))
    cols = [col[0] for col in cursor.description]
    items = [dict(zip(cols, row)) for row in cursor.fetchall()]

    total_items = len(items)
    total_units = sum(i["Quantity"] for i in items)
    total_discount = sum(i["Discount"] for i in items)
    subtotal_sum = sum(i["Subtotal"] for i in items)

    return jsonify({
        "header": header,
        "items": items,
        "totals": {
            "total_items": total_items,
            "total_units": total_units,
            "total_discount": total_discount,
            "subtotal_sum": subtotal_sum
        }
    })

@app.route('/logout')
def logout():
    # Clear all session data
    session.clear()
    # Redirect user back to login page
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
