from sqlalchemy import text
import psycopg2
import sqlalchemy
from psycopg2 import OperationalError
from config import DB_USER, DB_PASSWORD, DB_NAME, CLOUD_SQL_CONNECTION_NAME

def create_conn():
    try:
        db_user = DB_USER
        db_pass = DB_PASSWORD
        db_name = DB_NAME
        cloud_sql_connection_name = CLOUD_SQL_CONNECTION_NAME

        #########################
        #   Creating engine for connecting PostgreSQL database
        #########################
        engine = sqlalchemy.create_engine(
            sqlalchemy.engine.url.URL.create(
                drivername="postgresql+psycopg2",
                username=db_user,
                password=db_pass,
                database=db_name,
                host=f'/cloudsql/{cloud_sql_connection_name}',
            ),
        )
        return engine                                      
    except OperationalError:
        return 'Unable to connect to the database, please try again later.' 