import streamlit as st
import pandas as pd
import sqlite3
import pathlib
import re
import html
from datetime import datetime

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
DB_DIR.mkdir(exist_ok=True)

DB_PATH = DB_DIR / "hospital.db"


# =========================================================
# DATABASE
# =========================================================

def get_connection():
    return sqlite3.connect(DB_PATH)


def init_database():

    conn = get_connection()
    cur = conn.cursor()

    # ---------------- PATIENTS ----------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT UNIQUE,
            password TEXT,
            email TEXT,
            created_at TEXT
        )
    """)

    # ---------------- ADMINS ----------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    # ---------------- DOCTORS ----------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_name TEXT,
            hospital_name TEXT,
            department TEXT,
            phone TEXT,
            status TEXT,
            available_time TEXT
        )
    """)

    # ---------------- EQUIPMENT ----------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_name TEXT,
            equipment_name TEXT,
            department TEXT,
            total_units INTEGER,
            available_units INTEGER
        )
    """)

    # ---------------- RESERVATIONS ----------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT,
            phone TEXT,
            hospital_name TEXT,
            resource_type TEXT,
            department TEXT,
            doctor_name TEXT,
            equipment_name TEXT,
            reservation_date TEXT,
            reservation_time TEXT,
            notes TEXT,
            status TEXT,
            created_at TEXT
        )
    """)

    # ---------------- UPDATE HISTORY ----------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS update_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT,
            module TEXT,
            details TEXT,
            updated_at TEXT
        )
    """)

    # Default admin
    cur.execute(
        "SELECT COUNT(*) FROM admins"
    )

    admin_count = cur.fetchone()[0]

    if admin_count == 0:

        cur.execute(
            """
            INSERT INTO admins
            (username, password)
            VALUES (?, ?)
            """,
            ("admin", "admin123")
        )

    conn.commit()
    conn.close()


init_database()


# =========================================================
# SESSION STATE
# =========================================================

if "patient_logged_in" not in st.session_state:
    st.session_state.patient_logged_in = False

if "patient_name" not in st.session_state:
    st.session_state.patient_name = ""

if "patient_phone" not in st.session_state:
    st.session_state.patient_phone = ""

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False


# =========================================================
# GENERAL HELPERS
# =========================================================

def clean_text(value):

    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text.lower() in [
        "nan",
        "none",
        "null",
        "na",
        "n/a",
        "-"
    ]:
        return ""

    return text


def normalize_column_name(column):

    return re.sub(
        r"[^a-z0-9]",
        "",
        str(column).lower()
    )


def find_column(dataframe, candidates):

    normalized = {
        normalize_column_name(col): col
        for col in dataframe.columns
    }

    # Exact
    for candidate in candidates:

        key = normalize_column_name(candidate)

        if key in normalized:
            return normalized[key]

    # Partial
    for candidate in candidates:

        key = normalize_column_name(candidate)

        for normalized_name, original_name in normalized.items():

            if (
                key in normalized_name
                or normalized_name in key
            ):
                return original_name

    return None


def safe_number(value):

    try:

        if pd.isna(value):
            return None

        text = str(value).replace(",", "").strip()

        match = re.search(
            r"-?\d+(?:\.\d+)?",
            text
        )

        if match:
            return float(match.group())

    except Exception:
        pass

    return None


def log_update(action, module, details):

    conn = get_connection()

    conn.execute(
        """
        INSERT INTO update_history
        (action, module, details, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            action,
            module,
            details,
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )
    )

    conn.commit()
    conn.close()


# =========================================================
# LOAD HOSPITAL DATA
# =========================================================

@st.cache_data
def load_hospital_data():

    if not CSV_PATH.exists():

        return pd.DataFrame()

    encodings = [
        "utf-8-sig",
        "utf-8",
        "latin1"
    ]

    for encoding in encodings:

        try:

            data = pd.read_csv(
                CSV_PATH,
                encoding=encoding,
                low_memory=False
            )

            data.columns = [
                str(col).strip()
                for col in data.columns
            ]

            for col in data.select_dtypes(
                include=["object"]
            ).columns:

                data[col] = (
                    data[col]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                )

            return data

        except Exception:
            continue

    return pd.DataFrame()


df = load_hospital_data()


# =========================================================
# COLUMN DETECTION
# =========================================================

def get_hospital_column(data):
    return find_column(
        data,
        [
            "hospital_name",
            "hospital name",
            "hospital",
            "name"
        ]
    )


def get_state_column(data):
    return find_column(
        data,
        ["state"]
    )


def get_district_column(data):
    return find_column(
        data,
        ["district"]
    )


def get_subdistrict_column(data):
    return find_column(
        data,
        [
            "subdistrict",
            "sub district",
            "taluk",
            "tehsil"
        ]
    )


def get_address_column(data):
    return find_column(
        data,
        [
            "address_original_first_line",
            "address",
            "hospital_address"
        ]
    )


def get_location_column(data):
    return find_column(
        data,
        ["location"]
    )


def get_pincode_column(data):
    return find_column(
        data,
        [
            "pincode",
            "pin_code",
            "pin"
        ]
    )


def get_phone_column(data):
    return find_column(
        data,
        [
            "telephone",
            "phone",
            "mobile_number",
            "mobile"
        ]
    )


