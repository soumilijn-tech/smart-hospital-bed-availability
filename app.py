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
    initial_sidebar_state="expanded",
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
# DATABASE
# =========================================================

def get_connection():
    return sqlite3.connect(DB_PATH)


def initialize_database():

    conn = get_connection()
    cur = conn.cursor()

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
# LOAD CSV
# =========================================================

@st.cache_data
def load_hospital_data():

    if not CSV_PATH.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(
            CSV_PATH,
            low_memory=False
        )

    except Exception:

        try:
            return pd.read_csv(
                CSV_PATH,
                encoding="latin1",
                low_memory=False
            )

        except Exception:
            return pd.DataFrame()


hospital_df = load_hospital_data()


# =========================================================
# GENERAL HELPERS
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

    normalized_columns = {
        normalize_column_name(column): column
        for column in df.columns
    }

    for name in possible_names:

        key = normalize_column_name(name)

        if key in normalized_columns:
            return normalized_columns[key]

    return None


def safe_number(value, default=0):

    try:

        if pd.isna(value):
            return default

        value = str(value).strip()

        value = value.replace(",", "")

        if value == "":
            return default

        return float(value)

    except Exception:

        return default


# =========================================================
# HOSPITAL COLUMNS
# =========================================================

def hospital_name_column(df):

    return find_column(
        df,
        [
            "hospital_name",
            "hospital name",
            "name of hospital",
            "hospital",
            "hospitalname",
        ]
    )


def state_column(df):

    return find_column(
        df,
        [
            "state",
            "state name",
        ]
    )


def district_column(df):

    return find_column(
        df,
        [
            "district",
            "district name",
        ]
    )


def address_column(df):

    return find_column(
        df,
        [
            "address",
            "hospital address",
            "location",
            "hospital location",
        ]
    )


def pincode_column(df):

    return find_column(
        df,
        [
            "pincode",
            "pin code",
            "postal code",
            "pin",
        ]
    )


# =========================================================
# COORDINATE PARSER
# =========================================================

def parse_coordinates(value):

    if pd.isna(value):
        return None, None

    text = str(value).strip()

    if not text:
        return None, None

    # Remove brackets
    text = text.replace("(", "")
    text = text.replace(")", "")
    text = text.replace("[", "")
    text = text.replace("]", "")
    text = text.replace("{", "")
    text = text.replace("}", "")

    # Try normal separator
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
                and
                -180 <= lon <= 180
            ):
                return lat, lon

        except Exception:
            pass

    # Try extracting numbers from text
    numbers = re.findall(
        r"-?\d+(?:\.\d+)?",
        text
    )

    if len(numbers) >= 2:

        try:

            lat = float(numbers[0])
            lon = float(numbers[1])

            if (
                -90 <= lat <= 90
                and
                -180 <= lon <= 180
            ):
                return lat, lon

        except Exception:
            pass

    return None, None


# =========================================================
# PREPARE COORDINATES
# =========================================================

