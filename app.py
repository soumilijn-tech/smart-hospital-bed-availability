# ============================================================
# 🏥 SMART HOSPITAL BED AVAILABILITY SYSTEM
# ============================================================

import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path
import math

from services.hospitals import geocode_location


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Smart Hospital Bed Availability System",
    page_icon="🏥",
    layout="wide"
)


# ============================================================
# FILE PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = BASE_DIR / "database" / "hospital.db"

CSV_PATH = BASE_DIR / "hospital_directory.csv"


# ============================================================
# TITLE
# ============================================================

st.title("🏥 Smart Hospital Bed Availability System")

st.subheader(
    "Find nearby hospitals and check available beds."
)


# ============================================================
# LOAD HOSPITAL DIRECTORY CSV
# ============================================================

@st.cache_data
def load_hospital_directory():

    if not CSV_PATH.exists():

        st.error(
            f"❌ hospital_directory.csv not found.\n\n"
            f"Expected location:\n{CSV_PATH}"
        )

        return pd.DataFrame()

    try:

        df = pd.read_csv(
            CSV_PATH,
            low_memory=False
        )

        # Normalize column names
        df.columns = (
            df.columns
            .astype(str)
            .str.strip()
            .str.lower()
            .str.replace(r"[^a-z0-9]+", "_", regex=True)
            .str.strip("_")
        )

        return df

    except Exception as e:

        st.error(
            f"❌ Error loading hospital_directory.csv:\n{e}"
        )

        return pd.DataFrame()


# ============================================================
# LOAD CSV
# ============================================================

hospital_df = load_hospital_directory()


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():

    return sqlite3.connect(DB_PATH)


# ============================================================
# GET REGISTERED HOSPITAL DATA
# ============================================================

def get_hospital_data():

    try:

        conn = get_connection()

        query = """
        SELECT
            h.id,
            h.name,
            h.address,
            h.phone,
            COALESCE(SUM(b.total_beds), 0) AS total_beds,
            COALESCE(SUM(b.available_beds), 0) AS available_beds
        FROM hospitals h
        LEFT JOIN beds b
            ON h.id = b.hospital_id
        GROUP BY
            h.id,
            h.name,
            h.address,
            h.phone
        """

        df = pd.read_sql_query(
            query,
            conn
        )

        conn.close()

        return df

    except Exception as e:

        st.error(
            f"❌ Database error: {e}"
        )

        return pd.DataFrame()


# ============================================================
# GET BED DETAILS
# ============================================================

def get_bed_details(hospital_id):

    try:

        conn = get_connection()

        query = """
        SELECT
            bed_type,
            total_beds,
            available_beds,
            last_updated
        FROM beds
        WHERE hospital_id = ?
        """

        df = pd.read_sql_query(
            query,
            conn,
            params=(hospital_id,)
        )

        conn.close()

        return df

    except Exception:

        return pd.DataFrame()


# ============================================================
# HOSPITAL COLUMN FINDER
# ============================================================

def find_column(df, possible_names):

    for name in possible_names:

        if name in df.columns:
            return name

    return None


# ============================================================
# SEARCH HOSPITALS FROM CSV
# ============================================================

def search_hospitals_from_csv(query):

    if hospital_df.empty:
        return []

    search_df = hospital_df.copy()

    # Convert columns to string temporarily
    for col in search_df.columns:

        search_df[col] = (
            search_df[col]
            .fillna("")
            .astype(str)
        )

    # --------------------------------------------------------
    # Find possible columns
    # --------------------------------------------------------

    name_col = find_column(
        search_df,
        [
            "hospital_name",
            "hospitalname",
            "name"
        ]
    )

    state_col = find_column(
        search_df,
        [
            "state",
            "state_name"
        ]
    )

    district_col = find_column(
        search_df,
        [
            "district",
            "district_name"
        ]
    )

    address_col = find_column(
        search_df,
        [
            "address",
            "hospital_address",
            "location"
        ]
    )

    phone_col = find_column(
        search_df,
        [
            "phone",
            "telephone",
            "mobile",
            "contact_number",
            "telephone_no"
        ]
    )

    lat_col = find_column(
        search_df,
        [
            "latitude",
            "lat"
        ]
    )

    lon_col = find_column(
        search_df,
        [
            "longitude",
            "lon",
            "lng"
        ]
    )

    # --------------------------------------------------------
    # Hospital name column required
    # --------------------------------------------------------

    if name_col is None:

        st.error(
            "❌ Hospital name column was not found in CSV."
        )

        return []

    # --------------------------------------------------------
    # Search query
    # --------------------------------------------------------

    query = str(query).strip().lower()

    if not query:

        return []

    # Search hospital name
    mask = (
        search_df[name_col]
        .str.lower()
        .str.contains(
            query,
            na=False,
            regex=False
        )
    )

    # Search state
    if state_col:

        mask = (
            mask
            |
            search_df[state_col]
            .str.lower()
            .str.contains(
                query,
                na=False,
                regex=False
            )
        )

    # Search district
    if district_col:

        mask = (
            mask
            |
            search_df[district_col]
            .str.lower()
            .str.contains(
                query,
                na=False,
                regex=False
            )
        )

    # Search address
    if address_col:

        mask = (
            mask
            |
            search_df[address_col]
            .str.lower()
            .str.contains(
                query,
                na=False,
                regex=False
            )
        )

    # Maximum 50 results
    results = search_df[mask].head(50)

    hospitals = []

    # --------------------------------------------------------
    # Convert results into hospital objects
    # --------------------------------------------------------

    for _, row in results.iterrows():

        # Latitude
        h_lat = None

        if lat_col:

            try:

                value = str(row[lat_col]).strip()

                if value:
                    h_lat = float(value)

            except (ValueError, TypeError):

                h_lat = None

        # Longitude
        h_lon = None

        if lon_col:

            try:

                value = str(row[lon_col]).strip()

                if value:
                    h_lon = float(value)

            except (ValueError, TypeError):

                h_lon = None

        # Address
        address = "Not available"

        if address_col:

            address = str(
                row[address_col]
            ).strip()

            if not address:
                address = "Not available"

        # Phone
        phone = "Not available"

        if phone_col:

            phone = str(
                row[phone_col]
            ).strip()

            if not phone:
                phone = "Not available"

        # State
        state = ""

        if state_col:

            state = str(
                row[state_col]
            ).strip()

        # District
        district = ""

        if district_col:

            district = str(
                row[district_col]
            ).strip()

        # Hospital
        hospitals.append(
            {
                "name": str(
                    row[name_col]
                ).strip(),

                "address": address,

                "phone": phone,

                "state": state,

                "district": district,

                "latitude": h_lat,

                "longitude": h_lon,

                "distance": "N/A"
            }
        )

    return hospitals


