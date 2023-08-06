import requests
import logging
from config import STRAVA_TOKEN_URL, STRAVA_ACTIVITY_URL

# Configures logging to information level which will display detailed logs
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
#initialize logger
logger = logging.getLogger(__name__)

def get_activity_by_id(access_token, activity_id):
    logger.info(f"Fetching activity {activity_id} from the Strava API...")

    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    headers = {'Authorization': f'Bearer {access_token}'}

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise requests.exceptions.RequestException(response.json())

    activity = response.json()
    logger.info(f"Fetched activity: {activity}")

    return activity

def get_activities(access_token, activities_per_page):
    logger.info(f"Requesting activities from Strava API...")

    # Use STRAVA_ACTIVITY_URL from config
    url = STRAVA_ACTIVITY_URL
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    params = {
        'per_page': activities_per_page,  # Number of activities per page
        'page': 1       # Page number
    }

    # Making a GET request to Strava API to fetch activities
    response = requests.get(url, headers=headers, params=params)

    # Return activities as json for the FULL JSON
    activities = response.json()
    #return activities # if you want the full json
    # extract summary 
    summaries = []
    for activity in activities:
        summary = {}
        summary['id'] = activity['id']  
        summary['name'] = activity['name']
        summary['distance'] = activity['distance']
        summary['moving_time'] = activity['moving_time']
        summary['average_speed'] = activity['average_speed']
        summary['type'] = activity['type']
        summary['start_date_local'] = activity['start_date_local']
        summary['map'] = activity['map']
        summaries.append(summary)
    return summaries

def get_athlete_profile(access_token):
    url = "https://www.strava.com/api/v3/athlete"
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Status Code: {response.status_code}")
        print(f"Reason: {response.reason}")
        print(f"Content: {response.content}")
        raise Exception('Failed to fetch athlete profile')
    return response.json()

def deauthorize(access_token):
    url = "https://www.strava.com/oauth/deauthorize"
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.post(url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Failed to deauthorize the user: {response.content}")

    return response.json()

def process_auth_code(client_id, client_secret, code):
    # Use STRAVA_TOKEN_URL from config
    url = STRAVA_TOKEN_URL
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'grant_type': 'authorization_code'
    }

    # Making a POST request to Strava API to exchange auth code
    response = requests.post(url, params=payload)

    # Parsing JSON response data
    data = response.json()

    # Check if the request was successful
    if response.status_code != 200:
        raise requests.exceptions.RequestException(data)

    return data