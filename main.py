#TODO_LIST: 
#1. secure the credentials in google secret DONE, note had to add Secret manager secret accessor here: https://console.cloud.google.com/iam-admin/iam?project=gcp-strava
#2. save to DB instead of CSV, better output messages.
#3. fix WARNING:  Python 3.5-3.7 will be deprecated on August 8th, 2023. Please use Python version 3.8 and up.
#4  handle the case when the 'code' parameter is not in the request. You might want to send a response indicating that the request is not as expected. 
from flask import Flask, request, redirect
from google.cloud import secretmanager
import os
import requests
import csv

app = Flask(__name__)

# Function to get your Strava Client Secret
def get_secret_version(project_id, secret_id, version_id="latest"):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(name=name)
    return response.payload.data.decode('UTF-8')

# Use your actual project id, client id, and redirect URL
SECRET_MANAGER_PROJECT_ID = "97418787038"
STRAVA_CLIENT_ID = "110278"
REDIRECT_URL = "https://gcp-strava.wl.r.appspot.com/exchange_token"
STRAVA_CLIENT_SECRET = get_secret_version(SECRET_MANAGER_PROJECT_ID, "strava_client_secret")

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
    code = request.args.get('code')
    if code:
        url = "https://www.strava.com/oauth/token"

        payload = {
            'client_id': STRAVA_CLIENT_ID,
            'client_secret': STRAVA_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code'
        }

        try:
            response = requests.post(url, params=payload)
            response.raise_for_status()

            data = response.json()

            access_token = data['access_token']
            refresh_token = data['refresh_token']
            expires_at = data['expires_at']

            # Write the tokens into a temporary CSV file in the local file system
            with open('/tmp/tokens.csv', 'a', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=['client_id', 'access_token', 'expires_at', 'refresh_token'])
                writer.writerow({
                    'client_id': STRAVA_CLIENT_ID,
                    'access_token': access_token,
                    'expires_at': expires_at,
                    'refresh_token': refresh_token
                })

            return f"All done! Your tokens are stored in tokens.csv file."

        except requests.exceptions.RequestException as err:
            return str(err)
    else:
        return "No code received"

if __name__ == "__main__":
    app.run(debug=True)