import streamlit as st
import sqlite3
import pandas as pd

from pathlib import Path

from services.hospitals import (
    geocode_location,
    cached_hospital_search
)


# =========================
# DATABASE PATH
# =========================

DB_PATH = Path(__file__).resolve().parent / "database" / "hospital.db"


# =========================
# PAGE CONFIG
# =========================

st.set_page_config(
    page_title="Smart Hospital Bed Availability",
    page_icon="🏥",
    layout="wide"
)


# =========================
# HEADER
# =========================

st.title("🏥 Smart Hospital Bed Availability System")

st.write(
    "Find nearby hospitals and check current bed availability."
)


# =========================
# NAVIGATION
# =========================

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("👤 Patient Login", use_container_width=True):
        st.switch_page("pages/patient_login.py")

with col2:
    if st.button("📝 Patient Registration", use_container_width=True):
        st.switch_page("pages/patient_register.py")

with col3:
    if st.button("🔐 Admin Login", use_container_width=True):
        st.switch_page("pages/admin_login.py")

with col4:
    if st.button("🏥 Patient Dashboard", use_container_width=True):
        st.switch_page("pages/patient_dashboard.py")


st.divider()


# =========================
# NEARBY HOSPITAL SEARCH
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
    "🔍 Find Nearby Hospitals",
    type="primary"
):

    if not location.strip():

        st.warning(
            "⚠️ Please enter your location."
        )

    else:

        # -------------------------
        # GEOCODING
        # -------------------------

        with st.spinner(
            "📍 Finding your location..."
        ):

            try:

                coordinates = geocode_location(
                    location
                )

            except Exception:

                coordinates = None

                st.error(
                    "❌ Unable to find the location."
                )


        if coordinates is None:

            st.error(
                "❌ Location not found. "
                "Try another location."
            )

        else:

            lat = coordinates["lat"]
            lon = coordinates["lon"]


            # -------------------------
            # HOSPITAL SEARCH
            # -------------------------

            with st.spinner(
                "🏥 Searching nearby hospitals..."
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
                        "❌ Hospital search failed. "
                        "Please try again."
                    )


            if not hospitals:

                st.warning(
                    "⚠️ No hospitals found "
                    "within this radius."
                )

            else:

                st.success(
                    f"🏥 {len(hospitals)} hospital(s) found!"
                )


                # =========================
                # MAP
                # =========================

                st.subheader("🗺️ Hospital Map")

                map_df = pd.DataFrame(
                    [
                        {
                            "latitude": h["latitude"],
                            "longitude": h["longitude"]
                        }
                        for h in hospitals
                    ]
                )

                st.map(
                    map_df,
                    latitude="latitude",
                    longitude="longitude",
                    zoom=11
                )


                # =========================
                # HOSPITAL LIST
                # =========================

                st.subheader(
                    "🏥 Nearby Hospitals"
                )


                for hospital in hospitals:

                    with st.container(
                        border=True
                    ):

                        st.markdown(
                            f"### 🏥 {hospital['name']}"
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
                                "🗺️ Get Directions",
                                directions_url
                            )


st.divider()


# =========================
# REGISTERED HOSPITAL BED DATA
# =========================

st.subheader(
    "🛏️ Registered Hospital Bed Availability"
)


def get_hospital_data():

    conn = sqlite3.connect(DB_PATH)

    query = """
    SELECT
        h.hospital_id,
        h.name,
        h.address,
        h.latitude,
        h.longitude,
        h.phone,

        COALESCE(
            SUM(b.total_beds),
            0
        ) AS total_beds,

        COALESCE(
            SUM(b.available_beds),
            0
        ) AS available_beds

    FROM hospitals h

    LEFT JOIN beds b
        ON h.hospital_id = b.hospital_id

    GROUP BY
        h.hospital_id,
        h.name,
        h.address,
        h.latitude,
        h.longitude,
        h.phone
    """

    df = pd.read_sql_query(
        query,
        conn
    )

    conn.close()


    df["total_beds"] = (
        pd.to_numeric(
            df["total_beds"],
            errors="coerce"
        ).fillna(0)
    )

    df["available_beds"] = (
        pd.to_numeric(
            df["available_beds"],
            errors="coerce"
        ).fillna(0)
    )


    df["occupied_beds"] = (
        df["total_beds"]
        -
        df["available_beds"]
    )


    return df


