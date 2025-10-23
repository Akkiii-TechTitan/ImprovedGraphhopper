import requests
import urllib.parse
from typing import Dict, List, Optional, Tuple

API_KEY = "7ea9fa1c-282a-47fd-902f-f17b8c454373"
GEOCODE_URL = "https://graphhopper.com/api/1/geocode"
ROUTE_URL = "https://graphhopper.com/api/1/route"

_route_history: List[Dict] = []
_favorites: List[Dict] = []
_vehicle_profile: str = "car"

# ---------- Helpers ----------
def _format_duration_ms(ms: int) -> str:
    hrs = int(ms / 3600000)
    mins = int(ms / 60000 % 60)
    secs = int(ms / 1000 % 60)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"

# ---------- Geocoding ----------
def geocode_location(place: str) -> Dict:
    if not place or not place.strip():
        return {"status": 400, "error": "Location is empty."}

    try:
        resp = requests.get(GEOCODE_URL, params={"q": place, "limit": 1, "key": API_KEY}, timeout=10)
        data = resp.json()
    except Exception as e:
        return {"status": 500, "error": f"Geocoding error: {e}"}

    if resp.status_code != 200 or not data.get("hits"):
        return {"status": 404, "error": f"Could not geocode '{place}'."}

    hit = data["hits"][0]
    lat, lng = hit["point"]["lat"], hit["point"]["lng"]
    name = hit.get("name", place)
    state, country = hit.get("state", ""), hit.get("country", "")
    display = ", ".join([p for p in [name, state, country] if p])

    return {"status": 200, "lat": lat, "lng": lng, "name": display}

# ---------- Routing ----------
import math

def get_route(origin: str, destination: str, vehicle: Optional[str] = None) -> Dict:
    use_vehicle = vehicle or _vehicle_profile

    orig = geocode_location(origin)
    if orig.get("status") != 200:
        return {"status": 400, "error": orig.get("error")}
    dest = geocode_location(destination)
    if dest.get("status") != 200:
        return {"status": 400, "error": dest.get("error")}

    lat1, lon1 = orig["lat"], orig["lng"]
    lat2, lon2 = dest["lat"], dest["lng"]

    # ✈️ Handle airplane mode
    if use_vehicle == "airplane":
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371  # km
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
            return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance_km = haversine(lat1, lon1, lat2, lon2)
        distance_mi = distance_km / 1.61
        avg_speed_kmh = 850
        hours = distance_km / avg_speed_kmh
        total_ms = int(hours * 3600000)
        duration = _format_duration_ms(total_ms)
        route_points = [(lat1, lon1), (lat2, lon2)]

        _route_history.append({
            "Start": orig["name"],
            "End": dest["name"],
            "Vehicle": "airplane",
            "Distance (km)": f"{distance_km:.2f}",
            "Duration": duration,
        })

        return {
            "status": 200,
            "origin": orig["name"],
            "destination": dest["name"],
            "vehicle": "airplane",
            "distance_km": distance_km,
            "distance_mi": distance_mi,
            "duration": duration,
            "directions": [{"step": 1, "text": "Fly directly to destination.", "distance_km": distance_km, "distance_mi": distance_mi}],
            "origin_coords": (lat1, lon1),
            "dest_coords": (lat2, lon2),
            "route_points": route_points,
        }

    # 🛣️ Normal GraphHopper routes (car, bike, foot)
    params = [
        ("point", f"{orig['lat']},{orig['lng']}"),
        ("point", f"{dest['lat']},{dest['lng']}"),
        ("vehicle", use_vehicle),
        ("points_encoded", "false"),
        ("instructions", "true"),
        ("key", API_KEY),
    ]

    try:
        r = requests.get(ROUTE_URL, params=params, timeout=15)
        data = r.json()
    except Exception as e:
        return {"status": 500, "error": f"Routing error: {e}"}

    if r.status_code != 200 or "paths" not in data:
        return {"status": 400, "error": data.get("message", "Routing failed.")}

    path = data["paths"][0]
    distance_km = path["distance"] / 1000
    distance_mi = distance_km / 1.61
    duration = _format_duration_ms(path["time"])

    # Decode route polyline (GeoJSON)
    route_points = []
    if "points" in path and "coordinates" in path["points"]:
        coords = path["points"]["coordinates"]
        route_points = [(lat, lon) for lon, lat in coords]

    directions = [
        {
            "step": i + 1,
            "text": ins["text"],
            "distance_km": ins["distance"] / 1000,
            "distance_mi": ins["distance"] / 1000 / 1.61,
        }
        for i, ins in enumerate(path["instructions"])
    ]

    _route_history.append({
        "Start": orig["name"],
        "End": dest["name"],
        "Vehicle": use_vehicle,
        "Distance (km)": f"{distance_km:.2f}",
        "Duration": duration,
    })

    return {
        "status": 200,
        "origin": orig["name"],
        "destination": dest["name"],
        "vehicle": use_vehicle,
        "distance_km": distance_km,
        "distance_mi": distance_mi,
        "duration": duration,
        "directions": directions,
        "origin_coords": (lat1, lon1),
        "dest_coords": (lat2, lon2),
        "route_points": route_points,
    }


# ---------- History ----------
def get_route_history() -> List[Dict]:
    return list(_route_history)

def clear_route_history():
    _route_history.clear()

# ---------- Favorites ----------
def add_favorite(name: str, location: str):
    _favorites.append({"name": name, "location": location})

def get_favorites() -> List[Dict]:
    return list(_favorites)

def remove_favorite(index: int):
    if 0 <= index < len(_favorites):
        _favorites.pop(index)

# ---------- Vehicle ----------
def set_vehicle_profile(vehicle: str) -> bool:
    global _vehicle_profile
    if vehicle in ["car", "bike", "foot"]:
        _vehicle_profile = vehicle
        return True
    return False

def get_vehicle_profile() -> str:
    return _vehicle_profile

# ---------- Reverse last ----------
def reverse_last_route() -> Dict:
    if not _route_history:
        return {"status": 404, "error": "No route history."}
    last = _route_history[-1]
    return get_route(last["End"], last["Start"], last["Vehicle"])

# ---------- Recommendations ----------
_RECOMMENDATIONS = {
    "Manila": ["Intramuros", "Rizal Park", "Fort Santiago", "Binondo", "National Museum"],
    "Cebu": ["Magellan's Cross", "Temple of Leah", "Sirao Garden", "Fort San Pedro"],
    "Davao": ["Eden Nature Park", "Philippine Eagle Center", "People's Park"],
    "Baguio": ["Burnham Park", "Mines View Park", "Camp John Hay"],
    "Iloilo": ["Miag-ao Church", "Iloilo River Esplanade", "Garin Farm"],
    "Tagaytay": ["Taal Volcano Viewpoint", "Sky Ranch", "Picnic Grove"],
    "Boracay": ["White Beach", "Puka Shell Beach", "Mount Luho"],
    "Palawan": ["Underground River", "Honda Bay", "El Nido Lagoon"],
}

def get_recommendation_cities() -> List[str]:
    return sorted(list(_RECOMMENDATIONS.keys()))

def get_recommendation_spots(city: str) -> List[str]:
    if not city:
        return []
    for key in _RECOMMENDATIONS:
        if key.lower() == city.lower():
            return _RECOMMENDATIONS[key]
    return []
