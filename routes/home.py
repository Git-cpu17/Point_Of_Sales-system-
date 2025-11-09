from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from db import with_db, rows_to_dict_list

bp = Blueprint("home", __name__)

@bp.route('/')
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

@bp.route("/api/status", methods=["GET"])
def status():
    return jsonify({"message": "Flask API is running and connected to Azure SQL!"})
