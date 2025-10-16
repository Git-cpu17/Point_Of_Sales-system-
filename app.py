from flask import Flask, render_template, request, redirect, url_for
from config import Config
from models import db, Administrator, Employee, Customer, Department, Product, Transaction

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Reflect tables if they already exist in Azure MySQL
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print("Database connection issue:", e)

# -----------------------------
# Routes
# -----------------------------
@app.route('/')
def home():
    return render_template('regular_store_dashboard.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form['user_id']
        password = request.form['password']

        admin = Administrator.query.filter_by(username=user_id, password=password).first()
        emp = Employee.query.filter_by(username=user_id, password=password).first()

        if admin:
            return redirect(url_for('admin_dashboard'))
        elif emp:
            return redirect(url_for('employee_dashboard'))
        else:
            return render_template('login.html', error='Invalid ID or Password')
    return render_template('login.html')

@app.route('/admin')
def admin_dashboard():
    admins = Administrator.query.all()
    employees = Employee.query.all()
    return render_template('admin_dashboard.html', admins=admins, employees=employees)

@app.route('/employee')
def employee_dashboard():
    employees = Employee.query.all()
    return render_template('employee_dashboard.html', employees=employees)

@app.route('/customer')
def customer_dashboard():
    customers = Customer.query.all()
    return render_template('customer_dashboard.html', customers=customers)

@app.route('/department')
def department_dashboard():
    departments = Department.query.all()
    return render_template('department_dashboard.html', departments=departments)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
