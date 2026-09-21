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
    layout="wide"
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

def init_database():

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Doctors
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

    # Equipment
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

    # Reservations
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

    conn.commit()
    conn.close()


init_database()


# =========================================================
# GENERAL HELPERS
# =========================================================

def clean_text(value):
    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text.lower() in ["nan", "none", "null", "na", "n/a", "-"]:
        return ""

    return text


def normalize_column_name(column):
    return re.sub(r"[^a-z0-9]", "", str(column).lower())


def find_column(df, candidates):

    normalized = {
        normalize_column_name(col): col
        for col in df.columns
    }

    # Exact normalized match
    for candidate in candidates:

        key = normalize_column_name(candidate)

        if key in normalized:
            return normalized[key]

    # Partial match
    for candidate in candidates:

        key = normalize_column_name(candidate)

        for normalized_name, original_name in normalized.items():

            if key in normalized_name or normalized_name in key:
                return original_name

    return None


def safe_number(value):

    try:

        if pd.isna(value):
            return None

        text = str(value).replace(",", "").strip()

        match = re.search(r"-?\d+(?:\.\d+)?", text)

        if match:
            return float(match.group())

    except Exception:
        pass

    return None


# =========================================================
# LOAD OFFICIAL HOSPITAL CSV
# =========================================================

@st.cache_data
def load_hospital_data():

    if not CSV_PATH.exists():

        st.error(
            "❌ hospital_directory.csv পাওয়া যায়নি। "
            "app.py-এর একই folder-এ CSV file রাখুন।"
        )

        return pd.DataFrame()

    encodings = [
        "utf-8-sig",
        "utf-8",
        "latin1"
    ]

    for encoding in encodings:

        try:

            df = pd.read_csv(
                CSV_PATH,
                encoding=encoding,
                low_memory=False
            )

            break

        except Exception:
            df = None

    if df is None:

        st.error("❌ CSV file read করা যাচ্ছে না।")
        return pd.DataFrame()

    # Column names clean
    df.columns = [
        str(col).strip()
        for col in df.columns
    ]

    # Clean string columns
    for col in df.select_dtypes(include=["object"]).columns:

        df[col] = df[col].fillna("").astype(str).str.strip()

    return df


df = load_hospital_data()


# =========================================================
# OFFICIAL DATASET COLUMN DETECTION
# =========================================================

def get_hospital_column(df):

    return find_column(
        df,
        [
            "hospital_name",
            "hospital name",
            "hospital",
            "name"
        ]
    )


def get_state_column(df):

    return find_column(
        df,
        [
            "state"
        ]
    )


def get_district_column(df):

    return find_column(
        df,
        [
            "district"
        ]
    )


def get_subdistrict_column(df):

    return find_column(
        df,
        [
            "subdistrict",
            "sub district",
            "taluk",
            "tehsil"
        ]
    )


def get_address_column(df):

    return find_column(
        df,
        [
            "address_original_first_line",
            "address",
            "hospital_address"
        ]
    )


def get_location_column(df):

    return find_column(
        df,
        [
            "location"
        ]
    )


def get_pincode_column(df):

    return find_column(
        df,
        [
            "pincode",
            "pin_code",
            "pin"
        ]
    )


def get_phone_column(df):

    return find_column(
        df,
        [
            "telephone",
            "phone",
            "mobile_number",
            "mobile"
        ]
    )


def get_emergency_column(df):

    return find_column(
        df,
        [
            "emergency_num",
            "emergency_number",
            "emergency_phone"
        ]
    )


def get_ambulance_column(df):

    return find_column(
        df,
        [
            "ambulance_phone_no",
            "ambulance_phone",
            "ambulance"
        ]
    )


def get_specialties_column(df):

    return find_column(
        df,
        [
            "specialties",
            "speciality",
            "specialties_available"
        ]
    )


def get_facilities_column(df):

    return find_column(
        df,
        [
            "facilities",
            "facility"
        ]
    )


def get_total_beds_column(df):

    return find_column(
        df,
        [
            "total_num_beds",
            "total_beds",
            "number_of_beds",
            "beds",
            "total bed"
        ]
    )


def get_available_beds_column(df):

    return find_column(
        df,
        [
            "available_beds",
            "available_num_beds",
            "beds_available",
            "current_available_beds"
        ]
    )


def get_doctor_column(df):

    return find_column(
        df,
        [
            "number_doctor",
            "number_of_doctors",
            "doctors"
        ]
    )


