# 2023july10-1048
from flask import Flask, request, redirect, Markup, render_template, redirect, url_for, session, send_from_directory  # Flask for building web application
import requests                                                        # For making HTTP requests to Stava API
import psycopg2                                                        # PostgresSQL library for handling database operations
import sqlalchemy
from sqlalchemy import text                          # SQLAlchemy for ORM   
import logging                                                         # For logging information in the application
import time                                                             # to calculate and display time-based information
import json                                                            # For handling JSON data
from dateutil.parser import parse                                      # For parsing dates and times from stings 
from psycopg2 import OperationalError
from threading import Thread
from queue import Queue
from map_ride import generate_map
from google.cloud import secretmanager
from process_activity import process_activity

#initialize logger
logger = logging.getLogger(__name__)

from zillow_utils import get_zillow_info_1, get_zillow_info_2
from config import ZILLOW_SERVER_TOKEN

def get_secret_version(project_id, secret_id, version_id="latest"):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(name=name)
    return response.payload.data.decode('UTF-8')

#import code from existing .py code in the app:
from chatgpt_utils import get_fact_for_distance, get_chatgpt_fact
#from secrets_manager import get_secret_version
import strava_utils
from config import SITE_HOMEPAGE,GCP_PROJECT_ID, STRAVA_CLIENT_ID, REDIRECT_URL, STRAVA_CLIENT_SECRET, DB_USER,DB_PASSWORD, DB_NAME, CLOUD_SQL_CONNECTION_NAME, OPENAI_SECRET_KEY
from db_utils import create_conn, save_token_info
import db_utils

# Configures logging to information level which will display detailed logs
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Create a queue to hold results
result_queue = Queue()

# An instance of Flask is our WSGI (Web Server Gateway Interface) application.
app = Flask(__name__)
app.secret_key = 'super duper secret key'  # super duper secret cause Flask wants it for session info
@app.errorhandler(500)
def internal_error(error):
    return redirect(SITE_HOMEPAGE)

@app.route('/map/<map_name>', methods=['GET'])
def map(map_name):
    return send_from_directory('/tmp', map_name)

@app.route('/history', methods=['GET'])
def history():
    print("Before get_activities call, set activities to blank...")
    activities = []
    print("Attempt to get access token...")
    access_token = session.get('access_token')
    if access_token is None:
        print("No access token found in session")
        return redirect('/')
    print("Access token:", access_token)

    try: 
        print("Before get_activities call, set activities to blank...")
        activities = []
        activities = strava_utils.get_activities(session['access_token'], 50)
    except Exception as e:
        print("Error getting activities from strava_util /history path: ", e)
    print("After get_activities call...")

    # Create a new list that contains tuples with activity ID and name
    activity_ids_and_names = [(activity['id'], activity['name']) for activity in activities]

    logger.info(f"Fetched {len(activity_ids_and_names)} activity IDs and Names: {activity_ids_and_names}")
    logger.info(f"Rendering with activity_ids_and_names: {activity_ids_and_names}")  
    return render_template('history.html', activity_ids_and_names=activity_ids_and_names)

# Home endpoint to serve the login link for Strava
@app.route('/', methods=['GET', 'POST'])
def home():
    message = ("We'll grab your most recent activity data from Strava, pass the distance to chatGPT, and provide some fun distance-related facts. "
               "We don't save any of the data from the query; it's all stateless in this demo. "
               "This also means you'll most likely get a brand new fact each time you're here.")

    if request.method == 'POST':
        model_choice = request.form.get('model_choice')
        logger.info(f"Model choice: {model_choice}")
        return redirect(f'/login?model_choice={model_choice}')
    
    # We use Jinja2's templating engine which comes with Flask. 
    return render_template('home.html', message=message)

