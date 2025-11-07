import os

class Config:
    # Use the environment variable for security
    SQLALCHEMY_DATABASE_URI = os.getenv('AZURE_MYSQL_URI')

    # Optional fallback for local testing
    if not SQLALCHEMY_DATABASE_URI:
        SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:localpassword@localhost/store_db'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'supersecretkey')
