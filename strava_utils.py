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