def get_emergency_services_column(df):

    return find_column(
        df,
        [
            "emergency_services",
            "emergency service"
        ]
    )


def get_category_column(df):

    return find_column(
        df,
        [
            "hospital_category",
            "category"
        ]
    )


def get_care_type_column(df):

    return find_column(
        df,
        [
            "hospital_care_type",
            "care_type"
        ]
    )


def get_website_column(df):

    return find_column(
        df,
        [
            "website",
            "web_site"
        ]
    )


# =========================================================
# COORDINATE PARSER
# =========================================================

def parse_coordinates(value):

    if value is None:
        return None, None

    if pd.isna(value):
        return None, None

    text = str(value).strip()

    if not text:
        return None, None

    text = text.replace("°", " ")
    text = text.replace("(", " ")
    text = text.replace(")", " ")
    text = text.replace("[", " ")
    text = text.replace("]", " ")
    text = text.replace(";", ",")

    # -----------------------------------------------------
    # Direction based coordinate
    # Example:
    # 22.5726 N, 88.3639 E
    # -----------------------------------------------------

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

                values.append((number, direction))

            except Exception:
                pass

        if len(values) >= 2:

            a = values[0][0]
            b = values[1][0]

            # Direction explicitly identifies longitude
            if values[0][1] in ["E", "W"]:
                lon = a
                lat = b

                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return lat, lon

            if values[1][1] in ["E", "W"]:
                lat = a
                lon = b

                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return lat, lon

    # -----------------------------------------------------
    # Normal decimal pair
    # -----------------------------------------------------

    numbers = re.findall(
        r"-?\d+(?:\.\d+)?",
        text
    )

    if len(numbers) < 2:
        return None, None

    try:

        a = float(numbers[0])
        b = float(numbers[1])

        # -------------------------------------------------
        # India-specific detection
        # Latitude: roughly 6–37
        # Longitude: roughly 68–98
        # -------------------------------------------------

        if 6 <= a <= 37 and 68 <= b <= 98:
            return a, b

        if 6 <= b <= 37 and 68 <= a <= 98:
            return b, a

        # Generic coordinate detection
        if -90 <= a <= 90 and -180 <= b <= 180:
            return a, b

        if -90 <= b <= 90 and -180 <= a <= 180:
            return b, a

    except Exception:
        pass

    return None, None


# =========================================================
# PREPARE COORDINATES
# =========================================================

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

    # -----------------------------------------------------
    # First try coordinate column
    # -----------------------------------------------------

    if coordinate_column:

        parsed = data[coordinate_column].apply(
            parse_coordinates
        )

        data["map_lat"] = parsed.apply(
            lambda x: x[0]
        )

        data["map_lon"] = parsed.apply(
            lambda x: x[1]
        )

    # -----------------------------------------------------
    # Then use separate latitude / longitude columns
    # -----------------------------------------------------

    if latitude_column:

        lat_values = pd.to_numeric(
            data[latitude_column],
            errors="coerce"
        )

        data["map_lat"] = data["map_lat"].fillna(
            lat_values
        )

    if longitude_column:

        lon_values = pd.to_numeric(
            data[longitude_column],
            errors="coerce"
        )

        data["map_lon"] = data["map_lon"].fillna(
            lon_values
        )

    # Numeric conversion
    data["map_lat"] = pd.to_numeric(
        data["map_lat"],
        errors="coerce"
    )

    data["map_lon"] = pd.to_numeric(
        data["map_lon"],
        errors="coerce"
    )

    # Validate
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

    name_col = get_hospital_column(data)
    state_col = get_state_column(data)
    district_col = get_district_column(data)
    subdistrict_col = get_subdistrict_column(data)
    address_col = get_address_column(data)
    location_col = get_location_column(data)
    pincode_col = get_pincode_column(data)

    columns = [
        name_col,
        state_col,
        district_col,
        subdistrict_col,
        address_col,
        location_col,
        pincode_col
    ]

    columns = [
        col for col in columns
        if col is not None
    ]

    if not columns:
        data["_search_index"] = ""
        return data

    data["_search_index"] = (
        data[columns]
        .fillna("")
        .astype(str)
        .agg(" ".join, axis=1)
        .str.lower()
    )

    return data


df = create_search_index(df)


# =========================================================
# HOSPITAL SEARCH
# =========================================================

