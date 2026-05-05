# import os
# import pymysql
# from dotenv import load_dotenv

# load_dotenv()

# def get_main_db_connection():
#     return pymysql.connect(
#         host=os.getenv("MAIN_DB_HOST"),
#         port=int(os.getenv("MAIN_DB_PORT", "3306")),
#         user=os.getenv("MAIN_DB_USER"),
#         password=os.getenv("MAIN_DB_PASSWORD"),
#         database=os.getenv("MAIN_DB_NAME"),
#         cursorclass=pymysql.cursors.DictCursor,
#         autocommit=True,
#     ) 

import os
import pymysql
from dotenv import load_dotenv

load_dotenv()


def get_main_db_connection():
    return pymysql.connect(
        host=os.getenv("MAIN_DB_HOST"),
        port=int(os.getenv("MAIN_DB_PORT", "3306")),
        user=os.getenv("MAIN_DB_USER"),
        password=os.getenv("MAIN_DB_PASSWORD"),
        database=os.getenv("MAIN_DB_NAME"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )