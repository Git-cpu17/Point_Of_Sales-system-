from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from db import with_db, rows_to_dict_list
from utility.security import require_role

bp = Blueprint("reports", __name__)

@bp.get("/reports")
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

@bp.post("/reports/query")
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
