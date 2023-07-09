# GCP-Strava Integration

## Introduction
This project serves as a detailed illustration of a Python application that seamlessly integrates the features of the Google Cloud Platform (GCP) with Strava's API. This app is designed to be served through a Google App Engine instance.

## Google Cloud Platform (GCP) 

Google Cloud Platform is Google's suite of cloud computing services. Several services of GCP have been utilized in this project.

### Google App Engine (GAE)

GAE is a fully managed, serverless platform used for building highly scalable and reliable applications. 

In this project, our Flask application is hosted on GAE. GAE manages the app instances completely, allowing the app to scale up to serve traffic spikes and scale down when traffic decreases, without any management actions from our side.

The App Engine instance class definition can be found in the `app.yaml` file in the root directory, which specifies details for the App Engine application's setup.

### Google Cloud Secret Manager

In this project, the Google Cloud Secret Manager service is used to store and retrieve sensitive data such as the Strava client secret and the database password.

These keys are fetched using the `get_secret_version` function in our `main.py`. This allows us to handle sensitive data in a secure manner without the potential exposure risk that could come from hardcoding these values directly into our codebase.

We fetch the client secret for Strava and the database password from the Secret Manager in `main.py`.

## PostgreSQL Connection

PostgreSQL is used as the database to store user information and tokens. We're utilizing Google Cloud's Cloud SQL for this project. Google Cloud SQL is a fully-managed database service that makes it easy to set up and administer relational PostgreSQL databases on Google Cloud Platform. 

We established a PostgreSQL database connection using Python's SQLAlchemy library. This connection is utilized to perform database operations like fetching existing user tokens and storing new tokens. The database operations are handled in the `exchange_token` route in `main.py`.

## Strava API

This project uses Strava's RESTful API to authenticate users and retrieve user activities. Strava provides access to user data through OAuth2.0 protocol.

The initial call to the `/login` endpoint redirects the user to Strava's authorization url. After the user approves the requested permissions, Strava redirects back to our app `/exchange_token` endpoint with a `code` parameter which we can exchange for an access token. 

This whole Strava authorization flow happens in the `login` and `exchange_token` functions in `main.py`. 

After receiving the access token, the app makes authenticated requests to Strava's API to fetch user’s activities.

## Project Execution

The actual execution of the project starts with the home route (`/`). Here, you can find a 'Login with Strava' button that redirects to the `/login` endpoint, which subsequently redirects to Strava's OAuth authorization page.

Upon successful authorization from the user, Strava redicts the user to our `/exchange_token` endpoint that does all the heavy lifting of fetching the tokens, saving them in the database and finally, fetching the user activities.

## How to test

You can test the live functioning of this application at: https://gcp-strava.wl.r.appspot.com/ 


## Conclusion

In summation, this project is a demonstration of efficient utilization of various Google Cloud services such as App Engine, Secret Manager, Cloud SQL in conjunction with a third-party API (Strava in this case), illustrating best practices for developing secure, scalable and interactive web applications.