def get_emergency_column(data):
    return find_column(
        data,
        [
            "emergency_num",
            "emergency_number",
            "emergency_phone"
        ]
    )


def get_ambulance_column(data):
    return find_column(
        data,
        [
            "ambulance_phone_no",
            "ambulance_phone",
            "ambulance"
        ]
    )


def get_specialties_column(data):
    return find_column(
        data,
        [
            "specialties",
            "speciality",
            "specialties_available"
        ]
    )


def get_facilities_column(data):
    return find_column(
        data,
        [
            "facilities",
            "facility"
        ]
    )


def get_total_beds_column(data):
    return find_column(
        data,
        [
            "total_num_beds",
            "total_beds",
            "number_of_beds",
            "beds",
            "total bed"
        ]
    )


def get_available_beds_column(data):
    return find_column(
        data,
        [
            "available_beds",
            "available_num_beds",
            "beds_available",
            "current_available_beds"
        ]
    )


def get_doctor_column(data):
    return find_column(
        data,
        [
            "number_doctor",
            "number_of_doctors",
            "doctors"
        ]
    )


def get_emergency_services_column(data):
    return find_column(
        data,
        [
            "emergency_services",
            "emergency service"
        ]
    )


def get_category_column(data):
    return find_column(
        data,
        [
            "hospital_category",
            "category"
        ]
    )


def get_care_type_column(data):
    return find_column(
        data,
        [
            "hospital_care_type",
            "care_type"
        ]
    )


def get_website_column(data):
    return find_column(
        data,
        [
            "website",
            "web_site"
        ]
    )


# =========================================================
# COORDINATES
# =========================================================

def parse_coordinates(value):

    if value is None:
        return None, None

    if pd.isna(value):
        return None, None

    text = str(value).strip()

    if not text:
        return None, None

    text = (
        text
        .replace("°", " ")
        .replace("(", " ")
        .replace(")", " ")
        .replace("[", " ")
        .replace("]", " ")
        .replace(";", ",")
    )

    # Direction based
    pattern = re.findall(
        r"(-?\d+(?:\.\d+)?)\s*([NSWE])?",
        text.upper()
    )

    if len(pattern) >= 2:

        values = []

        for number, direction in pattern:

            try:

                number = float(number)

                if direction in ["S", "W"]:
                    number = -abs(number)

                values.append(
                    (number, direction)
                )

            except Exception:
                pass

        if len(values) >= 2:

            a = values[0][0]
            b = values[1][0]

            if values[0][1] in ["E", "W"]:

                lon = a
                lat = b

                if (
                    -90 <= lat <= 90
                    and -180 <= lon <= 180
                ):
                    return lat, lon

            if values[1][1] in ["E", "W"]:

                lat = a
                lon = b

                if (
                    -90 <= lat <= 90
                    and -180 <= lon <= 180
                ):
                    return lat, lon

    numbers = re.findall(
        r"-?\d+(?:\.\d+)?",
        text
    )

    if len(numbers) < 2:
        return None, None

    try:

        a = float(numbers[0])
        b = float(numbers[1])

        if 6 <= a <= 37 and 68 <= b <= 98:
            return a, b

        if 6 <= b <= 37 and 68 <= a <= 98:
            return b, a

        if -90 <= a <= 90 and -180 <= b <= 180:
            return a, b

        if -90 <= b <= 90 and -180 <= a <= 180:
            return b, a

    except Exception:
        pass

    return None, None


@st.cache_data
def prepare_coordinates(dataframe):

    data = dataframe.copy()

    coordinate_column = find_column(
        data,
        [
            "location_coordinates",
            "location coordinates",
            "coordinates",
            "geo_code",
            "geocode",
            "gps",
            "lat_long",
            "latitude_longitude"
        ]
    )

    latitude_column = find_column(
        data,
        [
            "latitude",
            "lat"
        ]
    )

    longitude_column = find_column(
        data,
        [
            "longitude",
            "lon",
            "lng"
        ]
    )

    data["map_lat"] = pd.NA
    data["map_lon"] = pd.NA

    if coordinate_column:

        parsed = data[
            coordinate_column
        ].apply(parse_coordinates)

        data["map_lat"] = parsed.apply(
            lambda x: x[0]
        )

        data["map_lon"] = parsed.apply(
            lambda x: x[1]
        )

    if latitude_column:

        lat_values = pd.to_numeric(
            data[latitude_column],
            errors="coerce"
        )

        data["map_lat"] = (
            data["map_lat"]
            .fillna(lat_values)
        )

    if longitude_column:

        lon_values = pd.to_numeric(
            data[longitude_column],
            errors="coerce"
        )

        data["map_lon"] = (
            data["map_lon"]
            .fillna(lon_values)
        )

    data["map_lat"] = pd.to_numeric(
        data["map_lat"],
        errors="coerce"
    )

    data["map_lon"] = pd.to_numeric(
        data["map_lon"],
        errors="coerce"
    )

    data.loc[
        ~data["map_lat"].between(-90, 90),
        "map_lat"
    ] = pd.NA

    data.loc[
        ~data["map_lon"].between(-180, 180),
        "map_lon"
    ] = pd.NA

    return (
        data,
        coordinate_column,
        latitude_column,
        longitude_column
    )


# =========================================================
# SEARCH INDEX
# =========================================================

