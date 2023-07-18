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
app.secret_key = 'super duper secret key'  # super duper secret cause Flask wants it
@app.errorhandler(500)
def internal_error(error):
    return redirect(SITE_HOMEPAGE)

@app.route('/map/<map_name>', methods=['GET'])
def map(map_name):
    return send_from_directory('/tmp', map_name)

# Home endpoint to serve the login link for Strava
@app.route('/', methods=['GET', 'POST'])
def home():
    message = ("We'll grab your most recent activity data from Strava, pass the distance to chatGPT, and provide some fun distance-related facts. "
               "We don't save any of the data from the query; it's all stateless in this demo. "
               "This also means you'll most likely get a brand new fact each time you're here.")

    if request.method == 'POST':
        model_choice = request.form.get('model_choice')
        return redirect(f'/login?model_choice={model_choice}')
    
    # We use Jinja2's templating engine which comes with Flask. 
    return render_template('home.html', message=message)

@app.route('/deauthorize', methods=['POST'])
def deauthorize():
    # Ensure the 'access_token' is in the request form data
    if 'access_token' not in request.form:
        return 'Access token required', 400
    access_token = request.form.get('access_token')
    # Call deauthorize() function from strava_utils
    try:
        strava_utils.deauthorize(access_token)
        return 'Successfully deauthorized', 200
    except Exception as e:
        return str(e), 400

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/profile')
def profile():
    return render_template('profile.html')

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

