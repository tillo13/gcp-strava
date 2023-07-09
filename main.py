# Import necessary libraries
from flask import Flask, request, redirect
from google.cloud import secretmanager
import os
import requests
import psycopg2
from psycopg2 import OperationalError
import sqlalchemy
from sqlalchemy import create_engine, text
import logging
import time

# Configure logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Initialize Flask application
app = Flask(__name__)

# Function to fetch secrets from Google Cloud Secret Manager
def get_secret_version(project_id, secret_id, version_id="latest"):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(name=name)
    return response.payload.data.decode('UTF-8')

# GCP and Strava configurations
GCP_PROJECT_ID = "97418787038"
STRAVA_CLIENT_ID = "110278"
REDIRECT_URL = "https://gcp-strava.wl.r.appspot.com/exchange_token"
STRAVA_API_SECRET = "strava_client_secret"
STRAVA_CLIENT_SECRET = get_secret_version(GCP_PROJECT_ID, STRAVA_API_SECRET)

# Fetch database password from Google Cloud Secret Manager
GOOGLE_SECRET_DB_ID = "gcp_strava_db_password"
DB_PASSWORD = get_secret_version(GCP_PROJECT_ID, GOOGLE_SECRET_DB_ID)

# Function to create connection to the database
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

# Home route, redirects users to the login page
@app.route('/', methods=['GET', 'POST'])
def home():
    return '<a href="/login">Login with Strava</a>'

# Login route, initiates the OAuth process with Strava
@app.route('/login', methods=['GET'])
def login():
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

# Route for handling token exchange with Strava, also handles storing token details in the database
@app.route('/exchange_token', methods=['GET'])
def exchange_token():
    start_time = time.time()  # Measure execution time of this request
    code = request.args.get('code')
    messages = []
    
    if code:
        try:
            # Step 1: Exchange code for tokens
            url = "https://www.strava.com/oauth/token"
            payload = {
                'client_id': STRAVA_CLIENT_ID,
                'client_secret': STRAVA_CLIENT_SECRET,
                'code': code,
                'grant_type': 'authorization_code'
            }
            response = requests.post(url, params=payload)
            response.raise_for_status()  # Raise an exception if the request was not successful
            data = response.json()

            # Store tokens and other data
            access_token = data['access_token']
            refresh_token = data['refresh_token']
            expires_at = data['expires_at']
            athlete_id = data['athlete']['id']
            expires_in = data['expires_in']

            #append the values to the output message at the end.
            messages.append('2. Token Exchange (strava.com/oauth/token): Success!')
            messages.append(f'3. Athlete_ID ({athlete_id}): Success!')
            messages.append(f'4. Token expires: {expires_at}')
            messages.append(f'5. Access Token: {access_token}')
            messages.append(f'6. Refresh Token: {refresh_token}')

            # Step 2: Store tokens in the database
            messages.append('7. Save to Database: Attempting...')
            engine = create_conn()
            with engine.begin() as connection:
                # Check if a record for this athlete_id already exists
                result = connection.execute(
                    text("SELECT * FROM strava_access_tokens WHERE athlete_id = :athlete_id"),
                    {"athlete_id": athlete_id}
                )
                row = result.fetchone()
                existing_token_info = row._asdict() if row else None

                if existing_token_info:
                    # If a record exists, update it
                    current_time = int(time.time())
                    if current_time > existing_token_info['expires_at']:
                        # If token is expired, update all fields
                        result = connection.execute(
                            text("""
                                UPDATE strava_access_tokens 
                                SET client_id=:client_id, 
                                    access_token=:access_token, 
                                    refresh_token=:refresh_token, 
                                    expires_at=:expires_at, 
                                    expires_in=:expires_in 
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
                        # If token is not expired, only update 'expires_in' and 'last_updated'
                        result = connection.execute(
                            text("""
                                UPDATE strava_access_tokens 
                                SET expires_in=:expires_in, 
                                    last_updated=now() 
                                WHERE athlete_id=:athlete_id
                                RETURNING pk_id
                            """),
                            {
                                "athlete_id": athlete_id,
                                "expires_in": expires_in
                            }
                        )
                else:
                    # If no record exists, insert a new one
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
            logging.error(f'Request Failed: {err}')
        
        except Exception as e:
            messages.append(f'Unexpected Error: {e}')
            logging.error(f'Unexpected Error: {e}')
        
        finally:
            roundtrip_time = round(time.time() - start_time, 3)
            messages.append(f'From login to now: {roundtrip_time} seconds.')
            messages.append('<br><a href="https://gcp-strava.wl.r.appspot.com/">Try again?</a>')
            return '<br>'.join(messages)
    
    return 'Uh oh, an error occurred when trying to get the token.'

if __name__ == "__main__":
    app.run(debug=True)
