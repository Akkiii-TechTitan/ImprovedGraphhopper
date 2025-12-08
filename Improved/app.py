# app.py — PathFinder (dark main area, glass sidebar, single-field inputs + improved Recommendations)
import streamlit as st
import io
import csv
import hashlib
import folium
from streamlit.components.v1 import html as st_html

from graphhopper_utils import (
    get_route,
    get_route_history,
    clear_route_history,
    add_favorite,
    get_favorites,
    remove_favorite,
    get_recommendation_cities,
    get_recommendation_spots,
    reverse_last_route,
    set_vehicle_profile,
    get_vehicle_profile,
)

from cost_utils import CostConfig, estimate_trip_cost

# ---------- Page ----------
st.set_page_config(
    page_title="PathFinder",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------- Styles ----------
def inject_css():
    st.markdown(
        """
        <style>
        /* App background: solid dark main area */
        .stApp {
            background: #020617; /* very dark navy */
        }

        /* Main container spacing */
        .block-container {
            padding-top: 2.5rem;
            padding-bottom: 2.5rem;
        }

        /* Main glass cards (dark mode style) */
        .glass {
            background: rgba(15,23,42,0.96); /* slate-900-ish */
            border-radius: 18px;
            padding: 1.5rem 1.75rem;
            box-shadow: 0 18px 45px rgba(0, 0, 0, 0.7);
            border: 1px solid rgba(148,163,184,0.45);
            margin-bottom: 1.5rem;
        }

        .section-title {
            font-size: 1.2rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            color: #e5e7eb;
        }

        .footer-note {
            text-align: center;
            font-size: 0.8rem;
            color: #9ca3af;
            padding: 0.75rem 0 0.5rem;
        }

        .metric-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.4rem 0.7rem;
            border-radius: 999px;
            background: rgba(248,113,113,0.15);
            color: #fecaca;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .chip {
            border-radius: 999px;
            padding: 0.35rem 0.8rem;
            border: 1px solid #4b5563;
            background: #020617;
            font-size: 0.75rem;
            cursor: pointer;
            color: #e5e7eb;
        }
        .chip:hover {
            border-color: #f97316;
            background: #111827;
        }

        /* Sidebar styling (keep transparent/glass look) */
        [data-testid="stSidebar"] {
            background: radial-gradient(circle at top left,
                rgba(248,113,113,0.24),
                rgba(15,23,42,0.98));
            color: #e5e7eb;
            border-right: 1px solid rgba(148,163,184,0.4);
            backdrop-filter: blur(20px) saturate(170%);
        }
        [data-testid="stSidebar"] * {
            color: #e5e7eb;
        }

        .sidebar-header {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.75rem 0.25rem 0.25rem;
            margin-bottom: 0.75rem;
        }
        .sidebar-logo {
            width: 34px;
            height: 34px;
            border-radius: 999px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: radial-gradient(circle at 30% 20%,
                #f97316,
                #ef4444);
            box-shadow: 0 0 16px rgba(248,113,113,0.8);
            font-size: 1.2rem;
        }
        .sidebar-text h2 {
            font-size: 1.1rem;
            font-weight: 700;
            margin: 0;
        }
        .sidebar-text p {
            margin: 0;
            font-size: 0.8rem;
            opacity: 0.8;
        }
        .sidebar-section-label {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #9ca3af;
            margin-top: 0.6rem;
            margin-bottom: 0.15rem;
        }
        .sidebar-note {
            font-size: 0.75rem;
            color: #9ca3af;
            margin-top: 0.25rem;
            margin-bottom: 0.5rem;
        }
        .sidebar-divider {
            border-top: 1px solid rgba(148,163,184,0.4);
            margin: 0.75rem 0 0.75rem;
        }

        /* Make default text in dark cards light */
        .glass, .glass * {
            color: #e5e7eb;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_css()


# ---------- Helpers ----------
def _map_tiles(theme: str) -> str:
    return {
        "Default": "OpenStreetMap",
        "Dark": "CartoDB dark_matter",
        "Light": "CartoDB positron",
        "Terrain": "Stamen Terrain",
        "Toner": "Stamen Toner",
    }.get(theme, "OpenStreetMap")


def build_folium_html(route_points, origin_coords, dest_coords, theme: str):
    if origin_coords and dest_coords:
        center = [
            (origin_coords[0] + dest_coords[0]) / 2,
            (origin_coords[1] + dest_coords[1]) / 2,
        ]
    elif origin_coords:
        center = [origin_coords[0], origin_coords[1]]
    else:
        center = [14.5995, 120.9842]  # Manila

    m = folium.Map(location=center, zoom_start=13, tiles=_map_tiles(theme))

    if origin_coords:
        folium.Marker(
            origin_coords, popup="Start", icon=folium.Icon(color="green", icon="play")
        ).add_to(m)
    if dest_coords:
        folium.Marker(
            dest_coords, popup="Destination", icon=folium.Icon(color="red", icon="flag")
        ).add_to(m)

    if route_points and len(route_points) > 1:
        folium.PolyLine(route_points, weight=5, opacity=0.9).add_to(m)

    return m._repr_html_()


def history_to_csv_bytes(history):
    if not history:
        return b""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=history[0].keys())
    writer.writeheader()
    writer.writerows(history)
    return output.getvalue().encode("utf-8")


# ---------- Location input helpers ----------
def _set_location_from_fav(state_key: str, loc: str):
    st.session_state[state_key] = loc


def location_input(label: str, key: str, favorites):
    """
    Single input where user can type or click favorites.
    Uses session_state[f"{key}_value"] for the text value.
    Each widget also gets a unique key=f"{key}_widget" to avoid duplicate IDs.
    """
    state_key = f"{key}_value"
    widget_key = f"{key}_widget"

    if state_key not in st.session_state:
        st.session_state[state_key] = ""

    value = st.text_input(
        label,
        value=st.session_state[state_key],
        placeholder=f"Type {label} or choose a favorite below…",
        key=widget_key,
    )
    st.session_state[state_key] = value

    if favorites:
        st.caption("Quick pick from favorites:")
        cols = st.columns(min(3, max(1, len(favorites))))
        for i, fav in enumerate(favorites):
            col = cols[i % len(cols)]
            with col:
                st.button(
                    f"⭐ {fav['name']}",
                    key=f"{key}_fav_{i}",
                    on_click=_set_location_from_fav,
                    args=(state_key, fav["location"]),
                )

    return st.session_state[state_key].strip()


# ---------- Session init ----------
if "waypoints" not in st.session_state:
    st.session_state["waypoints"] = []
if "reco_waypoints" not in st.session_state:
    st.session_state["reco_waypoints"] = []


# ---------- Sidebar ----------
with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-header">
          <div class="sidebar-logo">🧭</div>
          <div class="sidebar-text">
            <h2>PathFinder</h2>
            <p>Smart, friendly route planner</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="sidebar-section-label">Travel defaults</div>',
        unsafe_allow_html=True,
    )

    current_profile = get_vehicle_profile()
    st.caption(f"Current default: `{current_profile}`")

    new_profile = st.radio(
        "Default vehicle profile",
        options=["car", "bike", "foot"],
        index=["car", "bike", "foot"].index(current_profile)
        if current_profile in ["car", "bike", "foot"]
        else 0,
    )

    if st.button("💾 Save default vehicle"):
        if set_vehicle_profile(new_profile):
            st.success(f"Default vehicle set to **{new_profile}**.")
        else:
            st.error("Invalid vehicle profile.")

    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="sidebar-section-label">Map appearance</div>',
        unsafe_allow_html=True,
    )
    map_theme = st.selectbox(
        "Map theme",
        options=["Default", "Light", "Dark", "Terrain", "Toner"],
        index=0,
    )
    st.markdown(
        '<div class="sidebar-note">Choose a basemap style that matches how you like to read routes.</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sidebar-note">Tip: Save frequent places as favorites so you can tap them directly in the planner.</div>',
        unsafe_allow_html=True,
    )


# ---------- Main content ----------
st.title("🧭 PathFinder")
st.write("Plan trips, manage favorites, and explore recommendations.")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📍 Planner", "⭐ Favorites", "🕒 History", "🌏 Recommendations", "ℹ️ About"]
)

# ====================================================================
# ========================= PLANNER TAB ===============================
# ====================================================================

with tab1:
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Plan a Trip</div>', unsafe_allow_html=True)

    favorites = get_favorites()

    left, right = st.columns([1.1, 1.9])

    with left:
        origin = location_input("Origin", "origin", favorites)
        destination = location_input("Destination", "destination", favorites)

        vehicle_choice = st.selectbox(
            "Vehicle for this trip (optional)",
            options=["Use default", "car", "bike", "foot", "airplane"],
            index=0,
        )

        st.markdown("#### Waypoints (optional)")
        new_wp = location_input("Waypoint", "waypoint", favorites)

        cols_wp = st.columns([1, 1])
        with cols_wp[0]:
            if st.button("➕ Add waypoint"):
                if new_wp:
                    st.session_state["waypoints"].append(new_wp)
                    st.session_state["waypoint_value"] = ""
                else:
                    st.warning("Enter a waypoint before adding.")
        with cols_wp[1]:
            if st.button("🗑 Clear waypoints"):
                st.session_state["waypoints"] = []

        if st.session_state["waypoints"]:
            st.write("Current waypoints:")
            for idx, wp in enumerate(st.session_state["waypoints"]):
                st.write(f"{idx+1}. {wp}")

        st.markdown("---")
        go = st.button("🚀 Plan route", use_container_width=True)

    with right:
        if go:
            if not origin or not destination:
                st.error("Please provide both origin and destination.")
            else:
                vehicle = None if vehicle_choice == "Use default" else vehicle_choice
                with st.spinner("Requesting route from GraphHopper…"):
                    result = get_route(
                        origin=origin,
                        destination=destination,
                        vehicle=vehicle,
                        waypoints=st.session_state["waypoints"],
                    )

                if result.get("status") != 200:
                    st.error(result.get("error", "Unknown error while routing."))
                else:
                    distance_km = result.get("distance_km", 0.0)
                    duration = result.get("duration", "N/A")
                    used_vehicle = result.get("vehicle", vehicle_choice)

                    colm1, colm2, colm3 = st.columns(3)
                    with colm1:
                        st.metric("Distance (km)", f"{distance_km:.2f}")
                    with colm2:
                        st.metric("Duration", duration)
                    with colm3:
                        st.metric("Vehicle", used_vehicle)

                    route_points = result.get("route_points")
                    origin_coords = result.get("origin_coords")
                    dest_coords = result.get("dest_coords")
                    if route_points and origin_coords and dest_coords:
                        map_html = build_folium_html(
                            route_points, origin_coords, dest_coords, map_theme
                        )
                        st_html(map_html, height=480)
                    else:
                        st.info("No map data available for this route.")

                    st.markdown("#### Turn-by-Turn Directions")
                    directions = result.get("directions", [])
                    if directions:
                        for step in directions:
                            text = step.get("text", "")
                            dist = step.get("distance_km", 0.0)
                            st.write(f"• {text}  _(~{dist:.2f} km)_")
                    else:
                        st.info("No instructions returned.")
        else:
            st.info("Enter locations on the left and click **Plan route** to begin.")

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Quick Actions</div>', unsafe_allow_html=True)

    if st.button("🔁 Reverse last route"):
        res = reverse_last_route()
        if res.get("status") != 200:
            st.warning(res.get("error", "No route to reverse."))
        else:
            distance_km = res.get("distance_km", 0.0)
            duration = res.get("duration", "N/A")
            st.success(
                f"Reversed route from **{res.get('origin')}** to **{res.get('destination')}** "
                f"({distance_km:.2f} km, {duration}). Plan it from the Planner tab."
            )
    st.markdown('</div>', unsafe_allow_html=True)

# ====================================================================
# ========================= FAVORITES TAB =============================
# ====================================================================

with tab2:
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Manage Favorites</div>', unsafe_allow_html=True)

    fav_name = st.text_input("Favorite name (e.g., Home, School)")
    fav_loc = st.text_input("Location (address or place)")

    if st.button("⭐ Add to favorites"):
        if not fav_name or not fav_loc:
            st.error("Please provide both a name and location.")
        else:
            add_favorite(fav_name.strip(), fav_loc.strip())
            st.success(f"Added **{fav_name}** to favorites.")

    st.markdown("---")

    favorites = get_favorites()
    if not favorites:
        st.info("No favorites yet. Add one above.")
    else:
        for idx, fav in enumerate(favorites):
            cols = st.columns([3, 5, 1])
            cols[0].write(f"**{fav['name']}**")
            cols[1].write(fav["location"])
            if cols[2].button("Remove", key=f"remove_fav_{idx}"):
                remove_favorite(idx)
                st.experimental_rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# ====================================================================
# ========================= HISTORY TAB ===============================
# ====================================================================

with tab3:
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Trip History</div>', unsafe_allow_html=True)

    hist = get_route_history()
    if not hist:
        st.info("No trips recorded yet. Plan a route to start building history.")
    else:
        st.dataframe(hist, use_container_width=True)
        csv_bytes = history_to_csv_bytes(hist)
        hash_suffix = hashlib.sha1(csv_bytes).hexdigest()[:8]
        st.download_button(
            "⬇️ Download history as CSV",
            data=csv_bytes,
            file_name=f"pathfinder_history_{hash_suffix}.csv",
            mime="text/csv",
        )

    st.markdown("---")
    if st.button("🧹 Clear history"):
        clear_route_history()
        st.success("Route history cleared.")
        st.experimental_rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# ====================================================================
# ====================== RECOMMENDATIONS TAB ==========================
# ====================================================================

with tab4:
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">Travel Recommendations</div>', unsafe_allow_html=True
    )

    favorites = get_favorites()

    left, right = st.columns([1.1, 1.9])

    with left:
        cities = get_recommendation_cities()
        city = st.selectbox("City / Area", [""] + cities)

        spots = get_recommendation_spots(city) if city else []
        spot = st.selectbox("Recommended destination", [""] + spots)

        origin_rec = location_input("Origin", "reco_origin", favorites)

        st.markdown("#### Waypoints (optional)")
        new_reco_wp = location_input("Waypoint", "reco_waypoint", favorites)

        cols_wp = st.columns([1, 1])
        with cols_wp[0]:
            if st.button("➕ Add waypoint (recommended)", key="btn_add_reco_wp"):
                if new_reco_wp:
                    st.session_state["reco_waypoints"].append(new_reco_wp)
                    st.session_state["reco_waypoint_value"] = ""
                else:
                    st.warning("Enter a waypoint before adding.")
        with cols_wp[1]:
            if st.button("🗑 Clear waypoints (recommended)", key="btn_clear_reco_wp"):
                st.session_state["reco_waypoints"] = []

        if st.session_state["reco_waypoints"]:
            st.write("Current waypoints:")
            for idx, wp in enumerate(st.session_state["reco_waypoints"]):
                st.write(f"{idx+1}. {wp}")

        vehicle_rec = st.selectbox(
            "Vehicle for this recommended trip (optional)",
            options=["Use default", "car", "bike", "foot", "airplane"],
            index=0,
        )

        go_rec = st.button("🎯 Plan recommended route", use_container_width=True)

    with right:
        if go_rec:
            if not city or not spot or not origin_rec:
                st.warning("Please select a city, destination spot, and origin.")
            else:
                dest_str = f"{spot}, {city}, Philippines" if city else spot
                vehicle = None if vehicle_rec == "Use default" else vehicle_rec

                with st.spinner("Requesting recommended route from GraphHopper…"):
                    res = get_route(
                        origin=origin_rec,
                        destination=dest_str,
                        vehicle=vehicle,
                        waypoints=st.session_state["reco_waypoints"],
                    )

                if res.get("status") != 200:
                    st.error(res.get("error", "Unknown error while routing."))
                else:
                    distance_km = res.get("distance_km", 0.0)
                    duration = res.get("duration", "N/A")
                    used_vehicle = res.get("vehicle", vehicle_rec)

                    colm1, colm2, colm3 = st.columns(3)
                    with colm1:
                        st.metric("Distance (km)", f"{distance_km:.2f}")
                    with colm2:
                        st.metric("Duration", duration)
                    with colm3:
                        st.metric("Vehicle", used_vehicle)

                    route_points = res.get("route_points")
                    origin_coords = res.get("origin_coords")
                    dest_coords = res.get("dest_coords")
                    if route_points and origin_coords and dest_coords:
                        map_html = build_folium_html(
                            route_points, origin_coords, dest_coords, map_theme
                        )
                        st_html(map_html, height=480)
                    else:
                        st.info("No map data available for this route.")

                    st.markdown("#### Turn-by-Turn Directions")
                    directions = res.get("directions", [])
                    if directions:
                        for step in directions:
                            text = step.get("text", "")
                            dist = step.get("distance_km", 0.0)
                            st.write(f"• {text}  _(~{dist:.2f} km)_")
                    else:
                        st.info("No instructions returned.")
        else:
            st.info("Pick a city + spot, type your origin, then click **Plan recommended route**.")

    st.markdown('</div>', unsafe_allow_html=True)

# ====================================================================
# ========================= ABOUT TAB =================================
# ====================================================================

with tab5:
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">About PathFinder</div>', unsafe_allow_html=True)

    st.write(
        """
        **PathFinder** is a simple web app that helps you:
        - Plan routes with origin, destination, and optional waypoints  
        - Save frequent places as favorites  
        - Keep a history of your trips  
        - Explore suggested destinations for inspiration  

        The location inputs on the Planner and Recommendations tabs use
        **a single field** per category: you can either type any place or tap a favorite
        to autofill the same field.
        """
    )

    st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown('<div class="footer-note">TechTitan @ 2024.</div>', unsafe_allow_html=True)
