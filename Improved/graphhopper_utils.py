# graphhopper_utils.py
# GraphHopper integration for PathFinder
# Geocoding, routing (multi-stop), airplane mode, history, favorites, recommendations.

import requests
import math
from typing import Dict, List, Optional

# --- Configuration ---
API_KEY = "7ea9fa1c-282a-47fd-902f-f17b8c454373"
GEOCODE_URL = "https://graphhopper.com/api/1/geocode"
ROUTE_URL = "https://graphhopper.com/api/1/route"

# --- In-memory stores ---
_route_history: List[Dict] = []
_favorites: List[Dict] = []
_vehicle_profile: str = "car"

# -----------------------
# Helpers
# -----------------------
def _format_duration_ms(ms: int) -> str:
    hrs = int(ms / 3600000)
    mins = int(ms / 60000 % 60)
    secs = int(ms / 1000 % 60)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# -----------------------
# Geocoding
# -----------------------
def geocode_location(place: str) -> Dict:
    if not place or not place.strip():
        return {"status": 400, "error": "Location is empty."}
    try:
        resp = requests.get(GEOCODE_URL, params={"q": place, "limit": 1, "key": API_KEY}, timeout=30)
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

# -----------------------
# Routing
# -----------------------
def get_route(origin: str, destination: str,
              vehicle: Optional[str] = None,
              waypoints: Optional[List[str]] = None) -> Dict:
    """
    Returns dict with keys: status, origin, destination, vehicle, distance_km,
    duration, directions, origin_coords, dest_coords, route_points, waypoint_names
    """
    use_vehicle = vehicle or _vehicle_profile
    waypoints = waypoints or []

    # geocode origin
    orig = geocode_location(origin)
    if orig.get("status") != 200:
        return {"status": 400, "error": orig.get("error")}

    # geocode waypoints
    wp_coords = []
    for wp in waypoints:
        if not wp or not wp.strip():
            continue
        g = geocode_location(wp)
        if g.get("status") != 200:
            return {"status": 400, "error": f"Waypoint error: {g.get('error')}"}
        wp_coords.append(g)

    # geocode destination
    dest = geocode_location(destination)
    if dest.get("status") != 200:
        return {"status": 400, "error": dest.get("error")}

    lat1, lon1 = orig["lat"], orig["lng"]
    lat2, lon2 = dest["lat"], dest["lng"]

    # airplane: direct great-circle, ignore waypoints
    if use_vehicle == "airplane":
        distance_km = _haversine_km(lat1, lon1, lat2, lon2)
        duration = _format_duration_ms(int((distance_km / 850.0) * 3600000))
        route_points = [(lat1, lon1), (lat2, lon2)]
        _route_history.append({
            "Start": orig["name"], "End": dest["name"], "Vehicle": "airplane",
            "Distance (km)": f"{distance_km:.2f}", "Duration": duration
        })
        return {
            "status": 200, "origin": orig["name"], "destination": dest["name"], "vehicle": "airplane",
            "distance_km": distance_km, "distance_mi": distance_km/1.61, "duration": duration,
            "directions": [{"step": 1, "text": "Fly directly to destination.", "distance_km": distance_km}],
            "origin_coords": (lat1, lon1), "dest_coords": (lat2, lon2), "route_points": route_points
        }

    # build GraphHopper request
    params = [("point", f"{orig['lat']},{orig['lng']}")]
    for w in wp_coords:
        params.append(("point", f"{w['lat']},{w['lng']}"))
    params.append(("point", f"{dest['lat']},{dest['lng']}"))
    params.extend([
        ("vehicle", use_vehicle),
        ("points_encoded", "false"),
        ("instructions", "true"),
        ("key", API_KEY),
    ])

    try:
        r = requests.get(ROUTE_URL, params=params, timeout=25)
        data = r.json()
    except Exception as e:
        return {"status": 500, "error": f"Routing error: {e}"}

    if r.status_code != 200 or "paths" not in data:
        return {"status": 400, "error": data.get("message", "Routing failed.")}

    path = data["paths"][0]
    distance_km = path.get("distance", 0) / 1000.0
    duration = _format_duration_ms(path.get("time", 0))
    # extract coordinates (GeoJSON: [lon, lat])
    route_points = []
    if "points" in path and "coordinates" in path["points"]:
        coords = path["points"]["coordinates"]
        # convert to (lat, lon) tuples
        route_points = [(lat, lon) for lon, lat in coords]

    directions = []
    for i, ins in enumerate(path.get("instructions", [])):
        directions.append({
            "step": i + 1,
            "text": ins.get("text", ""),
            "distance_km": ins.get("distance", 0) / 1000.0
        })

    _route_history.append({
        "Start": orig["name"],
        "End": dest["name"],
        "Vehicle": use_vehicle,
        "Distance (km)": f"{distance_km:.2f}",
        "Duration": duration
    })

    return {
        "status": 200,
        "origin": orig["name"],
        "destination": dest["name"],
        "vehicle": use_vehicle,
        "distance_km": distance_km,
        "distance_mi": distance_km / 1.61,
        "duration": duration,
        "directions": directions,
        "origin_coords": (lat1, lon1),
        "dest_coords": (lat2, lon2),
        "route_points": route_points,
        "waypoint_names": [w["name"] for w in wp_coords]
    }

# -----------------------
# History & Favorites
# -----------------------
def get_route_history() -> List[Dict]:
    return list(_route_history)

def clear_route_history():
    _route_history.clear()

def add_favorite(name: str, location: str):
    _favorites.append({"name": name, "location": location})

def get_favorites() -> List[Dict]:
    return list(_favorites)

def remove_favorite(index: int):
    if 0 <= index < len(_favorites):
        _favorites.pop(index)

# -----------------------
# Vehicle profile & reverse
# -----------------------
def set_vehicle_profile(vehicle: str) -> bool:
    global _vehicle_profile
    if vehicle in ["car", "bike", "foot"]:
        _vehicle_profile = vehicle
        return True
    return False

def get_vehicle_profile() -> str:
    return _vehicle_profile

def reverse_last_route() -> Dict:
    if not _route_history:
        return {"status": 404, "error": "No route history."}
    last = _route_history[-1]
    return get_route(last["End"], last["Start"], last.get("Vehicle"))

# -----------------------
# Recommendations
# -----------------------
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
    for key, spots in _RECOMMENDATIONS.items():
        if key.lower() == city.lower():
            return spots
    return []
