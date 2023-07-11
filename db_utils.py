from sqlalchemy import text
import psycopg2
import sqlalchemy
import time
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

def save_token_info(connection, STRAVA_CLIENT_ID, athlete_id, access_token, refresh_token, expires_at, expires_in):
    # First, check if this athlete already has tokens in DB
    result = connection.execute(
        text("SELECT * FROM strava_access_tokens WHERE athlete_id = :athlete_id"),
        {"athlete_id": athlete_id}
    )

    # Fetch the result (if any)
    row = result.fetchone()
    existing_token_info = row._asdict() if row else None

    # Now, depending on whether we already have tokens for this athlete in DB, either update or insert new record
    if existing_token_info:
        current_time = int(time.time())
        update_result = connection.execute(text("UPDATE strava_access_tokens SET total_refresh_checks = total_refresh_checks + 1 WHERE athlete_id = :athlete_id RETURNING total_refresh_checks"), {"athlete_id": athlete_id})
        total_refresh_checks = update_result.fetchone()[0]

        # If the access token is expired, refresh it and increment total_refreshes
        if current_time > existing_token_info['expires_at']:
            result = connection.execute(
                text("""
                    UPDATE strava_access_tokens 
                    SET client_id=:client_id, 
                        access_token=:access_token, 
                        refresh_token=:refresh_token, 
                        expires_at=:expires_at, 
                        expires_in=:expires_in,
                        total_refreshes = total_refreshes + 1,
                     last_refreshed_by = 'gcp-strava.wl.r.appspot.com' 
                    WHERE athlete_id=:athlete_id
                    RETURNING pk_id
                """),
                {
                    "client_id": STRAVA_CLIENT_ID,
                    "athlete_id": athlete_id,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_at": expires_at,
                    "expires_in": expires_in
                }
            )
        else:
            # If the access token is not expired, only update the expires_in time, and last_refreshed_by
            result = connection.execute(
                text("""
                    UPDATE strava_access_tokens 
                    SET expires_in=:expires_in, 
                        last_updated=now(),
                        last_refreshed_by = 'gcp-strava.wl.r.appspot.com'
                    WHERE athlete_id=:athlete_id
                    RETURNING pk_id
                """),
                {
                    "athlete_id": athlete_id,
                    "expires_in": expires_in
                }
            )
    else:
        result = connection.execute(
            text("""
                INSERT INTO strava_access_tokens (client_id, athlete_id, access_token, refresh_token, expires_at, expires_in, last_refreshed_by)
                VALUES (:client_id, :athlete_id, :access_token, :refresh_token, :expires_at, :expires_in,'gcp-strava.wl.r.appspot.com')
                RETURNING pk_id
            """),
            {
                "client_id": STRAVA_CLIENT_ID,
                "athlete_id": athlete_id,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "expires_in": expires_in
            }
        )

        update_result = connection.execute(text("SELECT total_refresh_checks FROM strava_access_tokens WHERE athlete_id = :athlete_id"), {"athlete_id": athlete_id})
        total_refresh_checks = update_result.fetchone()[0]

    # Fetch the primary key id of the row just inserted/updated
    pk_id = result.fetchone()[0]
    return pk_id, total_refresh_checks