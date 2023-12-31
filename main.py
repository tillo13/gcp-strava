# 2023aug2 445pm
from flask import Flask, request, redirect, Markup, render_template, redirect, url_for, session, send_from_directory  # Flask for building web application
import requests                                                        # For making HTTP requests to Stava API
import psycopg2                                                        # PostgresSQL library for handling database operations
from sqlalchemy import text                          # SQLAlchemy for ORM   
import logging                                                         # For logging information in the application
import time                                                             # to calculate and display time-based information
from dateutil.parser import parse                                      # For parsing dates and times from stings 
import json
import sys
from queue import Queue
from map_ride import generate_map
from google.cloud import secretmanager
from process_activity import process_activity
#for stava_utlis.py import of only specific fields
from collections import namedtuple 

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

@app.route('/admin', methods=['GET'])
def admin():
    if 'authenticated' in session and session['authenticated']:
        athlete_id = session.get('athlete_id', None)
        if athlete_id == 18443678:    # Add Check for specific athlete ID
            print("Admin tab accessed by " + str(athlete_id) + "...")
            # Create a connection
            engine = create_conn()
            if isinstance(engine, str):     # If could not create engine (error message is returned)
                return engine
            
            # Connect to the database and execute a SQL query
            with engine.begin() as connection:
                # Get all records from strava_access_tokens table
                result = connection.execute(text("SELECT * FROM strava_access_tokens"))
                data = [row._asdict() for row in result]            
            return render_template('admin.html', data=data)
        else:
            return redirect('/')
    else:
        return redirect('/')

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
        activities = strava_utils.get_activities(session['access_token'], 20)
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
    notification = ("We'll grab your most recent activity data from Strava, pass the distance to chatGPT, and provide some fun distance-related facts. "
               "We don't save any of the data from the query; it's all stateless in this demo. "
               "This also means you'll most likely get a brand new fact each time you're here.")

    if request.method == 'POST':
        model_choice = request.form.get('model_choice')
        logger.info(f"Model choice: {model_choice}")
        return redirect(f'/login?model_choice={model_choice}')
    
    # We use Jinja2's templating engine which comes with Flask. 
    return render_template('home.html', notification=notification)

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
        return render_template('error.html', notification="No results found! Please try again.")

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

    # Initialize to previous session value or any default value...
    messages = session.get('messages', None)
    map_file = session.get('map_file', None)
    summary_polyline = session.get('summary_polyline', None)
    zillow_return_1 = session.get('zillow_return_1', None)
    zillow_return_2 = session.get('zillow_return_2', None)
    logging_messages = session.get('logging_messages', None)
    strava_time = 0  # Initialize strava_time
    chatgpt_time = 0  # Initialize chatgpt_time
    zillow_time = 0  # Initialize zillow_time
    activity = None  # Initialize activity

    try:
        messages, map_file, summary_polyline, zillow_return_1, zillow_return_2, logging_messages, strava_time, chatgpt_time, zillow_time, activity = process_activity(access_token, "gpt-3.5-turbo", activity_id)
    except Exception as err:
        print(f"Error in process_activity: {err}")

    session["activities"] = [{'id': activity['id'], 'name': activity['name']}] if activity else None
    session['activity_id'] = activity_id
    session['summary_polyline'] = summary_polyline
    session['map_file'] = map_file
    session['messages'] = messages
    session['logging_messages'] = logging_messages
    #session['zillow_return_1'] = zillow_return_1
    #session['zillow_return_2'] = zillow_return_2

    #count and show the size of the session as it can't be more than 4093bytes
    # Convert the Flask session object to a dictionary.
    session_dict = dict(session)

    # Then serialize that dictionary to a JSON string.
    session_json = json.dumps(session_dict)

    # Then, calculate the size of the JSON string.
    session_size = len(session_json.encode('utf-8'))  # This will give you the size in bytes

    app.logger.info(f"Size of session after storage in /activity_process: {session_size} bytes")
    app.logger.info(f"Session after storage in /activity_process: {session}")


    return render_template('response.html', 
                           messages=messages, 
                           logging_messages=logging_messages, 
                           activities=session["activities"], 
                           activity_id=session["activity_id"], 
                           summary_polyline=session["summary_polyline"], 
                           map_file=session["map_file"], 
                           zillow_return_1=zillow_return_1, 
                           zillow_return_2=zillow_return_2)


