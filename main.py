from flask import Flask, request, redirect
from google.cloud import secretmanager
import os
import requests
import csv
import psycopg2
from psycopg2 import OperationalError
import socket
import sqlalchemy
from sqlalchemy import create_engine, text
import logging
import time

logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

app = Flask(__name__)

def get_secret_version(project_id, secret_id, version_id="latest"):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(name=name)
    return response.payload.data.decode('UTF-8')

GCP_PROJECT_ID = "97418787038"
STRAVA_CLIENT_ID = "110278"
REDIRECT_URL = "https://gcp-strava.wl.r.appspot.com/exchange_token"
STRAVA_API_SECRET = "strava_client_secret"
STRAVA_CLIENT_SECRET = get_secret_version(GCP_PROJECT_ID, STRAVA_API_SECRET)

#get Google Secret DB
GOOGLE_SECRET_DB_ID = "gcp_strava_db_password"
DB_PASSWORD = get_secret_version(GCP_PROJECT_ID, GOOGLE_SECRET_DB_ID)

def create_conn():
    db_user = 'postgres'
    db_pass = DB_PASSWORD
    db_name = 'gcp_strava_data' 
    cloud_sql_connection_name = 'gcp-strava:us-central1:gcp-default'

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

@app.route('/', methods=['GET', 'POST'])
def home():
    return '<a href="/login">Login with Strava</a>'

@app.route('/login', methods=['GET'])
def login():
    global start_time
    start_time = time.time()
    params = {
        "client_id": STRAVA_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URL,
        "approval_prompt": "force",
        "scope": "read_all,profile:read_all,activity:read_all,activity:write"
    }
    url = "https://www.strava.com/oauth/authorize"
    r = requests.Request('GET', url, params=params).prepare()
    return redirect(r.url)

@app.route('/exchange_token', methods=['GET'])
def exchange_token():
    code = request.args.get('code')
    messages = []
    if code:
        try:
            # Build the payload to get the token
            url = "https://www.strava.com/oauth/token"
            payload = {
                'client_id': STRAVA_CLIENT_ID,
                'client_secret': STRAVA_CLIENT_SECRET,
                'code': code,
                'grant_type': 'authorization_code'
            }
            # Attempt to get token
            response = requests.post(url, params=payload)
            response.raise_for_status()
            data = response.json()

            messages.append('1. Connect to Strava authorize (strava.com/oauth/authorize): Success!') 
            
            # Get tokens
            access_token = data['access_token']
            refresh_token = data['refresh_token']
            expires_at = data['expires_at']
            athlete_id = data['athlete']['id']
            expires_in = data['expires_in']

            messages.append('2. Token Exchange (strava.com/oauth/token): Success!')
            messages.append(f'3. Athlete_ID ({athlete_id}): Success!')
            messages.append(f'4. Token expires: {expires_at}')
            messages.append(f'5. Access Token: {access_token}')
            messages.append(f'6. Refresh Token: {refresh_token}')

            # Attempt to save to database
            messages.append('7. Save to Database: Attempting...')
            engine = create_conn()
            with engine.begin() as connection:
                result = connection.execute(
                    text("""
                    INSERT INTO strava_access_tokens (client_id, athlete_id, access_token, refresh_token, expires_at, expires_in)
                    VALUES (:client_id, :athlete_id, :access_token, :refresh_token, :expires_at, :expires_in)
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
                pk_id = result.fetchone()[0]
            messages.append(f'8. Save to Database: Success! pk_id = {pk_id}')

        except requests.exceptions.RequestException as err:
            messages.append(f'Request Failed: {err}')
        
        except Exception as e:
            messages.append(f'Unexpected Error: {e}')
        
        finally:
            roundtrip_time = time.time() - start_time
            messages.append(f'From login to now: {roundtrip_time} seconds.')
            messages.append('<br><a href="https://gcp-strava.wl.r.appspot.com/">Try again?</a>')
            return '<br>'.join(messages)
    return 'Uh oh, an error occurred when trying to get the token.'

if __name__ == "__main__":
    app.run(debug=True)