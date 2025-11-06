# app.py — PathFinder
import streamlit as st
import io, csv, hashlib
import folium
from streamlit.components.v1 import html as st_html

from graphhopper_utils import (
    get_route, get_route_history, clear_route_history,
    add_favorite, get_favorites, remove_favorite,
    get_recommendation_cities, get_recommendation_spots,
    reverse_last_route, set_vehicle_profile, get_vehicle_profile
)

# ---------- Page ----------
st.set_page_config(page_title="PathFinder", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root {
  --glass-bg: rgba(255,255,255,0.06);
  --glass-border: rgba(255,255,255,0.1);
  --glass-blur: 8px;
}
body { background: linear-gradient(135deg, #060b10 0%, #0c1219 100%); }
.stApp { font-family: 'Inter', sans-serif; color: #e6eef8; }
.glass { background: var(--glass-bg); border: 1px solid var(--glass-border); border-radius: 14px; padding: 1rem; box-shadow: 0 10px 30px rgba(2,6,23,0.6); backdrop-filter: blur(var(--glass-blur)); }
h1,h2,h3 { color: #f8fafc; margin: 0; }
.footer-note { color: #9aa9bd; font-size:0.85rem; margin-top:6px; }
</style>
""", unsafe_allow_html=True)

st.title("PathFinder")
st.caption("Destination over misdirection")

# ---------- Session State ----------
if "waypoints" not in st.session_state: st.session_state.waypoints = []
if "map_theme" not in st.session_state: st.session_state.map_theme = "dark"
if "last_route" not in st.session_state: st.session_state.last_route = None
if "cached_map_html" not in st.session_state: st.session_state.cached_map_html = None
if "cached_hash" not in st.session_state: st.session_state.cached_hash = None

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.header("⚙️ Settings")
    current = get_vehicle_profile()
    vehicle = st.selectbox("Vehicle profile", ["car", "bike", "foot", "airplane"],
                           index=["car","bike","foot","airplane"].index(current) if current in ["car","bike","foot","airplane"] else 0)
    if st.button("Set vehicle"):
        if set_vehicle_profile(vehicle):
            st.success(f"Vehicle set to {vehicle}")
        else:
            st.warning("Airplane mode can't be saved as default.")
    st.markdown("---")
    map_theme = st.radio("Map theme", ["dark", "light", "watercolor", "toner"],
                         index=["dark","light","watercolor","toner"].index(st.session_state.map_theme))
    st.session_state.map_theme = map_theme
    st.markdown("---")
    if st.button("↩️ Reverse Last Route"):
        with st.spinner("Reversing..."):
            res = reverse_last_route()
        if res.get("status") == 200:
            st.session_state.last_route = res
            st.session_state.cached_map_html = None
            st.success(f"Reversed: {res['origin']} ➜ {res['destination']}")
        else:
            st.error(res.get("error"))
    st.markdown('</div>', unsafe_allow_html=True)

# ---------- Map tiles helper ----------
def _map_tiles(theme: str):
    return {
        "dark": "CartoDB dark_matter",
        "light": "OpenStreetMap",
        "watercolor": "Stamen Watercolor",
        "toner": "Stamen Toner"
    }.get(theme, "OpenStreetMap")

# ---------- Build folium map and return HTML ----------
def build_folium_html(route_points, origin_coords, dest_coords, theme):
    center = [(origin_coords[0] + dest_coords[0]) / 2, (origin_coords[1] + dest_coords[1]) / 2]
    m = folium.Map(location=center, zoom_start=13, tiles=_map_tiles(theme))
    folium.Marker(origin_coords, popup="Start", icon=folium.Icon(color="green")).add_to(m)
    folium.Marker(dest_coords, popup="Destination", icon=folium.Icon(color="red")).add_to(m)
    if route_points and len(route_points) > 1:
        folium.PolyLine(route_points, color="#2b6cb0", weight=5, opacity=0.9).add_to(m)
    return m._repr_html_()

# ---------- Tabs ----------
tab1, tab2, tab3, tab4 = st.tabs(["🧭 Planner", "🏝️ Recommendations", "⭐ Favorites", "📈 Dashboard"])

with tab1:
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.subheader("Find a Route")

    # Load favorites for quick selection
    favorites = get_favorites()
    fav_options = [""] + [f"{fav['name']} — {fav['location']}" for fav in favorites]

    left, right = st.columns([1, 2])

    with left:
        st.markdown("### Input Locations")
        st.write("Select from favorites or type manually.")

        # Origin input
        origin_choice = st.selectbox("Select Origin (optional)", fav_options, key="origin_fav")
        origin = st.text_input("Origin (manual entry)", key="origin_text")
        if origin_choice:
            # extract the actual location string from selected favorite
            origin = origin_choice.split(" — ", 1)[-1]

        # Destination input
        destination_choice = st.selectbox("Select Destination (optional)", fav_options, key="dest_fav")
        destination = st.text_input("Destination (manual entry)", key="dest_text")
        if destination_choice:
            destination = destination_choice.split(" — ", 1)[-1]

        vehicle_choice = st.selectbox("Vehicle (optional)", ["", "car", "bike", "foot", "airplane"])

        # Waypoints with favorites
        st.markdown("**Waypoints** — Add intermediate stops")
        c1, c2 = st.columns([4, 1])
        new_wp_choice = c1.selectbox("Select waypoint from favorites (optional)", fav_options, key="wp_fav")
        new_wp_manual = c1.text_input("Add waypoint manually", key="wp_manual")

        # Prefer favorite waypoint if selected
        new_wp = new_wp_choice.split(" — ", 1)[-1] if new_wp_choice else new_wp_manual

        if c2.button("Add"):
            if new_wp.strip():
                st.session_state.waypoints.append(new_wp.strip())
                st.session_state.cached_map_html = None

        if st.session_state.waypoints:
            for i, wp in enumerate(st.session_state.waypoints):
                c1, c2 = st.columns([8, 1])
                c1.write(f"{i+1}. {wp}")
                if c2.button("❌", key=f"rmwp{i}"):
                    st.session_state.waypoints.pop(i)
                    st.session_state.cached_map_html = None

        # Find route button
        if st.button("Find Route", use_container_width=True):
            if not origin or not destination:
                st.warning("Please fill or select both origin and destination.")
            else:
                with st.spinner("Fetching route..."):
                    res = get_route(origin, destination, vehicle_choice or None, waypoints=st.session_state.waypoints)
                if res.get("status") == 200:
                    st.session_state.last_route = res
                    st.session_state.cached_map_html = None
                    st.success(f"Route: {res['origin']} ➜ {res['destination']} ({res['vehicle']})")
                else:
                    st.error(res.get("error"))
                    st.session_state.last_route = None

    with right:
        res = st.session_state.last_route
        if res:
            st.markdown(f"**{res['origin']} ➜ {res['destination']}** — {res.get('waypoint_names', [])}")
            st.markdown(f"**Distance:** {res['distance_km']:.2f} km")
            st.markdown(f"**Duration:** {res['duration']}")
            # compute simple hash for map cache
            import hashlib
            route_repr = str(res.get("route_points", [])) + st.session_state.map_theme
            route_hash = hashlib.sha256(route_repr.encode("utf-8")).hexdigest()
            if st.session_state.cached_map_html is None or st.session_state.cached_hash != route_hash:
                lat1, lon1 = res["origin_coords"]
                lat2, lon2 = res["dest_coords"]
                html = build_folium_html(res.get("route_points", []), (lat1, lon1), (lat2, lon2), st.session_state.map_theme)
                st.session_state.cached_map_html = html
                st.session_state.cached_hash = route_hash
            # embed cached html
            st.components.v1.html(st.session_state.cached_map_html, height=520)
            with st.expander("📋 Directions"):
                for d in res.get("directions", []):
                    st.markdown(f"{d['step']}. {d['text']} ({d['distance_km']:.2f} km)")
        else:
            st.info("Search a route to preview the map.")

    st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.subheader("Recommendations")
    cities = get_recommendation_cities()
    city = st.selectbox("City", [""] + cities, index=0)
    spots = get_recommendation_spots(city) if city else []
    spot = st.selectbox("Spot", [""] + spots, index=0)
    start = st.text_input("Starting point", placeholder="Enter your starting location")
    if st.button("Get Recommended Route"):
        if not city or not spot or not start:
            st.warning("Please fill all fields.")
        else:
            dest = f"{spot}, {city}"
            with st.spinner("Fetching route..."):
                res = get_route(start, dest)
            if res.get("status") == 200:
                st.session_state.last_route = res
                st.session_state.cached_map_html = None
                st.success(f"{res['origin']} ➜ {res['destination']}")
            else:
                st.error(res.get("error"))
                st.session_state.last_route = None
    if st.session_state.last_route:
        res = st.session_state.last_route
        st.markdown(f"**Distance:** {res['distance_km']:.2f} km")
        st.markdown(f"**Duration:** {res['duration']}")
        # refresh cached map if needed
        route_repr = str(res.get("route_points", [])) + st.session_state.map_theme
        route_hash = hashlib.sha256(route_repr.encode("utf-8")).hexdigest()
        if st.session_state.cached_map_html is None or st.session_state.cached_hash != route_hash:
            lat1, lon1 = res["origin_coords"]
            lat2, lon2 = res["dest_coords"]
            st.session_state.cached_map_html = build_folium_html(res.get("route_points", []), (lat1, lon1), (lat2, lon2), st.session_state.map_theme)
            st.session_state.cached_hash = route_hash
        st_html(st.session_state.cached_map_html, height=520)
    st.markdown('</div>', unsafe_allow_html=True)

with tab3:
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.subheader("Favorites")
    name = st.text_input("Favorite name", key="fav_name")
    loc = st.text_input("Location", key="fav_loc")
    if st.button("Add Favorite"):
        if name and loc:
            add_favorite(name, loc)
            st.success("Added to favorites.")
        else:
            st.warning("Please fill both fields.")
    favs = get_favorites()
    if favs:
        for i, f in enumerate(favs):
            c1, c2 = st.columns([4,1])
            c1.write(f"**{i+1}. {f['name']}** — {f['location']}")
            if c2.button("❌ Remove", key=f"rem{i}"):
                remove_favorite(i)
                try:
                    st.rerun()
                except AttributeError:
                    st.experimental_rerun()

    else:
        st.info("No favorites yet.")
    st.markdown('</div>', unsafe_allow_html=True)

with tab4:
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.subheader("Mini Dashboard")
    hist = get_route_history()
    total_trips = len(hist)
    total_distance = sum(float(r.get("Distance (km)", 0)) for r in hist)
    total_secs = 0
    for r in hist:
        try:
            h, m, s = map(int, r.get("Duration", "0:0:0").split(":"))
            total_secs += h*3600 + m*60 + s
        except:
            pass
    avg = total_secs // total_trips if total_trips else 0
    avg_str = f"{avg//3600:02d}:{(avg%3600)//60:02d}:{avg%60:02d}" if total_trips else "00:00:00"
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Trips", total_trips)
    c2.metric("Total Distance (km)", f"{total_distance:.2f}")
    c3.metric("Avg Duration", avg_str)
    if hist:
        st.dataframe(hist, use_container_width=True)
    else:
        st.info("No trips yet.")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="footer-note">TechTitan @ 2024.</div>', unsafe_allow_html=True)
