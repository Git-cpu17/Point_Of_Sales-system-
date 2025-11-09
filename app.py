import os
from flask import Flask
from flask_cors import CORS

from db import with_db, rows_to_dict_list, get_db_connection

def create_app():
    app = Flask(__name__)
    CORS(app)
    app.secret_key = os.environ.get('SECRET_KEY')

    from routes.home import bp as home_bp
    from routes.auth import bp as auth_bp
    from routes.products import bp as products_bp
    from routes.reports import bp as reports_bp
    from routes.admin import bp as admin_bp
    from routes.employee import bp as employee_bp
    from routes.customer import bp as customer_bp
    from routes.department import bp as department_bp

    app.register_blueprint(home_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(department_bp)
    
    return app

app = create_app()
