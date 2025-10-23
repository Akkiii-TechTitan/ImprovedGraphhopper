import requests
import urllib.parse
import csv
import os
import time

route_url = "https://graphhopper.com/api/1/route?"
key = "7ea9fa1c-282a-47fd-902f-f17b8c454373"
history_file = "route_history.csv"
favorites_file = "favorites.csv"

# ---------------- GEOCODING FUNCTION ---------------- #
def geocoding(location, key):
    while location == "":
        location = input("Enter the location again: ")
    geocode_url = "https://graphhopper.com/api/1/geocode?"
    url = geocode_url + urllib.parse.urlencode({"q": location, "limit": "1", "key": key})
    replydata = requests.get(url)
    json_data = replydata.json()
    json_status = replydata.status_code

    if json_status == 200 and len(json_data["hits"]) != 0:
        lat = json_data["hits"][0]["point"]["lat"]
        lng = json_data["hits"][0]["point"]["lng"]
        name = json_data["hits"][0]["name"]
        value = json_data["hits"][0]["osm_value"]

        country = json_data["hits"][0].get("country", "")
        state = json_data["hits"][0].get("state", "")

        if len(state) != 0 and len(country) != 0:
            new_loc = name + ", " + state + ", " + country
        elif len(state) != 0:
            new_loc = name + ", " + country
        else:
            new_loc = name

        print("Geocoding API URL for " + new_loc + " (Location Type: " + value + ")\n" + url)
    else:
        lat = "null"
        lng = "null"
        new_loc = location
        if json_status != 200:
            print("Geocode API status: " + str(json_status) + "\nError message: " + json_data["message"])
    return json_status, lat, lng, new_loc

# ---------------- DIRECTIONS FUNCTION ---------------- #
def get_directions(orig, dest, vehicle, key):
    op = "&point=" + str(orig[1]) + "%2C" + str(orig[2])
    dp = "&point=" + str(dest[1]) + "%2C" + str(dest[2])
    paths_url = route_url + urllib.parse.urlencode({"key": key, "vehicle": vehicle}) + op + dp
    paths_status = requests.get(paths_url).status_code
    paths_data = requests.get(paths_url).json()
    print("=================================================")
    print("Routing API Status: " + str(paths_status) + "\nRouting API URL:\n" + paths_url)
    print("=================================================")
    print("Directions from " + orig[3] + " to " + dest[3] + " by " + vehicle)
    print("=================================================")
    if paths_status == 200:
        miles = (paths_data["paths"][0]["distance"]) / 1000 / 1.61
        km = (paths_data["paths"][0]["distance"]) / 1000
        sec = int(paths_data["paths"][0]["time"] / 1000 % 60)
        mins = int(paths_data["paths"][0]["time"] / 1000 / 60 % 60)
        hrs = int(paths_data["paths"][0]["time"] / 1000 / 60 / 60)
        print("Distance Traveled: {0:.1f} miles / {1:.1f} km".format(miles, km))
        print("Trip Duration: {0:02d}:{1:02d}:{2:02d}".format(hrs, mins, sec))
        print("=================================================")
        for each in range(len(paths_data["paths"][0]["instructions"])):
            path = paths_data["paths"][0]["instructions"][each]["text"]
            distance = paths_data["paths"][0]["instructions"][each]["distance"]
            print("{0} ( {1:.1f} km / {2:.1f} miles )".format(path, distance / 1000, distance / 1000 / 1.61))
        print("=============================================")
        save_route_history(orig[3], dest[3], vehicle, km, hrs, mins, sec)
    else:
        print("Error message: " + paths_data["message"])
        print("*************************************************")

# ---------------- ROUTE HISTORY ---------------- #
def save_route_history(start, end, vehicle, km, hrs, mins, sec):
    if not os.path.exists(history_file):
        with open(history_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Start", "End", "Vehicle", "Distance_km", "Duration"])
    with open(history_file, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([start, end, vehicle, f"{km:.1f}", f"{hrs:02d}:{mins:02d}:{sec:02d}"])

def view_route_history():
    if not os.path.exists(history_file):
        print("No route history found.")
        return
    print("\n========================================")
    print("ROUTE HISTORY")
    print("========================================")
    with open(history_file, "r") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            print(f"{row[0]} ➜ {row[1]} | {row[2]} | {row[3]} km | {row[4]}")
    print("========================================\n")

# ---------------- FAVORITES FEATURE ---------------- #
def load_favorites():
    favorites = []
    if os.path.exists(favorites_file):
        with open(favorites_file, "r") as f:
            reader = csv.reader(f)
            next(reader, None)
            favorites = list(reader)
    return favorites

def save_favorite(name, location):
    if not os.path.exists(favorites_file):
        with open(favorites_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Name", "Location"])
    with open(favorites_file, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([name, location])
    print(f"✅ Saved '{name}' as favorite ({location}).\n")

def view_favorites():
    favorites = load_favorites()
    if not favorites:
        print("\nNo favorite locations saved yet.\n")
        return
    print("\n========================================")
    print(" FAVORITE LOCATIONS ")
    print("========================================")
    for i, fav in enumerate(favorites, start=1):
        print(f"[{i}] {fav[0]} - {fav[1]}")
    print("========================================")

# ---------------- RECOMMENDATIONS ---------------- #
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
    input("Press Enter to return to menu...")

# ---------------- MAIN ---------------- #
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
        print("[6] Exit")
        print("========================================")
        choice = input("Enter choice: ")

        if choice == "1":
            loc1 = input("\nStarting Location: ")
            if loc1.lower() in ["q", "quit"]:
                continue
            orig = geocoding(loc1, key)
            if not orig:
                continue

            loc2 = input("Destination: ")
            if loc2.lower() in ["q", "quit"]:
                continue
            dest = geocoding(loc2, key)
            if not dest:
                continue

            if orig[0] == 200 and dest[0] == 200:
                get_directions(orig, dest, vehicle, key)
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
                print("[2] Add a Favorite")
                print("[3] Get Directions Between Favorites")
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

                    print("\n========================================")
                    print("SELECT START LOCATION")
                    print("========================================")
                    view_favorites()
                    start_choice = input("Select start favorite: ")
                    if not start_choice.isdigit() or int(start_choice) not in range(1, len(favorites) + 1):
                        print("Invalid choice.\n")
                        continue
                    start_loc = favorites[int(start_choice) - 1][1]

                    print("\n========================================")
                    print("SELECT DESTINATION")
                    print("========================================")
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
                    input("Press Enter to return to menu...")

                elif fav_choice == "4":
                    break

                else:
                    print("Invalid choice. Please select 1–4.\n")

        elif choice == "6":
            print("\nExiting application... Goodbye!")
            time.sleep(1)
            break

        else:
            print("Invalid option. Please select 1–6.\n")

if __name__ == "__main__":
    main()