# =========================
# BED DETAILS
# =========================

def get_bed_details(hospital_id):

    conn = sqlite3.connect(DB_PATH)

    query = """
    SELECT
        bed_type,
        total_beds,
        available_beds,
        last_updated

    FROM beds

    WHERE hospital_id = ?

    ORDER BY bed_type
    """

    df = pd.read_sql_query(
        query,
        conn,
        params=(hospital_id,)
    )

    conn.close()

    return df


# =========================
# LOAD DATABASE
# =========================

try:

    df = get_hospital_data()

except Exception as e:

    st.error(
        "❌ Unable to load hospital bed data."
    )

    st.stop()


# =========================
# DISPLAY HOSPITALS
# =========================

if df.empty:

    st.info(
        "No registered hospitals available."
    )

else:

    # -------------------------
    # SUMMARY
    # -------------------------

    total_beds = int(
        df["total_beds"].sum()
    )

    available_beds = int(
        df["available_beds"].sum()
    )

    occupied_beds = int(
        df["occupied_beds"].sum()
    )


    st.markdown("### 📊 Overall Bed Summary")


    col1, col2, col3 = st.columns(3)


    with col1:

        st.metric(
            "🛏️ Total Beds",
            total_beds
        )


    with col2:

        st.metric(
            "✅ Available Beds",
            available_beds
        )


    with col3:

        st.metric(
            "🔴 Occupied Beds",
            occupied_beds
        )


    st.divider()


    # -------------------------
    # HOSPITAL CARDS
    # -------------------------

    for _, hospital in df.iterrows():

        with st.container(
            border=True
        ):

            st.markdown(
                f"### 🏥 {hospital['name']}"
            )


            col1, col2, col3 = st.columns(3)


            with col1:

                st.metric(
                    "🛏️ Total Beds",
                    int(
                        hospital["total_beds"]
                    )
                )


            with col2:

                available = int(
                    hospital["available_beds"]
                )

                st.metric(
                    "✅ Available Beds",
                    available
                )


            with col3:

                st.metric(
                    "🔴 Occupied Beds",
                    int(
                        hospital["occupied_beds"]
                    )
                )


            # -------------------------
            # BED STATUS
            # -------------------------

            if available == 0:

                st.error(
                    "🔴 No beds currently available"
                )

            elif available <= 2:

                st.warning(
                    "🟡 Very limited beds available"
                )

            else:

                st.success(
                    f"🟢 {available} beds available"
                )


            # -------------------------
            # HOSPITAL INFORMATION
            # -------------------------

            col1, col2 = st.columns(2)


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

                if pd.notna(
                    hospital["latitude"]
                ) and pd.notna(
                    hospital["longitude"]
                ):

                    directions_url = (
                        "https://www.google.com/maps/dir/"
                        f"{hospital['latitude']},"
                        f"{hospital['longitude']}"
                    )

                    st.link_button(
                        "🗺️ Open Location",
                        directions_url
                    )


            # -------------------------
            # BED TYPE DETAILS
            # -------------------------

            bed_df = get_bed_details(
                int(
                    hospital["hospital_id"]
                )
            )


            if not bed_df.empty:

                st.write(
                    "**🛏️ Bed Type Availability**"
                )


                cols = st.columns(3)


                for i, row in bed_df.iterrows():

                    with cols[i % 3]:

                        bed_available = int(
                            row["available_beds"]
                        )

                        bed_total = int(
                            row["total_beds"]
                        )


                        st.metric(
                            str(
                                row["bed_type"]
                            ),
                            f"{bed_available} / {bed_total}"
                        )


                        if bed_available == 0:

                            st.error(
                                "🔴 No Bed"
                            )

                        elif bed_available <= 2:

                            st.warning(
                                "🟡 Low"
                            )

                        else:

                            st.success(
                                "🟢 Available"
                            )


                        st.caption(
                            f"Updated: "
                            f"{row['last_updated']}"
                        )


st.divider()


# =========================
# FOOTER
# =========================

st.caption(
    "⚠️ Bed availability shown in this prototype "
    "is based on registered/demo hospital data."
        )