def prepare_coordinates(df):

    df = df.copy()

    coordinate_column = find_column(
        df,
        [
            "Location_Coordinates",
            "Location Coordinates",
            "location_coordinates",
            "Location Coordinates ",
            "coordinates",
            "coordinate",
            "geo_coordinates",
            "geo code",
            "geo_code",
            "geocode",
            "lat long",
            "latlong",
        ]
    )

    latitude_column = find_column(
        df,
        [
            "Latitude",
            "latitude",
            "lat",
            "latitude_coordinate",
            "latitude coordinates",
        ]
    )

    longitude_column = find_column(
        df,
        [
            "Longitude",
            "longitude",
            "lon",
            "lng",
            "longitude_coordinate",
            "longitude coordinates",
        ]
    )

    df["map_lat"] = pd.NA
    df["map_lon"] = pd.NA

    # ---------------------------------------------
    # METHOD 1
    # Location_Coordinates
    # ---------------------------------------------

    if coordinate_column:

        parsed = df[
            coordinate_column
        ].apply(parse_coordinates)

        df["map_lat"] = parsed.apply(
            lambda x: x[0]
        )

        df["map_lon"] = parsed.apply(
            lambda x: x[1]
        )

    # ---------------------------------------------
    # METHOD 2
    # Latitude + Longitude
    # ---------------------------------------------

    if (
        latitude_column
        and
        longitude_column
    ):

        lat = pd.to_numeric(
            df[latitude_column],
            errors="coerce"
        )

        lon = pd.to_numeric(
            df[longitude_column],
            errors="coerce"
        )

        df["map_lat"] = df[
            "map_lat"
        ].fillna(lat)

        df["map_lon"] = df[
            "map_lon"
        ].fillna(lon)

    # ---------------------------------------------
    # Numeric conversion
    # ---------------------------------------------

    df["map_lat"] = pd.to_numeric(
        df["map_lat"],
        errors="coerce"
    )

    df["map_lon"] = pd.to_numeric(
        df["map_lon"],
        errors="coerce"
    )

    # ---------------------------------------------
    # Validate latitude
    # ---------------------------------------------

    df.loc[
        ~df["map_lat"].between(
            -90,
            90
        ),
        "map_lat"
    ] = pd.NA

    # ---------------------------------------------
    # Validate longitude
    # ---------------------------------------------

    df.loc[
        ~df["map_lon"].between(
            -180,
            180
        ),
        "map_lon"
    ] = pd.NA

    return (
        df,
        coordinate_column,
        latitude_column,
        longitude_column
    )


# =========================================================
# SEARCH
# =========================================================