# At this endpoint, after login, the client receives an auth code from Strava which we exchange 
# for an access token that we can use to make requests to the Strava API. 
@app.route('/exchange_token', methods=['GET'])
def exchange_token():
    start_time = time.time()

    #Initialize to None or any default value...
    messages = None
    map_file = None
    summary_polyline = None
    zillow_return_1 = None
    zillow_return_2 = None
    strava_time = 0 
    db_time = 0  
    zillow_time = 0 
    error_message = None 

    data = {}  # Initialize data as an empty dictionary
    model_choice=request.args.get('model_choice')

    #this is just the default messages on the response.html page
    messages = []
    #set values to put in the "logging tab"
    logging_messages = []

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
            # The session is a secure place to store information between requests. 
            # When a user successfully authenticates, set session['authenticated'] to True.
            if 'access_token' in data:
                session['authenticated'] = True
                session['access_token'] = data['access_token'] # store for profile tab
                # store the athlete_id in the session
                athlete_id = data['athlete']['id']
                session['athlete_id'] = athlete_id
            app.logger.info(f"Session after creation in /exchange_token: {session}")
        except requests.exceptions.RequestException as e:
            return f"Error occurred while processing the code: {str(e)}."

        # check if "code" processing was successful
        if "access_token" not in data:
            return render_template('error.html', notification="We couldn't process your request with the permissions provided. <br>Please start again and provide the necessary permissions.")

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
            return render_template('error.html', notification=error_message)
        
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
        logging_messages.append('6. Query GCP Postgres: Attempting...')

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
            logging_messages.append(f'7. Save to GCP Database: Success! pk_id = {pk_id}, and total_refresh_checks={total_refresh_checks}')  

            # fetch the activities
            try:
                #for this first query, just get the latest 1
                activities = strava_utils.get_activities(access_token,1)
                app.logger.info(f"Activities: {activities}")
                app.logger.info(f"Session after get_activities call in /exchange_token: {session}")

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
                app.logger.info(f"Session before processing activity in /exchange_token: {session}")
                logging_messages.append(f"Processing Activity {num}: {activity}")
                activity_id = activity['id'] 

                #removing the summary polyline from this as it duplicates and is already stored, so we'll just remove it first, but then also make sure it's not in.
                #summary_polyline = activity['map'].get('summary_polyline', 'N/A')
                if 'summary_polyline' in activity['map']:
                    del activity['map']['summary_polyline']

                date = parse(activity['start_date_local'])  # parses to datetime
                formatted_date = date.strftime('%Y-%m-%d %H:%M:%S')  # to your preferred string format
                distance = activity.get('distance', 'N/A')
                moving_time = activity.get('moving_time', 'N/A')
                average_speed = activity.get('average_speed', 'N/A')
                type_ = activity.get('type', 'N/A')
                messages.append(f"Activity {num}: {formatted_date} : {activity['name']} | Distance: {distance} meters | Moving Time: {moving_time // 60} minutes and {moving_time % 60} seconds | Average Speed: {average_speed} m/s | Type: {type_}")
                messages.append('')

                
                # go get chatGPT data
                try:
                    gpt_fact, chatgpt_time = get_chatgpt_fact(distance, model_choice, OPENAI_SECRET_KEY)
                    logging_messages.append(f"ChatGPT fact: {gpt_fact}")
                    messages.append(f"{model_choice.capitalize()} fact: {gpt_fact}")
                except Exception as e:
                    print(f"Failed to get chatGPT fact. Error: {e}")
                    chatgpt_time = 0

            # Prepare the HTML and Bootstrap template
            map_file = None
            # Timestamp before Zillow process starts
            zillow_start = time.time()

            zillow_return_1 = None
            zillow_return_2 = None
            try:
                #generate the google map file: 
                map_file, _ = generate_map(summary_polyline)
                
                #generate the zillow lists
                zillow_return_1 = get_zillow_info_1(ZILLOW_SERVER_TOKEN, summary_polyline)
                zillow_return_2 = get_zillow_info_2(ZILLOW_SERVER_TOKEN, summary_polyline)
                session['zillow_return_1'] = zillow_return_1
                session['zillow_return_2'] = zillow_return_2

            except Exception as e: 
                print(f"Error in getting Zillow information: {e}")

            app.logger.info(f"zillow_return_1: {zillow_return_1}")
            app.logger.info(f"zillow_return_2: {zillow_return_2}")

            # Timestamp right after Zillow process
            zillow_end = time.time()
            zillow_time = zillow_end - zillow_start
            logging_messages.append(f'8. Query Zillow: Success! (Zillow process took {zillow_time} seconds)')
            
            #count and show the size of the session as it can't be more than 4093bytes
            # Convert the Flask session object to a dictionary.
            session_dict = dict(session)

            # Then serialize that dictionary to a JSON string.
            session_json = json.dumps(session_dict)

            # Then, calculate the size of the JSON string.
            session_size = len(session_json.encode('utf-8'))  # This will give you the size in bytes

            app.logger.info(f"Size of session after processing activity in /exchange_token: {session_size} bytes")
            app.logger.info(f"Session after processing activity in /exchange_token: {session}")


            return render_template('response.html', messages=messages, logging_messages=logging_messages, activities=activities, activity_id=activity_id, summary_polyline=summary_polyline, map_file=map_file, zillow_return_1=zillow_return_1, zillow_return_2=zillow_return_2)
        

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
                f'Zillow: {round(zillow_time, 3)} seconds.', 
                f'Total time: {round(time.time() - start_time, 3)} seconds.',
            ]
            
            # Prepare the HTML and Bootstrap template
            session['messages'] = messages
            session['logging_messages'] = logging_messages
            session['activities'] = activities
            session['activity_id'] = activity_id
            session['summary_polyline'] = summary_polyline
            session['map_file'] = map_file
            app.logger.info(f"Messages at end of /exchange_token: {messages}")
            return render_template('response.html', messages=messages, logging_messages=logging_messages, activities=activities, activity_id=activity_id,summary_polyline=summary_polyline,map_file=map_file, zillow_return_1=zillow_return_1, zillow_return_2=zillow_return_2)
                    
        else:
            return error_message

if __name__ == "__main__":
    # Allows us to run a development server and debug our application
    app.run(debug=True)