def create_search_index(data):

    data = data.copy()

    columns = [
        get_hospital_column(data),
        get_state_column(data),
        get_district_column(data),
        get_subdistrict_column(data),
        get_address_column(data),
        get_location_column(data),
        get_pincode_column(data)
    ]

    columns = [
        col for col in columns
        if col is not None
    ]

    if columns:

        data["_search_index"] = (
            data[columns]
            .fillna("")
            .astype(str)
            .agg(" ".join, axis=1)
            .str.lower()
        )

    else:

        data["_search_index"] = ""

    return data


df = create_search_index(df)


def search_hospitals(data, search_text):

    if not search_text.strip():
        return data.copy()

    query = search_text.strip().lower()

    return data[
        data["_search_index"].str.contains(
            query,
            regex=False,
            na=False
        )
    ].copy()


# =========================================================
# BED HELPERS
# =========================================================

def get_bed_values(row, source_df=None):

    if source_df is None:
        source_df = df

    total_col = get_total_beds_column(
        source_df
    )

    available_col = get_available_beds_column(
        source_df
    )

    total = None
    available = None

    if total_col:
        total = safe_number(
            row.get(total_col)
        )

    if available_col:
        available = safe_number(
            row.get(available_col)
        )

    return total, available


def get_bed_status(total, available):

    if available is None:
        return "Current availability not provided"

    if available <= 0:
        return "Full"

    if total is None or total <= 0:
        return "Available"

    percentage = (
        available / total
    ) * 100

    if percentage <= 10:
        return "Critical"

    if percentage <= 30:
        return "Low"

    return "Available"


def format_bed_value(value):

    if value is None:
        return "Not provided"

    if float(value).is_integer():
        return str(int(value))

    return str(round(value, 2))


# =========================================================
# HOSPITAL DETAILS
# =========================================================

