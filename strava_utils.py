# strava_utils.py
import requests
import time

def get_auth_url(model_choice, STRAVA_CLIENT_ID):
    params = {
        "client_id": STRAVA_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": f"https://gcp-strava.wl.r.appspot.com/exchange_token?model_choice={model_choice}",
        "approval_prompt": "force",
        "scope": "read_all,profile:read_all,activity:read_all,activity:write"
    } 
    url = "https://www.strava.com/oauth/authorize"
    r = requests.Request('GET', url, params=params).prepare()
    return r.url

def exchange_code_for_token(code, STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET):
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
        return None, 'You have exceeded your request limit, please try again later.'

    response.raise_for_status()

    # Parsing JSON response data 
    data = response.json()

    return data, None

def get_recent_activities(access_token):
    url = "https://www.strava.com/api/v3/athlete/activities"

    # Set up the auth headers with the access token
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    # Define the parameters for the request. Here we limit the number of results and specify the page number.
    params = {
        'per_page': 1,  # Number of activities per page
        'page': 1  # Page number
    }

    # Make the request to the Strava API
    response = requests.get(url, headers=headers, params=params)

    # Try to decode the JSON response
    try:
        activities = response.json()
    except Exception:
        return None, f"Error decoding JSON response: {response.text}"

    return activities, None