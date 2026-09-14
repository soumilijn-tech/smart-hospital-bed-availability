
import streamlit as st
import sqlite3
import pandas as pd

from services.hospitals import (
    geocode_location,
    cached_hospital_search
)

DB_PATH = "/content/smart_hospital/database/hospital.db"

st.set_page_config(
    page_title="Patient Dashboard",
    page_icon="🏥",
    layout="wide"
)

# =========================
# LOGIN CHECK
# =========================

if not st.session_state.get("patient_logged_in", False):

    st.warning("🔐 Please login as Patient first.")

    if st.button("Go to Patient Login"):
        st.switch_page("pages/patient_login.py")

    st.stop()


# =========================
# HEADER
# =========================

col1, col2 = st.columns([4, 1])

with col1:
    st.title("🏥 Patient Dashboard")
    st.write(
        f"Welcome, **{st.session_state.get('patient_name', 'Patient')}**"
    )

with col2:
    if st.button("🚪 Logout"):

        st.session_state["patient_logged_in"] = False
        st.session_state.pop("patient_id", None)
        st.session_state.pop("patient_name", None)

        st.switch_page("pages/patient_login.py")


st.divider()


# =========================
# BED SEARCH FILTER
# =========================

st.subheader("🔎 Find Required Bed")

filter_col1, filter_col2 = st.columns(2)

with filter_col1:

    bed_filter = st.selectbox(
        "🛏️ Select Bed Type",
        [
            "ALL",
            "GENERAL",
            "ICU",
            "EMERGENCY"
        ]
    )

with filter_col2:

    available_only = st.checkbox(
        "✅ Show only hospitals with available beds"
    )


st.divider()


# =========================
# LOCATION SEARCH
# =========================

st.subheader("📍 Find Nearby Hospitals")

location = st.text_input(
    "Enter your location",
    placeholder="Example: Kolkata"
)

radius = st.slider(
    "Search Radius (KM)",
    min_value=1,
    max_value=20,
    value=5
)


