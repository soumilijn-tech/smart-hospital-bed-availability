import streamlit as st
import pandas as pd
import sqlite3
import pathlib
import re
import html
from datetime import date

import folium
from streamlit_folium import st_folium


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Smart Hospital Bed Availability System",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =========================================================
# PATHS
# =========================================================

BASE_DIR = pathlib.Path(__file__).parent

CSV_PATH = BASE_DIR / "hospital_directory.csv"

DB_DIR = BASE_DIR / "database"
DB_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DB_DIR / "hospital.db"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_connection():
    return sqlite3.connect(DB_PATH)


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def initialize_database():

    conn = get_connection()
    cur = conn.cursor()

    # Doctors
    cur.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_name TEXT NOT NULL,
            hospital_name TEXT NOT NULL,
            department TEXT,
            phone TEXT,
            status TEXT DEFAULT 'Available',
            available_time TEXT
        )
    """)

    # Equipment
    cur.execute("""
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_name TEXT NOT NULL,
            equipment_name TEXT NOT NULL,
            department TEXT,
            total_units INTEGER DEFAULT 0,
            available_units INTEGER DEFAULT 0
        )
    """)

    # Reservations
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            phone TEXT,
            hospital_name TEXT NOT NULL,
            resource_type TEXT,
            department TEXT,
            doctor_name TEXT,
            equipment_name TEXT,
            reservation_date TEXT,
            reservation_time TEXT,
            notes TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


initialize_database()


# =========================================================
# LOAD HOSPITAL CSV
# =========================================================

@st.cache_data
def load_hospital_data():

    if not CSV_PATH.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(CSV_PATH, low_memory=False)
    except Exception:
        try:
            df = pd.read_csv(
                CSV_PATH,
                encoding="latin1",
                low_memory=False
            )
        except Exception:
            return pd.DataFrame()

    # Clean column names
    df.columns = [
        str(col).strip()
        for col in df.columns
    ]

    return df


hospital_df = load_hospital_data()


# =========================================================
# COLUMN FINDER
# =========================================================

def normalize_column_name(name):

    return re.sub(
        r"[^a-z0-9]",
        "",
        str(name).lower()
    )


def find_column(df, possible_names):

    if df.empty:
        return None

    normalized = {
        normalize_column_name(col): col
        for col in df.columns
    }

    for name in possible_names:

        key = normalize_column_name(name)

        if key in normalized:
            return normalized[key]

    return None


# =========================================================
# SAFE NUMBER
# =========================================================

def safe_number(value, default=0):

    try:
        if pd.isna(value):
            return default

        text = str(value).replace(",", "").strip()

        if text == "":
            return default

        return float(text)

    except Exception:
        return default


# =========================================================
# BED STATUS
# =========================================================

def get_bed_status(total_beds, available_beds):

    total_beds = safe_number(total_beds)
    available_beds = safe_number(available_beds)

    if total_beds <= 0:
        return "⚪ Unknown"

    if available_beds <= 0:
        return "🔴 Full"

    percentage = (
        available_beds / total_beds
    ) * 100

    if percentage <= 15:
        return "🟠 Critical"

    elif percentage <= 30:
        return "🟡 Low"

    else:
        return "🟢 Available"


# =========================================================
# PARSE COORDINATES
# =========================================================

def parse_coordinates(value):

    if pd.isna(value):
        return None, None

    text = str(value).strip()

    if not text:
        return None, None

    # Remove brackets if present
    text = (
        text
        .replace("(", "")
        .replace(")", "")
        .replace("[", "")
        .replace("]", "")
    )

    # Example:
    # 11.6357989, 92.7120575

    parts = re.split(
        r"[,;\s]+",
        text
    )

    if len(parts) >= 2:

        try:

            lat = float(parts[0])
            lon = float(parts[1])

            if (
                -90 <= lat <= 90
                and -180 <= lon <= 180
            ):
                return lat, lon

        except Exception:
            pass

    return None, None


# =========================================================
# ADD MAP COORDINATES
# =========================================================

def prepare_coordinates(df):

    df = df.copy()

    coordinate_column = find_column(
        df,
        [
            "Location_Coordinates",
            "Location Coordinates",
            "location_coordinates",
            "coordinates",
            "geo_coordinates",
            "geo code"
        ]
    )

    latitude_column = find_column(
        df,
        [
            "Latitude",
            "latitude",
            "lat"
        ]
    )

    longitude_column = find_column(
        df,
        [
            "Longitude",
            "longitude",
            "lon",
            "lng"
        ]
    )

    df["map_lat"] = pd.NA
    df["map_lon"] = pd.NA

    # First preference:
    # Location_Coordinates

    if coordinate_column:

        coordinates = df[
            coordinate_column
        ].apply(parse_coordinates)

        df["map_lat"] = coordinates.apply(
            lambda x: x[0]
        )

        df["map_lon"] = coordinates.apply(
            lambda x: x[1]
        )

    # If Location_Coordinates doesn't work,
    # try separate latitude/longitude columns

    if latitude_column and longitude_column:

        lat_values = pd.to_numeric(
            df[latitude_column],
            errors="coerce"
        )

        lon_values = pd.to_numeric(
            df[longitude_column],
            errors="coerce"
        )

        df["map_lat"] = df["map_lat"].fillna(
            lat_values
        )

        df["map_lon"] = df["map_lon"].fillna(
            lon_values
        )

    return df


# =========================================================
# HOSPITAL COLUMN HELPERS
# =========================================================

def hospital_name_column(df):

    return find_column(
        df,
        [
            "hospital_name",
            "hospital name",
            "name of hospital",
            "hospital"
        ]
    )


def state_column(df):

    return find_column(
        df,
        [
            "state",
            "state name"
        ]
    )


def district_column(df):

    return find_column(
        df,
        [
            "district",
            "district name"
        ]
    )


def address_column(df):

    return find_column(
        df,
        [
            "address",
            "hospital address",
            "location"
        ]
    )


def pincode_column(df):

    return find_column(
        df,
        [
            "pincode",
            "pin code",
            "postal code"
        ]
    )


# =========================================================
# HOSPITAL SEARCH
# =========================================================

def search_hospitals(df, search_text):

    if df.empty:
        return df

    if not search_text.strip():
        return df

    search_text = search_text.strip().lower()

    columns_to_search = []

    for col in [
        hospital_name_column(df),
        state_column(df),
        district_column(df),
        address_column(df),
        pincode_column(df)
    ]:

        if col and col not in columns_to_search:
            columns_to_search.append(col)

    if not columns_to_search:
        return df.iloc[0:0]

    mask = pd.Series(
        False,
        index=df.index
    )

    for col in columns_to_search:

        mask = mask | (
            df[col]
            .fillna("")
            .astype(str)
            .str.lower()
            .str.contains(
                search_text,
                regex=False
            )
        )

    return df[mask]


# =========================================================
# BED DATABASE READER
# =========================================================

def get_bed_database():

    try:

        conn = get_connection()

        tables = pd.read_sql_query(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            """,
            conn
        )

        table_names = set(
            tables["name"].astype(str)
        )

        # Existing hospitals table
        if "hospitals" in table_names:

            df = pd.read_sql_query(
                "SELECT * FROM hospitals",
                conn
            )

            conn.close()

            return df

        conn.close()

    except Exception:
        pass

    return pd.DataFrame()


