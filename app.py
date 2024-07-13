from flask import Flask, render_template, request, jsonify
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import pytz

app = Flask(__name__)

# Replace with your actual API key
api_key = "kevil-46e5-85e7-f0cb650fe43b"

def get_station_names(api_key, station_name, max_results):
    url = "https://vbb.demo.hafas.de/fahrinfo/restproxy/2.32/location.name"
    params = {
        "accessId": api_key,
        "input": station_name,
        "maxNo": max_results,
        "type": "S"
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        ns = {"h": "http://hacon.de/hafas/proxy/hafas-proxy"}
        
        station_names = []
        station_info_map = {}
        
        stop_locations = root.findall(".//h:StopLocation", ns)
        
        for stop_location in stop_locations:
            station_name = stop_location.get("name")
            ext_id = stop_location.get("extId")
            
            station_names.append(station_name)
            station_info_map[station_name] = {
                "extId": ext_id,
                "products": []
            }
            
            product_at_stops = stop_location.findall(".//h:productAtStop", ns)
            
            for product_at_stop in product_at_stops:
                product_info = {
                    "name": product_at_stop.get("name"),
                    "type": product_at_stop.get("catOut")
                }
                station_info_map[station_name]["products"].append(product_info)
        
        return station_names, station_info_map
        
    except requests.exceptions.RequestException as e:
        print(f"Error occurred during station search: {e}")
        return None, None
    except ET.ParseError as e:
        print(f"Error parsing XML response: {e}")
        return None, None

def get_departure_board(api_key, station_id):
    url = f"https://vbb.demo.hafas.de/fahrinfo/restproxy/2.32/departureBoard?accessId={api_key}&extId={station_id}&duration=60"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        ns = {"h": "http://hacon.de/hafas/proxy/hafas-proxy"}
        
        departures = []
        
        # Extract station name from the first <Departure> element
        first_departure = root.find(".//h:Departure", ns)
        if first_departure is not None:
            station_name = first_departure.get("stop")
        else:
            station_name = "Unknown"
        
        # Berlin timezone
        berlin_tz = pytz.timezone('Europe/Berlin')
        current_time = datetime.now(berlin_tz).replace(second=0, microsecond=0)
        
        for departure_elem in root.findall(".//h:Departure", ns):
            departure = {}
            
            departure["name"] = departure_elem.get("name")
            departure["direction"] = departure_elem.get("direction")
            departure["planned_time"] = departure_elem.get("time")
            departure["planned_date"] = departure_elem.get("date")
            departure["real_time"] = departure_elem.get("rtTime")
            departure["real_date"] = departure_elem.get("rtDate")
            
            product_elem = departure_elem.find(".//h:ProductAtStop", ns)
            if product_elem is not None:
                departure["product_type"] = product_elem.get("catOut")  # Retrieve product category
            else:
                departure["product_type"] = "Unknown"
            
            # Check if departure is cancelled
            departure["cancelled"] = departure_elem.get("cancelled") == "true"
            
            if departure["cancelled"]:
                departure["time_left_str"] = "Cancelled"
                
                # Parse notes for cancellation reason
                notes = []
                for note_elem in departure_elem.findall(".//h:Note[@type='R']", ns):
                    note = {
                        "key": note_elem.get("key"),
                        "type": note_elem.get("type"),
                        "txtN": note_elem.get("txtN")
                    }
                    notes.append(note)
                
                departure["notes"] = notes
            
            else:
                # Calculate time left to departure
                if departure["real_time"]:
                    rt_datetime_str = f"{departure['real_date']} {departure['real_time']}"
                    rt_datetime = datetime.strptime(rt_datetime_str, "%Y-%m-%d %H:%M:%S")
                else:
                    planned_datetime_str = f"{departure['planned_date']} {departure['planned_time']}"
                    rt_datetime = datetime.strptime(planned_datetime_str, "%Y-%m-%d %H:%M:%S")
                
                # Convert to Berlin timezone
                rt_datetime = berlin_tz.localize(rt_datetime)
                
                time_to_departure = (rt_datetime - current_time).total_seconds() // 60
                
                if time_to_departure <= 0:
                    departure["time_left_str"] = "Jetz"
                else:
                    departure["time_left_str"] = f"{int(time_to_departure)} '"
            
            departures.append(departure)
        
        return departures, station_name
    
    except requests.exceptions.RequestException as e:
        print(f"Error occurred during departure board request: {e}")
        return None, "Unknown"
    except ET.ParseError as e:
        print(f"Error parsing XML response: {e}")
        return None, "Unknown"

@app.route('/', methods=['GET', 'POST'])
def search_station():
    if request.method == 'POST':
        station_name = request.form['station_name']
        max_results = request.form.get('max_results', 5, type=int)
        station_names, station_info_map = get_station_names(api_key, station_name, max_results)
        if station_names and station_info_map:
            return render_template('search.html', station_names=station_names, station_info_map=station_info_map)
        else:
            return render_template('search.html', error_message=f"No stations found for '{station_name}'")
    return render_template('search.html')

@app.route('/departures/<station_id>')
def show_departures(station_id):
    departures, station_name = get_departure_board(api_key, station_id)
    
    if departures:
        # Sort departures by real_time or planned_time
        departures_sorted = sorted(departures, key=lambda dep: dep['real_time'] or dep['planned_time'])
        return render_template('departures.html', departures=departures_sorted, station_name=station_name, station_id=station_id)
    else:
        return render_template('departures.html', error_message="Failed to fetch departures.")

@app.route('/api/departures/<station_id>')
def api_departures(station_id):
    departures, station_name = get_departure_board(api_key, station_id)
    
    if departures:
        departures_sorted = sorted(departures, key=lambda dep: dep['real_time'] or dep['planned_time'])
        return jsonify(departures=departures_sorted, station_name=station_name)
    else:
        return jsonify(error="Failed to fetch departures."), 500

if __name__ == '__main__':
    app.run(debug=True)