@app.route('/deauthorize', methods=['POST'])
def deauthorize():
    # Ensure the 'access_token' is in the request form data
    if 'access_token' not in session:
        return 'Access token required', 400

    access_token = session['access_token']
    # Call deauthorize() function from strava_utils
    try:
        strava_utils.deauthorize(access_token)
        session.clear()  # clear all session data
        return redirect('/')  # Redirect user to the main page
    except Exception as e:
        # Here we handle the case where the access_token is invalid.
        # This could be because it was already deauthorized in another session, 
        # or it could have expired.
        session.clear()  # clear all session data in any case
        return redirect('/')  # redirect the user to the main/login page

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/profile')
def profile():
    if 'authenticated' in session and session['authenticated']:
        access_token = session.get('access_token')
        if access_token is None:
            return render_template('profile.html', status="Not Authenticated", athlete_id='None')

        athlete_id = session.get('athlete_id', 'None')
        try:
            # Get athlete profile from the strava_utils
            athlete_profile = strava_utils.get_athlete_profile(access_token)
            return render_template('profile.html', status='Authenticated', athlete_id=athlete_id, profile=athlete_profile)
        except Exception as e:
            # Add logging or error handling as needed
            return str(e), 400
    else:
        return render_template('profile.html', status="Not Authenticated", athlete_id='None')

# Login endpoint to redirect users to the Stava login page
@app.route('/login', methods=['GET'])
def login():
    model_choice=request.args.get('model_choice')

    params = {
        "client_id": STRAVA_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": f"{REDIRECT_URL}?model_choice={model_choice}",
        "approval_prompt": "force",
        "scope": "read_all,profile:read_all,activity:read_all,activity:write"
    } 
    url = "https://www.strava.com/oauth/authorize"
    r = requests.Request('GET', url, params=params).prepare()
    return redirect(r.url)

#this is the static version of the response after connect with strava
@app.route('/activity', methods=['GET'])
def activity():
    # Check if data exists in session
    if 'activity_id' not in session:
        return render_template('error.html', message="No results found! Please try again.")

    # Retrieve data from session
    messages = session['messages']
    logging_messages = session['logging_messages']
    activities = session['activities']
    activity_id = session['activity_id']
    summary_polyline = session['summary_polyline']
    map_file = session['map_file']
    zillow_return_1 = session['zillow_return_1']
    zillow_return_2 = session['zillow_return_2']

    return render_template('response.html', messages=messages, logging_messages=logging_messages, activities=activities, activity_id=activity_id, summary_polyline=summary_polyline,map_file=map_file, zillow_return_1=zillow_return_1, zillow_return_2=zillow_return_2)

@app.route('/activity_process', methods=['POST'])
def activity_process():
    activity_id = request.form.get('activity_id')
    access_token = session.get('access_token')

    if not access_token:
        return "No access token found in session", 400

    messages, map_file, summary_polyline, zillow_return_1, zillow_return_2, logging_messages, strava_time, chatgpt_time, zillow_time, activity = process_activity(access_token, "gpt-3.5-turbo", activity_id)

    session["activities"] = [activity]
    session['activity_id'] = activity_id
    session['summary_polyline'] = summary_polyline
    session['map_file'] = map_file
    session['messages'] = messages
    session['logging_messages'] = logging_messages
    session['zillow_return_1'] = zillow_return_1
    session['zillow_return_2'] = zillow_return_2

    return render_template('response.html', messages=messages, logging_messages=logging_messages, activities=session["activities"], activity_id=session["activity_id"], summary_polyline=session["summary_polyline"], map_file=session["map_file"], zillow_return_1=session['zillow_return_1'], zillow_return_2=session["zillow_return_2"])



