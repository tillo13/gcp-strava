# Begin by importing necessary third-party libraries
from flask import Flask, request, redirect                             # Flask for building web application
from google.cloud import secretmanager                                 # For managing secrets in Google Cloud platform
import requests                                                        # For making HTTP requests to Stava API
import psycopg2                                                        # PostgresSQL library for handling database operations
import sqlalchemy
from sqlalchemy import text                          # SQLAlchemy for ORM   
import logging                                                         # For logging information in the application
import time                                                             # to calculate and display time-based information
import json                                                            # For handling JSON data
from dateutil.parser import parse                                      # For parsing dates and times from stings 

from psycopg2 import OperationalError

# Configures logging to information level which will display detailed logs
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# An instance of Flask is our WSGI (Web Server Gateway Interface) application.
app = Flask(__name__)

# The function to extract secret information from Google Cloud Secret Manager 
# Secret Manager is a way to store application secrets in Google Cloud
def get_secret_version(project_id, secret_id, version_id="latest"):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(name=name)
    return response.payload.data.decode('UTF-8')

# Configurations for Stava API and Google Cloud
GCP_PROJECT_ID = "97418787038"                                        # Google Cloud Project ID
STRAVA_CLIENT_ID = "110278"                                           # Strava API client ID
REDIRECT_URL = "https://gcp-strava.wl.r.appspot.com/exchange_token"   # Redirect URL is where users redirect after Stava login
STRAVA_SECRET_API_ID = "strava_client_secret"                         # Stava API secret ID is used to access Stava API
STRAVA_CLIENT_SECRET = get_secret_version(GCP_PROJECT_ID, STRAVA_SECRET_API_ID)  

# Storing credentials securely in secrets 
GOOGLE_SECRET_DB_ID = "gcp_strava_db_password"
DB_PASSWORD = get_secret_version(GCP_PROJECT_ID, GOOGLE_SECRET_DB_ID)  

# The function to create connection with the PostgreSQL database.
def create_conn():
    try:
        db_user = 'postgres'
        db_pass = DB_PASSWORD
        db_name = 'gcp_strava_data' 
        cloud_sql_connection_name = 'gcp-strava:us-central1:gcp-default'

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
        return engine                                      # Return connection engine
    except OperationalError:
        return 'Unable to connect to the database, please try again later.'                

# Home endpoint to serve the login link for Strava
@app.route('/', methods=['GET', 'POST'])
def home():
    return '<a href="/login">Login with Strava</a>'

# Login endpoint to redirect users to the Stava login page
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

# At this endpoint, after login, the client receives an auth code from Strava which we exchange 
# for an access token that we can use to make requests to the Strava API. 
@app.route('/exchange_token', methods=['GET'])
def exchange_token():
    start_time = time.time()
    messages = []

    #########################
    #   Extracting 'code' from request arguments
    #########################
    try:
        code = request.args.get('code')

        # Check if 'code' is valid
        if not code or not isinstance(code, str):
            return "Invalid 'code' supplied"

        # Stava API endpoint for exchanging code with refresh and access token.
        url = "https://www.strava.com/oauth/token"
        payload = {
            'client_id': STRAVA_CLIENT_ID,
            'client_secret': STRAVA_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code'
        }

        # Making a POST request to Stava API to exchange auth code
        response = requests.post(url, params=payload, timeout=10)

        if response.status_code == 429:
            return 'You have exceeded your request limit, please try again later.'

        response.raise_for_status()

        # Parsing JSON response data 
        data = response.json() 
        messages.append('1. Connect to Stava authorize (strava.com/oauth/authorize): Success!')

        # Store access and refresh tokens and other user details in variables
        access_token = data['access_token']
        refresh_token = data['refresh_token']
        expires_at = data['expires_at']
        athlete_id = data['athlete']['id']
        expires_in = data['expires_in']

        # Add token exchange message to the list of messages
        messages.append('2. Token Exchange (strava.com/oauth/token): Success!')
        messages.append(f'3. Athlete_ID ({athlete_id}): Success!')
        messages.append(f'4. Token expires: {expires_at}')
        messages.append(f'5. Access Token: {access_token}')
        messages.append(f'6. Refresh Token: {refresh_token}')

        # Attempt to save tokens and user details in database
        messages.append('7. Save to Database: Attempting...')

        # Create database engine
        engine = create_conn()
        if isinstance(engine, str):     # If could not create engine (error message is returned), return the engine error message
            return engine
        
        # Connect to DB and execute SQL statements
        with engine.begin() as connection:
            
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
                
                # Check if current token is expired. If yes, update all tokens, else update only expires_in time
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

            # Fetch the primary key id of the row just inserted/updated
            pk_id = result.fetchone()[0]
            
            # Add success message to the list of messages
            messages.append(f'8. Save to Database: Success! pk_id = {pk_id}')
            
            # Now let's get some activities for the athlete
            messages.append(f'9. Let us go find some activities...')
            url = "https://www.strava.com/api/v3/athlete/activities"

            # Set up the auth headers with the access token
            headers = {
                'Authorization': f'Bearer {access_token}'
            }

            # Define the parameters for the request. Here we limit the number of results and specify the page number.
            params = {
                'per_page': 13,  # Number of activities per page
                'page': 1  # Page number
            }

            # Make the request to the Strava API
            response = requests.get(url, headers=headers, params=params)

            # Try to decode the JSON response
            try:
                activities = response.json()
            except json.JSONDecodeError:
                # Add error message to the list of messages if we fail to decode the JSON
                messages.append(f"Error decoding JSON response: {response.text}")
                return '<br>'.join(messages)

            # Ensure the activities object is a list
            if not isinstance(activities, list):
                messages.append(f"Unexpected API response: {activities}")
                return '<br>'.join(messages)

            # Once we have the response, we can go through each activity and print the details
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
        # If the request to Strava API times out
        return 'The request timed out, please try again later.'

    except requests.exceptions.RequestException as e:
        # If there was some other issue with the request
        return f'An error occurred while processing your request: {str(e)}'

    except psycopg2.OperationalError as ex:
        # If there was an issue with the SQL
        return f'Database connection error: {str(ex)}'

    finally:
        # Calculate time taken for the whole process
        roundtrip_time = round(time.time() - start_time, 3)
        messages.append(f'From login to now: {roundtrip_time} seconds.')
        messages.append('<br><a href="https://gcp-strava.wl.r.appspot.com/">Try again?</a>')
        # Return all messages in one string
        return '<br>'.join(messages)


if __name__ == "__main__":
    # Allows us to run a development server and debug our application
    app.run(debug=True)