# At this endpoint, after login, the client receives an auth code from Strava which we exchange 
# for an access token that we can use to make requests to the Strava API. 
@app.route('/exchange_token', methods=['GET'])
def exchange_token():
    start_time = time.time()
    model_choice=request.args.get('model_choice')
    strava_time = 0  # Initialize strava_time
    db_time = 0  # Initialize db_time
    #this is just the default messages on the response.html page
    messages = []
    #set values to put in the "logging tab"
    logging_messages = []
    error_message = None # Initialize an error message variable    

    # Check if the 'error' is in the request arguments
    if 'error' in request.args:
        error = request.args.get('error')
        
        if error == 'access_denied':
            return 'For the app to work, you have to allow us to see the data. <a href="/">Try again?</a>'
    
    # Start the timer for Strava
    strava_auth_start = time.time()
    try:
        code = request.args.get('code')
        strava_auth_end = time.time()
        strava_time = strava_auth_end - strava_auth_start   
        db_start = time.time()

        # Check if 'code' is valid
        if not code or not isinstance(code, str):
            return "Invalid 'code' supplied"

        # Process the 'code' to get access and refresh tokens
        try:
            data = strava_utils.process_auth_code(STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, code)
        except requests.exceptions.RequestException as e:
            return f"Error occurred while processing the code: {str(e)}."

        # check if "code" processing was successful
        if "access_token" not in data:
            return render_template('error.html', message="We couldn't process your request with the permissions provided. <br>Please start again and provide the necessary permissions.")

        # Get scope from the arguments
        scope = request.args.get('scope')

        # Add explicit checks for each expected permission
        required_permissions = ['read', 'activity:read_all']
        granted_permissions = scope.split(',')

        # Check for missing permissions and return an appropriate error message if any are missing
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

        # Timestamp right after Strava authorization
        strava_auth_end = time.time()
        # Store Strava interaction time in a variable
        strava_time = strava_auth_end - strava_auth_start
        
        # Add token exchange message to the list of messages
        logging_messages.append(f'1. Strava Auth: Success! (scope: {scope})')
        logging_messages.append(f'2. Athlete_ID ({athlete_id}): Success!')
        logging_messages.append(f'3. Token Expires: {expires_at}')
        logging_messages.append(f'4. Access Token: {access_token}')
        logging_messages.append(f'5. Refresh Token: {refresh_token}')

        # Timestamp right after Strava authorization
        strava_auth_end = time.time()
        # Store Strava interaction time in a variable
        strava_time = strava_auth_end - strava_auth_start

        # Attempt to save tokens and user details in database
        logging_messages.append('6. Query Database: Attempting...')

        # Timestamp before database process starts
        db_start = time.time() 
        
        # Create database engine
        engine = create_conn()
        if isinstance(engine, str):     # If could not create engine (error message is returned), return the engine error message
            return engine

        # Connect to DB and execute SQL statements
        with engine.begin() as connection:

            # Call the new db_utils function to perform the insert/update operations
            pk_id, total_refresh_checks = db_utils.save_token_info(connection, STRAVA_CLIENT_ID, athlete_id, access_token, refresh_token, expires_at, expires_in, scope)
            # Timestamp right after database process
            db_end = time.time()
            # Store DB operation time in a variable.
            db_time = db_end - db_start
            logging_messages.append(f'7. Save to Database: Success! pk_id = {pk_id}, and total_refresh_checks={total_refresh_checks}')  

            # fetch the activities
            try:
                activities = strava_utils.get_activities(access_token)
            except Exception as e:
                # Handle any exceptions that arise from fetching the activities
                messages.append(f"Error occurred while fetching activities: {str(e)}")
                return '<br>'.join(messages)

            # Once we have the response, we can go through each activity and print the details
            activity_id = None 
            summary_polyline = None
            chatgpt_time = 0  # Initialize chatgpt_time
            messages.append('Your latest Strava activity...')
            for num, activity in enumerate(activities, 1):
                activity_id = activity['id'] 
                summary_polyline = activity['map'].get('summary_polyline', 'N/A')
                date = parse(activity['start_date_local'])  # parses to datetime
                formatted_date = date.strftime('%Y-%m-%d %H:%M:%S')  # to your preferred string format
                distance = activity.get('distance', 'N/A')
                moving_time = activity.get('moving_time', 'N/A')
                average_speed = activity.get('average_speed', 'N/A')
                type_ = activity.get('type', 'N/A')
                messages.append(f"Activity {num}: {formatted_date} : {activity['name']} | Distance: {distance} meters | Moving Time: {moving_time // 60} minutes and {moving_time % 60} seconds | Average Speed: {average_speed} m/s | Type: {type_}")
                messages.append('')

                
                # go get chatGPT data
                gpt_fact, chatgpt_time = get_chatgpt_fact(distance, model_choice, OPENAI_SECRET_KEY)  
                messages.append(f"{model_choice.capitalize()} fact: {gpt_fact}")

            # Prepare the HTML and Bootstrap template
            map_file = None
            try:
                map_file, _ = generate_map(summary_polyline)
            except Exception as e: 
                print(f"Error in generating map: {e}") 
            return render_template('response.html', messages=messages, logging_messages=logging_messages, activities=activities, activity_id=activity_id, summary_polyline=summary_polyline,map_file=map_file)

    except requests.exceptions.Timeout:
        # If the request to Strava API times out
        return 'The request timed out, please try again later.'

    except requests.exceptions.RequestException as e:
        # If there was some other issue with the request
        return redirect(url_for('home')) 

    except psycopg2.OperationalError as ex:
        # If there was an issue with the SQL
        return f'Database connection error: {str(ex)}'


    finally:
        # Add logging only if there was no error previously
        if not error_message:
            # Calculate time taken for the whole process
            roundtrip_time = time.time() - start_time
            logging_messages += [
                '',
                '---INTERACTION TIME VALUES---',
                f'Strava: {round(strava_time, 3)} seconds.',
                f'Google Cloud SQL: {round(db_time, 3)} seconds.',
                f'OpenAI/ChatGPT: {round(chatgpt_time, 3)} seconds.',
                f'Total time: {round(time.time() - start_time, 3)} seconds.',
            ]
            
            # Prepare the HTML and Bootstrap template
            return render_template('response.html', messages=messages, logging_messages=logging_messages, activities=activities, activity_id=activity_id,summary_polyline=summary_polyline,map_file=map_file)
            
        else:
            return error_message

if __name__ == "__main__":
    # Allows us to run a development server and debug our application
    app.run(debug=True)