@app.route('/exchange_token', methods=['GET'])
def exchange_token():
    start_time = time.time()
    data = {}  # Initialize data as an empty dictionary
    model_choice=request.args.get('model_choice')
    strava_time = 0  # Initialize strava_time
    db_time = 0  # Initialize db_time
    zillow_time = 0 # Initialize zillow_time
    zillow_start = time.time()
    messages = []
    logging_messages = []
    error_message = None
    scope = None

    if 'error' in request.args:
        error = request.args.get('error')

        if error == 'access_denied':
            return 'For the app to work, you have to allow us to see the data. <a href="/">Try again?</a>'
    
    strava_auth_start = time.time()
    try:
        code = request.args.get('code')
        strava_auth_end = time.time()
        strava_time = strava_auth_end - strava_auth_start
        db_start = time.time()

        if not code or not isinstance(code, str):
            return "Invalid 'code' supplied"

        try:
            data = strava_utils.process_auth_code(STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, code)

            if 'access_token' in data:
                session['authenticated'] = True
                session['access_token'] = data['access_token']
                athlete_id = data['athlete']['id']
                session['athlete_id'] = athlete_id

        except requests.exceptions.RequestException as e:
            return f"Error occurred while processing the code: {str(e)}."

        if "access_token" not in data:
            return render_template('error.html', message="We couldn't process your request with the permissions provided. <br>Please start again and provide the necessary permissions.")

        scope = request.args.get('scope')
        required_permissions = ['read', 'activity:read_all']
        granted_permissions = scope.split(',')
        missing_permissions = [permission for permission in required_permissions if permission not in granted_permissions]

        if missing_permissions:
            error_message = "So to run as of 2023July10, we need at least these permissions: " + ', '.join(missing_permissions)
            error_message = Markup(f"{error_message}. <br>Feel free to uncheck the others for now.<br><br><a href='/'>Please start again</a> and provide the necessary permissions.")
            return render_template('error.html', message=error_message)
        
        access_token = data['access_token']
        refresh_token = data['refresh_token']
        expires_at = data['expires_at']
        athlete_id = data['athlete']['id']
        expires_in = data['expires_in']

        strava_auth_end = time.time()
        strava_time = strava_auth_end - strava_auth_start

        logging_messages.append(f'1. Strava Auth: Success! (scope: {scope})')
        logging_messages.append(f'2. Athlete_ID ({athlete_id}): Success!')
        logging_messages.append(f'3. Token Expires: {expires_at}')
        logging_messages.append(f'4. Access Token: {access_token}')
        logging_messages.append(f'5. Refresh Token: {refresh_token}')

        strava_auth_end = time.time()
        strava_time = strava_auth_end - strava_auth_start

        logging_messages.append('6. Query GCP Postgres: Attempting...')
        db_start = time.time() 
        engine = create_conn()
        if isinstance(engine, str):
            return engine

        with engine.begin() as connection:
            pk_id, total_refresh_checks = db_utils.save_token_info(connection, STRAVA_CLIENT_ID, athlete_id, access_token, refresh_token, expires_at, expires_in, scope)
            db_end = time.time()
            db_time = db_end - db_start
            logging_messages.append(f'7. Save to GCP Database: Success! pk_id = {pk_id}, and total_refresh_checks= {total_refresh_checks}')  

            # Fetch the latest activity
            activities = strava_utils.get_activities(access_token,1)
            
            if len(activities) > 0:
                activity_id = activities[0]['id'] 
            
                # Now we can use process_activity.py's function
                messages, map_file, summary_polyline, zillow_return_1, zillow_return_2, logging_messages, strava_time, chatgpt_time, zillow_time, activity = process_activity(access_token, model_choice, activity_id)
            else:
                # Handle case if no activities
                messages.append('No activities found. Please record an activity and try again.')
            
            zillow_end = time.time()
            zillow_time = zillow_end - zillow_start
            logging_messages.append(f'8. Query Zillow: Success! (Zillow process took {zillow_time} seconds)')

            return render_template('response.html', messages=messages, logging_messages=logging_messages, activities=activities, activity_id=activity_id, summary_polyline=summary_polyline, map_file=map_file, zillow_return_1=zillow_return_1, zillow_return_2=zillow_return_2)

    except requests.exceptions.Timeout:
        return 'The request timed out, please try again later.'
    except requests.exceptions.RequestException as e:
        return redirect(url_for('home')) 
    except psycopg2.OperationalError as ex:
        return f'Database connection error: {str(ex)}'
    except Exception as e:
        return str(e)
    finally:
        if not error_message:
            roundtrip_time = time.time() - start_time
            logging_messages += [
                '',
                '---INTERACTION TIME VALUES---',
                f'Strava: {round(strava_time, 3)} seconds.',
                f'Google Cloud SQL: {round(db_time, 3)} seconds.',
                f'OpenAI/ChatGPT: {round(chatgpt_time, 3)} seconds.',
                f'Zillow: {round(zillow_time, 3)} seconds.', 
                f'Total time: {round(time.time() - start_time, 3)} seconds.',
            ]
            return render_template('response.html', messages=messages, logging_messages=logging_messages, activities=activities, activity_id=activity_id,summary_polyline=summary_polyline,map_file=map_file, zillow_return_1=zillow_return_1, zillow_return_2=zillow_return_2)
        else:
            return error_message

if __name__ == "__main__":
    # Allows us to run a development server and debug our application
    app.run(debug=True)