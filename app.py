from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from flask_cors import CORS
from db import with_db, rows_to_dict_list, get_db_connection
import os
import traceback, sys

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get('SECRET_KEY')
