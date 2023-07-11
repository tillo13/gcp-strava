import requests
import os
from config import STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_TOKEN_URL
import psycopg2
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file
DB_PW = os.getenv('DB_STRAVA_ACCESS_TOKENS_PW')


def create_conn():
    conn = psycopg2.connect(
        host='34.133.105.15',
        dbname='gcp_strava_data',
        user='postgres',
        password=DB_PW
    )
    return conn

def refresh_strava_tokens():
    """Refreshes Strava tokens using refresh token present in the database."""

    # Creating connection to your database
    conn = create_conn()

    # If connection successful, fetch the refresh token stored in the database
    with conn.cursor() as cursor:

        # Query to select all athletes' refresh tokens from your specific table
        cursor.execute("SELECT athlete_id, refresh_token FROM strava_access_tokens")

        # Fetch all athletes
        athletes = cursor.fetchall() # <--- Corrected indentation here

    if not athletes:
        print('No athletes found in the database.')
        return

    # For each athlete, refresh their Strava token
    for athlete_id, refresh_token in athletes:

        # Use the refresh_token from the database to get new access_token
        payload = {
            'client_id': STRAVA_CLIENT_ID,
            'client_secret': STRAVA_CLIENT_SECRET,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
        
        response = requests.post(STRAVA_TOKEN_URL, params=payload)
        
        # If the request was successful, the new access token, refresh token and expiration date will be in the response
        if response.status_code == 200:
            new_access_token = response.json()['access_token']
            new_refresh_token = response.json()['refresh_token']
            new_expires_at = response.json()['expires_at']

            # Save these new tokens to your database
            with conn.cursor() as cursor:
                cursor.execute("""
                        UPDATE strava_access_tokens
                        SET access_token = %s, 
                            refresh_token = %s, 
                            expires_at = %s, 
                            last_updated = now(),
                            total_refreshes = total_refreshes + 1,
                            total_refresh_checks = total_refresh_checks + 1,
                            last_refreshed_by = 'local_script'
                        WHERE athlete_id = %s
                    """,
                    (new_access_token, new_refresh_token, new_expires_at, athlete_id))
                # Commit the transaction
                conn.commit()

            print(f'Successfully updated refresh token for athlete {athlete_id}.')
            
        else:
            print(f'Failed to refresh token for athlete {athlete_id}:', response.json())

if __name__ == "__main__":
    refresh_strava_tokens()