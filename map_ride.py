import polyline
import gmplot
import datetime
import time
from config import GOOGLE_MAPS_API_KEY

def generate_map(summary_polyline):
    if summary_polyline and summary_polyline.strip():
        route = polyline.decode(summary_polyline)
        latitudes, longitudes = zip(*route)

        gmap = gmplot.GoogleMapPlotter(latitudes[0], longitudes[0], 16, apikey=GOOGLE_MAPS_API_KEY)
        gmap.plot(latitudes, longitudes, 'cornflowerblue', edge_width=10)
        map_file = f"static/maps/map_{int(time.time())}.html"
        gmap.draw(map_file)
        return map_file, True
    else:
        print(f"No summary_polyline available.")
        return None, False