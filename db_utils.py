from google.cloud import secretmanager
import sqlalchemy
from sqlalchemy import text
from psycopg2 import OperationalError

GCP_PROJECT_ID = "97418787038"

def get_secret_version(project_id, secret_id, version_id="latest"):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(name=name)
    return response.payload.data.decode('UTF-8')

def create_conn(db_user, db_password, db_name, cloud_sql_connection_name):
    try:
        engine = sqlalchemy.create_engine(
            sqlalchemy.engine.url.URL.create(
                drivername="postgresql+psycopg2",
                username=db_user,
                password=db_password,
                database=db_name,
                host=f'/cloudsql/{cloud_sql_connection_name}',
            ),
        )
        return engine                                     
    except OperationalError:
        return 'Unable to connect to the database, please try again later.'