def hospital_details(row, source_df):

    name_col = get_hospital_column(source_df)
    state_col = get_state_column(source_df)
    district_col = get_district_column(source_df)
    subdistrict_col = get_subdistrict_column(source_df)
    address_col = get_address_column(source_df)
    pincode_col = get_pincode_column(source_df)
    phone_col = get_phone_column(source_df)
    emergency_col = get_emergency_column(source_df)
    ambulance_col = get_ambulance_column(source_df)
    specialties_col = get_specialties_column(source_df)
    facilities_col = get_facilities_column(source_df)
    category_col = get_category_column(source_df)
    care_type_col = get_care_type_column(source_df)
    emergency_services_col = get_emergency_services_column(source_df)
    website_col = get_website_column(source_df)

    total_beds, available_beds = get_bed_values(
        row,
        source_df
    )

    name = (
        row.get(name_col)
        if name_col
        else "Unknown Hospital"
    )

    st.markdown(
        f"### 🏥 {clean_text(name)}"
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.write(
            "**State:** "
            + (
                clean_text(row.get(state_col))
                if state_col
                else "Not provided"
            )
        )

        st.write(
            "**District:** "
            + (
                clean_text(row.get(district_col))
                if district_col
                else "Not provided"
            )
        )

        st.write(
            "**Subdistrict:** "
            + (
                clean_text(row.get(subdistrict_col))
                if subdistrict_col
                else "Not provided"
            )
        )

    with c2:

        st.write(
            "**Category:** "
            + (
                clean_text(row.get(category_col))
                if category_col
                else "Not provided"
            )
        )

        st.write(
            "**Care Type:** "
            + (
                clean_text(row.get(care_type_col))
                if care_type_col
                else "Not provided"
            )
        )

        st.write(
            "**Emergency Services:** "
            + (
                clean_text(row.get(emergency_services_col))
                if emergency_services_col
                else "Not provided"
            )
        )

    with c3:

        st.write(
            f"**Total Beds:** "
            f"{format_bed_value(total_beds)}"
        )

        st.write(
            f"**Available Beds:** "
            f"{format_bed_value(available_beds)}"
        )

    st.markdown("---")

    st.write(
        "📍 **Address:** "
        + (
            clean_text(row.get(address_col))
            if address_col
            else "Not provided"
        )
    )

    st.write(
        "📮 **Pincode:** "
        + (
            clean_text(row.get(pincode_col))
            if pincode_col
            else "Not provided"
        )
    )

    st.write(
        "☎️ **Phone:** "
        + (
            clean_text(row.get(phone_col))
            if phone_col
            else "Not provided"
        )
    )

    st.write(
        "🚨 **Emergency Number:** "
        + (
            clean_text(row.get(emergency_col))
            if emergency_col
            else "Not provided"
        )
    )

    st.write(
        "🚑 **Ambulance:** "
        + (
            clean_text(row.get(ambulance_col))
            if ambulance_col
            else "Not provided"
        )
    )

    st.write(
        "🩺 **Specialties:** "
        + (
            clean_text(row.get(specialties_col))
            if specialties_col
            else "Not provided"
        )
    )

    st.write(
        "🛠️ **Facilities:** "
        + (
            clean_text(row.get(facilities_col))
            if facilities_col
            else "Not provided"
        )
    )

    if website_col:

        website = clean_text(
            row.get(website_col)
        )

        if website:

            if not website.startswith(
                ("http://", "https://")
            ):
                website = "https://" + website

            st.markdown(
                f"🌐 **Website:** [{website}]({website})"
            )


# =========================================================
# MAP
# =========================================================

def create_hospital_map(
    map_df,
    source_df,
    max_markers=100
):

    if map_df.empty:
        return None

    map_df = map_df.head(
        max_markers
    ).copy()

    valid = map_df[
        map_df["map_lat"].notna()
        & map_df["map_lon"].notna()
    ]

    if valid.empty:
        return None

    center_lat = valid["map_lat"].mean()
    center_lon = valid["map_lon"].mean()

    m = folium.Map(
        location=[
            center_lat,
            center_lon
        ],
        zoom_start=11,
        control_scale=True
    )

    name_col = get_hospital_column(
        source_df
    )

    state_col = get_state_column(
        source_df
    )

    district_col = get_district_column(
        source_df
    )

    address_col = get_address_column(
        source_df
    )

    for _, row in valid.iterrows():

        lat = row["map_lat"]
        lon = row["map_lon"]

        hospital_name = (
            clean_text(row.get(name_col))
            if name_col
            else "Hospital"
        )

        state = (
            clean_text(row.get(state_col))
            if state_col
            else "Not provided"
        )

        district = (
            clean_text(row.get(district_col))
            if district_col
            else "Not provided"
        )

        address = (
            clean_text(row.get(address_col))
            if address_col
            else "Not provided"
        )

        total, available = get_bed_values(
            row,
            source_df
        )

        status = get_bed_status(
            total,
            available
        )

        if status == "Full":
            marker_color = "red"
        elif status in ["Critical", "Low"]:
            marker_color = "orange"
        else:
            marker_color = "blue"

        popup_html = f"""
        <div style="width:320px">

        <h4>🏥 {html.escape(hospital_name)}</h4>

        <b>State:</b>
        {html.escape(state)}<br>

        <b>District:</b>
        {html.escape(district)}<br><br>

        <b>Address:</b><br>
        {html.escape(address)}<br><br>

        <b>Total Beds:</b>
        {html.escape(format_bed_value(total))}<br>

        <b>Available Beds:</b>
        {html.escape(format_bed_value(available))}<br>

        <b>Status:</b>
        {html.escape(status)}

        </div>
        """

        folium.Marker(
            location=[lat, lon],
            tooltip=hospital_name[:80],
            popup=folium.Popup(
                popup_html,
                max_width=350
            ),
            icon=folium.Icon(
                color=marker_color,
                icon="plus-sign",
                prefix="glyphicon"
            )
        ).add_to(m)

    return m


# =========================================================
# SIDEBAR NAVIGATION
# =========================================================

st.sidebar.title(
    "🏥 Hospital System"
)

st.sidebar.caption(
    "Smart Hospital Resource Platform"
)

menu = st.sidebar.radio(
    "Navigate",
    [
        "🏠 Home",
        "🔎 Hospital Search",
        "🚨 Emergency Search",
        "🛏️ Bed Availability",
        "👨‍⚕️ Doctor Availability",
        "🛠️ Equipment Availability",
        "📋 Reservation Management",
        "👤 Patient Login",
        "📝 Patient Registration",
        "🧑‍⚕️ Patient Dashboard",
        "🏥 Hospital Management",
        "🛏️ Bed Management",
        "📊 Analytics",
        "📜 Update History",
        "🔐 Admin Login",
        "📊 Admin Dashboard"
    ]
)

st.sidebar.markdown("---")

st.sidebar.info(
    "Prototype / Academic Demo\n\n"
    "Hospital directory data may not represent "
    "real-time availability."
)


# =========================================================
# HOME
# =========================================================

if menu == "🏠 Home":

    st.title(
        "🏥 Smart Hospital Bed Availability System"
    )

    st.subheader(
        "Find hospitals, resources and emergency information."
    )

    if df.empty:

        st.error(
            "hospital_directory.csv পাওয়া যায়নি."
        )
        st.stop()

    prepared_df, coord_col, lat_col, lon_col = (
        prepare_coordinates(df)
    )

    total_hospitals = len(
        prepared_df
    )

    mapped = int(
        prepared_df["map_lat"].notna().sum()
    )

    total_beds_col = get_total_beds_column(
        prepared_df
    )

    if total_beds_col:

        total_beds = pd.to_numeric(
            prepared_df[total_beds_col],
            errors="coerce"
        ).sum()

    else:

        total_beds = 0

    doctors_col = get_doctor_column(
        prepared_df
    )

    if doctors_col:

        total_doctors = pd.to_numeric(
            prepared_df[doctors_col],
            errors="coerce"
        ).sum()

    else:

        total_doctors = 0

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "🏥 Hospitals",
        f"{total_hospitals:,}"
    )

    c2.metric(
        "📍 Mapped Hospitals",
        f"{mapped:,}"
    )

    c3.metric(
        "🛏️ Listed Beds",
        f"{int(total_beds):,}"
    )

    c4.metric(
        "👨‍⚕️ Listed Doctors",
        f"{int(total_doctors):,}"
    )

    st.markdown("---")

    st.info(
        "ℹ️ Listed bed capacity is not the same as "
        "real-time available beds."
    )

    st.subheader(
        "📍 Interactive Hospital Map"
    )

    map_df = prepared_df[
        prepared_df["map_lat"].notna()
        & prepared_df["map_lon"].notna()
    ].head(100)

    hospital_map = create_hospital_map(
        map_df,
        prepared_df,
        100
    )

    if hospital_map:

        st_folium(
            hospital_map,
            width=None,
            height=600
        )

    else:

        st.warning(
            "No valid hospital coordinates found."
        )


