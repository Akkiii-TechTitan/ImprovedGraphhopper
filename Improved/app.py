import streamlit as st
from graphhopper_utils import get_route, get_route_history, clear_route_history

st.set_page_config(page_title="GraphHopper Route Finder", layout="centered")

# --- UI Styling ---
st.markdown(
    """
    <style>
        body, .stApp {
            background-color: #0e1117;
            color: #fafafa;
        }
        .stTextInput>div>div>input, .stSelectbox>div>div>select {
            background-color: #262730;
            color: white;
        }
        .stButton>button {
            border-radius: 8px;
            background-color: #1f77b4;
            color: white;
            padding: 0.5em 1.2em;
            font-weight: 500;
        }
        .stButton>button:hover {
            background-color: #005f9e;
        }
    </style>
    """, unsafe_allow_html=True
)

# --- Header ---
st.title(" GraphHopper Route Finder")
st.caption("Fast route lookup using GraphHopper API — with dark mode elegance.")

# --- Session State ---
if "history" not in st.session_state:
    st.session_state.history = []

# --- Input Form ---
st.markdown("### 🗺️ Enter Route Details")
col1, col2 = st.columns(2)
with col1:
    origin = st.text_input("Starting Location", placeholder="e.g. New York")
with col2:
    destination = st.text_input("Destination", placeholder="e.g. Boston")

vehicle = st.selectbox("Select Vehicle Type", ["car", "bike", "foot"], index=0)

# --- Buttons ---
col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
with col_btn1:
    find_route = st.button("Find Route")
with col_btn2:
    view_history = st.button("View History")
with col_btn3:
    clear_history = st.button("Clear History")

# --- Logic ---
if find_route:
    with st.spinner("Fetching route data..."):
        result = get_route(origin, destination, vehicle)

    if result.get("status") == 200:
        st.success(f"**Route from {result['origin']} to {result['destination']} by {result['vehicle']}**")
        st.markdown(f"**Distance:** {result['distance_km']:.2f} km / {result['distance_mi']:.2f} miles")
        st.markdown(f"**Duration:** {result['duration']}")

        st.divider()
        st.markdown("### Directions")
        for step in result["directions"]:
            st.markdown(f"**{step['step']}.** {step['text']} — ({step['distance_km']:.2f} km / {step['distance_mi']:.2f} mi)")

        # Store to session state
        st.session_state.history = get_route_history()

    else:
        st.error(f"Error: {result.get('error')} (Status {result.get('status')})")

if view_history:
    history = get_route_history()
    if history:
        st.markdown("### Route History")
        st.dataframe(history, use_container_width=True, hide_index=True)
    else:
        st.info("No route history available yet.")

if clear_history:
    clear_route_history()
    st.session_state.history = []
    st.warning("All route history cleared!")

st.divider()
st.caption("Built by T.T. Tech")
