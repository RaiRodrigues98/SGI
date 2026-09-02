import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    server = os.getenv("DB_SERVER")
    database = os.getenv("DB_DATABASE")
    username = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    driver = os.getenv(
        "DB_DRIVER",
        "ODBC Driver 17 for SQL Server"
    )

    connection_string = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        f"TrustServerCertificate=yes;"
    )

    return pyodbc.connect(
        connection_string,
        timeout=10
    )