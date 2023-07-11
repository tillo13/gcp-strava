# GCP-Strava Integration

## Introduction

This project serves as a detailed illustration of a Python application that seamlessly integrates the features of the Google Cloud Platform (GCP) with Strava's API. This app is designed to be served through a Google App Engine instance.

Google Cloud Platform (GCP) is Google's suite of cloud computing services. Several services of GCP have been utilized in this project.

Google App Engine (GAE) is a fully managed, serverless platform used for building highly scalable and reliable applications. In this project, our Flask application is hosted on GAE. GAE manages the app instances completely, allowing the app to scale up to serve traffic spikes and scale down when traffic decreases, without any management actions from our side.

Google Cloud Secret Manager is used to store and retrieve sensitive data such as the Strava client secret and the database password. These keys are fetched using the `get_secret_version` function in our `main.py` file. This allows us to handle sensitive data in a secure manner without hardcoding these values directly into our codebase.

Google SQL/PostgreSQL is used as the database to store user information and tokens. We're utilizing Google Cloud's Cloud SQL for this project. Google Cloud SQL is a fully-managed database service that makes it easy to set up and administer relational PostgreSQL databases on Google Cloud Platform. The database operations are handled in the `exchange_token` route in `main.py`.

Strava API is used to authenticate users and retrieve user activities. Strava provides access to user data through OAuth2.0 protocol. The authorization flow happens in the `login` and `exchange_token` functions in `main.py`.

## Project Execution

The actual execution of the project starts with the home route (`/`). Here, you can find a 'Login with Strava' button that redirects to the `/login` endpoint, which subsequently redirects to Strava's OAuth authorization page.

Upon successful authorization from the user, Strava redirects the user to our `/exchange_token` endpoint that fetches the tokens, saves them in the database, and fetches the user activities.

## Token Refresh with Google Cloud Functions and Cloud Scheduler

In addition to the core functionality, this project also utilizes Google Cloud Functions and Cloud Scheduler to implement token refresh for the Strava API.

Google Cloud Functions is a serverless execution environment for building and connecting cloud services. We have set up a Google Cloud Function named `update_tokens` to handle the token refresh process. This function can be triggered periodically to refresh the access tokens for the connected Strava accounts.

Google Cloud Scheduler is a fully managed cron job service that allows you to schedule the execution of functions or HTTP requests at specified intervals. We have set up a Cloud Scheduler job to trigger the `update_tokens` function at the desired frequency.

To set up token refresh using Google Cloud Functions and Cloud Scheduler:

1. Set up the `update_tokens` function: This function should be implemented in your Google Cloud project. It should include the logic to refresh the access tokens for the connected Strava accounts and update the tokens in the database. Make sure to deploy the function to the correct region and set up any necessary environment variables.

2. Configure Cloud Scheduler: Create a Cloud Scheduler job in your Google Cloud project. Configure the job to trigger the `update_tokens` function at the desired frequency (e.g., every hour, every day). Specify the appropriate HTTP target for the Cloud Function.

3. Verify and monitor: Once the Cloud Scheduler job is set up, you can use the Cloud Scheduler console to verify the job status and monitor the execution logs of the `update_tokens` function.

## How to Test

You can test the live functioning of this application at: [https://gcp-strava.wl.r.appspot.com/](https://gcp-strava.wl.r.appspot.com/)

## Conclusion

In summation, this project is a demonstration of efficient utilization of various Google Cloud services such as App Engine, Secret Manager, Cloud SQL, Google Cloud Functions, and Cloud Scheduler in conjunction with a third-party API (Strava in this case). It illustrates best practices for developing secure, scalable, and interactive web applications.

## Next steps
- Thinking about tying in a real-estate API to track houses for sale in the area of a polyline chart from strava.
- more sabermetric data...
- if ride/distance is zero, iterate until a ride isn't zero.
- save rides/chatGPT results?
- 