def search_hospitals(data, search_text):

    if not search_text.strip():
        return data.copy()

    query = search_text.strip().lower()

    result = data[
        data["_search_index"].str.contains(
            query,
            regex=False,
            na=False
        )
    ].copy()

    return result


# =========================================================
# BED INFORMATION
# =========================================================

def get_bed_values(row):

    total_col = get_total_beds_column(df)
    available_col = get_available_beds_column(df)

    total = None
    available = None

    if total_col:
        total = safe_number(row.get(total_col))

    if available_col:
        available = safe_number(row.get(available_col))

    return total, available


def get_bed_status(total, available):

    if available is None:
        return "Current availability not provided"

    if available <= 0:
        return "Full"

    if total is None or total <= 0:
        return "Available"

    percentage = (available / total) * 100

    if percentage <= 10:
        return "Critical"

    if percentage <= 30:
        return "Low"

    return "Available"


# =========================================================
# FORMATTERS
# =========================================================

def display_value(value):

    value = clean_text(value)

    return value if value else "Not provided"


def format_bed_value(value):

    if value is None:
        return "Not provided"

    if float(value).is_integer():
        return str(int(value))

    return str(round(value, 2))


# =========================================================
# HOSPITAL DETAIL
# =========================================================

def hospital_details(row):

    name_col = get_hospital_column(df)
    state_col = get_state_column(df)
    district_col = get_district_column(df)
    subdistrict_col = get_subdistrict_column(df)
    address_col = get_address_column(df)
    pincode_col = get_pincode_column(df)
    phone_col = get_phone_column(df)
    emergency_col = get_emergency_column(df)
    ambulance_col = get_ambulance_column(df)
    specialties_col = get_specialties_column(df)
    facilities_col = get_facilities_column(df)
    category_col = get_category_column(df)
    care_type_col = get_care_type_column(df)
    emergency_services_col = get_emergency_services_column(df)
    website_col = get_website_column(df)

    total_beds, available_beds = get_bed_values(row)

    name = (
        row.get(name_col, "")
        if name_col
        else "Unknown Hospital"
    )

    st.markdown(
        f"### 🏥 {display_value(name)}"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.write(
            f"**State:** "
            f"{display_value(row.get(state_col)) if state_col else 'Not provided'}"
        )

        st.write(
            f"**District:** "
            f"{display_value(row.get(district_col)) if district_col else 'Not provided'}"
        )

        st.write(
            f"**Subdistrict:** "
            f"{display_value(row.get(subdistrict_col)) if subdistrict_col else 'Not provided'}"
        )

    with col2:

        st.write(
            f"**Category:** "
            f"{display_value(row.get(category_col)) if category_col else 'Not provided'}"
        )

        st.write(
            f"**Care Type:** "
            f"{display_value(row.get(care_type_col)) if care_type_col else 'Not provided'}"
        )

        st.write(
            f"**Emergency Services:** "
            f"{display_value(row.get(emergency_services_col)) if emergency_services_col else 'Not provided'}"
        )

    with col3:

        st.write(
            f"**Total Beds:** {format_bed_value(total_beds)}"
        )

        if available_beds is not None:

            st.write(
                f"**Available Beds:** "
                f"{format_bed_value(available_beds)}"
            )

        else:

            st.write(
                "**Current Available Beds:** Not provided"
            )

    st.markdown("---")

    st.write(
        f"📍 **Address:** "
        f"{display_value(row.get(address_col)) if address_col else 'Not provided'}"
    )

    st.write(
        f"📮 **Pincode:** "
        f"{display_value(row.get(pincode_col)) if pincode_col else 'Not provided'}"
    )

    st.write(
        f"☎️ **Phone:** "
        f"{display_value(row.get(phone_col)) if phone_col else 'Not provided'}"
    )

    st.write(
        f"🚨 **Emergency Number:** "
        f"{display_value(row.get(emergency_col)) if emergency_col else 'Not provided'}"
    )

    st.write(
        f"🚑 **Ambulance:** "
        f"{display_value(row.get(ambulance_col)) if ambulance_col else 'Not provided'}"
    )

    st.write(
        f"🩺 **Specialties:** "
        f"{display_value(row.get(specialties_col)) if specialties_col else 'Not provided'}"
    )

    st.write(
        f"🛠️ **Facilities:** "
        f"{display_value(row.get(facilities_col)) if facilities_col else 'Not provided'}"
    )

    if website_col:

        website = clean_text(row.get(website_col))

        if website:

            if not website.startswith("http"):
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

    map_df = map_df.head(max_markers).copy()

    if map_df["map_lat"].dropna().empty:
        return None

    center_lat = map_df["map_lat"].mean()
    center_lon = map_df["map_lon"].mean()

    m = folium.Map(
        location=[
            center_lat,
            center_lon
        ],
        zoom_start=11,
        control_scale=True
    )

    name_col = get_hospital_column(source_df)
    state_col = get_state_column(source_df)
    district_col = get_district_column(source_df)
    address_col = get_address_column(source_df)

    category_col = get_category_column(source_df)
    emergency_col = get_emergency_services_column(source_df)

    total_beds_col = get_total_beds_column(source_df)

    for _, row in map_df.iterrows():

        lat = row["map_lat"]
        lon = row["map_lon"]

        if pd.isna(lat) or pd.isna(lon):
            continue

        hospital_name = (
            display_value(row.get(name_col))
            if name_col
            else "Hospital"
        )

        state = (
            display_value(row.get(state_col))
            if state_col
            else "Not provided"
        )

        district = (
            display_value(row.get(district_col))
            if district_col
            else "Not provided"
        )

        address = (
            display_value(row.get(address_col))
            if address_col
            else "Not provided"
        )

        category = (
            display_value(row.get(category_col))
            if category_col
            else "Not provided"
        )

        emergency = (
            display_value(row.get(emergency_col))
            if emergency_col
            else "Not provided"
        )

        total_beds, available_beds = get_bed_values(row)

        if available_beds is not None:

            status = get_bed_status(
                total_beds,
                available_beds
            )

        else:

            status = "Current availability not provided"

        if status == "Full":
            marker_color = "red"

        elif status == "Critical":
            marker_color = "orange"

        elif status == "Low":
            marker_color = "orange"

        else:
            marker_color = "blue"

        popup_html = f"""
        <div style="width:320px">

        <h4>🏥 {html.escape(hospital_name)}</h4>

        <b>State:</b> {html.escape(state)}<br>
        <b>District:</b> {html.escape(district)}<br>
        <b>Category:</b> {html.escape(category)}<br><br>

        <b>Address:</b><br>
        {html.escape(address)}<br><br>

        <b>Total Beds:</b>
        {html.escape(format_bed_value(total_beds))}<br>

        <b>Current Available Beds:</b>
        {html.escape(format_bed_value(available_beds))}<br>

        <b>Status:</b>
        {html.escape(status)}<br><br>

        <b>Emergency Services:</b>
        {html.escape(emergency)}

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

    folium.LayerControl().add_to(m)

    return m


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("🏥 Hospital System")

page = st.sidebar.radio(
    "Navigate",
    [
        "🏠 Home",
        "🔎 Hospital Search",
        "🚨 Emergency Search",
        "🛏️ Bed Availability",
        "👨‍⚕️ Doctor Availability",
        "🛠️ Equipment Availability",
        "📋 Reservation Management",
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

if page == "🏠 Home":

    st.title("🏥 Smart Hospital Bed Availability System")

    st.subheader(
        "Find hospitals, resources and emergency information."
    )

    if df.empty:

        st.warning("Hospital dataset পাওয়া যায়নি.")
        st.stop()

    prepared_df, coord_col, lat_col, lon_col = prepare_coordinates(df)

    total_hospitals = len(prepared_df)

    hospitals_with_coordinates = int(
        prepared_df["map_lat"].notna().sum()
    )

    total_beds_col = get_total_beds_column(prepared_df)

    if total_beds_col:

        total_beds = pd.to_numeric(
            prepared_df[total_beds_col],
            errors="coerce"
        ).sum()

    else:

        total_beds = 0

    doctors_col = get_doctor_column(prepared_df)

    if doctors_col:

        total_doctors = pd.to_numeric(
            prepared_df[doctors_col],
            errors="coerce"
        ).sum()

    else:

        total_doctors = 0

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "🏥 Hospitals",
            f"{total_hospitals:,}"
        )

    with c2:
        st.metric(
            "📍 Mapped Hospitals",
            f"{hospitals_with_coordinates:,}"
        )

    with c3:
        st.metric(
            "🛏️ Listed Beds",
            f"{int(total_beds):,}"
        )

    with c4:
        st.metric(
            "👨‍⚕️ Listed Doctors",
            f"{int(total_doctors):,}"
        )

    st.markdown("---")

    st.info(
        "ℹ️ The official hospital directory provides hospital information "
        "and listed bed capacity. It does not necessarily provide "
        "real-time available-bed status."
    )

    st.markdown("### 📍 Hospital Map")

    map_df = prepared_df[
        prepared_df["map_lat"].notna() &
        prepared_df["map_lon"].notna()
    ].head(100)

    if not map_df.empty:

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

elif page == "🔎 Hospital Search":

    st.title("🔎 Hospital Search")

    st.write(
        "Search by hospital name, city/location, state, "
        "district, subdistrict or pincode."
    )

    if df.empty:
        st.stop()

    prepared_df, coord_col, lat_col, lon_col = prepare_coordinates(df)

    search_text = st.text_input(
        "Search Hospital / City / State / District / Pincode",
        placeholder="Example: Kolkata"
    )

    col1, col2 = st.columns(2)

    with col1:

        max_results = st.slider(
            "Maximum results",
            10,
            500,
            100
        )

    with col2:

        max_markers = st.slider(
            "Maximum map markers",
            10,
            300,
            100
        )

    # Debug information
    with st.expander("🔧 Dataset / Coordinate Information"):

        st.write(
            f"Total records: **{len(prepared_df):,}**"
        )

        st.write(
            f"Valid coordinates: **{prepared_df['map_lat'].notna().sum():,}**"
        )

        st.write(
            f"Detected coordinate column: "
            f"**{coord_col if coord_col else 'Not found'}**"
        )

        st.write(
            f"Detected latitude column: "
            f"**{lat_col if lat_col else 'Not found'}**"
        )

        st.write(
            f"Detected longitude column: "
            f"**{lon_col if lon_col else 'Not found'}**"
        )

    results = search_hospitals(
        prepared_df,
        search_text
    )

    # Remove duplicates
    name_col = get_hospital_column(results)
    address_col = get_address_column(results)

    if name_col:

        duplicate_columns = [name_col]

        if address_col:
            duplicate_columns.append(address_col)

        results = results.drop_duplicates(
            subset=duplicate_columns
        )

    results = results.head(max_results)

    st.success(
        f"Found {len(results):,} hospital record(s)"
    )

    if results.empty:

        st.warning(
            "❌ No hospitals found. Try another spelling, "
            "district, state or pincode."
        )

    else:

        for index, row in results.iterrows():

            name = (
                row.get(name_col)
                if name_col
                else "Hospital"
            )

            with st.expander(
                f"🏥 {display_value(name)}"
            ):

                hospital_details(row)

                if (
                    pd.notna(row["map_lat"])
                    and pd.notna(row["map_lon"])
                ):

                    st.write(
                        f"📍 Coordinates: "
                        f"{row['map_lat']:.6f}, "
                        f"{row['map_lon']:.6f}"
                    )

        st.markdown("---")

        st.subheader("🗺️ Interactive Hospital Map")

        mapped_results = results[
            results["map_lat"].notna() &
            results["map_lon"].notna()
        ]

        if mapped_results.empty:

            st.warning(
                "Search results পাওয়া গেছে, কিন্তু "
                "এই records-এর valid coordinates পাওয়া যায়নি."
            )

        else:

            hospital_map = create_hospital_map(
                mapped_results,
                prepared_df,
                max_markers
            )

            if hospital_map:

                st_folium(
                    hospital_map,
                    width=None,
                    height=650
                )


# =========================================================
# EMERGENCY SEARCH
# =========================================================

elif page == "🚨 Emergency Search":

    st.title("🚨 Emergency Hospital Search")

    st.warning(
        "Academic prototype: this feature does not guarantee "
        "real-time bed/admission availability."
    )

    prepared_df, _, _, _ = prepare_coordinates(df)

    name_col = get_hospital_column(prepared_df)
    state_col = get_state_column(prepared_df)
    district_col = get_district_column(prepared_df)
    specialty_col = get_specialties_column(prepared_df)
    emergency_col = get_emergency_services_column(prepared_df)
    ambulance_col = get_ambulance_column(prepared_df)
    total_beds_col = get_total_beds_column(prepared_df)

    col1, col2 = st.columns(2)

    with col1:

        emergency_search = st.text_input(
            "📍 Location / Hospital / District",
            placeholder="Example: Kolkata"
        )

    with col2:

        specialty_search = st.text_input(
            "🩺 Required Specialty",
            placeholder="Example: Cardiology"
        )

    require_emergency = st.checkbox(
        "🚨 Show hospitals with emergency services information"
    )

    require_ambulance = st.checkbox(
        "🚑 Show hospitals with ambulance information"
    )

    minimum_beds = st.number_input(
        "Minimum listed total beds",
        min_value=0,
        value=0,
        step=10
    )

    results = prepared_df.copy()

    # Location search
    if emergency_search.strip():

        results = search_hospitals(
            results,
            emergency_search
        )

    # Specialty search
    if specialty_search.strip() and specialty_col:

        results = results[
            results[specialty_col]
            .fillna("")
            .astype(str)
            .str.contains(
                specialty_search,
                case=False,
                regex=False
            )
        ]

    # Emergency filter
    if require_emergency and emergency_col:

        results = results[
            results[emergency_col]
            .fillna("")
            .astype(str)
            .str.strip()
            .ne("")
        ]

    # Ambulance filter
    if require_ambulance and ambulance_col:

        results = results[
            results[ambulance_col]
            .fillna("")
            .astype(str)
            .str.strip()
            .ne("")
        ]

    # Minimum beds
    if minimum_beds > 0 and total_beds_col:

        bed_numbers = pd.to_numeric(
            results[total_beds_col],
            errors="coerce"
        ).fillna(0)

        results = results[
            bed_numbers >= minimum_beds
        ]

    results = results.head(200)

    st.success(
        f"Emergency search returned {len(results):,} result(s)"
    )

    if results.empty:

        st.info(
            "No matching hospital found. Try relaxing the filters."
        )

    else:

        for _, row in results.iterrows():

            name = (
                row.get(name_col)
                if name_col
                else "Hospital"
            )

            st.markdown(
                f"### 🏥 {display_value(name)}"
            )

            c1, c2, c3 = st.columns(3)

            with c1:

                if state_col:
                    st.write(
                        f"**State:** "
                        f"{display_value(row.get(state_col))}"
                    )

                if district_col:
                    st.write(
                        f"**District:** "
                        f"{display_value(row.get(district_col))}"
                    )

            with c2:

                total, available = get_bed_values(row)

                st.write(
                    f"**Total Beds:** "
                    f"{format_bed_value(total)}"
                )

                st.write(
                    f"**Current Available:** "
                    f"{format_bed_value(available)}"
                )

            with c3:

                if emergency_col:
                    st.write(
                        f"**Emergency:** "
                        f"{display_value(row.get(emergency_col))}"
                    )

                if ambulance_col:
                    st.write(
                        f"**Ambulance:** "
                        f"{display_value(row.get(ambulance_col))}"
                    )

            if specialty_col:

                st.write(
                    f"🩺 **Specialties:** "
                    f"{display_value(row.get(specialty_col))}"
                )

            st.markdown("---")


# =========================================================
# BED AVAILABILITY
# =========================================================

elif page == "🛏️ Bed Availability":

    st.title("🛏️ Hospital Bed Information")

    st.info(
        "The official directory provides listed total bed capacity. "
        "Real-time available beds are shown only if an availability "
        "field exists in your dataset."
    )

    prepared_df, _, _, _ = prepare_coordinates(df)

    search = st.text_input(
        "Search hospital / city / district",
        placeholder="Example: Kolkata"
    )

    results = search_hospitals(
        prepared_df,
        search
    ).head(200)

    total_col = get_total_beds_column(prepared_df)
    available_col = get_available_beds_column(prepared_df)
    name_col = get_hospital_column(prepared_df)

    if total_col:

        total_beds = pd.to_numeric(
            results[total_col],
            errors="coerce"
        ).fillna(0).sum()

    else:

        total_beds = 0

    c1, c2 = st.columns(2)

    with c1:
        st.metric(
            "Hospitals",
            len(results)
        )

    with c2:
        st.metric(
            "Listed Total Beds",
            f"{int(total_beds):,}"
        )

    st.markdown("---")

    for _, row in results.iterrows():

        name = (
            row.get(name_col)
            if name_col
            else "Hospital"
        )

        total, available = get_bed_values(row)

        status = get_bed_status(
            total,
            available
        )

        st.markdown(
            f"### 🏥 {display_value(name)}"
        )

        c1, c2, c3 = st.columns(3)

        with c1:

            st.write(
                f"**Total Beds:** "
                f"{format_bed_value(total)}"
            )

        with c2:

            st.write(
                f"**Available Beds:** "
                f"{format_bed_value(available)}"
            )

        with c3:

            st.write(
                f"**Status:** {status}"
            )

        st.markdown("---")


# =========================================================
# DOCTOR AVAILABILITY
# =========================================================

elif page == "👨‍⚕️ Doctor Availability":

    st.title("👨‍⚕️ Doctor Availability")

    conn = sqlite3.connect(DB_PATH)

    doctors = pd.read_sql_query(
        "SELECT * FROM doctors ORDER BY id DESC",
        conn
    )

    conn.close()

    if not doctors.empty:

        st.dataframe(
            doctors,
            use_container_width=True
        )

    else:

        st.info(
            "No doctor records added yet."
        )

    st.markdown("---")

    st.subheader("➕ Add Doctor")

    with st.form("doctor_form"):

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

            conn = sqlite3.connect(DB_PATH)

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

elif page == "🛠️ Equipment Availability":

    st.title("🛠️ Equipment Availability")

    conn = sqlite3.connect(DB_PATH)

    equipment = pd.read_sql_query(
        "SELECT * FROM equipment ORDER BY id DESC",
        conn
    )

    conn.close()

    if not equipment.empty:

        st.dataframe(
            equipment,
            use_container_width=True
        )

    else:

        st.info(
            "No equipment records added yet."
        )

    st.markdown("---")

    st.subheader("➕ Add Equipment")

    with st.form("equipment_form"):

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

            conn = sqlite3.connect(DB_PATH)

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

    st.title("📋 Reservation Management")

    conn = sqlite3.connect(DB_PATH)

    reservations = pd.read_sql_query(
        "SELECT * FROM reservations ORDER BY id DESC",
        conn
    )

    conn.close()

    if not reservations.empty:

        st.dataframe(
            reservations,
            use_container_width=True
        )

    else:

        st.info(
            "No reservations yet."
        )

    st.markdown("---")

    st.subheader("➕ Create Reservation")

    with st.form("reservation_form"):

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

            conn = sqlite3.connect(DB_PATH)

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

            st.success(
                "Reservation created successfully."
            )

            st.rerun()


# =========================================================
# ADMIN DASHBOARD
# =========================================================

elif page == "📊 Admin Dashboard":

    st.title("📊 Admin Dashboard")

    conn = sqlite3.connect(DB_PATH)

    doctor_count = pd.read_sql_query(
        "SELECT COUNT(*) AS count FROM doctors",
        conn
    )["count"][0]

    equipment_count = pd.read_sql_query(
        "SELECT COUNT(*) AS count FROM equipment",
        conn
    )["count"][0]

    reservation_count = pd.read_sql_query(
        "SELECT COUNT(*) AS count FROM reservations",
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

    conn.close()

    prepared_df, coord_col, lat_col, lon_col = prepare_coordinates(df)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "🏥 Hospitals",
            f"{len(prepared_df):,}"
        )

    with c2:
        st.metric(
            "👨‍⚕️ Registered Doctors",
            doctor_count
        )

    with c3:
        st.metric(
            "🛠️ Equipment Records",
            equipment_count
        )

    with c4:
        st.metric(
            "📋 Reservations",
            reservation_count
        )

    st.markdown("---")

    st.subheader("📌 Pending Reservations")

    st.metric(
        "Pending",
        pending_count
    )

    st.markdown("---")

    st.subheader("📍 Dataset Information")

    st.write(
        f"**CSV file:** `{CSV_PATH.name}`"
    )

    st.write(
        f"**Total hospital records:** "
        f"{len(prepared_df):,}"
    )

    st.write(
        f"**Records with coordinates:** "
        f"{prepared_df['map_lat'].notna().sum():,}"
    )

    st.write(
        f"**Coordinate column:** "
        f"{coord_col if coord_col else 'Not found'}"
    )

    st.write(
        f"**Latitude column:** "
        f"{lat_col if lat_col else 'Not found'}"
    )

    st.write(
        f"**Longitude column:** "
        f"{lon_col if lon_col else 'Not found'}"
    )

    st.markdown("---")

    st.subheader("⚠️ Important")

    st.info(
        "Hospital directory information and total bed capacity "
        "should not be interpreted as live hospital availability. "
        "Live availability requires an authorized real-time data source."
    )


# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.caption(
    "🏥 Smart Hospital Bed Availability System | "
    "Prototype / Academic Demo"
    )
