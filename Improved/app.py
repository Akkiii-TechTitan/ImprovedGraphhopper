import streamlit as st
import io, csv, folium
from streamlit_folium import st_folium
from graphhopper_utils import (
    get_route, get_route_history, clear_route_history,
    add_favorite, get_favorites, remove_favorite,
    get_recommendation_cities, get_recommendation_spots,
    reverse_last_route, set_vehicle_profile, get_vehicle_profile
)

# ---------- Page setup ----------
st.set_page_config(page_title="Pathfinder", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #e2e8f0; font-family: 'Inter', sans-serif; }
    h1,h2,h3 { color: #f8fafc; }
    .card { background: #1e293b; border-radius: 12px; padding: 1rem; box-shadow: 0 2px 8px rgba(0,0,0,0.4); }
    .stButton>button { background-color: #2563eb; color: white; border-radius: 8px; font-weight: 600; }
    .stButton>button:hover { background-color: #1e40af; }
</style>
""", unsafe_allow_html=True)

st.title("Pathfinder")
st.caption("Destination over misdirection.")
# ---------- Folium map helper ----------
def show_folium_map(lat1, lon1, lat2, lon2, route_points=None):
    """Display Folium interactive map with markers and route line."""
    center = [(lat1 + lat2) / 2, (lon1 + lon2) / 2]
    m = folium.Map(location=center, zoom_start=13, tiles="CartoDB dark_matter")

    folium.Marker([lat1, lon1], popup="Start", icon=folium.Icon(color="green")).add_to(m)
    folium.Marker([lat2, lon2], popup="Destination", icon=folium.Icon(color="red")).add_to(m)

    if route_points:
        folium.PolyLine(route_points, color="blue", weight=4, opacity=0.8).add_to(m)

    st_folium(m, width=700, height=400)

# ---------- Initialize session state ----------
for key in ["last_route", "recommendation_result"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ---------- Sidebar ----------
with st.sidebar:
    st.header("⚙️ Settings")
    current_vehicle = get_vehicle_profile()
    vehicle = st.selectbox("Vehicle profile", ["car", "bike", "foot", "airplane"],index=["car", "bike", "foot", "airplane"].index(current_vehicle))
    if st.button("Set vehicle"):
        if set_vehicle_profile(vehicle):
            st.success(f"Vehicle set to {vehicle}")
    st.markdown("---")
    if st.button("↩️ Reverse Last Route"):
        with st.spinner("Reversing..."):
            res = reverse_last_route()
        if res.get("status") == 200:
            st.session_state.last_route = res
            st.success(f"Reversed: {res['origin']} ➜ {res['destination']}")
        else:
            st.error(res.get("error"))

# ---------- Tabs ----------
tab1, tab2, tab3, tab4 = st.tabs(["🧭 Route Planner", "🏝️ Recommendations", "⭐ Favorites", "🕒 History"])

# ========== ROUTE PLANNER ==========
with tab1:
    st.subheader("Find a Route")
    col1, col2 = st.columns(2)
    with col1:
        origin = st.text_input("Origin", placeholder="e.g., Ayala Center Cebu")
    with col2:
        destination = st.text_input("Destination", placeholder="e.g., Magellan's Cross, Cebu City")
    vehicle_choice = st.selectbox("Vehicle (optional)", ["", "car", "bike", "foot", "airplane"], index=0)

    if st.button("Find Route", use_container_width=True):
        if not origin or not destination:
            st.warning("Please fill both fields.")
        else:
            with st.spinner("Fetching route..."):
                res = get_route(origin, destination, vehicle_choice or None)
            if res.get("status") == 200:
                st.session_state.last_route = res
                st.success(f"Route: {res['origin']} ➜ {res['destination']} ({res['vehicle']})")
            else:
                st.error(res.get("error"))
                st.session_state.last_route = None

    # Keep displaying the last successful route
    if st.session_state.last_route:
        res = st.session_state.last_route
        st.markdown(f"**Distance:** {res['distance_km']:.2f} km / {res['distance_mi']:.2f} mi")
        st.markdown(f"**Duration:** {res['duration']}")
        lat1, lon1 = res["origin_coords"]
        lat2, lon2 = res["dest_coords"]
        show_folium_map(lat1, lon1, lat2, lon2, res.get("route_points"))
        with st.expander("📋 Directions"):
            for d in res["directions"]:
                st.markdown(f"**{d['step']}**. {d['text']} ({d['distance_km']:.2f} km)")

# ========== RECOMMENDATIONS ==========
with tab2:
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
                st.session_state.recommendation_result = res
                st.success(f"{res['origin']} ➜ {res['destination']}")
            else:
                st.error(res.get("error"))
                st.session_state.recommendation_result = None

    if st.session_state.recommendation_result:
        res = st.session_state.recommendation_result
        st.markdown(f"**Distance:** {res['distance_km']:.2f} km / {res['distance_mi']:.2f} mi")
        st.markdown(f"**Duration:** {res['duration']}")
        lat1, lon1 = res["origin_coords"]
        lat2, lon2 = res["dest_coords"]
        show_folium_map(lat1, lon1, lat2, lon2, res.get("route_points"))
        with st.expander("📋 Directions"):
            for d in res["directions"]:
                st.markdown(f"{d['step']}. {d['text']} ({d['distance_km']:.2f} km)")

# ========== FAVORITES ==========
with tab3:
    st.subheader("Favorites")
    name = st.text_input("Favorite name")
    loc = st.text_input("Location")
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
                st.experimental_rerun()
    else:
        st.info("No favorites yet.")

# ========== HISTORY ==========
with tab4:
    st.subheader("Route History (in-memory)")
    hist = get_route_history()
    if hist:
        st.dataframe(hist, use_container_width=True)
        col1, col2 = st.columns(2)
        if col1.button("🧹 Clear History"):
            clear_route_history()
            st.success("History cleared.")
        if col2.button("📄 Export CSV"):
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=["Start", "End", "Vehicle", "Distance (km)", "Duration"])
            writer.writeheader()
            for row in get_route_history():
                writer.writerow(row)
            st.download_button("⬇️ Download", buf.getvalue(), "route_history.csv", "text/csv")
    else:
        st.info("No routes yet.")
