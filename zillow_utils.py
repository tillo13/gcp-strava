import requests
import polyline
import logging

logger = logging.getLogger()

def get_zillow_info_1(access_token, encoded_polyline):
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
            logger.info(f"Zillow query 1: {url}")
            return response.json()
        else:
            return None

def get_zillow_info_2(access_token, encoded_polyline):
    if encoded_polyline and encoded_polyline.strip():
        decoded_polyline = polyline.decode(encoded_polyline)

        url = f"https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates?access_token={access_token}&limit=10&near={decoded_polyline[0][1]},{decoded_polyline[0][0]}&radius=100"
        response = requests.get(url)

        if response.status_code == 200:
            logger.info(f"Zillow query 2: {url}")
            return response.json()
        else:
            return None