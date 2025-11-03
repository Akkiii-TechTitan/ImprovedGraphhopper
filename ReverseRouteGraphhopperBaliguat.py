import requests
import urllib.parse
import csv
import os
import time

# ---------------- CONFIG ----------------
route_url = "https://graphhopper.com/api/1/route?"
key = "7ea9fa1c-282a-47fd-902f-f17b8c454373"  # use your real key here
history_file = "route_history.csv"
favorites_file = "favorites.csv"

# ---------------- GEOCODING FUNCTION ----------------
def geocoding(location, key):
    # ensure non-empty
    while location == "":
        location = input("Enter the location again: ")

    geocode_url = "https://graphhopper.com/api/1/geocode?"
    # urlencode the location so spaces/special chars don't break request
    params = {"q": location, "limit": "1", "key": key}
    url = geocode_url + urllib.parse.urlencode(params)
    try:
        reply = requests.get(url, timeout=10)
    except Exception as e:
        print(f"Geocoding request failed: {e}")
        return 0, None, None, location

    try:
        json_data = reply.json()
    except Exception:
        print(f"Invalid JSON response from geocoding (status {reply.status_code}). Raw text:\n{reply.text}")
        return reply.status_code, None, None, location

    status = reply.status_code
    if status == 200 and json_data.get("hits"):
        hit = json_data["hits"][0]
        lat = hit["point"]["lat"]
        lng = hit["point"]["lng"]
        # build a human-friendly display name if available
        name = hit.get("name", location)
        country = hit.get("country", "")
        state = hit.get("state", "")
        # prefer name, state, country formatting (but skip empty parts)
        parts = [p for p in (name, state, country) if p]
        display_name = ", ".join(parts) if parts else location
        print(f"Geocoding OK: {display_name}\nURL: {url}")
        return status, lat, lng, display_name
    else:
        # print helpful debug info
        msg = json_data.get("message") if isinstance(json_data, dict) else None
        print(f"Geocoding failed (status {status}). Message: {msg}")
        return status, None, None, location

# ---------------- DIRECTIONS FUNCTION ----------------
def get_directions(orig, dest, vehicle, key):
    # orig and dest are tuples: (status, lat, lng, display_name)
    if orig[1] is None or orig[2] is None or dest[1] is None or dest[2] is None:
        print("Cannot compute directions: missing coordinates.")
        return

    # GraphHopper expects point=lat,lon
    op = "&point=" + urllib.parse.quote_plus(f"{orig[1]},{orig[2]}")
    dp = "&point=" + urllib.parse.quote_plus(f"{dest[1]},{dest[2]}")
    # build route request
    params = {"key": key, "vehicle": vehicle, "instructions": "true", "points_encoded": "false"}
    paths_url = route_url + urllib.parse.urlencode(params) + op + dp

    try:
        reply = requests.get(paths_url, timeout=15)
    except Exception as e:
        print(f"Routing request failed: {e}")
        return

    try:
        paths_data = reply.json()
    except Exception:
        print(f"Invalid JSON from routing (status {reply.status_code}). Raw:\n{reply.text}")
        return

    paths_status = reply.status_code
    print("=================================================")
    print("Routing API Status: " + str(paths_status) + "\nRouting API URL:\n" + paths_url)
    print("=================================================")
    print("Directions from " + str(orig[3]) + " to " + str(dest[3]) + " by " + vehicle)
    print("=================================================")

    if paths_status == 200 and "paths" in paths_data and len(paths_data["paths"]) > 0:
        path = paths_data["paths"][0]
        distance_m = path.get("distance", 0)
        distance_km = distance_m / 1000.0
        time_ms = path.get("time", 0)
        sec = int(time_ms / 1000 % 60)
        mins = int(time_ms / 1000 / 60 % 60)
        hrs = int(time_ms / 1000 / 60 / 60)
        print("Distance Traveled: {0:.1f} km".format(distance_km))
        print("Trip Duration: {0:02d}:{1:02d}:{2:02d}".format(hrs, mins, sec))
        print("=================================================")
        instructions = path.get("instructions", [])
        if instructions:
            for idx, inst in enumerate(instructions, start=1):
                text = inst.get("text", "")
                inst_dist = inst.get("distance", 0)
                print(f"{idx}. {text} ( {inst_dist/1000:.2f} km )")
        else:
            print("No turn-by-turn instructions available for this route.")
        print("=============================================")
        # save to history using the display names
        save_route_history(orig[3], dest[3], vehicle, distance_km, hrs, mins, sec)
    else:
        # print the error details returned from GraphHopper (if any)
        err_msg = paths_data.get("message") if isinstance(paths_data, dict) else None
        print("Error message from routing API:", err_msg)
        # occasionally GraphHopper returns hints field with useful info
        if isinstance(paths_data, dict) and "hints" in paths_data:
            print("Hints:", paths_data["hints"])
        print("*************************************************")

