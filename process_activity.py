from strava_utils import get_activity_by_id
import time
from chatgpt_utils import get_chatgpt_fact
from config import OPENAI_SECRET_KEY
from map_ride import generate_map
from zillow_utils import get_zillow_info_1, get_zillow_info_2
from config import ZILLOW_SERVER_TOKEN

def process_activity(access_token, model_choice, activity_id):
    logging_messages = []    
    strava_start = time.time()

    activity = get_activity_by_id(access_token, activity_id)
    logging_messages.append("Fetched the Strava activity.")

    strava_end = time.time()
    strava_time = strava_end - strava_start

    summary_polyline = activity['map'].get('summary_polyline', 'N/A')
    distance = activity.get('distance', 'N/A')

    gpt_fact, chatgpt_time = get_chatgpt_fact(distance, model_choice, OPENAI_SECRET_KEY)
    logging_messages.append(f"Fetched ChatGPT fact with model: {model_choice}.")

    zillow_start = time.time()
    zillow_return_1 = get_zillow_info_1(ZILLOW_SERVER_TOKEN, summary_polyline)
    zillow_return_2 = get_zillow_info_2(ZILLOW_SERVER_TOKEN, summary_polyline)
    zillow_end = time.time()
    zillow_time = zillow_end - zillow_start
    logging_messages.append(f"Fetched Zillow data return 1: {zillow_return_1}, return 2: {zillow_return_2}.")

    map_file, _ = generate_map(summary_polyline)
    logging_messages.append(f"Generated Google map from activity polyline.")

    messages = []
    formatted_date = activity['start_date_local'] 
    moving_time = activity.get('moving_time', 'N/A')
    average_speed = activity.get('average_speed', 'N/A')
    type_ = activity.get('type', 'N/A')

    messages.append(f"Activity: {formatted_date} | Distance: {distance} meters | Moving Time: {moving_time // 60} minutes and {moving_time % 60} seconds | Average Speed: {average_speed} m/s | Type: {type_}")
    messages.append('')
    messages.append(f"{model_choice.capitalize()} fact: {gpt_fact}")

    return messages, map_file, summary_polyline, zillow_return_1, zillow_return_2, logging_messages, strava_time, chatgpt_time, zillow_time, activity