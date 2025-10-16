import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('AZURE_SQL_URI')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'supersecretkey')
