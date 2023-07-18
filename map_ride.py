import polyline
import gmplot
import datetime
import time
from config import GOOGLE_MAPS_API_KEY
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

def generate_map(summary_polyline):
    if summary_polyline and summary_polyline.strip():
        route = polyline.decode(summary_polyline)
        latitudes, longitudes = zip(*route)
        gmap = gmplot.GoogleMapPlotter(latitudes[0], longitudes[0], 16, apikey=GOOGLE_MAPS_API_KEY)
        gmap.plot(latitudes, longitudes, 'cornflowerblue', edge_width=10)
        map_full_path = f"/tmp/map_{int(time.time())}.html"
        gmap.draw(map_full_path)
        logging.info(f"Map created and saved in path {map_full_path}")   
        
        # Get just the filename
        map_file_name = map_full_path.split('/')[-1]  # This will split on '/', and take the last part
        logging.info(f"Map file name: {map_file_name}")

        return map_file_name, True  # Return just the filename (not the whole path)
    else:
        logging.info(f"No summary_polyline available.")
        return None, False