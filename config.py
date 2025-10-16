import os

class Config:
    # Retrieve the MySQL connection string from environment variables
    SQLALCHEMY_DATABASE_URI = os.getenv('AZURE_MYSQL_URI')

    # Recommended: fallback local connection (optional)
    if not SQLALCHEMY_DATABASE_URI:
        SQLALCHEMY_DATABASE_URI = (
            'mysql+pymysql://root:localpassword@localhost/store_db'
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'supersecretkey')
