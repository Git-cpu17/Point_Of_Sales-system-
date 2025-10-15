from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# Home page before login
@app.route('/')
def home():
    return render_template('regular_store_dashboard.html')

# Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form['user_id']
        password = request.form['password']

        # Example login logic (you can connect this to DB later)
        if user_id == 'admin' and password == 'admin123':
            return redirect(url_for('admin_dashboard'))
        elif user_id == 'employee' and password == 'emp123':
            return redirect(url_for('employee_dashboard'))
        elif user_id == 'customer' and password == 'cust123':
            return redirect(url_for('customer_dashboard'))
        elif user_id == 'department' and password == 'dept123':
            return redirect(url_for('department_dashboard'))
        else:
            return render_template('login.html', error='Invalid ID or Password')
    return render_template('login.html')

@app.route('/admin')
def admin_dashboard():
    return render_template('admin_dashboard.html')

@app.route('/employee')
def employee_dashboard():
    return render_template('employee_dashboard.html')

@app.route('/customer')
def customer_dashboard():
    return render_template('customer_dashboard.html')

@app.route('/department')
def department_dashboard():
    return render_template('department_dashboard.html')

if __name__ == '__main__':
    app.run(debug=True)