def search_hospitals(
    df,
    search_text
):

    if df.empty:
        return df

    search_text = search_text.strip().lower()

    if not search_text:
        return df.copy()

    columns = [
        hospital_name_column(df),
        state_column(df),
        district_column(df),
        address_column(df),
        pincode_column(df),
    ]

    columns = [
        column
        for column in columns
        if column
    ]

    if not columns:
        return df.iloc[0:0]

    mask = pd.Series(
        False,
        index=df.index
    )

    for column in columns:

        mask |= (
            df[column]
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
# BED STATUS
# =========================================================

def get_bed_status(
    total_beds,
    available_beds
):

    total_beds = safe_number(
        total_beds
    )

    available_beds = safe_number(
        available_beds
    )

    if total_beds <= 0:
        return "⚪ Unknown"

    if available_beds <= 0:
        return "🔴 Full"

    percentage = (
        available_beds
        /
        total_beds
    ) * 100

    if percentage <= 15:
        return "🟠 Critical"

    elif percentage <= 30:
        return "🟡 Low"

    else:
        return "🟢 Available"


# =========================================================
# BED DATABASE
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

        if "hospitals" in table_names:

            data = pd.read_sql_query(
                "SELECT * FROM hospitals",
                conn
            )

            conn.close()

            return data

        conn.close()

    except Exception:
        pass

    return pd.DataFrame()


def find_bed_columns(df):

    if df.empty:
        return None, None, None

    name_col = find_column(
        df,
        [
            "hospital_name",
            "hospital name",
            "name",
            "hospital",
        ]
    )

    total_col = find_column(
        df,
        [
            "total_beds",
            "total beds",
            "total_num_beds",
            "beds",
        ]
    )

    available_col = find_column(
        df,
        [
            "available_beds",
            "available beds",
            "available",
        ]
    )

    return (
        name_col,
        total_col,
        available_col
    )


def get_csv_bed_columns(df):

    total_col = find_column(
        df,
        [
            "total_beds",
            "total beds",
            "total_num_beds",
            "number of beds",
        ]
    )

    available_col = find_column(
        df,
        [
            "available_beds",
            "available beds",
            "available_beds_demo",
            "available bed",
        ]
    )

    return (
        total_col,
        available_col
    )


def attach_bed_data(df):

    df = df.copy()

    df["db_total_beds"] = pd.NA
    df["db_available_beds"] = pd.NA

    bed_df = get_bed_database()

    if bed_df.empty:
        return df

    csv_name = hospital_name_column(
        df
    )

    bed_name, bed_total, bed_available = (
        find_bed_columns(
            bed_df
        )
    )

    if not all([
        csv_name,
        bed_name,
        bed_total,
        bed_available,
    ]):
        return df

    temp = bed_df[
        [
            bed_name,
            bed_total,
            bed_available,
        ]
    ].copy()

    temp["hospital_key"] = (
        temp[bed_name]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    temp = temp.drop_duplicates(
        "hospital_key"
    )

    df["hospital_key"] = (
        df[csv_name]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df = df.merge(
        temp[
            [
                "hospital_key",
                bed_total,
                bed_available,
            ]
        ],
        on="hospital_key",
        how="left"
    )

    df["db_total_beds"] = pd.to_numeric(
        df[bed_total],
        errors="coerce"
    )

    df["db_available_beds"] = pd.to_numeric(
        df[bed_available],
        errors="coerce"
    )

    df.drop(
        columns=[
            "hospital_key",
            bed_total,
            bed_available,
        ],
        inplace=True,
        errors="ignore"
    )

    return df


def get_bed_values(
    row,
    original_df
):

    db_total = row.get(
        "db_total_beds",
        pd.NA
    )

    db_available = row.get(
        "db_available_beds",
        pd.NA
    )

    if (
        not pd.isna(db_total)
        and
        not pd.isna(db_available)
    ):

        return (
            safe_number(db_total),
            safe_number(db_available)
        )

    total_col, available_col = (
        get_csv_bed_columns(
            original_df
        )
    )

    if (
        total_col
        and
        available_col
    ):

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
# CREATE MAP
# =========================================================

def create_hospital_map(
    map_df
):

    name_col = hospital_name_column(
        map_df
    )

    state_col = state_column(
        map_df
    )

    district_col = district_column(
        map_df
    )

    address_col = address_column(
        map_df
    )

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

    for _, row in map_df.iterrows():

        name = (
            str(row.get(
                name_col,
                "Hospital"
            ))
            if name_col
            else "Hospital"
        )

        state = (
            str(row.get(
                state_col,
                "N/A"
            ))
            if state_col
            else "N/A"
        )

        district = (
            str(row.get(
                district_col,
                "N/A"
            ))
            if district_col
            else "N/A"
        )

        address = (
            str(row.get(
                address_col,
                "N/A"
            ))
            if address_col
            else "N/A"
        )

        total, available = (
            get_bed_values(
                row,
                map_df
            )
        )

        if (
            total is not None
            and
            available is not None
        ):

            status = get_bed_status(
                total,
                available
            )

            if available <= 0:

                marker_color = "red"

            else:

                percentage = (
                    available
                    /
                    total
                    *
                    100
                    if total > 0
                    else 0
                )

                if percentage <= 15:
                    marker_color = "orange"

                elif percentage <= 30:
                    marker_color = "beige"

                else:
                    marker_color = "green"

            bed_text = (
                f"{int(available)} / "
                f"{int(total)}"
            )

        else:

            status = "⚪ Not Available"
            marker_color = "gray"
            bed_text = "Not Available"

        popup_html = f"""
        <div style="
            width:280px;
            font-family:Arial;
        ">

            <h4>
                🏥 {html.escape(name)}
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
            {html.escape(bed_text)}
            <br>

            <b>📊 Status:</b>
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

            tooltip=f"🏥 {name}",

            icon=folium.Icon(
                color=marker_color,
                icon="plus"
            )

        ).add_to(
            hospital_map
        )

    # Legend

    legend = """
    <div style="
        position: fixed;
        bottom: 30px;
        left: 30px;
        z-index: 9999;
        background: white;
        padding: 12px;
        border: 2px solid grey;
        border-radius: 8px;
        font-size: 13px;
    ">

        <b>🛏️ Bed Availability</b>
        <br>

        <span style="color:green;">
            ●
        </span>
        Available
        <br>

        <span style="color:#d97706;">
            ●
        </span>
        Critical
        <br>

        <span style="color:red;">
            ●
        </span>
        Full
        <br>

        <span style="color:gray;">
            ●
        </span>
        Data unavailable

    </div>
    """

    hospital_map.get_root().html.add_child(
        folium.Element(
            legend
        )
    )

    return hospital_map


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title(
    "🏥 Smart Hospital"
)

page = st.sidebar.radio(
    "Navigation",
    [
        "🏠 Home",
        "🏥 Hospital Search",
        "🛏️ Bed Availability",
        "👨‍⚕️ Doctor Availability",
        "🩺 Equipment Availability",
        "📋 Reservation Management",
        "📊 Admin Dashboard",
    ]
)

st.sidebar.markdown("---")

st.sidebar.info(
    "Search hospitals, view the interactive map, "
    "check registered resources and manage reservations."
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

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "🏥 Hospitals",
        f"{len(hospital_df):,}"
    )

    bed_db = get_bed_database()

    if not bed_db.empty:

        _, total_col, available_col = (
            find_bed_columns(
                bed_db
            )
        )

        if (
            total_col
            and
            available_col
        ):

            available = pd.to_numeric(
                bed_db[
                    available_col
                ],
                errors="coerce"
            ).sum()

            c2.metric(
                "🛏️ Available Beds",
                f"{int(available):,}"
            )

        else:

            c2.metric(
                "🛏️ Available Beds",
                "N/A"
            )

    else:

        c2.metric(
            "🛏️ Available Beds",
            "N/A"
        )

    conn = get_connection()

    try:

        doctor_count = pd.read_sql_query(
            """
            SELECT COUNT(*) AS c
            FROM doctors
            """,
            conn
        ).iloc[0]["c"]

    except Exception:

        doctor_count = 0

    conn.close()

    c3.metric(
        "👨‍⚕️ Doctors",
        int(doctor_count)
    )

    st.markdown("---")

    st.info(
        "Use Hospital Search to find hospitals "
        "and view them on the interactive map."
    )


# =========================================================
# HOSPITAL SEARCH
# =========================================================

elif page == "🏥 Hospital Search":

    st.title(
        "🏥 Hospital Search"
    )

    if hospital_df.empty:

        st.error(
            "hospital_directory.csv was not found."
        )

        st.stop()

    # IMPORTANT:
    # Coordinates are prepared for the COMPLETE CSV
    # before search and head().

    (
        full_df,
        coordinate_column,
        latitude_column,
        longitude_column
    ) = prepare_coordinates(
        hospital_df
    )

    # Count valid coordinates

    valid_coordinates = full_df[
        [
            "map_lat",
            "map_lon"
        ]
    ].notna().all(axis=1).sum()

    valid_coordinates = int(
        valid_coordinates
    )

    # Debug section

    with st.expander(
        "🔧 Map Data Check"
    ):

        st.write(
            "Total CSV rows:",
            len(full_df)
        )

        st.write(
            "Valid coordinate rows:",
            valid_coordinates
        )

        st.write(
            "Detected coordinate column:",
            coordinate_column
            or
            "Not found"
        )

        st.write(
            "Detected latitude column:",
            latitude_column
            or
            "Not found"
        )

        st.write(
            "Detected longitude column:",
            longitude_column
            or
            "Not found"
        )

        st.write(
            "CSV columns:",
            list(hospital_df.columns)
        )

    # Search box

    search_text = st.text_input(
        "🔎 Search Hospital / State / District / Pincode",
        placeholder="Example: Kolkata"
    )

    c1, c2 = st.columns(2)

    with c1:

        max_results = st.slider(
            "Maximum search results",
            10,
            500,
            100
        )

    with c2:

        max_markers = st.slider(
            "Maximum map markers",
            20,
            300,
            100
        )

    # Search

    searched_df = search_hospitals(
        full_df,
        search_text
    )

    # Attach database bed data

    results = searched_df.head(
        max_results
    ).copy()

    results = attach_bed_data(
        results
    )

    # =====================================================
    # RESULTS
    # =====================================================

    st.markdown("---")

    st.subheader(
        f"🏥 Hospital Results ({len(results)})"
    )

    if results.empty:

        st.warning(
            "No hospitals found."
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

        for _, row in results.iterrows():

            name = (
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

            total, available = (
                get_bed_values(
                    row,
                    results
                )
            )

            if (
                total is not None
                and
                available is not None
            ):

                bed_text = (
                    f"{int(available)} / "
                    f"{int(total)}"
                )

                status = get_bed_status(
                    total,
                    available
                )

            else:

                bed_text = "Not Available"
                status = "⚪ Not Available"

            with st.expander(
                f"🏥 {name}"
            ):

                a, b, c = st.columns(3)

                a.write(
                    f"**State:** {state}"
                )

                a.write(
                    f"**District:** {district}"
                )

                b.write(
                    f"**Beds:** {bed_text}"
                )

                b.write(
                    f"**Status:** {status}"
                )

                if (
                    pd.notna(
                        row["map_lat"]
                    )
                    and
                    pd.notna(
                        row["map_lon"]
                    )
                ):

                    c.write(
                        "📍 "
                        f"{float(row['map_lat']):.5f}, "
                        f"{float(row['map_lon']):.5f}"
                    )

                else:

                    c.write(
                        "📍 Location unavailable"
                    )

                st.write(
                    f"**Address:** {address}"
                )

    # =====================================================
    # MAP
    # =====================================================

    st.markdown("---")

    st.subheader(
        "📍 Interactive Hospital Map"
    )

    # Take coordinate-valid hospitals
    # AFTER coordinate processing

    map_df = searched_df[
        [
            "map_lat",
            "map_lon"
        ]
    ].dropna()

    # Keep original columns

    map_df = searched_df.dropna(
        subset=[
            "map_lat",
            "map_lon"
        ]
    ).copy()

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

    # Maximum markers

    map_df = map_df.head(
        max_markers
    )

    if map_df.empty:

        if valid_coordinates == 0:

            st.error(
                "❌ No valid latitude/longitude "
                "was found in hospital_directory.csv."
            )

            st.info(
                "The app checked:"
            )

            st.write(
                "• Location_Coordinates"
            )

            st.write(
                "• Latitude + Longitude"
            )

            st.write(
                "Open '🔧 Map Data Check' above "
                "to see the detected columns."
            )

        elif search_text:

            st.warning(
                "Hospitals were found, but the "
                "matching hospitals do not have "
                "valid coordinates."
            )

        else:

            st.warning(
                "No hospital with valid coordinates "
                "is available."
            )

    else:

        st.success(
            f"📍 Showing {len(map_df)} hospital markers."
        )

        hospital_map = create_hospital_map(
            map_df
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
            "No registered bed availability "
            "records are currently available."
        )

    else:

        (
            name_col,
            total_col,
            available_col
        ) = find_bed_columns(
            bed_df
        )

        if not all([
            name_col,
            total_col,
            available_col
        ]):

            st.error(
                "Bed database columns "
                "could not be detected."
            )

        else:

            bed_df[
                "total_beds_numeric"
            ] = pd.to_numeric(
                bed_df[total_col],
                errors="coerce"
            ).fillna(0)

            bed_df[
                "available_beds_numeric"
            ] = pd.to_numeric(
                bed_df[available_col],
                errors="coerce"
            ).fillna(0)

            bed_df[
                "occupied_beds"
            ] = (
                bed_df[
                    "total_beds_numeric"
                ]
                -
                bed_df[
                    "available_beds_numeric"
                ]
            ).clip(
                lower=0
            )

            bed_df[
                "occupancy_percent"
            ] = (
                bed_df[
                    "occupied_beds"
                ]
                /
                bed_df[
                    "total_beds_numeric"
                ].replace(
                    0,
                    pd.NA
                )
                *
                100
            ).fillna(0)

            search = st.text_input(
                "Search hospital"
            )

            if search:

                bed_df = bed_df[
                    bed_df[name_col]
                    .fillna("")
                    .astype(str)
                    .str.contains(
                        search,
                        case=False,
                        regex=False
                    )
                ]

            total = int(
                bed_df[
                    "total_beds_numeric"
                ].sum()
            )

            available = int(
                bed_df[
                    "available_beds_numeric"
                ].sum()
            )

            occupied = int(
                bed_df[
                    "occupied_beds"
                ].sum()
            )

            a, b, c = st.columns(3)

            a.metric(
                "Total Beds",
                total
            )

            b.metric(
                "Available Beds",
                available
            )

            c.metric(
                "Occupied Beds",
                occupied
            )

            display_df = bed_df[
                [
                    name_col,
                    "total_beds_numeric",
                    "available_beds_numeric",
                    "occupied_beds",
                    "occupancy_percent",
                ]
            ].copy()

            display_df.columns = [
                "Hospital",
                "Total Beds",
                "Available Beds",
                "Occupied Beds",
                "Occupancy %",
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

    with tab1:

        conn = get_connection()

        doctors = pd.read_sql_query(
            """
            SELECT *
            FROM doctors
            ORDER BY doctor_name
            """,
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

                filtered = filtered[
                    mask
                ]

            if status_filter != "All":

                filtered = filtered[
                    filtered["status"]
                    ==
                    status_filter
                ]

            st.dataframe(
                filtered[
                    [
                        "id",
                        "doctor_name",
                        "hospital_name",
                        "department",
                        "status",
                        "available_time",
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )

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

                if (
                    not doctor_name
                    or
                    not hospital_name
                ):

                    st.error(
                        "Doctor name and hospital "
                        "name are required."
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
            ORDER BY hospital_name,
                     equipment_name
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

                filtered = filtered[
                    mask
                ]

            filtered["status"] = filtered.apply(
                lambda row:

                "🟢 Available"
                if row[
                    "available_units"
                ] > 2

                else

                "🟡 Low"
                if row[
                    "available_units"
                ] > 0

                else

                "🔴 Unavailable",

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
                    or
                    not equipment_name
                ):

                    st.error(
                        "Hospital and equipment "
                        "name are required."
                    )

                elif (
                    available_units
                    >
                    total_units
                ):

                    st.error(
                        "Available units cannot "
                        "exceed total units."
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
                    or
                    not hospital_name
                ):

                    st.error(
                        "Patient name and hospital "
                        "name are required."
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


# =========================================================
# ADMIN DASHBOARD
# =========================================================

elif page == "📊 Admin Dashboard":

    st.title(
        "📊 Admin Dashboard"
    )

    conn = get_connection()

    def count_table(table):

        try:

            return int(
                pd.read_sql_query(
                    f"""
                    SELECT COUNT(*) AS c
                    FROM {table}
                    """,
                    conn
                ).iloc[0]["c"]
            )

        except Exception:

            return 0

    doctor_count = count_table(
        "doctors"
    )

    equipment_count = count_table(
        "equipment"
    )

    reservation_count = count_table(
        "reservations"
    )

    try:

        pending_count = int(
            pd.read_sql_query(
                """
                SELECT COUNT(*) AS c
                FROM reservations
                WHERE status='Pending'
                """,
                conn
            ).iloc[0]["c"]
        )

    except Exception:

        pending_count = 0

    conn.close()

    a, b, c, d = st.columns(4)

    a.metric(
        "🏥 Hospitals",
        f"{len(hospital_df):,}"
    )

    b.metric(
        "👨‍⚕️ Doctors",
        doctor_count
    )

    c.metric(
        "🩺 Equipment",
        equipment_count
    )

    d.metric(
        "📋 Reservations",
        reservation_count
    )

    st.markdown("---")

    st.subheader(
        "📋 Reservation Status"
    )

    conn = get_connection()

    try:

        status_df = pd.read_sql_query(
            """
            SELECT
                status,
                COUNT(*) AS count
            FROM reservations
            GROUP BY status
            """,
            conn
        )

    except Exception:

        status_df = pd.DataFrame()

    conn.close()

    if status_df.empty:

        st.info(
            "No reservation statistics available."
        )

    else:

        st.dataframe(
            status_df,
            use_container_width=True,
            hide_index=True
        )

    st.metric(
        "⏳ Pending Reservations",
        pending_count
    )

    st.markdown("---")

    st.subheader(
        "ℹ️ System Information"
    )

    st.write(
        "Hospital directory records: "
        f"**{len(hospital_df):,}**"
    )

    st.write(
        "Map uses Location_Coordinates or "
        "Latitude + Longitude when available."
    )

    st.write(
        "Bed availability is not claimed as "
        "real-time unless a live source is connected."
    )


# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.caption(
    "🏥 Smart Hospital Bed Availability System | "
    "Hospital directory + registered resource data | "
    "Prototype/Demo System"
            )
