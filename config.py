from google.cloud import secretmanager

def get_secret_version(project_id, secret_id, version_id="latest"):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(name=name)
    return response.payload.data.decode('UTF-8')

GCP_PROJECT_ID = "97418787038"
SITE_HOMEPAGE = "https://gcp-strava.wl.r.appspot.com/"

# Strava API Configurations
STRAVA_CLIENT_ID = "110278"
REDIRECT_URL = "https://gcp-strava.wl.r.appspot.com/exchange_token"
STRAVA_SECRET_API_ID = "strava_client_secret"
STRAVA_CLIENT_SECRET = get_secret_version(GCP_PROJECT_ID, STRAVA_SECRET_API_ID) 
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITY_URL = "https://www.strava.com/api/v3/athlete/activities"

# Database Configurations
DB_USER = 'postgres'
DB_NAME = 'gcp_strava_data'
CLOUD_SQL_CONNECTION_NAME = 'gcp-strava:us-central1:gcp-default'
GOOGLE_SECRET_DB_ID = "gcp_strava_db_password"
DB_PASSWORD = get_secret_version(GCP_PROJECT_ID, GOOGLE_SECRET_DB_ID)

# OpenAI API Configurations
OPENAI_API_KEY_ID = "OPENAI_API_KEY"
OPENAI_SECRET_KEY = get_secret_version(GCP_PROJECT_ID, OPENAI_API_KEY_ID)

# Google Maps API Configurations
GOOGLE_MAPS_SECRET_API_ID = "google_maps_api_key"
GOOGLE_MAPS_API_KEY = get_secret_version(GCP_PROJECT_ID, GOOGLE_MAPS_SECRET_API_ID)

# Zillow Server Token
ZILLOW_SERVER_TOKEN_ID = "ZILLOW_SERVER_TOKEN"
ZILLOW_SERVER_TOKEN = get_secret_version(GCP_PROJECT_ID, ZILLOW_SERVER_TOKEN_ID)