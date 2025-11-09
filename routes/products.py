from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from db import with_db, rows_to_dict_list
from utility.security import require_role

bp = Blueprint("products", __name__)

@bp.route("/products", methods=["GET"])
@with_db
def get_products(cursor, conn):
    cursor.execute("""
        SELECT ProductID, Name, Description, Price, QuantityInStock, Barcode, DepartmentID
        FROM Product
    """)
    rows = rows_to_dict_list(cursor)
    return jsonify(rows)

@bp.route("/add", methods=["POST"])
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