# =========================================================
# HOSPITAL SEARCH
# =========================================================

elif menu == "🔎 Hospital Search":

    st.title(
        "🔎 Hospital Search"
    )

    prepared_df, coord_col, lat_col, lon_col = (
        prepare_coordinates(df)
    )

    search = st.text_input(
        "Search Hospital / City / State / District / Pincode",
        placeholder="Example: Kolkata"
    )

    max_results = st.slider(
        "Maximum results",
        10,
        500,
        100
    )

    results = search_hospitals(
        prepared_df,
        search
    ).head(max_results)

    st.success(
        f"Found {len(results):,} hospital record(s)"
    )

    with st.expander(
        "🔧 Dataset / Coordinate Information"
    ):

        st.write(
            f"Total records: {len(prepared_df):,}"
        )

        st.write(
            f"Valid coordinates: "
            f"{prepared_df['map_lat'].notna().sum():,}"
        )

        st.write(
            f"Coordinate column: "
            f"{coord_col or 'Not found'}"
        )

        st.write(
            f"Latitude column: "
            f"{lat_col or 'Not found'}"
        )

        st.write(
            f"Longitude column: "
            f"{lon_col or 'Not found'}"
        )

    name_col = get_hospital_column(
        results
    )

    if results.empty:

        st.warning(
            "No hospital found."
        )

    else:

        for _, row in results.iterrows():

            name = (
                row.get(name_col)
                if name_col
                else "Hospital"
            )

            with st.expander(
                f"🏥 {clean_text(name)}"
            ):

                hospital_details(
                    row,
                    prepared_df
                )

        mapped = results[
            results["map_lat"].notna()
            & results["map_lon"].notna()
        ]

        st.subheader(
            "🗺️ Interactive Hospital Map"
        )

        hospital_map = create_hospital_map(
            mapped,
            prepared_df,
            100
        )

        if hospital_map:

            st_folium(
                hospital_map,
                width=None,
                height=600
            )


# =========================================================
# EMERGENCY SEARCH
# =========================================================

elif menu == "🚨 Emergency Search":

    st.title(
        "🚨 Emergency Hospital Search"
    )

    st.warning(
        "Academic prototype. This does not guarantee "
        "real-time admission or bed availability."
    )

    prepared_df, _, _, _ = (
        prepare_coordinates(df)
    )

    specialty_col = get_specialties_column(
        prepared_df
    )

    emergency_col = get_emergency_services_column(
        prepared_df
    )

    ambulance_col = get_ambulance_column(
        prepared_df
    )

    total_beds_col = get_total_beds_column(
        prepared_df
    )

    location = st.text_input(
        "📍 Location / Hospital / District",
        placeholder="Example: Kolkata"
    )

    specialty = st.text_input(
        "🩺 Required Specialty",
        placeholder="Example: Cardiology"
    )

    c1, c2 = st.columns(2)

    with c1:

        require_emergency = st.checkbox(
            "🚨 Emergency information available"
        )

    with c2:

        require_ambulance = st.checkbox(
            "🚑 Ambulance information available"
        )

    minimum_beds = st.number_input(
        "Minimum listed beds",
        min_value=0,
        value=0,
        step=10
    )

    results = prepared_df.copy()

    if location.strip():

        results = search_hospitals(
            results,
            location
        )

    if (
        specialty.strip()
        and specialty_col
    ):

        results = results[
            results[specialty_col]
            .fillna("")
            .astype(str)
            .str.contains(
                specialty,
                case=False,
                regex=False
            )
        ]

    if (
        require_emergency
        and emergency_col
    ):

        results = results[
            results[emergency_col]
            .fillna("")
            .astype(str)
            .str.strip()
            .ne("")
        ]

    if (
        require_ambulance
        and ambulance_col
    ):

        results = results[
            results[ambulance_col]
            .fillna("")
            .astype(str)
            .str.strip()
            .ne("")
        ]

    if (
        minimum_beds > 0
        and total_beds_col
    ):

        beds = pd.to_numeric(
            results[total_beds_col],
            errors="coerce"
        ).fillna(0)

        results = results[
            beds >= minimum_beds
        ]

    results = results.head(200)

    st.success(
        f"Found {len(results):,} hospital(s)"
    )

    name_col = get_hospital_column(
        prepared_df
    )

    for _, row in results.iterrows():

        name = (
            row.get(name_col)
            if name_col
            else "Hospital"
        )

        st.markdown(
            f"### 🏥 {clean_text(name)}"
        )

        total, available = get_bed_values(
            row,
            prepared_df
        )

        c1, c2, c3 = st.columns(3)

        c1.write(
            f"**Total Beds:** "
            f"{format_bed_value(total)}"
        )

        c2.write(
            f"**Available:** "
            f"{format_bed_value(available)}"
        )

        c3.write(
            f"**Status:** "
            f"{get_bed_status(total, available)}"
        )

        if specialty_col:

            st.write(
                "🩺 **Specialties:** "
                + clean_text(
                    row.get(specialty_col)
                )
            )

        st.markdown("---")


# =========================================================
# BED AVAILABILITY
# =========================================================

