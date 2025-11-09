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

@app.route('/logout')
def logout():
    # Clear all session data
    session.clear()
    # Redirect user back to login page
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