# ============================================================
# NAVIGATION SECTION
# ============================================================

st.markdown("---")

st.subheader("🔐 Patient & Admin Portal")

col1, col2, col3, col4 = st.columns(4)


with col1:

    if st.button(
        "👤 Patient Login",
        use_container_width=True
    ):

        st.switch_page(
            "pages/patient_login.py"
        )


with col2:

    if st.button(
        "📝 Patient Register",
        use_container_width=True
    ):

        st.switch_page(
            "pages/patient_register.py"
        )


with col3:

    if st.button(
        "🔑 Admin Login",
        use_container_width=True
    ):

        st.switch_page(
            "pages/admin_login.py"
        )


with col4:

    if st.button(
        "📊 Patient Dashboard",
        use_container_width=True
    ):

        st.switch_page(
            "pages/patient_dashboard.py"
        )


# ============================================================
# HOSPITAL SEARCH
# ============================================================

st.markdown("---")

st.header("🔎 Find Hospitals")

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


# ============================================================
# SEARCH BUTTON
# ============================================================

if st.button(
    "🔍 Find Hospitals",
    use_container_width=True
):

    if not location.strip():

        st.warning(
            "⚠️ Please enter a location."
        )

    else:

        with st.spinner(
            "Searching hospitals..."
        ):

            try:

                # ------------------------------------------------
                # Geocode user location
                # ------------------------------------------------

                geo_result = geocode_location(
                    location.strip()
                )

                if geo_result:

                    user_lat = geo_result[0]
                    user_lon = geo_result[1]

                else:

                    user_lat = None
                    user_lon = None

                # ------------------------------------------------
                # Search CSV
                # ------------------------------------------------

                hospitals = search_hospitals_from_csv(
                    location.strip()
                )

                # ------------------------------------------------
                # Store in session
                # ------------------------------------------------

                st.session_state[
                    "search_results"
                ] = hospitals

                st.session_state[
                    "user_lat"
                ] = user_lat

                st.session_state[
                    "user_lon"
                ] = user_lon

                st.session_state[
                    "search_radius"
                ] = radius

            except Exception as e:

                st.error(
                    f"❌ Search error: {e}"
                )

                hospitals = []


# ============================================================
# DISPLAY SEARCH RESULTS
# ============================================================

