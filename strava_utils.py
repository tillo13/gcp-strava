import requests
from config import STRAVA_TOKEN_URL, STRAVA_ACTIVITY_URL

def get_activities(access_token):
    # Use STRAVA_ACTIVITY_URL from config
    url = STRAVA_ACTIVITY_URL
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    params = {
        'per_page': 1,  # Number of activities per page
        'page': 1       # Page number
    }

    # Making a GET request to Strava API to fetch activities
    response = requests.get(url, headers=headers, params=params)

    # Return activities as json
    activities = response.json()
    return activities

def process_auth_code(client_id, client_secret, code):
    # Use STRAVA_TOKEN_URL from config
    url = STRAVA_TOKEN_URL
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'grant_type': 'authorization_code'
    }

    # Making a POST request to Stava API to exchange auth code
    response = requests.post(url, params=payload)

    # Throw an exception if the response from Strava was not successful
    response.raise_for_status()

    # Parsing JSON response data
    data = response.json()

    return data