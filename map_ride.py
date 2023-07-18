import requests
import polyline
import gmplot
from psycopg2 import connect
from config import STRAVA_CLIENT_SECRET, STRAVA_TOKEN_URL, GOOGLE_MAPS_API_KEY
from db_utils import create_conn

def generate_map(DB_PW, athlete_id):
    conn = create_conn()
    cur = conn.cursor()

    cur.execute(f"SELECT refresh_token, client_id FROM strava_access_tokens WHERE athlete_id = {athlete_id}")
    refresh_token, client_id = cur.fetchone()

    payload = {
        'client_id': client_id,
        'client_secret': STRAVA_CLIENT_SECRET,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
        'f': 'json'
    }

    response = requests.post(STRAVA_TOKEN_URL, params=payload)
    access_token = response.json()['access_token']

    headers = {'Authorization': f'Bearer {access_token}'}
    params = {'per_page': 50, 'page': 1}
    response = requests.get("https://www.strava.com/api/v3/athlete/activities", headers=headers, params=params)

    activities = response.json()
    for count, activity in enumerate(activities[::-1], start=1):
        summary_polyline = activity.get("map", {}).get("summary_polyline")
        if summary_polyline and summary_polyline.strip():
            route = polyline.decode(summary_polyline)
            latitudes, longitudes = zip(*route)

            gmap = gmplot.GoogleMapPlotter(latitudes[0], longitudes[0], 16, apikey=GOOGLE_MAPS_API_KEY)
            gmap.plot(latitudes, longitudes, 'cornflowerblue', edge_width=10)
            map_file = f"/tmp/map_{activity['id']}.html"
            gmap.draw(map_file)

            print(f"Match found for athlete_id {athlete_id} after scanning {count} activities.")
            return map_file, True

    print(f"No match found for athlete_id {athlete_id} after scanning all activities.")
    return None, False