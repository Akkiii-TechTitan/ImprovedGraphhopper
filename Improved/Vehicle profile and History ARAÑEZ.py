import requests
import urllib.parse
import csv
import os
import time

route_url = "https://graphhopper.com/api/1/route?"
key = "7ea9fa1c-282a-47fd-902f-f17b8c454373"
history_file = "route_history.csv"


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
        elif len(country) != 0:
            new_loc = name + ", " + country
        else:
            new_loc = name

        print("Geocoding API URL for " + new_loc + " (Location Type: " + value + ")\n" + url)
    else:
        lat = "null"
        lng = "null"
        new_loc = location
        if json_status != 200:
            print("Geocode API status: " + str(json_status))
            if "message" in json_data:
                print("Error message: " + json_data["message"])
    return json_status, lat, lng, new_loc


def get_directions(orig, dest, vehicle, key):
    op = "&point=" + str(orig[1]) + "%2C" + str(orig[2])
    dp = "&point=" + str(dest[1]) + "%2C" + str(dest[2])
    paths_url = route_url + urllib.parse.urlencode({"key": key, "vehicle": vehicle}) + op + dp

    response = requests.get(paths_url)
    paths_status = response.status_code
    paths_data = response.json()

    print("=================================================")
    print("Routing API Status: " + str(paths_status) + "\nRouting API URL:\n" + paths_url)
    print("=================================================")
    print("Directions from " + orig[3] + " to " + dest[3] + " by " + vehicle)
    print("=================================================")

    if paths_status == 200 and "paths" in paths_data:
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
        if "message" in paths_data:
            print("Error message: " + paths_data["message"])
        else:
            print("Error getting route — please check the locations or vehicle type.")
        print("*************************************************")


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


def main():
    vehicle = "car"
    while True:
        print("========================================")
        print("  GRAPHOPPER ROUTE APPLICATION")
        print("========================================")
        print("[1] Get Directions")
        print("[2] Change Vehicle Profile")
        print("[3] View Last Routes")
        print("[4] Exit")
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
            print("\nExiting application... Goodbye!")
            time.sleep(1)
            break

        else:
            print("Invalid option. Please select 1–4.\n")


if __name__ == "__main__":
    main()