elif menu == "🛏️ Bed Availability":

    st.title(
        "🛏️ Bed Availability"
    )

    prepared_df, _, _, _ = (
        prepare_coordinates(df)
    )

    search = st.text_input(
        "Search hospital / city / district",
        placeholder="Example: Kolkata"
    )

    results = search_hospitals(
        prepared_df,
        search
    ).head(200)

    total_col = get_total_beds_column(
        prepared_df
    )

    if total_col:

        total_beds = pd.to_numeric(
            results[total_col],
            errors="coerce"
        ).fillna(0).sum()

    else:

        total_beds = 0

    c1, c2 = st.columns(2)

    c1.metric(
        "Hospitals",
        len(results)
    )

    c2.metric(
        "Listed Total Beds",
        f"{int(total_beds):,}"
    )

    name_col = get_hospital_column(
        prepared_df
    )

    st.markdown("---")

    for _, row in results.iterrows():

        name = (
            row.get(name_col)
            if name_col
            else "Hospital"
        )

        total, available = get_bed_values(
            row,
            prepared_df
        )

        status = get_bed_status(
            total,
            available
        )

        st.markdown(
            f"### 🏥 {clean_text(name)}"
        )

        c1, c2, c3 = st.columns(3)

        c1.write(
            f"**Total:** "
            f"{format_bed_value(total)}"
        )

        c2.write(
            f"**Available:** "
            f"{format_bed_value(available)}"
        )

        c3.write(
            f"**Status:** {status}"
        )

        st.markdown("---")


# =========================================================
# DOCTOR AVAILABILITY
# =========================================================

elif menu == "👨‍⚕️ Doctor Availability":

    st.title(
        "👨‍⚕️ Doctor Availability"
    )

    conn = get_connection()

    doctors = pd.read_sql_query(
        "SELECT * FROM doctors ORDER BY id DESC",
        conn
    )

    conn.close()

    if not doctors.empty:

        st.dataframe(
            doctors,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "No doctor records added yet."
        )

    st.markdown("---")

    st.subheader(
        "➕ Add Doctor"
    )

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
                "Unavailable"
            ]
        )

        available_time = st.text_input(
            "Available Time"
        )

        submitted = st.form_submit_button(
            "Add Doctor"
        )

        if submitted:

            if not doctor_name or not hospital_name:

                st.error(
                    "Doctor Name and Hospital Name required."
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

                log_update(
                    "CREATE",
                    "Doctor",
                    f"Added doctor: {doctor_name}"
                )

                st.success(
                    "Doctor added successfully."
                )

                st.rerun()


# =========================================================
# EQUIPMENT
# =========================================================

elif menu == "🛠️ Equipment Availability":

    st.title(
        "🛠️ Equipment Availability"
    )

    conn = get_connection()

    equipment = pd.read_sql_query(
        "SELECT * FROM equipment ORDER BY id DESC",
        conn
    )

    conn.close()

    if not equipment.empty:

        st.dataframe(
            equipment,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "No equipment records yet."
        )

    st.markdown("---")

    st.subheader(
        "➕ Add Equipment"
    )

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
            "Add Equipment"
        )

        if submitted:

            if (
                available_units
                > total_units
            ):

                st.error(
                    "Available units cannot exceed total units."
                )

            elif not hospital_name or not equipment_name:

                st.error(
                    "Hospital and Equipment are required."
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

                log_update(
                    "CREATE",
                    "Equipment",
                    f"Added equipment: {equipment_name}"
                )

                st.success(
                    "Equipment added successfully."
                )

                st.rerun()


# =========================================================
# RESERVATION MANAGEMENT
# =========================================================

elif menu == "📋 Reservation Management":

    st.title(
        "📋 Reservation Management"
    )

    conn = get_connection()

    reservations = pd.read_sql_query(
        """
        SELECT *
        FROM reservations
        ORDER BY id DESC
        """,
        conn
    )

    conn.close()

    if not reservations.empty:

        st.dataframe(
            reservations,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "No reservations yet."
        )

    st.markdown("---")

    st.subheader(
        "➕ Create Reservation"
    )

    with st.form(
        "reservation_form"
    ):

        patient_name = st.text_input(
            "Patient Name"
        )

        phone = st.text_input(
            "Phone"
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
            "Reservation Date"
        )

        reservation_time = st.text_input(
            "Reservation Time"
        )

        notes = st.text_area(
            "Notes"
        )

        submitted = st.form_submit_button(
            "Create Reservation"
        )

        if submitted:

            if not patient_name or not hospital_name:

                st.error(
                    "Patient Name and Hospital Name required."
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
                        status,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        reservation_time,
                        notes,
                        "Pending",
                        datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    )
                )

                conn.commit()
                conn.close()

                log_update(
                    "CREATE",
                    "Reservation",
                    f"Reservation by {patient_name}"
                )

                st.success(
                    "Reservation created successfully."
                )

                st.rerun()


# =========================================================
# PATIENT REGISTRATION
# =========================================================

