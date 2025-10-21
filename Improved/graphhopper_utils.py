import requests
import urllib.parse

# GraphHopper API key
API_KEY = "7ea9fa1c-282a-47fd-902f-f17b8c454373"
GEOCODE_URL = "https://graphhopper.com/api/1/geocode?"
ROUTE_URL = "https://graphhopper.com/api/1/route?"

# In-memory route history
route_history = []

def get_geocode(location: str):
    """Return geocoded data (lat, lng, formatted name) for a given location."""
    if not location:
        return { "status": 400, "error": "Location cannot be empty." }

    try:
        params = {"q": location, "limit": 1, "key": API_KEY}
        url = GEOCODE_URL + urllib.parse.urlencode(params)
        resp = requests.get(url, timeout=10)
        data = resp.json()

        if resp.status_code != 200:
            return { "status": resp.status_code, "error": data.get("message", "Geocoding failed.") }
        if not data.get("hits"):
            return { "status": 404, "error": f"No results found for '{location}'." }

        hit = data["hits"][0]
        lat, lng = hit["point"]["lat"], hit["point"]["lng"]
        name = hit.get("name", location)
        state = hit.get("state", "")
        country = hit.get("country", "")
        formatted = ", ".join([p for p in [name, state, country] if p])

        return { "status": 200, "lat": lat, "lng": lng, "name": formatted }

    except requests.RequestException as e:
        return { "status": 500, "error": f"Network error: {e}" }


def get_route(origin: str, destination: str, vehicle: str = "car"):
    """Fetch route information and return structured data."""
    orig = get_geocode(origin)
    dest = get_geocode(destination)

    if orig.get("status") != 200:
        return { "status": orig.get("status"), "error": orig.get("error") }
    if dest.get("status") != 200:
        return { "status": dest.get("status"), "error": dest.get("error") }

    op = f"&point={orig['lat']}%2C{orig['lng']}"
    dp = f"&point={dest['lat']}%2C{dest['lng']}"
    url = ROUTE_URL + urllib.parse.urlencode({"vehicle": vehicle, "key": API_KEY}) + op + dp

    try:
        resp = requests.get(url, timeout=15)
        data = resp.json()
        if resp.status_code != 200:
            return { "status": resp.status_code, "error": data.get("message", "Routing failed.") }

        path = data["paths"][0]
        km = path["distance"] / 1000
        miles = km / 1.61
        t_ms = path["time"]
        hrs, mins, secs = int(t_ms / 3600000), int(t_ms / 60000 % 60), int(t_ms / 1000 % 60)
        duration = f"{hrs:02d}:{mins:02d}:{secs:02d}"

        directions = [
            {
                "step": idx + 1,
                "text": step["text"],
                "distance_km": step["distance"] / 1000,
                "distance_mi": step["distance"] / 1000 / 1.61
            }
            for idx, step in enumerate(path.get("instructions", []))
        ]

        save_route_history(orig["name"], dest["name"], vehicle, km, duration)

        return {
            "status": 200,
            "origin": orig["name"],
            "destination": dest["name"],
            "vehicle": vehicle,
            "distance_km": km,
            "distance_mi": miles,
            "duration": duration,
            "directions": directions
        }

    except requests.RequestException as e:
        return { "status": 500, "error": f"Network error: {e}" }


def save_route_history(start, end, vehicle, km, duration):
    """Add route record to in-memory history."""
    route_history.append({
        "Start": start,
        "End": end,
        "Vehicle": vehicle,
        "Distance (km)": f"{km:.2f}",
        "Duration": duration
    })


def get_route_history():
    """Return a list of all saved routes."""
    return route_history


def clear_route_history():
    """Clear all route history."""
    route_history.clear()
