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