elif menu == "📝 Patient Registration":

    st.title(
        "📝 Patient Registration"
    )

    with st.form(
        "patient_registration"
    ):

        name = st.text_input(
            "Full Name"
        )

        phone = st.text_input(
            "Phone Number"
        )

        email = st.text_input(
            "Email"
        )

        password = st.text_input(
            "Password",
            type="password"
        )

        confirm = st.text_input(
            "Confirm Password",
            type="password"
        )

        submitted = st.form_submit_button(
            "Register"
        )

        if submitted:

            if not name or not phone or not password:

                st.error(
                    "Name, phone and password are required."
                )

            elif password != confirm:

                st.error(
                    "Passwords do not match."
                )

            else:

                try:

                    conn = get_connection()

                    conn.execute(
                        """
                        INSERT INTO patients
                        (
                            name,
                            phone,
                            password,
                            email,
                            created_at
                        )
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            name,
                            phone,
                            password,
                            email,
                            datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                        )
                    )

                    conn.commit()
                    conn.close()

                    st.success(
                        "Registration successful. "
                        "Now login."
                    )

                except sqlite3.IntegrityError:

                    st.error(
                        "This phone number is already registered."
                    )


# =========================================================
# PATIENT LOGIN
# =========================================================

elif menu == "👤 Patient Login":

    st.title(
        "👤 Patient Login"
    )

    if st.session_state.patient_logged_in:

        st.success(
            f"Logged in as "
            f"{st.session_state.patient_name}"
        )

        if st.button(
            "Logout"
        ):

            st.session_state.patient_logged_in = False
            st.session_state.patient_name = ""
            st.session_state.patient_phone = ""

            st.rerun()

    else:

        with st.form(
            "patient_login"
        ):

            phone = st.text_input(
                "Phone"
            )

            password = st.text_input(
                "Password",
                type="password"
            )

            submitted = st.form_submit_button(
                "Login"
            )

            if submitted:

                conn = get_connection()

                user = pd.read_sql_query(
                    """
                    SELECT *
                    FROM patients
                    WHERE phone = ?
                    AND password = ?
                    """,
                    conn,
                    params=(
                        phone,
                        password
                    )
                )

                conn.close()

                if not user.empty:

                    st.session_state.patient_logged_in = True

                    st.session_state.patient_name = (
                        user.iloc[0]["name"]
                    )

                    st.session_state.patient_phone = (
                        user.iloc[0]["phone"]
                    )

                    st.success(
                        "Login successful."
                    )

                    st.rerun()

                else:

                    st.error(
                        "Invalid phone or password."
                    )


# =========================================================
# PATIENT DASHBOARD
# =========================================================

elif menu == "🧑‍⚕️ Patient Dashboard":

    st.title(
        "🧑‍⚕️ Patient Dashboard"
    )

    if not st.session_state.patient_logged_in:

        st.warning(
            "Please login first from Patient Login."
        )

    else:

        st.success(
            f"Welcome, "
            f"{st.session_state.patient_name}"
        )

        conn = get_connection()

        reservations = pd.read_sql_query(
            """
            SELECT *
            FROM reservations
            WHERE phone = ?
            ORDER BY id DESC
            """,
            conn,
            params=(
                st.session_state.patient_phone,
            )
        )

        conn.close()

        st.subheader(
            "📋 My Reservations"
        )

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


# =========================================================
# HOSPITAL MANAGEMENT
# =========================================================

elif menu == "🏥 Hospital Management":

    st.title(
        "🏥 Hospital Management"
    )

    if df.empty:

        st.error(
            "Hospital CSV not found."
        )

    else:

        prepared_df, _, _, _ = (
            prepare_coordinates(df)
        )

        st.metric(
            "Total Hospitals",
            f"{len(prepared_df):,}"
        )

        search = st.text_input(
            "Search Hospital"
        )

        results = search_hospitals(
            prepared_df,
            search
        ).head(100)

        name_col = get_hospital_column(
            prepared_df
        )

        if name_col:

            display_columns = [
                col for col in [
                    name_col,
                    get_state_column(prepared_df),
                    get_district_column(prepared_df),
                    get_phone_column(prepared_df),
                    get_total_beds_column(prepared_df)
                ]
                if col
            ]

            st.dataframe(
                results[display_columns],
                use_container_width=True,
                hide_index=True
            )


# =========================================================
# BED MANAGEMENT
# =========================================================

elif menu == "🛏️ Bed Management":

    st.title(
        "🛏️ Bed Management"
    )

    st.info(
        "Official hospital CSV provides listed bed capacity. "
        "This section manages local prototype bed data."
    )

    conn = get_connection()

    reservations = pd.read_sql_query(
        """
        SELECT *
        FROM reservations
        WHERE resource_type = 'Bed'
        ORDER BY id DESC
        """,
        conn
    )

    conn.close()

    if reservations.empty:

        st.info(
            "No bed reservations yet."
        )

    else:

        st.dataframe(
            reservations,
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# ANALYTICS
# =========================================================

elif menu == "📊 Analytics":

    st.title(
        "📊 Hospital System Analytics"
    )

    if df.empty:

        st.error(
            "Hospital dataset not found."
        )

    else:

        prepared_df, _, _, _ = (
            prepare_coordinates(df)
        )

        state_col = get_state_column(
            prepared_df
        )

        total_col = get_total_beds_column(
            prepared_df
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Hospitals",
            f"{len(prepared_df):,}"
        )

        c2.metric(
            "Mapped",
            f"{prepared_df['map_lat'].notna().sum():,}"
        )

        if total_col:

            total = pd.to_numeric(
                prepared_df[total_col],
                errors="coerce"
            ).sum()

        else:

            total = 0

        c3.metric(
            "Listed Beds",
            f"{int(total):,}"
        )

        st.markdown("---")

        if state_col:

            state_counts = (
                prepared_df[state_col]
                .replace("", pd.NA)
                .dropna()
                .value_counts()
                .head(20)
            )

            st.subheader(
                "🏛️ Hospitals by State"
            )

            st.bar_chart(
                state_counts
            )

        st.subheader(
            "📋 Dataset Preview"
        )

        st.dataframe(
            prepared_df.head(100),
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# UPDATE HISTORY
# =========================================================

elif menu == "📜 Update History":

    st.title(
        "📜 Update History"
    )

    conn = get_connection()

    history = pd.read_sql_query(
        """
        SELECT *
        FROM update_history
        ORDER BY id DESC
        """,
        conn
    )

    conn.close()

    if history.empty:

        st.info(
            "No update history yet."
        )

    else:

        st.dataframe(
            history,
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# ADMIN LOGIN
# =========================================================

elif menu == "🔐 Admin Login":

    st.title(
        "🔐 Admin Login"
    )

    if st.session_state.admin_logged_in:

        st.success(
            "Admin is already logged in."
        )

        if st.button(
            "Logout Admin"
        ):

            st.session_state.admin_logged_in = False

            st.rerun()

    else:

        with st.form(
            "admin_login"
        ):

            username = st.text_input(
                "Username"
            )

            password = st.text_input(
                "Password",
                type="password"
            )

            submitted = st.form_submit_button(
                "Login"
            )

            if submitted:

                conn = get_connection()

                admin = pd.read_sql_query(
                    """
                    SELECT *
                    FROM admins
                    WHERE username = ?
                    AND password = ?
                    """,
                    conn,
                    params=(
                        username,
                        password
                    )
                )

                conn.close()

                if not admin.empty:

                    st.session_state.admin_logged_in = True

                    st.success(
                        "Admin login successful."
                    )

                    st.rerun()

                else:

                    st.error(
                        "Invalid admin credentials."
                    )

        st.info(
            "Demo credentials:\n\n"
            "Username: `admin`\n\n"
            "Password: `admin123`"
        )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

elif menu == "📊 Admin Dashboard":

    st.title(
        "📊 Admin Dashboard"
    )

    if not st.session_state.admin_logged_in:

        st.warning(
            "Please login through Admin Login first."
        )

    else:

        conn = get_connection()

        doctor_count = pd.read_sql_query(
            """
            SELECT COUNT(*) AS count
            FROM doctors
            """,
            conn
        )["count"][0]

        equipment_count = pd.read_sql_query(
            """
            SELECT COUNT(*) AS count
            FROM equipment
            """,
            conn
        )["count"][0]

        reservation_count = pd.read_sql_query(
            """
            SELECT COUNT(*) AS count
            FROM reservations
            """,
            conn
        )["count"][0]

        pending_count = pd.read_sql_query(
            """
            SELECT COUNT(*) AS count
            FROM reservations
            WHERE status = 'Pending'
            """,
            conn
        )["count"][0]

        patient_count = pd.read_sql_query(
            """
            SELECT COUNT(*) AS count
            FROM patients
            """,
            conn
        )["count"][0]

        conn.close()

        prepared_df, coord_col, lat_col, lon_col = (
            prepare_coordinates(df)
        )

        c1, c2, c3, c4, c5 = st.columns(5)

        c1.metric(
            "🏥 Hospitals",
            f"{len(prepared_df):,}"
        )

        c2.metric(
            "👨‍⚕️ Doctors",
            doctor_count
        )

        c3.metric(
            "🛠️ Equipment",
            equipment_count
        )

        c4.metric(
            "📋 Reservations",
            reservation_count
        )

        c5.metric(
            "👤 Patients",
            patient_count
        )

        st.markdown("---")

        st.subheader(
            "⏳ Pending Reservations"
        )

        st.metric(
            "Pending",
            pending_count
        )

        st.markdown("---")

        st.subheader(
            "📍 Dataset Information"
        )

        st.write(
            f"**CSV:** `{CSV_PATH.name}`"
        )

        st.write(
            f"**Hospital records:** "
            f"{len(prepared_df):,}"
        )

        st.write(
            f"**Records with coordinates:** "
            f"{prepared_df['map_lat'].notna().sum():,}"
        )

        st.write(
            f"**Coordinate column:** "
            f"{coord_col or 'Not found'}"
        )

        st.write(
            f"**Latitude:** "
            f"{lat_col or 'Not found'}"
        )

        st.write(
            f"**Longitude:** "
            f"{lon_col or 'Not found'}"
        )

        st.markdown("---")

        st.subheader(
            "📋 Recent Reservations"
        )

        conn = get_connection()

        recent = pd.read_sql_query(
            """
            SELECT *
            FROM reservations
            ORDER BY id DESC
            LIMIT 20
            """,
            conn
        )

        conn.close()

        if not recent.empty:

            st.dataframe(
                recent,
                use_container_width=True,
                hide_index=True
            )

        st.info(
            "⚠️ Hospital directory data should not be "
            "interpreted as live availability."
        )


# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.caption(
    "🏥 Smart Hospital Bed Availability System | "
    "Prototype / Academic Demo"
    )
