from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# -----------------------------
# Entity Definitions
# -----------------------------

class Administrator(db.Model):
    __tablename__ = 'administrator'
    admin_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(100))
    role = db.Column(db.String(50))
    employees = db.relationship('Employee', backref='administrator', lazy=True)


class Department(db.Model):
    __tablename__ = 'department'
    department_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    description = db.Column(db.String(200))
    employees = db.relationship('Employee', backref='department', lazy=True)
    products = db.relationship('Product', backref='department', lazy=True)


class Product(db.Model):
    __tablename__ = 'product'
    product_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    description = db.Column(db.String(200))
    price = db.Column(db.Float)
    barcode = db.Column(db.String(50))
    department_id = db.Column(db.Integer, db.ForeignKey('department.department_id'))
    quantity_in_stock = db.Column(db.Integer)
    transactions = db.relationship('TransactionProduct', back_populates='product')
    inventories = db.relationship('Inventory', secondary='inventory_product', back_populates='products')


class Employee(db.Model):
    __tablename__ = 'employee'
    employee_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    job_title = db.Column(db.String(50))
    hire_date = db.Column(db.Date)
    department_id = db.Column(db.Integer, db.ForeignKey('department.department_id'))
    admin_id = db.Column(db.Integer, db.ForeignKey('administrator.admin_id'))
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(100))
    transactions = db.relationship('Transaction', backref='employee', lazy=True)


class Customer(db.Model):
    __tablename__ = 'customer'
    customer_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    transactions = db.relationship('Transaction', backref='customer', lazy=True)
    products = db.relationship('Product', secondary='customer_product', backref='customers')


class Transaction(db.Model):
    __tablename__ = 'transaction'
    transaction_id = db.Column(db.Integer, primary_key=True)
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.employee_id'))
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.customer_id'))
    payment_method = db.Column(db.String(50))
    products = db.relationship('TransactionProduct', back_populates='transaction')


class Inventory(db.Model):
    __tablename__ = 'inventory'
    inventory_id = db.Column(db.Integer, primary_key=True)
    quant_available = db.Column(db.Integer)
    last_restock_date = db.Column(db.Date)
    reorder_level = db.Column(db.Integer)
    products = db.relationship('Product', secondary='inventory_product', back_populates='inventories')


# Association tables
inventory_product = db.Table(
    'inventory_product',
    db.Column('inventory_id', db.Integer, db.ForeignKey('inventory.inventory_id')),
    db.Column('product_id', db.Integer, db.ForeignKey('product.product_id'))
)

customer_product = db.Table(
    'customer_product',
    db.Column('customer_id', db.Integer, db.ForeignKey('customer.customer_id')),
    db.Column('product_id', db.Integer, db.ForeignKey('product.product_id'))
)

class TransactionProduct(db.Model):
    __tablename__ = 'transaction_product'
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.transaction_id'), primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.product_id'), primary_key=True)
    quantity = db.Column(db.Integer)
    transaction = db.relationship('Transaction', back_populates='products')
    product = db.relationship('Product', back_populates='transactions')