# =========================================================
# BED DATA COLUMN DETECTION
# =========================================================

def find_bed_columns(df):

    if df.empty:
        return None, None, None

    name_col = find_column(
        df,
        [
            "hospital_name",
            "hospital name",
            "name",
            "hospital"
        ]
    )

    total_col = find_column(
        df,
        [
            "total_beds",
            "total beds",
            "total_num_beds",
            "beds"
        ]
    )

    available_col = find_column(
        df,
        [
            "available_beds",
            "available beds",
            "available"
        ]
    )

    return (
        name_col,
        total_col,
        available_col
    )


# =========================================================
# MERGE BED DATA
# =========================================================

def attach_bed_data(df):

    df = df.copy()

    df["db_total_beds"] = pd.NA
    df["db_available_beds"] = pd.NA

    bed_df = get_bed_database()

    if bed_df.empty:
        return df

    csv_name_col = hospital_name_column(df)

    (
        bed_name_col,
        bed_total_col,
        bed_available_col
    ) = find_bed_columns(bed_df)

    if not (
        csv_name_col
        and bed_name_col
        and bed_total_col
        and bed_available_col
    ):
        return df

    bed_temp = bed_df[
        [
            bed_name_col,
            bed_total_col,
            bed_available_col
        ]
    ].copy()

    bed_temp["hospital_key"] = (
        bed_temp[bed_name_col]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    bed_temp = bed_temp.drop_duplicates(
        "hospital_key"
    )

    df["hospital_key"] = (
        df[csv_name_col]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df = df.merge(
        bed_temp[
            [
                "hospital_key",
                bed_total_col,
                bed_available_col
            ]
        ],
        on="hospital_key",
        how="left"
    )

    df["db_total_beds"] = pd.to_numeric(
        df[bed_total_col],
        errors="coerce"
    )

    df["db_available_beds"] = pd.to_numeric(
        df[bed_available_col],
        errors="coerce"
    )

    df.drop(
        columns=[
            "hospital_key",
            bed_total_col,
            bed_available_col
        ],
        inplace=True,
        errors="ignore"
    )

    return df


# =========================================================
# FALLBACK BED DATA FROM CSV
# =========================================================

def get_csv_bed_columns(df):

    total_col = find_column(
        df,
        [
            "total_num_beds",
            "total_beds",
            "total beds",
            "number of beds"
        ]
    )

    available_col = find_column(
        df,
        [
            "available_beds",
            "available beds",
            "available bed"
        ]
    )

    return total_col, available_col


def get_bed_values(row):

    total = row.get(
        "db_total_beds",
        pd.NA
    )

    available = row.get(
        "db_available_beds",
        pd.NA
    )

    # Database data has priority

    if (
        not pd.isna(total)
        and not pd.isna(available)
    ):

        return (
            safe_number(total),
            safe_number(available)
        )

    # Otherwise check CSV

    total_col, available_col = (
        get_csv_bed_columns(
            pd.DataFrame([row])
        )
    )

    if total_col and available_col:

        return (
            safe_number(
                row.get(total_col)
            ),
            safe_number(
                row.get(available_col)
            )
        )

    return None, None


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("🏥 Smart Hospital")

st.sidebar.markdown(
    "### Navigation"
)

page = st.sidebar.radio(
    "Go to",
    [
        "🏠 Home",
        "🏥 Hospital Search",
        "🛏️ Bed Availability",
        "👨‍⚕️ Doctor Availability",
        "🩺 Equipment Availability",
        "📋 Reservation Management",
        "📊 Admin Dashboard"
    ]
)

st.sidebar.markdown("---")

st.sidebar.info(
    """
    **Smart Hospital Bed Availability System**

    Search hospitals, view bed information,
    healthcare resources and reservations.
    """
)


# =========================================================
# HOME
# =========================================================

if page == "🏠 Home":

    st.title(
        "🏥 Smart Hospital Bed Availability System"
    )

    st.subheader(
        "Find hospitals, beds and healthcare resources."
    )

    st.markdown("---")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "🏥 Hospitals",
            f"{len(hospital_df):,}"
        )

    with col2:

        bed_db = get_bed_database()

        if not bed_db.empty:

            _, total_col, available_col = (
                find_bed_columns(bed_db)
            )

            if total_col and available_col:

                total = pd.to_numeric(
                    bed_db[total_col],
                    errors="coerce"
                ).sum()

                available = pd.to_numeric(
                    bed_db[available_col],
                    errors="coerce"
                ).sum()

                st.metric(
                    "🛏️ Available Beds",
                    f"{int(available):,}"
                )

            else:
                st.metric(
                    "🛏️ Available Beds",
                    "N/A"
                )

        else:

            st.metric(
                "🛏️ Available Beds",
                "N/A"
            )

    with col3:

        conn = get_connection()

        try:

            count = pd.read_sql_query(
                "SELECT COUNT(*) AS c FROM doctors",
                conn
            ).iloc[0]["c"]

        except Exception:

            count = 0

        conn.close()

        st.metric(
            "👨‍⚕️ Doctors",
            int(count)
        )

    st.markdown("---")

    st.info(
        """
        🔎 Use **Hospital Search** to find hospitals.

        🗺️ The interactive map displays hospital locations.

        🛏️ Bed availability is shown when registered
        bed data is available.

        👨‍⚕️ Doctor and 🩺 equipment availability can
        be managed from the respective sections.
        """
    )


# =========================================================
# HOSPITAL SEARCH + MAP
# =========================================================

elif page == "🏥 Hospital Search":

    st.title("🏥 Hospital Search")

    if hospital_df.empty:

        st.error(
            """
            `hospital_directory.csv` was not found.

            Please keep the original CSV file in the
            same GitHub folder as `app.py`.
            """
        )

        st.stop()

    search_text = st.text_input(
        "🔎 Search Hospital / State / District / Pincode",
        placeholder="Example: Kolkata, West Bengal, Apollo..."
    )

    col1, col2 = st.columns(2)

    with col1:

        max_results = st.slider(
            "Maximum search results",
            10,
            500,
            100
        )

    with col2:

        max_markers = st.slider(
            "Maximum map markers",
            20,
            300,
            100
        )

    # Search
    results = search_hospitals(
        hospital_df,
        search_text
    )

    results = results.head(
        max_results
    ).copy()

    # Coordinates
    results = prepare_coordinates(
        results
    )

    # Bed data
    results = attach_bed_data(
        results
    )

    st.markdown("---")

    st.subheader(
        f"🏥 Hospital Results ({len(results)})"
    )

    if results.empty:

        st.warning(
            "No hospitals found for your search."
        )

    else:

        name_col = hospital_name_column(
            results
        )

        state_col = state_column(
            results
        )

        district_col = district_column(
            results
        )

        address_col = address_column(
            results
        )

        # -------------------------------------------------
        # Hospital cards
        # -------------------------------------------------

        for index, row in results.iterrows():

            hospital_name = (
                str(row[name_col])
                if name_col
                else "Hospital"
            )

            state = (
                str(row[state_col])
                if state_col
                else "N/A"
            )

            district = (
                str(row[district_col])
                if district_col
                else "N/A"
            )

            address = (
                str(row[address_col])
                if address_col
                else "N/A"
            )

            total_beds, available_beds = (
                get_bed_values(row)
            )

            if (
                total_beds is not None
                and available_beds is not None
            ):

                status = get_bed_status(
                    total_beds,
                    available_beds
                )

                bed_text = (
                    f"{int(available_beds)} / "
                    f"{int(total_beds)}"
                )

            else:

                status = "⚪ Not Available"

                bed_text = "Not Available"

            with st.expander(
                f"🏥 {hospital_name}"
            ):

                c1, c2, c3 = st.columns(3)

                with c1:
                    st.write(
                        f"**State:** {state}"
                    )
                    st.write(
                        f"**District:** {district}"
                    )

                with c2:
                    st.write(
                        f"**Beds:** {bed_text}"
                    )
                    st.write(
                        f"**Status:** {status}"
                    )

                with c3:
                    lat = row.get(
                        "map_lat"
                    )

                    lon = row.get(
                        "map_lon"
                    )

                    if (
                        pd.notna(lat)
                        and pd.notna(lon)
                    ):

                        st.write(
                            f"📍 {float(lat):.5f}, "
                            f"{float(lon):.5f}"
                        )

                    else:

                        st.write(
                            "📍 Location unavailable"
                        )

                st.write(
                    f"**Address:** {address}"
                )

        # -------------------------------------------------
        # MAP
        # -------------------------------------------------

        st.markdown("---")

        st.subheader(
            "📍 Interactive Hospital Map"
        )

        map_df = results.dropna(
            subset=[
                "map_lat",
                "map_lon"
            ]
        ).copy()

        # Convert coordinates to numeric
        map_df["map_lat"] = pd.to_numeric(
            map_df["map_lat"],
            errors="coerce"
        )

        map_df["map_lon"] = pd.to_numeric(
            map_df["map_lon"],
            errors="coerce"
        )

        map_df = map_df.dropna(
            subset=[
                "map_lat",
                "map_lon"
            ]
        )

        # Limit markers
        map_df = map_df.head(
            max_markers
        )

        if map_df.empty:

            st.warning(
                """
                📍 No hospitals with valid
                latitude/longitude were found
                for the current search.

                The app checks both:
                • Location_Coordinates
                • Latitude + Longitude columns
                """
            )

        else:

            st.success(
                f"📍 Showing {len(map_df)} hospital markers."
            )

            # Map center
            center_lat = map_df[
                "map_lat"
            ].mean()

            center_lon = map_df[
                "map_lon"
            ].mean()

            hospital_map = folium.Map(
                location=[
                    center_lat,
                    center_lon
                ],
                zoom_start=6,
                control_scale=True
            )

            # -------------------------------------------------
            # MARKERS
            # -------------------------------------------------

            for _, row in map_df.iterrows():

                hospital_name = (
                    str(row[name_col])
                    if name_col
                    else "Hospital"
                )

                state = (
                    str(row[state_col])
                    if state_col
                    else "N/A"
                )

                district = (
                    str(row[district_col])
                    if district_col
                    else "N/A"
                )

                address = (
                    str(row[address_col])
                    if address_col
                    else "N/A"
                )

                total_beds, available_beds = (
                    get_bed_values(row)
                )

                if (
                    total_beds is not None
                    and available_beds is not None
                ):

                    status = get_bed_status(
                        total_beds,
                        available_beds
                    )

                    bed_text = (
                        f"{int(available_beds)} / "
                        f"{int(total_beds)}"
                    )

                    # Marker color
                    if available_beds <= 0:
                        marker_color = "red"

                    else:

                        percentage = (
                            available_beds /
                            total_beds
                        ) * 100

                        if percentage <= 15:
                            marker_color = "orange"

                        elif percentage <= 30:
                            marker_color = "beige"

                        else:
                            marker_color = "green"

                else:

                    status = "⚪ Not Available"

                    bed_text = "Not Available"

                    marker_color = "gray"

                popup_html = f"""
                <div style="
                    width: 260px;
                    font-family: Arial;
                ">

                    <h4>
                        🏥 {html.escape(hospital_name)}
                    </h4>

                    <b>State:</b>
                    {html.escape(state)}
                    <br>

                    <b>District:</b>
                    {html.escape(district)}
                    <br>

                    <b>Address:</b>
                    {html.escape(address)}
                    <br><br>

                    <b>🛏️ Beds:</b>
                    {bed_text}
                    <br>

                    <b>📊 Bed Status:</b>
                    {html.escape(status)}

                </div>
                """

                folium.Marker(
                    location=[
                        float(row["map_lat"]),
                        float(row["map_lon"])
                    ],
                    popup=folium.Popup(
                        popup_html,
                        max_width=350
                    ),
                    tooltip=(
                        f"🏥 {hospital_name}"
                    ),
                    icon=folium.Icon(
                        color=marker_color,
                        icon="plus-sign"
                    )
                ).add_to(
                    hospital_map
                )

            # -------------------------------------------------
            # MAP LEGEND
            # -------------------------------------------------

            legend_html = """
            <div style="
                position: fixed;
                bottom: 30px;
                left: 30px;
                z-index: 9999;
                background-color: white;
                padding: 12px;
                border: 2px solid grey;
                border-radius: 8px;
                font-size: 13px;
            ">

            <b>🛏️ Bed Availability</b><br>

            <span style="color:green;">
            ●
            </span>
            Available<br>

            <span style="color:orange;">
            ●
            </span>
            Critical<br>

            <span style="color:red;">
            ●
            </span>
            Full<br>

            <span style="color:gray;">
            ●
            </span>
            Data unavailable

            </div>
            """

            hospital_map.get_root().html.add_child(
                folium.Element(
                    legend_html
                )
            )

            st_folium(
                hospital_map,
                width=None,
                height=600,
                returned_objects=[]
            )


# =========================================================
# BED AVAILABILITY
# =========================================================

elif page == "🛏️ Bed Availability":

    st.title(
        "🛏️ Bed Availability"
    )

    bed_df = get_bed_database()

    if bed_df.empty:

        st.info(
            """
            No registered bed availability records
            are currently available.

            The hospital directory is not treated as
            real-time bed availability.
            """
        )

    else:

        (
            bed_name_col,
            bed_total_col,
            bed_available_col
        ) = find_bed_columns(
            bed_df
        )

        if not (
            bed_name_col
            and bed_total_col
            and bed_available_col
        ):

            st.error(
                "Bed database columns could not be detected."
            )

        else:

            bed_df["total_beds_numeric"] = pd.to_numeric(
                bed_df[bed_total_col],
                errors="coerce"
            ).fillna(0)

            bed_df["available_beds_numeric"] = pd.to_numeric(
                bed_df[bed_available_col],
                errors="coerce"
            ).fillna(0)

            bed_df["occupied_beds"] = (
                bed_df["total_beds_numeric"]
                -
                bed_df["available_beds_numeric"]
            ).clip(lower=0)

            bed_df["occupancy_percent"] = (
                bed_df["occupied_beds"]
                /
                bed_df["total_beds_numeric"]
                .replace(0, pd.NA)
                * 100
            ).fillna(0)

            # Search
            search = st.text_input(
                "Search hospital"
            )

            if search:

                bed_df = bed_df[
                    bed_df[
                        bed_name_col
                    ]
                    .fillna("")
                    .astype(str)
                    .str.contains(
                        search,
                        case=False,
                        regex=False
                    )
                ]

            # Metrics

            total_beds = int(
                bed_df[
                    "total_beds_numeric"
                ].sum()
            )

            available_beds = int(
                bed_df[
                    "available_beds_numeric"
                ].sum()
            )

            occupied_beds = int(
                bed_df[
                    "occupied_beds"
                ].sum()
            )

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "Total Beds",
                total_beds
            )

            c2.metric(
                "Available Beds",
                available_beds
            )

            c3.metric(
                "Occupied Beds",
                occupied_beds
            )

            st.markdown("---")

            # Table

            display_df = bed_df[
                [
                    bed_name_col,
                    "total_beds_numeric",
                    "available_beds_numeric",
                    "occupied_beds",
                    "occupancy_percent"
                ]
            ].copy()

            display_df.columns = [
                "Hospital",
                "Total Beds",
                "Available Beds",
                "Occupied Beds",
                "Occupancy %"
            ]

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )


# =========================================================
# DOCTOR AVAILABILITY
# =========================================================

elif page == "👨‍⚕️ Doctor Availability":

    st.title(
        "👨‍⚕️ Doctor Availability"
    )

    tab1, tab2 = st.tabs(
        [
            "🔎 View Doctors",
            "➕ Add Doctor"
        ]
    )

    # -----------------------------------------------------
    # VIEW
    # -----------------------------------------------------

    with tab1:

        conn = get_connection()

        doctors = pd.read_sql_query(
            "SELECT * FROM doctors ORDER BY doctor_name",
            conn
        )

        conn.close()

        if doctors.empty:

            st.info(
                "No doctors have been added yet."
            )

        else:

            search = st.text_input(
                "Search doctor / hospital / department"
            )

            status_filter = st.selectbox(
                "Status",
                [
                    "All",
                    "Available",
                    "Busy",
                    "On Leave"
                ]
            )

            filtered = doctors.copy()

            if search:

                mask = (
                    filtered[
                        [
                            "doctor_name",
                            "hospital_name",
                            "department"
                        ]
                    ]
                    .fillna("")
                    .astype(str)
                    .apply(
                        lambda col:
                        col.str.contains(
                            search,
                            case=False,
                            regex=False
                        )
                    )
                    .any(axis=1)
                )

                filtered = filtered[mask]

            if status_filter != "All":

                filtered = filtered[
                    filtered["status"]
                    == status_filter
                ]

            st.dataframe(
                filtered[
                    [
                        "doctor_name",
                        "hospital_name",
                        "department",
                        "status",
                        "available_time"
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )

            st.markdown("---")

            if not filtered.empty:

                selected_id = st.selectbox(
                    "Select Doctor ID",
                    filtered["id"].tolist()
                )

                selected = doctors[
                    doctors["id"]
                    == selected_id
                ].iloc[0]

                new_status = st.selectbox(
                    "Update Status",
                    [
                        "Available",
                        "Busy",
                        "On Leave"
                    ],
                    index=[
                        "Available",
                        "Busy",
                        "On Leave"
                    ].index(
                        selected["status"]
                    )
                    if selected["status"]
                    in [
                        "Available",
                        "Busy",
                        "On Leave"
                    ]
                    else 0
                )

                new_time = st.text_input(
                    "Available Time",
                    value=str(
                        selected[
                            "available_time"
                        ]
                        or ""
                    )
                )

                if st.button(
                    "💾 Update Doctor",
                    width="stretch"
                ):

                    conn = get_connection()

                    conn.execute(
                        """
                        UPDATE doctors
                        SET status = ?,
                            available_time = ?
                        WHERE id = ?
                        """,
                        (
                            new_status,
                            new_time,
                            selected_id
                        )
                    )

                    conn.commit()
                    conn.close()

                    st.success(
                        "Doctor updated successfully."
                    )

                    st.rerun()

    # -----------------------------------------------------
    # ADD
    # -----------------------------------------------------

    with tab2:

        with st.form(
            "doctor_form"
        ):

            doctor_name = st.text_input(
                "Doctor Name"
            )

            hospital_name = st.text_input(
                "Hospital Name"
            )

            department = st.text_input(
                "Department"
            )

            phone = st.text_input(
                "Phone"
            )

            status = st.selectbox(
                "Status",
                [
                    "Available",
                    "Busy",
                    "On Leave"
                ]
            )

            available_time = st.text_input(
                "Available Time"
            )

            submitted = st.form_submit_button(
                "➕ Add Doctor"
            )

            if submitted:

                if not doctor_name or not hospital_name:

                    st.error(
                        "Doctor name and hospital name are required."
                    )

                else:

                    conn = get_connection()

                    conn.execute(
                        """
                        INSERT INTO doctors
                        (
                            doctor_name,
                            hospital_name,
                            department,
                            phone,
                            status,
                            available_time
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            doctor_name,
                            hospital_name,
                            department,
                            phone,
                            status,
                            available_time
                        )
                    )

                    conn.commit()
                    conn.close()

                    st.success(
                        "Doctor added successfully."
                    )

                    st.rerun()


# =========================================================
# EQUIPMENT
# =========================================================

elif page == "🩺 Equipment Availability":

    st.title(
        "🩺 Equipment Availability"
    )

    tab1, tab2 = st.tabs(
        [
            "🔎 View Equipment",
            "➕ Add Equipment"
        ]
    )

    with tab1:

        conn = get_connection()

        equipment = pd.read_sql_query(
            """
            SELECT *
            FROM equipment
            ORDER BY hospital_name, equipment_name
            """,
            conn
        )

        conn.close()

        if equipment.empty:

            st.info(
                "No equipment records available."
            )

        else:

            search = st.text_input(
                "Search equipment / hospital"
            )

            filtered = equipment.copy()

            if search:

                mask = (
                    filtered[
                        [
                            "hospital_name",
                            "equipment_name",
                            "department"
                        ]
                    ]
                    .fillna("")
                    .astype(str)
                    .apply(
                        lambda col:
                        col.str.contains(
                            search,
                            case=False,
                            regex=False
                        )
                    )
                    .any(axis=1)
                )

                filtered = filtered[mask]

            filtered["status"] = filtered.apply(
                lambda row:
                (
                    "🟢 Available"
                    if row["available_units"] > 2
                    else
                    "🟡 Low"
                    if row["available_units"] > 0
                    else
                    "🔴 Unavailable"
                ),
                axis=1
            )

            st.dataframe(
                filtered,
                use_container_width=True,
                hide_index=True
            )

    with tab2:

        with st.form(
            "equipment_form"
        ):

            hospital_name = st.text_input(
                "Hospital Name"
            )

            equipment_name = st.text_input(
                "Equipment Name"
            )

            department = st.text_input(
                "Department"
            )

            total_units = st.number_input(
                "Total Units",
                min_value=0,
                value=1
            )

            available_units = st.number_input(
                "Available Units",
                min_value=0,
                value=1
            )

            submitted = st.form_submit_button(
                "➕ Add Equipment"
            )

            if submitted:

                if (
                    not hospital_name
                    or not equipment_name
                ):

                    st.error(
                        "Hospital and equipment name are required."
                    )

                elif available_units > total_units:

                    st.error(
                        "Available units cannot exceed total units."
                    )

                else:

                    conn = get_connection()

                    conn.execute(
                        """
                        INSERT INTO equipment
                        (
                            hospital_name,
                            equipment_name,
                            department,
                            total_units,
                            available_units
                        )
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            hospital_name,
                            equipment_name,
                            department,
                            total_units,
                            available_units
                        )
                    )

                    conn.commit()
                    conn.close()

                    st.success(
                        "Equipment added successfully."
                    )

                    st.rerun()


# =========================================================
# RESERVATION MANAGEMENT
# =========================================================

elif page == "📋 Reservation Management":

    st.title(
        "📋 Reservation Management"
    )

    tab1, tab2 = st.tabs(
        [
            "➕ New Reservation",
            "📄 Reservation List"
        ]
    )

    # -----------------------------------------------------
    # NEW RESERVATION
    # -----------------------------------------------------

    with tab1:

        with st.form(
            "reservation_form"
        ):

            patient_name = st.text_input(
                "Patient Name"
            )

            phone = st.text_input(
                "Phone Number"
            )

            hospital_name = st.text_input(
                "Hospital Name"
            )

            resource_type = st.selectbox(
                "Resource Type",
                [
                    "Bed",
                    "Doctor",
                    "Equipment",
                    "Emergency"
                ]
            )

            department = st.text_input(
                "Department"
            )

            doctor_name = st.text_input(
                "Doctor Name"
            )

            equipment_name = st.text_input(
                "Equipment Name"
            )

            reservation_date = st.date_input(
                "Reservation Date",
                min_value=date.today()
            )

            reservation_time = st.time_input(
                "Reservation Time"
            )

            notes = st.text_area(
                "Notes"
            )

            submitted = st.form_submit_button(
                "📋 Submit Reservation"
            )

            if submitted:

                if (
                    not patient_name
                    or not hospital_name
                ):

                    st.error(
                        "Patient name and hospital name are required."
                    )

                else:

                    conn = get_connection()

                    conn.execute(
                        """
                        INSERT INTO reservations
                        (
                            patient_name,
                            phone,
                            hospital_name,
                            resource_type,
                            department,
                            doctor_name,
                            equipment_name,
                            reservation_date,
                            reservation_time,
                            notes,
                            status
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            patient_name,
                            phone,
                            hospital_name,
                            resource_type,
                            department,
                            doctor_name,
                            equipment_name,
                            str(reservation_date),
                            str(reservation_time),
                            notes,
                            "Pending"
                        )
                    )

                    conn.commit()
                    conn.close()

                    st.success(
                        "Reservation submitted successfully."
                    )


    # -----------------------------------------------------
    # RESERVATION LIST
    # -----------------------------------------------------

    with tab2:

        conn = get_connection()

        reservations = pd.read_sql_query(
            """
            SELECT *
            FROM reservations
            ORDER BY created_at DESC
            """,
            conn
        )

        conn.close()

        if reservations.empty:

            st.info(
                "No reservations found."
            )

        else:

            st.dataframe(
                reservations,
                use_container_width=True,
                hide_index=True
            )

            st.markdown("---")

            selected_id = st.selectbox(
                "Select Reservation ID",
                reservations["id"].tolist()
            )

            selected_status = st.selectbox(
                "Update Status",
                [
                    "Pending",
                    "Confirmed",
                    "Rejected",
                    "Cancelled"
                ]
            )

            if st.button(
                "💾 Update Reservation",
                width="stretch"
            ):

                conn = get_connection()

                conn.execute(
                    """
                    UPDATE reservations
                    SET status = ?
                    WHERE id = ?
                    """,
                    (
                        selected_status,
                        selected_id
                    )
                )

                conn.commit()
                conn.close()

                st.success(
                    "Reservation status updated."
                )

                st.rerun()


# =========================================================
# ADMIN DASHBOARD
# =========================================================

elif page == "📊 Admin Dashboard":

    st.title(
        "📊 Admin Dashboard"
    )

    conn = get_connection()

    try:
        doctor_count = pd.read_sql_query(
            "SELECT COUNT(*) AS c FROM doctors",
            conn
        ).iloc[0]["c"]
    except Exception:
        doctor_count = 0

    try:
        equipment_count = pd.read_sql_query(
            "SELECT COUNT(*) AS c FROM equipment",
            conn
        ).iloc[0]["c"]
    except Exception:
        equipment_count = 0

    try:
        reservation_count = pd.read_sql_query(
            "SELECT COUNT(*) AS c FROM reservations",
            conn
        ).iloc[0]["c"]
    except Exception:
        reservation_count = 0

    try:
        pending_count = pd.read_sql_query(
            """
            SELECT COUNT(*) AS c
            FROM reservations
            WHERE status = 'Pending'
            """,
            conn
        ).iloc[0]["c"]
    except Exception:
        pending_count = 0

    conn.close()

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "🏥 Hospitals",
        f"{len(hospital_df):,}"
    )

    c2.metric(
        "👨‍⚕️ Doctors",
        int(doctor_count)
    )

    c3.metric(
        "🩺 Equipment",
        int(equipment_count)
    )

    c4.metric(
        "📋 Reservations",
        int(reservation_count)
    )

    st.markdown("---")

    st.subheader(
        "📋 Reservation Status"
    )

    conn = get_connection()

    try:

        reservation_status = pd.read_sql_query(
            """
            SELECT status, COUNT(*) AS count
            FROM reservations
            GROUP BY status
            """,
            conn
        )

    except Exception:

        reservation_status = pd.DataFrame()

    conn.close()

    if reservation_status.empty:

        st.info(
            "No reservation statistics available."
        )

    else:

        st.dataframe(
            reservation_status,
            use_container_width=True,
            hide_index=True
        )

    st.metric(
        "⏳ Pending Reservations",
        int(pending_count)
    )

    st.markdown("---")

    st.subheader(
        "ℹ️ System Information"
    )

    st.write(
        f"Hospital directory records: "
        f"**{len(hospital_df):,}**"
    )

    st.write(
        "Hospital map coordinates are read from "
        "**Location_Coordinates** or "
        "**Latitude / Longitude** columns."
    )

    st.write(
        "Bed availability is shown only when "
        "registered/database data is available."
    )


# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.caption(
    """
    🏥 Smart Hospital Bed Availability System |
    Hospital directory + registered resource data |
    Bed availability should not be considered guaranteed
    real-time unless connected to a live hospital system.
    """
        )