if st.button(
    "🔍 Search Nearby Hospitals",
    type="primary"
):

    if not location.strip():

        st.warning(
            "⚠️ Please enter your location."
        )

    else:

        with st.spinner(
            "📍 Finding location..."
        ):

            try:
                coordinates = geocode_location(
                    location
                )
            except Exception:
                coordinates = None

        if coordinates is None:

            st.error(
                "❌ Location not found."
            )

        else:

            lat = coordinates["lat"]
            lon = coordinates["lon"]

            with st.spinner(
                "🏥 Searching hospitals..."
            ):

                try:

                    hospitals = cached_hospital_search(
                        round(lat, 4),
                        round(lon, 4),
                        radius * 1000
                    )

                except Exception:

                    hospitals = []

                    st.error(
                        "❌ Hospital search failed."
                    )


            if not hospitals:

                st.warning(
                    "⚠️ No hospitals found."
                )

            else:

                # =========================
                # MAP
                # =========================

                st.success(
                    f"🏥 {len(hospitals)} hospital(s) found!"
                )

                st.subheader("🗺️ Hospital Map")

                map_df = pd.DataFrame([
                    {
                        "latitude": h["latitude"],
                        "longitude": h["longitude"]
                    }
                    for h in hospitals
                ])

                st.map(
                    map_df,
                    latitude="latitude",
                    longitude="longitude",
                    zoom=11
                )


                # =========================
                # REGISTERED HOSPITAL DATA
                # =========================

                conn = sqlite3.connect(DB_PATH)

                db_hospitals = pd.read_sql_query(
                    """
                    SELECT
                        hospital_id,
                        name,
                        address,
                        phone,
                        latitude,
                        longitude
                    FROM hospitals
                    """,
                    conn
                )

                bed_data = pd.read_sql_query(
                    """
                    SELECT
                        hospital_id,
                        bed_type,
                        total_beds,
                        available_beds,
                        last_updated
                    FROM beds
                    """,
                    conn
                )

                conn.close()


                # =========================
                # FILTER REGISTERED HOSPITALS
                # =========================

                st.subheader(
                    "🏥 Nearby Hospital Details"
                )

                displayed_count = 0

                for hospital in hospitals:

                    hospital_name = hospital["name"]

                    matching = db_hospitals[
                        db_hospitals["name"].str.lower()
                        ==
                        hospital_name.lower()
                    ]

                    if matching.empty:
                        continue

                    hospital_id = int(
                        matching.iloc[0]["hospital_id"]
                    )

                    hospital_beds = bed_data[
                        bed_data["hospital_id"]
                        == hospital_id
                    ]

                    # Bed type filter
                    if bed_filter != "ALL":

                        hospital_beds = hospital_beds[
                            hospital_beds["bed_type"]
                            == bed_filter
                        ]

                    # Available-only filter
                    if available_only:

                        hospital_beds = hospital_beds[
                            hospital_beds["available_beds"]
                            > 0
                        ]

                    if hospital_beds.empty:
                        continue

                    displayed_count += 1

                    # =========================
                    # HOSPITAL CARD
                    # =========================

                    with st.container(border=True):

                        st.markdown(
                            f"### 🏥 {hospital_name}"
                        )

                        col1, col2, col3 = st.columns(3)

                        with col1:

                            st.write(
                                f"📍 **Address:** "
                                f"{hospital['address']}"
                            )

                            st.write(
                                f"📞 **Phone:** "
                                f"{hospital['phone']}"
                            )

                        with col2:

                            st.metric(
                                "📏 Distance",
                                f"{hospital['distance']} KM"
                            )

                        with col3:

                            directions_url = (
                                "https://www.google.com/maps/dir/"
                                f"{lat},{lon}/"
                                f"{hospital['latitude']},"
                                f"{hospital['longitude']}"
                            )

                            st.link_button(
                                "🧭 Get Directions",
                                directions_url
                            )


                        st.write(
                            "### 🛏️ Bed Availability"
                        )

                        bed_cols = st.columns(
                            min(3, len(hospital_beds))
                        )

                        for i, row in hospital_beds.iterrows():

                            with bed_cols[
                                i % len(bed_cols)
                            ]:

                                available = int(
                                    row["available_beds"]
                                )

                                total = int(
                                    row["total_beds"]
                                )

                                st.metric(
                                    row["bed_type"],
                                    f"{available} / {total}"
                                )

                                if available == 0:

                                    st.error(
                                        "🔴 No Bed"
                                    )

                                elif available <= 2:

                                    st.warning(
                                        "🟡 Low Availability"
                                    )

                                else:

                                    st.success(
                                        "🟢 Available"
                                    )

                                st.caption(
                                    f"Last updated: "
                                    f"{row['last_updated']}"
                                )


                if displayed_count == 0:

                    st.warning(
                        "⚠️ No registered hospital "
                        "matches your selected bed filter."
                    )


st.divider()


# =========================
# ALL REGISTERED HOSPITALS
# =========================

st.subheader(
    "🛏️ Registered Hospital Bed Status"
)

conn = sqlite3.connect(DB_PATH)

query = """
SELECT
    h.hospital_id,
    h.name,
    h.address,
    h.phone,
    SUM(b.total_beds) AS total_beds,
    SUM(b.available_beds) AS available_beds
FROM hospitals h
JOIN beds b
ON h.hospital_id = b.hospital_id
GROUP BY h.hospital_id
ORDER BY h.name
"""

df = pd.read_sql_query(
    query,
    conn
)

conn.close()

df["occupied_beds"] = (
    df["total_beds"]
    -
    df["available_beds"]
)


for _, hospital in df.iterrows():

    with st.container(border=True):

        st.markdown(
            f"### 🏥 {hospital['name']}"
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "🛏️ Total",
                int(hospital["total_beds"])
            )

        with col2:
            st.metric(
                "✅ Available",
                int(hospital["available_beds"])
            )

        with col3:
            st.metric(
                "🔴 Occupied",
                int(hospital["occupied_beds"])
            )


st.caption(
    "⚠️ Bed availability in this prototype "
    "is maintained through the hospital registry."
)