if "search_results" in st.session_state:

    hospitals = st.session_state[
        "search_results"
    ]

    if not hospitals:

        st.warning(
            "❌ No hospitals found for this location."
        )

        st.info(
            "Try searching with a city, district or state name."
        )

    else:

        st.success(
            f"🏥 {len(hospitals)} hospitals found."
        )

        # ----------------------------------------------------
        # MAP DATA
        # ----------------------------------------------------

        map_data = []

        for hospital in hospitals:

            if (
                hospital["latitude"] is not None
                and
                hospital["longitude"] is not None
            ):

                map_data.append(
                    {
                        "latitude":
                            hospital["latitude"],

                        "longitude":
                            hospital["longitude"]
                    }
                )

        # ----------------------------------------------------
        # MAP
        # ----------------------------------------------------

        if map_data:

            st.subheader(
                "🗺️ Hospital Map"
            )

            map_df = pd.DataFrame(
                map_data
            )

            st.map(
                map_df,
                latitude="latitude",
                longitude="longitude",
                size=20
            )

        # ----------------------------------------------------
        # HOSPITAL LIST
        # ----------------------------------------------------

        st.subheader(
            "🏥 Hospital List"
        )

        for index, hospital in enumerate(
            hospitals,
            start=1
        ):

            with st.container():

                st.markdown(
                    f"### {index}. "
                    f"{hospital['name']}"
                )

                col1, col2 = st.columns(
                    [3, 1]
                )

                with col1:

                    st.write(
                        f"📍 **Address:** "
                        f"{hospital['address']}"
                    )

                    if hospital["state"]:

                        st.write(
                            f"🗺️ **State:** "
                            f"{hospital['state']}"
                        )

                    if hospital["district"]:

                        st.write(
                            f"🏙️ **District:** "
                            f"{hospital['district']}"
                        )

                    st.write(
                        f"📞 **Phone:** "
                        f"{hospital['phone']}"
                    )

                    st.write(
                        f"📏 **Distance:** "
                        f"{hospital['distance']}"
                    )

                with col2:

                    lat = hospital[
                        "latitude"
                    ]

                    lon = hospital[
                        "longitude"
                    ]

                    if (
                        lat is not None
                        and lon is not None
                    ):

                        maps_url = (
                            "https://www.google.com/maps/dir/?api=1"
                            f"&destination={lat},{lon}"
                        )

                        st.link_button(
                            "🧭 Directions",
                            maps_url,
                            use_container_width=True
                        )

                st.markdown("---")


# ============================================================
# LIVE BED AVAILABILITY
# ============================================================

st.markdown("---")

st.header("🛏️ Live Bed Availability")


# ============================================================
# AUTO REFRESH EVERY 30 SECONDS
# ============================================================

@st.fragment(run_every="30s")
def live_bed_availability():

    df = get_hospital_data()

    if df.empty:

        st.info(
            "No registered hospital bed data available."
        )

        return

    # --------------------------------------------------------
    # Overall statistics
    # --------------------------------------------------------

    total_beds = int(
        df["total_beds"].sum()
    )

    available_beds = int(
        df["available_beds"].sum()
    )

    occupied_beds = (
        total_beds - available_beds
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "🛏️ Total Beds",
            total_beds
        )

    with col2:

        st.metric(
            "🟢 Available Beds",
            available_beds
        )

    with col3:

        st.metric(
            "🔴 Occupied Beds",
            occupied_beds
        )

    st.markdown("---")

    # --------------------------------------------------------
    # Hospital cards
    # --------------------------------------------------------

    for _, hospital in df.iterrows():

        hospital_id = hospital["id"]

        name = hospital["name"]

        address = hospital["address"]

        phone = hospital["phone"]

        total = int(
            hospital["total_beds"]
        )

        available = int(
            hospital["available_beds"]
        )

        # ----------------------------------------------------
        # Availability status
        # ----------------------------------------------------

        if available == 0:

            status = "🔴 No bed available"

        elif available <= 2:

            status = "🟠 Low availability"

        else:

            status = "🟢 Beds available"

        # ----------------------------------------------------
        # Hospital expander
        # ----------------------------------------------------

        with st.expander(
            f"🏥 {name} — {status}"
        ):

            col1, col2 = st.columns(2)

            with col1:

                st.write(
                    f"📍 **Address:** {address}"
                )

                st.write(
                    f"📞 **Phone:** {phone}"
                )

            with col2:

                st.metric(
                    "Available Beds",
                    available,
                    delta=f"out of {total}"
                )

            # ------------------------------------------------
            # Bed type details
            # ------------------------------------------------

            bed_details = get_bed_details(
                hospital_id
            )

            if not bed_details.empty:

                st.markdown(
                    "#### 🛏️ Bed Type Details"
                )

                st.dataframe(
                    bed_details,
                    use_container_width=True,
                    hide_index=True
                )

            # ------------------------------------------------
            # Google Maps
            # ------------------------------------------------

            st.markdown(
                "📍 **Hospital Location**"
            )

            search_query = (
                name + " " + address
            )

            maps_search_url = (
                "https://www.google.com/maps/search/?api=1"
                "&query="
                +
                search_query.replace(
                    " ",
                    "+"
                )
            )

            st.link_button(
                "🧭 Open in Google Maps",
                maps_search_url
            )


live_bed_availability()


# ============================================================
# INFORMATION SECTION
# ============================================================

st.markdown("---")

st.subheader(
    "ℹ️ About This System"
)

st.write(
    """
    The Smart Hospital Bed Availability System helps users
    search hospitals and view available bed information.

    🏥 Hospital directory information is loaded from
    hospital_directory.csv.

    🛏️ Registered hospital bed availability is currently
    obtained from the application's database.

    🤖 Machine Learning based bed availability prediction
    can be integrated as a separate module.
    """
)


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "🏥 Smart Hospital Bed Availability System | "
    "Hospital directory + Bed availability platform"
)
