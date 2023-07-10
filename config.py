# Secrets obtained securely from secrets manager
from secrets_manager import get_secret_version

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