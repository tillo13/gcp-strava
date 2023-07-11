import sys
import os
import requests
import json
import time
import psycopg2
from config import STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_TOKEN_URL
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file
DB_PW = os.getenv('DB_STRAVA_ACCESS_TOKENS_PW')

def get_athletes():
    # Create database connection
    conn = psycopg2.connect(
        host='34.133.105.15',
        dbname='gcp_strava_data',
        user='postgres',
        password=DB_PW
    )

    # Create a cursor object
    cur = conn.cursor()

    # Execute the query
    cur.execute("SELECT DISTINCT athlete_id FROM strava_access_tokens;")

    # Get the result
    result = cur.fetchall()

    # Close the cursor and connection
    cur.close()
    conn.close()

    # Return a list of athlete_ids
    return [athlete[0] for athlete in result]

def get_refresh_token(athlete_id):
    # Create database connection
    conn = psycopg2.connect(
        host='34.133.105.15',
        dbname='gcp_strava_data',
        user='postgres',
        password=DB_PW
    )

    # Create a cursor object
    cur = conn.cursor()

    # Execute the query
    cur.execute(f"SELECT refresh_token, client_id FROM strava_access_tokens WHERE athlete_id = {athlete_id}")
    
    # Get the result
    result = cur.fetchone()

    # Close the cursor and connection
    cur.close()
    conn.close()

    return result[0], result[1]

def get_new_token(athlete_id):
    url = "https://www.strava.com/oauth/token"
    refresh_token, client_id = get_refresh_token(athlete_id)

    payload = {
        'client_id': client_id,
        'client_secret': STRAVA_CLIENT_SECRET,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
        'f': 'json'
    }
      
    response = requests.post(url, params=payload)
    response.raise_for_status()

    response_json = response.json()
    return response_json['access_token']

def check_token(athlete_id):
    print(f"Getting new access token for athlete_id: {athlete_id}")
    access_token = get_new_token(athlete_id)
    print(f"The access token for athlete_id {athlete_id} is: {access_token}")
    return access_token

def log_activities(athlete_id, access_token):
    url = "https://www.strava.com/api/v3/athlete/activities"

    headers = { 'Authorization': f'Bearer {access_token}' }
    params = { 'per_page': 50, 'page': 1 }  # set page number and activities per page

    response = requests.get(url, headers=headers, params=params)

    activities = response.json()
    
    folder_path = './activities'
    os.makedirs(folder_path, exist_ok=True)

    existing_files = os.listdir(folder_path)
    num_duplicates = 0
    num_new_activities = 0
    start_time = time.time()

    for activity in activities:
        activity_id = activity['id']
        file_path = os.path.join(folder_path, f'{athlete_id}_{activity_id}.json')
        if f'{athlete_id}_{activity_id}.json' in existing_files:
            num_duplicates += 1
        else:
            with open(file_path, 'w') as file:
                json.dump(activity, file, indent=4)
            num_new_activities += 1

    print(f"Athlete_id: {athlete_id}")
    print(f"Requested activities: 50")  # always request 50 at a time
    print(f"Duplicates: {num_duplicates} files already exist in the activities folder.")
    print(f"New activities: {num_new_activities} new files were created.")
    print(f"Script run time: {time.time() - start_time} seconds.") 

if __name__ == "__main__":
    athletes = get_athletes()
    for athlete_id in athletes:
        access_token = check_token(athlete_id)
        log_activities(athlete_id, access_token)