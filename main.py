# Import necessary libraries
from flask import Flask, request, redirect, render_template
from google.cloud import secretmanager
import os
import requests
import psycopg2
from psycopg2 import OperationalError
import sqlalchemy
from sqlalchemy import create_engine, text
import logging
import time
import json
from dateutil.parser import parse

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
STRAVA_SECRET_API_ID = "strava_client_secret"
STRAVA_CLIENT_SECRET = get_secret_version(GCP_PROJECT_ID, STRAVA_SECRET_API_ID)

# Fetch database password from Google Cloud Secret Manager
GOOGLE_SECRET_DB_ID = "gcp_strava_db_password"
DB_PASSWORD = get_secret_version(GCP_PROJECT_ID, GOOGLE_SECRET_DB_ID)


# Function to create a connection to the database
def create_conn():
    try:
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
    except OperationalError:
        return 'Unable to connect to the database, please try again later.'


@app.route('/', methods=['GET', 'POST'])
def home():
    return '<a href="/login">Login with Strava</a>'


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

@app.route('/exchange_token', methods=['GET'])
def exchange_token():
    start_time = time.time()
    messages = []
    
    try:
        code = request.args.get('code')

        if not code or not isinstance(code, str):
            return "Invalid 'code' supplied"

        url = "https://www.strava.com/oauth/token"
        payload = {
            'client_id': STRAVA_CLIENT_ID,
            'client_secret': STRAVA_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code'
        }
        response = requests.post(url, params=payload, timeout=10)

        # check status code
        if response.status_code == 429:
            return 'You have exceeded your request limit, please try again later.'

        response.raise_for_status()

        data = response.json() 
        messages.append('1. Connect to Strava authorize (strava.com/oauth/authorize): Success!')

        # Store tokens and other data
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

        messages.append('7. Save to Database: Attempting...')
        engine = create_conn()
        if isinstance(engine, str):  # Forward potential DB error messages
            return engine
        with engine.begin() as connection:
            result = connection.execute(
                text("SELECT * FROM strava_access_tokens WHERE athlete_id = :athlete_id"),
                {"athlete_id": athlete_id}
            )
            row = result.fetchone()
            existing_token_info = row._asdict() if row else None

            if existing_token_info:
                current_time = int(time.time())
                if current_time > existing_token_info['expires_at']:
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
            # Getting activities
            messages.append(f'9. Let us go find some activities...')
            url = "https://www.strava.com/api/v3/athlete/activities"

            headers = {
                'Authorization': f'Bearer {access_token}'
            }

            params = {
                'per_page': 13,  # Number of activities per page
                'page': 1  # Page number
            }

            response = requests.get(url, headers=headers, params=params)

            # check if the response is JSON
            try:
                activities = response.json()
            except json.JSONDecodeError:
                messages.append(f"Error decoding JSON response: {response.text}")
                return '<br>'.join(messages)

            # ensure the activities object is a list
            if not isinstance(activities, list):
                messages.append(f"Unexpected API response: {activities}")
                return '<br>'.join(messages)

            # Print activities
            messages.append('----------ACTIVITIES-----')
            for num, activity in enumerate(activities, 1):
                date = parse(activity['start_date_local'])  # parses to datetime
                formatted_date = date.strftime('%Y-%m-%d %H:%M:%S')  # to your preferred string format
                distance = activity.get('distance', 'N/A')
                moving_time = activity.get('moving_time', 'N/A')
                average_speed = activity.get('average_speed', 'N/A')
                type_ = activity.get('type', 'N/A')
                messages.append(f"Activity {num}: {formatted_date} : {activity['name']} | Distance: {distance} meters | Moving Time: {moving_time // 60} minutes and {moving_time % 60} seconds | Average Speed: {average_speed} m/s | Type: {type_}")

    except requests.exceptions.Timeout:
        return 'The request timed out, please try again later.'

    except requests.exceptions.RequestException as e:
        return f'An error occurred while processing your request: {str(e)}'

    except psycopg2.OperationalError as ex:
        return f'Database connection error: {str(ex)}'

    finally:
        roundtrip_time = round(time.time() - start_time, 3)
        messages.append(f'From login to now: {roundtrip_time} seconds.')
        messages.append('<br><a href="https://gcp-strava.wl.r.appspot.com/">Try again?</a>')
        return '<br>'.join(messages)


if __name__ == "__main__":
    app.run(debug=True)