import requests
import polyline
import logging 

logger = logging.getLogger()

def get_zillow_info(access_token, encoded_polyline):
    results = []
    if encoded_polyline and encoded_polyline.strip():
        decoded_polyline = polyline.decode(encoded_polyline)
        formatted_polyline = ""
        for coordinate in decoded_polyline:
            latitude, longitude = coordinate
            formatted_polyline += f"{longitude},{latitude},"

        if formatted_polyline.endswith(','):
            formatted_polyline = formatted_polyline[:-1]

        url = f"https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates?access_token={access_token}&limit=10&poly={formatted_polyline}"
        response = requests.get(url)

        if response.status_code == 200:
            logger.info(f"Zillow query: {url}")
            return response.json()
        else:
            return None