import os
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
    try:
        print(f"Attempting to connect to DB at {DB_HOST}...")
        conn_str = (
            "Driver={ODBC Driver 18 for SQL Server};"
            f"Server=tcp:{DB_HOST},1433;"
            f"Database={DB_NAME};"
            f"Uid={DB_USER};"
            f"Pwd={DB_PASSWORD};"
            "Encrypt=yes;"
            "TrustServerCertificate=yes;"
            "Connection Timeout=30;"
        )
        conn = pyodbc.connect(conn_str)
        print("Connection successful!")
        return conn
    except Exception as e:
        print(f"Error while connecting to SQL Server: {str(e)}")
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
            cursor = conn.cursor()
            return f(cursor, conn, *args, **kwargs)
        except Exception as e:
            print("DB error:", e)
            traceback.print_exc()
            return jsonify({"message": "Database error"}), 500
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    return decorated
