import os
import sys
import pyodbc
import traceback
from functools import wraps
from flask import jsonify

# Database credentials
DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_NAME = os.environ.get('DB_NAME')

if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
    raise RuntimeError("Database credentials are not fully set in environment variables.")

# -----------------------------
# Database connection
# -----------------------------

def get_db_connection():
    # List of ODBC drivers to try, in order of preference
    drivers = [
        'ODBC Driver 18 for SQL Server',
        'ODBC Driver 17 for SQL Server',
        'ODBC Driver 13 for SQL Server',
        'ODBC Driver 11 for SQL Server',
        'FreeTDS',
    ]

    # Get available drivers
    available_drivers = pyodbc.drivers()
    print(f"Available ODBC drivers: {available_drivers}", flush=True)
    sys.stderr.write(f"Available ODBC drivers: {available_drivers}\n")
    sys.stderr.flush()

    # Find the first available driver from our preferred list
    driver_to_use = None
    for driver in drivers:
        if driver in available_drivers:
            driver_to_use = driver
            break

    if not driver_to_use:
        msg = f"ERROR: No compatible SQL Server ODBC driver found! Available: {available_drivers}"
        print(msg, flush=True)
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
        return None

    try:
        msg = f"Connecting to DB at {DB_HOST} as {DB_USER}, database {DB_NAME} using driver: {driver_to_use}"
        print(msg, flush=True)
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()

        conn_str = (
            f"Driver={{{driver_to_use}}};"
            f"Server=tcp:{DB_HOST},1433;"
            f"Database={DB_NAME};"
            f"Uid={DB_USER};"
            f"Pwd={DB_PASSWORD};"
            "Encrypt=yes;"
            "TrustServerCertificate=yes;"
            "Connection Timeout=30;"
        )
        conn = pyodbc.connect(conn_str)
        print("Connection successful!", flush=True)
        sys.stderr.write("Connection successful!\n")
        sys.stderr.flush()
        return conn
    except Exception as e:
        msg = f"ERROR: Failed to connect to SQL Server - {type(e).__name__}: {str(e)}"
        print(msg, flush=True)
        sys.stderr.write(msg + "\n")
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        return None

def rows_to_dict_list(cursor):
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

def with_db(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            if conn is None:
                msg = "ERROR: Failed to establish database connection"
                print(msg, flush=True)
                sys.stderr.write(msg + "\n")
                sys.stderr.flush()
                return jsonify({"message": "Database connection failed"}), 500
            cursor = conn.cursor()
            return f(cursor, conn, *args, **kwargs)
        except Exception as e:
            msg = f"DB error: {e}"
            print(msg, flush=True)
            sys.stderr.write(msg + "\n")
            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()
            return jsonify({"message": "Database error"}), 500
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    return decorated
