import sqlalchemy
from flask import Flask, request
from google.cloud import secretmanager
import os
import requests
import time
from psycopg2 import OperationalError
from config import STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_TOKEN_URL, DB_USER, DB_PASSWORD, DB_NAME, CLOUD_SQL_CONNECTION_NAME

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
    conn = create_conn()
    with conn.connect() as connection:
        result = connection.execute(sqlalchemy.text(
            "SELECT athlete_id, refresh_token FROM strava_access_tokens"))
    if result.rowcount == 0:
        print('No athletes found in the database.')
        return 'No athletes found in the database.'
    else:
        print(f'{result.rowcount} athletes found in the database.')

    for row in result:
        athlete_id, refresh_token = row.athlete_id, row.refresh_token
        print(f'Updating tokens for athlete {athlete_id}...')
        payload = {
            'client_id': STRAVA_CLIENT_ID,
            'client_secret': STRAVA_CLIENT_SECRET,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
        response = requests.post(STRAVA_TOKEN_URL, params=payload)
        if response.status_code == 200:
            new_access_token = response.json()['access_token']
            new_refresh_token = response.json()['refresh_token']
            new_expires_at = response.json()['expires_at']
            with conn.connect() as connection:
                connection.execute(sqlalchemy.text("""
                        UPDATE strava_access_tokens
                        SET access_token = :access_token, 
                            refresh_token = :refresh_token, 
                            expires_at = :expires_at, 
                            last_updated = now(),
                            total_refreshes = total_refreshes + 1,
                            total_refresh_checks = total_refresh_checks + 1
                        WHERE athlete_id = :athlete_id
                    """),
                    {
                        "access_token": new_access_token, 
                        "refresh_token": new_refresh_token, 
                        "expires_at": new_expires_at, 
                        "athlete_id": athlete_id
                    })
            print(f'Successfully updated tokens for athlete {athlete_id}.')
        else:
            print(f'Failed to update tokens for athlete {athlete_id}. Response from Strava: {response.json()}')
    return 'Tokens update process completed!', 200