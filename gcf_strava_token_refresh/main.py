import sqlalchemy
from flask import Flask, request
from google.cloud import secretmanager
import os
import requests
import time
from psycopg2 import OperationalError
from config import STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_TOKEN_URL, DB_USER, DB_PASSWORD, DB_NAME, CLOUD_SQL_CONNECTION_NAME
import logging
from datetime import datetime

def create_conn():
    db_user = DB_USER
    db_pass = DB_PASSWORD
    db_name = DB_NAME
    cloud_sql_connection_name = CLOUD_SQL_CONNECTION_NAME

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

app = Flask(__name__)

@app.route('/update-strava-tokens', methods=['POST'])
def update_tokens(request):
    # Get root logger
    logger = logging.getLogger()
    try:
        conn = create_conn()
        with conn.connect() as connection:
            result = connection.execute(sqlalchemy.text(
                "SELECT athlete_id, refresh_token, access_token FROM strava_access_tokens"))
        # Log row count
        row_count = result.rowcount if result else 0
        logger.info(f'{row_count} athletes found in the database.')
        logger.info(f'Executed SQL: {result}')
        if row_count == 0:
            return 'No athletes found in the database.', 204

        expire_data = {}  # create a dictionary to store athlete_id and expires_in values
        for row in result:
            athlete_id, refresh_token, access_token = row.athlete_id, row.refresh_token, row.access_token
            logger.info(f'Updating tokens for athlete {athlete_id}...')
            payload = {
                'client_id': STRAVA_CLIENT_ID,
                'client_secret': STRAVA_CLIENT_SECRET,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            }
            response = requests.post(STRAVA_TOKEN_URL, params=payload)
            if response.status_code == 200:
                new_access_token = response.json().get('access_token')
                new_refresh_token = response.json().get('refresh_token')
                new_expires_at = response.json().get('expires_at')
                new_expires_in = response.json().get('expires_in')

                with conn.connect() as connection:
                    if access_token == new_access_token:
                        # Only update the relevant fields
                        updated_rows = connection.execute(sqlalchemy.text("""
                            UPDATE strava_access_tokens
                            SET last_updated = now(),
                                expires_in = :expires_in,
                                total_refresh_checks = total_refresh_checks + 1,
                                last_refreshed_by = 'google_cloud_function'
                            WHERE athlete_id = :athlete_id
                        """),
                        {
                            "expires_in": new_expires_in,
                            "athlete_id": athlete_id
                        }).rowcount
                        logger.info(f'No token update (but updated relevant fields) for athlete {athlete_id}.')
                    else:
                        # Update all token-related fields
                        updated_rows = connection.execute(sqlalchemy.text("""
                            UPDATE strava_access_tokens
                            SET access_token = :access_token,
                                refresh_token = :refresh_token,
                                expires_at = :expires_at,
                                expires_in = :expires_in,
                                last_updated = now(),
                                total_refreshes = total_refreshes + 1,
                                total_refresh_checks = total_refresh_checks + 1,
                                last_refreshed_by = 'google_cloud_function'
                            WHERE athlete_id = :athlete_id
                        """),
                        {
                            "access_token": new_access_token,
                            "refresh_token": new_refresh_token,
                            "expires_at": new_expires_at,
                            "expires_in": new_expires_in,
                            "athlete_id": athlete_id
                        }).rowcount
                        logger.info(f'Successfully updated tokens for athlete {athlete_id}.')

                    connection.commit()  # Explicitly commit the transaction
                    time.sleep(0.1)  # pause for 100ms as I was seeing it not do all entries...

                logger.info(f'Updated {updated_rows} rows for athlete {athlete_id}.')
                expire_data[athlete_id] = new_expires_in  # add athlete_id and expires_in to the dictionary
                
            else:
                logger.error(f'Failed to fetch tokens for athlete {athlete_id}. Response from Strava: {response.json()}')

        return {'Tokens update process completed!': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'expire_data': expire_data}, 200

    except Exception as e:
        logger.error(f'Error while updating tokens: {e}')