# ---------------- ROUTE HISTORY ----------------
def save_route_history(start, end, vehicle, km, hrs, mins, sec):
    header = ["Start", "End", "Vehicle", "Distance_km", "Duration", "Timestamp"]
    exists = os.path.exists(history_file)
    with open(history_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(header)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([start, end, vehicle, f"{km:.2f}", f"{hrs:02d}:{mins:02d}:{sec:02d}", timestamp])

def view_route_history():
    if not os.path.exists(history_file):
        print("No route history found.")
        return
    print("\n========================================")
    print("ROUTE HISTORY")
    print("========================================")
    with open(history_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        rows = list(reader)
        if not rows:
            print("No routes recorded yet.")
        else:
            for i, row in enumerate(rows, start=1):
                # row format: Start,End,Vehicle,Distance_km,Duration,Timestamp
                start, end, veh, dist, dur, ts = (row + [""] * 6)[:6]
                print(f"[{i}] {start} ➜ {end} | {veh} | {dist} km | {dur} | {ts}")
    print("========================================\n")

# ---------------- FAVORITES ----------------
def load_favorites():
    favs = []
    if os.path.exists(favorites_file):
        with open(favorites_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            favs = [row for row in reader if row]
    return favs

def save_favorite(name, location):
    exists = os.path.exists(favorites_file)
    with open(favorites_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["Name", "Location"])
        writer.writerow([name, location])
    print(f"✅ Saved favorite: {name} -> {location}")

def view_favorites():
    favs = load_favorites()
    if not favs:
        print("No favorite locations saved yet.")
        return
    print("\n========================================")
    print(" FAVORITE LOCATIONS ")
    print("========================================")
    for i, fav in enumerate(favs, start=1):
        print(f"[{i}] {fav[0]} - {fav[1]}")
    print("========================================")

# ---------------- RECOMMENDATIONS ----------------
def city_recommendations(vehicle, key):
    cities = {
        "1": ("Manila", ["Intramuros", "Rizal Park", "Binondo", "National Museum"]),
        "2": ("Cebu", ["Magellan's Cross", "Temple of Leah", "Sirao Garden", "Fort San Pedro"]),
        "3": ("Davao", ["Eden Nature Park", "Philippine Eagle Center", "Roxas Night Market"]),
        "4": ("Baguio", ["Burnham Park", "Mines View Park", "Camp John Hay", "The Mansion"]),
        "5": ("Iloilo", ["Miag-ao Church", "Iloilo River Esplanade", "Garin Farm"]),
    }

    print("\n========================================")
    print(" CITY RECOMMENDATIONS ")
    print("========================================")
    for key_city, (city_name, _) in cities.items():
        print(f"[{key_city}] {city_name}")
    print("========================================")

    choice = input("Select a city: ")
    if choice not in cities:
        print("Invalid city choice.\n")
        return

    city_name, spots = cities[choice]
    print(f"\nTop destinations in {city_name}:")
    for i, spot in enumerate(spots, start=1):
        print(f"[{i}] {spot}")
    dest_choice = input("Select a destination: ")

    if not dest_choice.isdigit() or int(dest_choice) not in range(1, len(spots) + 1):
        print("Invalid destination choice.\n")
        return

    selected_spot = spots[int(dest_choice) - 1]

    print("\nWould you like to use a favorite location as your starting point?")
    print("[1] Yes, use a favorite")
    print("[2] No, enter manually")
    start_choice = input("Enter choice: ")

    if start_choice == "1":
        favorites = load_favorites()
        if not favorites:
            print("No favorites found. Please add one first.\n")
            return
        view_favorites()
        pick = input("Select a favorite: ")
        if not pick.isdigit() or int(pick) not in range(1, len(favorites) + 1):
            print("Invalid choice.\n")
            return
        start_loc = favorites[int(pick) - 1][1]
    else:
        start_loc = input("\nEnter your starting location: ")

    orig = geocoding(start_loc, key)
    dest = geocoding(selected_spot + ", " + city_name, key)

    if orig[0] == 200 and dest[0] == 200:
        get_directions(orig, dest, vehicle, key)
    else:
        print("Error getting directions for the chosen recommendation.\n")
    input("Press Enter to return to menu...")

# ---------------- REVERSE LAST ROUTE ----------------
def reverse_last_route(vehicle, key):
    if not os.path.exists(history_file):
        print("No route history found.\n")
        return

    with open(history_file, "r", encoding="utf-8") as f:
        reader = list(csv.reader(f))
        if len(reader) <= 1:
            print("No previous routes to reverse.\n")
            return
        last_route = reader[-1]  # last CSV row
        start = last_route[0]
        end = last_route[1]

    print(f"\nReversing last route: {end} ➜ {start}")
    orig = geocoding(end, key)
    dest = geocoding(start, key)

    if orig[0] == 200 and dest[0] == 200:
        get_directions(orig, dest, vehicle, key)
    else:
        print("❌ Could not reverse route due to geocoding error.\n")

# ---------------- MAIN ----------------
def main():
    vehicle = "car"
    while True:
        print("========================================")
        print("  GRAPHOPPER ROUTE APPLICATION")
        print("========================================")
        print("[1] Get Directions")
        print("[2] Change Vehicle Profile")
        print("[3] View Last Routes")
        print("[4] Recommendations")
        print("[5] Favorites")
        print("[6] Reverse Last Route")
        print("[7] Exit")
        print("========================================")
        choice = input("Enter choice: ")

        if choice == "1":
            loc1 = input("\nStarting Location: ")
            if loc1.lower() in ["q", "quit"]:
                continue
            orig = geocoding(loc1, key)

            loc2 = input("Destination: ")
            if loc2.lower() in ["q", "quit"]:
                continue
            dest = geocoding(loc2, key)

            if orig[0] == 200 and dest[0] == 200:
                get_directions(orig, dest, vehicle, key)
            else:
                print("Error getting route. Make sure both locations are spelled correctly and your API key is valid.\n")
            input("Press Enter to return to menu...")

        elif choice == "2":
            print("\nAvailable vehicle profiles: car, bike, foot")
            new_vehicle = input("Enter vehicle: ").lower()
            if new_vehicle in ["car", "bike", "foot"]:
                vehicle = new_vehicle
                print(f"Vehicle profile set to: {vehicle}\n")
            else:
                print("Invalid vehicle. Defaulting to 'car'.")
                vehicle = "car"

        elif choice == "3":
            view_route_history()
            input("Press Enter to return to menu...")

        elif choice == "4":
            city_recommendations(vehicle, key)

        elif choice == "5":
            while True:
                print("\n========================================")
                print(" FAVORITE LOCATIONS MENU ")
                print("========================================")
                print("[1] View Favorites")
                print("[2] Add Favorite")
                print("[3] Get Directions Between Favorites / Custom")
                print("[4] Return to Main Menu")
                print("========================================")
                fav_choice = input("Enter choice: ")

                if fav_choice == "1":
                    view_favorites()
                    input("Press Enter to return to menu...")

                elif fav_choice == "2":
                    name = input("Enter a name for this favorite (e.g., Home, Work): ")
                    location = input("Enter the location address or city: ")
                    save_favorite(name, location)
                    input("Press Enter to return to menu...")

                elif fav_choice == "3":
                    favorites = load_favorites()
                    if not favorites:
                        print("No favorites found. Please add one first.\n")
                        input("Press Enter to return to menu...")
                        continue

                    print("\nSELECT START LOCATION")
                    view_favorites()
                    start_choice = input("Select start favorite: ")
                    if not start_choice.isdigit() or int(start_choice) not in range(1, len(favorites) + 1):
                        print("Invalid choice.\n")
                        continue
                    start_loc = favorites[int(start_choice) - 1][1]

                    print("\nSELECT DESTINATION")
                    print("[1] Choose from Favorites")
                    print("[2] Enter a Custom Destination")
                    dest_option = input("Enter choice: ")

                    if dest_option == "1":
                        view_favorites()
                        end_choice = input("Select destination favorite: ")
                        if not end_choice.isdigit() or int(end_choice) not in range(1, len(favorites) + 1):
                            print("Invalid choice.\n")
                            continue
                        end_loc = favorites[int(end_choice) - 1][1]

                    elif dest_option == "2":
                        end_loc = input("Enter custom destination: ")

                    else:
                        print("Invalid choice.\n")
                        continue

                    orig = geocoding(start_loc, key)
                    dest = geocoding(end_loc, key)

                    if orig[0] == 200 and dest[0] == 200:
                        get_directions(orig, dest, vehicle, key)
                    else:
                        print("Error getting route for selected favorites/destination.\n")
                    input("Press Enter to return to menu...")

                elif fav_choice == "4":
                    break

                else:
                    print("Invalid choice. Please select 1–4.\n")

        elif choice == "6":
            reverse_last_route(vehicle, key)
            input("Press Enter to return to menu...")

        elif choice == "7":
            print("\nExiting application... Goodbye!")
            time.sleep(1)
            break

        else:
            print("Invalid option. Please select 1–7.\n")

if __name__ == "__main__":
    main()
