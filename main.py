import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# Function to search for stations by name and retrieve details
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
        response.raise_for_status()  # Raise an error for bad status codes
        
        # Parse XML response
        root = ET.fromstring(response.content)
        
        # Namespace for ElementTree parsing
        ns = {"h": "http://hacon.de/hafas/proxy/hafas-proxy"}
        
        station_names = []
        station_info_map = {}  # To map station names to their detailed information
        
        # Find all StopLocation elements
        stop_locations = root.findall(".//h:StopLocation", ns)
        
        for stop_location in stop_locations:
            station_name = stop_location.get("name")
            ext_id = stop_location.get("extId")
            
            station_names.append(station_name)
            station_info_map[station_name] = {
                "extId": ext_id,
                "products": []
            }
            
            # Extract productAtStop elements
            product_at_stops = stop_location.findall(".//h:productAtStop", ns)
            
            for product_at_stop in product_at_stops:
                product_info = {
                    "name": product_at_stop.get("name"),
                    "line": product_at_stop.get("line"),
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

# Function to fetch departures for a selected station
def get_departures(api_key, ext_id):
    url = f"https://vbb.demo.hafas.de/fahrinfo/restproxy/2.32/departureBoard"
    params = {
        "accessId": api_key,
        "extId": ext_id
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise an error for bad status codes
        
        # Parse XML response
        root = ET.fromstring(response.content)
        
        # Namespace for ElementTree parsing
        ns = {"h": "http://hacon.de/hafas/proxy/hafas-proxy"}
        
        departures = []
        
        # Find all Departure elements
        departure_elements = root.findall(".//h:Departure", ns)
        
        for departure_elem in departure_elements:
            departure = {
                "line": departure_elem.get("name"),
                "type": departure_elem.get("type"),
                "stop": departure_elem.get("stop"),
                "stop_id": departure_elem.get("stopid"),
                "stop_extId": departure_elem.get("stopExtId"),
                "prognosis_type": departure_elem.get("prognosisType"),
                "time": departure_elem.get("time"),
                "date": departure_elem.get("date"),
                "rt_time": departure_elem.get("rtTime"),
                "rt_date": departure_elem.get("rtDate"),
                "reachable": departure_elem.get("reachable"),
                "direction": departure_elem.get("direction"),
                "platform": departure_elem.findtext(".//h:platform", namespaces=ns),
                "remarks": []
            }
            
            # Extract remarks if available
            remark_elems = departure_elem.findall(".//h:Remark", namespaces=ns)
            for remark_elem in remark_elems:
                departure["remarks"].append(remark_elem.findtext(".//h:Text", namespaces=ns))
            
            departures.append(departure)
        
        return departures
        
    except requests.exceptions.RequestException as e:
        print(f"Error occurred during departure fetch: {e}")
        return None
    except ET.ParseError as e:
        print(f"Error parsing XML response: {e}")
        return None

# Function to select a station from the list and display detailed information
def select_station_and_display(station_names, station_info_map, api_key):
    if not station_names:
        print("No station names found.")
        return
    
    print("Station names:")
    for index, name in enumerate(station_names):
        print(f"{index + 1}. {name}")
    
    # Ask user to select a station
    while True:
        try:
            choice = int(input("\nSelect a station (enter number): "))
            if 1 <= choice <= len(station_names):
                selected_station = station_names[choice - 1]
                break
            else:
                print("Invalid choice. Please enter a valid number.")
        except ValueError:
            print("Invalid input. Please enter a number.")
    
    # Display detailed information for the selected station
    station_info = station_info_map[selected_station]
    products_summary = []
    for product in station_info["products"]:
        if product["type"] == "Bus":
            products_summary.append(f"{product['name']} 🚌")
        elif product["type"] in ("S", "U"):
            products_summary.append(f"{product['name']} 🚆")
        else:
            products_summary.append(product['name'])
    
    summary = ", ".join(products_summary)
    print(f"\nHere are the details for '{selected_station}':")
    print(f"Available Connections: {summary}")
    
    # Fetch and display departures for the selected station
    departures = get_departures(api_key, station_info["extId"])
    if departures:
        print("\nDepartures:")
        for departure in departures:
            line = departure["line"]
            direction = departure["direction"]
            planned_time = departure["time"]
            planned_date = departure["date"]
            rt_time = departure["rt_time"]
            rt_date = departure["rt_date"]
            platform = departure["platform"]
            
            # Calculate delay or early status
            if rt_time and planned_time:
                rt_datetime = datetime.strptime(f"{rt_date} {rt_time}", "%Y-%m-%d %H:%M:%S")
                planned_datetime = datetime.strptime(f"{planned_date} {planned_time}", "%Y-%m-%d %H:%M:%S")
                delay = (rt_datetime - planned_datetime).total_seconds() // 60
                if delay > 0:
                    delay_status = f" (Delay: {delay} min)"
                    rt_time_formatted = f"\033[91m{rt_time}\033[0m"  # Red color for delay
                elif delay < 0:
                    delay_status = f" (Early: {-delay} min)"
                    rt_time_formatted = f"\033[93m{rt_time}\033[0m"  # Yellow color for early
                else:
                    delay_status = ""
                    rt_time_formatted = rt_time
                
                # Calculate minutes left to departure
                current_datetime = datetime.now()
                time_to_departure = (rt_datetime - current_datetime).total_seconds() // 60
                
                # Determine time left string
                if time_to_departure < 1:
                    time_left_str = "NOW"
                else:
                    time_left_str = f"{time_to_departure} min"
            else:
                delay_status = ""
                rt_time_formatted = rt_time
                time_left_str = "N/A"
            
            # Print the departure information
            print(f"{line} to {direction}")
            print(f"  Real Time: {rt_time_formatted}{delay_status}")
            print(f"  Time Left: {time_left_str}")
            print(f"  Platform: {platform if platform else 'None'}")
            if departure["remarks"]:
                print("  Remarks:")
                for remark in departure["remarks"]:
                    print(f"    - {remark}")
            print()  # Empty line for readability
    else:
        print("No departures found.")

# Function to handle user input for station search and selection
def handle_station_search(api_key):
    while True:
        station_name = input("Enter a part of station name to search (less than one word): ")
        try:
            max_results = int(input("How many results do you want to show? "))
            break
        except ValueError:
            print("Invalid input. Please enter a number.")
    
    station_names, station_info_map = get_station_names(api_key, station_name, max_results)
    
    if station_names and station_info_map:
        # Select a station from the list and display detailed information
        select_station_and_display(station_names, station_info_map, api_key)
    else:
        print(f"No station names found for '{station_name}'.")

# Example usage
if __name__ == "__main__":
    api_key = "kevil-46e5-85e7-f0cb650fe43b"
    
    # Handle station search and selection
    handle_station_search(api_key)
