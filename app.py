import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path
from datetime import date, datetime
import math
import html

# Optional map libraries
try:
    import folium
    from streamlit_folium import st_folium
    MAP_AVAILABLE = True
except Exception:
    MAP_AVAILABLE = False


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Smart Hospital Bed Availability System",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "hospital_directory.csv"
DB_DIR = BASE_DIR / "database"
DB_PATH = DB_DIR / "hospital.db"

DB_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# DATABASE
# ============================================================

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def quote_identifier(name):
    """Safely quote a SQLite identifier."""
    return '"' + str(name).replace('"', '""') + '"'


def initialize_database():
    """Create the new management tables if they do not exist."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(""" CREATE TABLE IF NOT EXISTS doctors ( doctor_id INTEGER PRIMARY KEY AUTOINCREMENT, hospital_name TEXT NOT NULL, doctor_name TEXT NOT NULL, department TEXT, specialization TEXT, availability_status TEXT DEFAULT 'Available', available_from TEXT, available_to TEXT, last_updated TEXT ) """)

    cur.execute(""" CREATE TABLE IF NOT EXISTS equipment ( equipment_id INTEGER PRIMARY KEY AUTOINCREMENT, hospital_name TEXT NOT NULL, equipment_name TEXT NOT NULL, total_units INTEGER DEFAULT 0, available_units INTEGER DEFAULT 0, last_updated TEXT ) """)

    cur.execute(""" CREATE TABLE IF NOT EXISTS reservations ( reservation_id INTEGER PRIMARY KEY AUTOINCREMENT, patient_name TEXT NOT NULL, phone TEXT, hospital_name TEXT NOT NULL, reservation_type TEXT, department TEXT, doctor_name TEXT, equipment_name TEXT, reservation_date TEXT, reservation_time TEXT, notes TEXT, status TEXT DEFAULT 'Pending', created_at TEXT ) """)

    conn.commit()
    conn.close()


initialize_database()


# ============================================================
# GENERIC HELPERS
# ============================================================

def normalize_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def safe_int(value, default=0):
    try:
        if pd.isna(value):
            return default
        return int(float(str(value).replace(",", "").strip()))
    except Exception:
        return default


def safe_float(value, default=None):
    try:
        if pd.isna(value):
            return default
        return float(str(value).replace(",", "").strip())
    except Exception:
        return default


def find_column(columns, candidates):
    """Find a column by exact/normalized candidate names."""
    normalized = {
        str(c).strip().lower().replace(" ", "_"): c
        for c in columns
    }

    for candidate in candidates:
        key = candidate.strip().lower().replace(" ", "_")
        if key in normalized:
            return normalized[key]

    # Fuzzy fallback
    for c in columns:
        low = str(c).lower().replace(" ", "_")
        for candidate in candidates:
            if candidate.lower().replace(" ", "_") in low:
                return c

    return None


def get_bed_status(total_beds, available_beds):
    if available_beds is None:
        return "⚪ Unknown"

    total = safe_int(total_beds)
    available = safe_int(available_beds)

    if total <= 0:
        return "⚪ Unknown"

    if available <= 0:
        return "🔴 Full"

    percentage = (available / total) * 100

    if percentage <= 15:
        return "🟠 Critical"
    elif percentage <= 30:
        return "🟡 Low"
    return "🟢 Available"


def get_bed_color(total_beds, available_beds):
    if available_beds is None:
        return "blue"

    total = safe_int(total_beds)
    available = safe_int(available_beds)

    if total <= 0:
        return "blue"

    if available <= 0:
        return "red"

    percentage = (available / total) * 100

    if percentage <= 15:
        return "orange"
    elif percentage <= 30:
        return "beige"
    return "green"


def parse_coordinates(value):
    """ Parse coordinates stored like: '11.6357989, 92.7120575' """
    if pd.isna(value):
        return None, None

    text = str(value).strip()

    if not text:
        return None, None

    try:
        parts = [x.strip() for x in text.split(",")]
        if len(parts) >= 2:
            lat = float(parts[0])
            lon = float(parts[1])

            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon
    except Exception:
        pass

    return None, None


# ============================================================
# HOSPITAL DIRECTORY
# ============================================================

@st.cache_data(show_spinner=False)
def load_hospital_directory():
    if not CSV_PATH.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(
            CSV_PATH,
            low_memory=False,
            encoding="utf-8",
        )
    except UnicodeDecodeError:
        df = pd.read_csv(
            CSV_PATH,
            low_memory=False,
            encoding="latin1",
        )

    df.columns = [str(c).strip() for c in df.columns]

    # Keep the ORIGINAL CSV; only create normalized working columns.
    mapping = {
        "hospital_name": find_column(
            df.columns,
            ["Hospital_Name", "hospital_name", "Hospital Name"]
        ),
        "state": find_column(
            df.columns,
            ["State", "state"]
        ),
        "district": find_column(
            df.columns,
            ["District", "district"]
        ),
        "address": find_column(
            df.columns,
            [
                "Address_Original_First_Line",
                "Address",
                "address"
            ]
        ),
        "pincode": find_column(
            df.columns,
            ["Pincode", "PIN", "pincode"]
        ),
        "coordinates": find_column(
            df.columns,
            [
                "Location_Coordinates",
                "Latitude_Longitude",
                "Coordinates",
                "coordinates"
            ]
        ),
        "total_beds": find_column(
            df.columns,
            [
                "Total_Num_Beds",
                "total_num_beds",
                "Total Beds",
                "total_beds"
            ]
        ),
        "specialties": find_column(
            df.columns,
            ["Specialties", "specialties"]
        ),
        "facilities": find_column(
            df.columns,
            ["Facilities", "facilities"]
        ),
        "emergency": find_column(
            df.columns,
            [
                "Emergency_Services",
                "Emergency Services",
                "emergency_services"
            ]
        ),
        "phone": find_column(
            df.columns,
            ["Telephone", "Mobile_Number", "Phone", "phone"]
        ),
        "website": find_column(
            df.columns,
            ["Website", "website"]
        ),
    }

    # Create working columns without modifying/removing original data.
    for new_col, original_col in mapping.items():
        if original_col is not None:
            df[new_col] = df[original_col].apply(normalize_text)
        else:
            df[new_col] = ""

    # Parse map coordinates.
    parsed = df["coordinates"].apply(parse_coordinates)
    df["latitude"] = parsed.apply(lambda x: x[0])
    df["longitude"] = parsed.apply(lambda x: x[1])

    df["total_beds_numeric"] = df["total_beds"].apply(
        lambda x: safe_int(x, 0)
    )

    # Remove rows without a hospital name.
    df = df[df["hospital_name"].str.strip() != ""].copy()

    return df


hospitals = load_hospital_directory()


# ============================================================
# BED DATA FROM SQLITE
# ============================================================

def get_sqlite_tables(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return [r[0] for r in rows]


def get_table_dataframe(conn, table_name):
    try:
        return pd.read_sql_query(
            f"SELECT * FROM {quote_identifier(table_name)}",
            conn
        )
    except Exception:
        return pd.DataFrame()


def load_bed_availability_from_database():
    """ Tries common hospital/bed table structures. This keeps the app compatible with an existing hospital.db. """
    if not DB_PATH.exists():
        return pd.DataFrame(
            columns=["hospital_name", "total_beds", "available_beds"]
        )

    conn = get_connection()

    try:
        tables = get_sqlite_tables(conn)

        # Prefer tables whose names suggest bed/hospital information.
        preferred = [
            t for t in tables
            if any(k in t.lower() for k in ["bed", "hospital"])
        ]

        # Search preferred tables first, then other tables.
        ordered_tables = preferred + [
            t for t in tables if t not in preferred
        ]

        for table in ordered_tables:
            # Management tables are not bed tables.
            if table.lower() in {"doctors", "equipment", "reservations"}:
                continue

            df = get_table_dataframe(conn, table)

            if df.empty:
                continue

            hospital_col = find_column(
                df.columns,
                [
                    "hospital_name",
                    "hospital",
                    "name",
                    "hospital_name_text"
                ]
            )

            available_col = find_column(
                df.columns,
                [
                    "available_beds",
                    "available_bed",
                    "beds_available",
                    "available"
                ]
            )

            total_col = find_column(
                df.columns,
                [
                    "total_beds",
                    "total_bed",
                    "beds",
                    "total_num_beds"
                ]
            )

            if hospital_col is None:
                continue

            if available_col is None and total_col is None:
                continue

            result = pd.DataFrame()
            result["hospital_name"] = df[hospital_col].apply(normalize_text)

            if total_col is not None:
                result["total_beds"] = df[total_col].apply(
                    lambda x: safe_int(x, 0)
                )
            else:
                result["total_beds"] = 0

            if available_col is not None:
                result["available_beds"] = df[available_col].apply(
                    lambda x: safe_int(x, 0)
                )
            else:
                result["available_beds"] = None

            result = result[
                result["hospital_name"].str.strip() != ""
            ].copy()

            if not result.empty:
                # If the database has multiple rows per hospital,
                # aggregate them.
                result = (
                    result.groupby("hospital_name", as_index=False)
                    .agg({
                        "total_beds": "max",
                        "available_beds": "max"
                    })
                )

                return result

        return pd.DataFrame(
            columns=["hospital_name", "total_beds", "available_beds"]
        )

    finally:
        conn.close()


@st.cache_data(ttl=30, show_spinner=False)
def get_bed_data_cached():
    return load_bed_availability_from_database()


bed_data = get_bed_data_cached()


def attach_bed_data(df):
    result = df.copy()

    if "total_beds_numeric" not in result.columns:
        result["total_beds_numeric"] = 0

    # Directory total beds are used only as hospital directory capacity.
    result["total_beds_display"] = result["total_beds_numeric"]

    result["available_beds"] = None

    if not bed_data.empty:
        lookup = bed_data.copy()
        lookup["hospital_key"] = (
            lookup["hospital_name"]
            .str.lower()
            .str.strip()
        )

        result["hospital_key"] = (
            result["hospital_name"]
            .str.lower()
            .str.strip()
        )

        result = result.merge(
            lookup[
                [
                    "hospital_key",
                    "total_beds",
                    "available_beds"
                ]
            ],
            on="hospital_key",
            how="left",
            suffixes=("", "_db")
        )

        result["available_beds"] = result["available_beds"].apply(
            lambda x: None if pd.isna(x) else safe_int(x, 0)
        )

        # Prefer DB total beds when available.
        result["total_beds_display"] = result.apply(
            lambda row: (
                safe_int(row["total_beds_db"], 0)
                if "total_beds_db" in row.index
                and safe_int(row["total_beds_db"], 0) > 0
                else safe_int(row["total_beds_numeric"], 0)
            ),
            axis=1
        )

    result["occupied_beds"] = result.apply(
        lambda row: (
            max(
                safe_int(row["total_beds_display"], 0)
                - safe_int(row["available_beds"], 0),
                0
            )
            if row["available_beds"] is not None
            else None
        ),
        axis=1
    )

    result["availability_status"] = result.apply(
        lambda row: get_bed_status(
            row["total_beds_display"],
            row["available_beds"]
        ),
        axis=1
    )

    return result


# ============================================================
# DISTANCE
# ============================================================

def haversine_km(lat1, lon1, lat2, lon2):
    radius = 6371.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(d_lambda / 2) ** 2
    )

    return 2 * radius * math.asin(math.sqrt(a))


# ============================================================
# UI HEADER
# ============================================================

st.title("🏥 Smart Hospital Bed Availability System")
st.caption(
    "Hospital search, interactive map, hospital markers and bed availability"
)

if hospitals.empty:
    st.error(
        "hospital_directory.csv was not found or could not be loaded. "
        "Keep the CSV in the same folder as app.py."
    )
    st.stop()


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

st.sidebar.title("📌 Navigation")

page = st.sidebar.radio(
    "Go to",
    [
        "🏠 Home",
        "🏥 Hospital Search & Map",
        "🛏️ Bed Availability",
        "👨‍⚕️ Doctor Availability",
        "🩺 Equipment Availability",
        "📋 Reservation Management",
        "📊 Admin Dashboard",
    ]
)


# ============================================================
# HOME
# ============================================================

if page == "🏠 Home":

    st.header("🏠 Smart Hospital Bed Availability System")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("🏥 Hospitals in Directory", f"{len(hospitals):,}")

    with c2:
        mapped = hospitals["latitude"].notna().sum()
        st.metric("📍 Hospitals with Coordinates", f"{mapped:,}")

    with c3:
        db_beds = len(bed_data)
        st.metric("🛏️ Bed Records Available", f"{db_beds:,}")

    st.markdown("---")

    st.subheader("Main Features")

    st.markdown(
        """ - 🏥 **Hospital Search** — Search by hospital name, state, district and address. - 📍 **Interactive Map** — View hospitals as map markers. - 🛏️ **Bed Availability** — View total, available and occupied beds when bed data is available. - 👨‍⚕️ **Doctor Availability** — Manage doctor availability. - 🩺 **Equipment Availability** — Track medical equipment. - 📋 **Reservation Management** — Manage reservation requests. - 📊 **Admin Dashboard** — Monitor system statistics. """
    )

    st.info(
        "Bed availability is shown from the connected hospital database when "
        "matching bed records exist. The directory CSV itself is not treated "
        "as real-time bed availability."
    )


# ============================================================
# HOSPITAL SEARCH + INTERACTIVE MAP
# ============================================================

elif page == "🏥 Hospital Search & Map":

    st.header("🏥 Hospital Search")

    st.write(
        "Search hospitals by name, state, district or address and view "
        "matching hospitals on the interactive map."
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        search_text = st.text_input(
            "🔎 Search Hospital",
            placeholder="Enter hospital name, address, state or district"
        )

    with col2:
        states = sorted(
            [
                x for x in hospitals["state"].dropna().unique()
                if str(x).strip()
            ]
        )

        selected_state = st.selectbox(
            "State",
            ["All States"] + states
        )

    if selected_state != "All States":
        district_options = sorted(
            [
                x for x in hospitals.loc[
                    hospitals["state"] == selected_state,
                    "district"
                ].dropna().unique()
                if str(x).strip()
            ]
        )
    else:
        district_options = sorted(
            [
                x for x in hospitals["district"].dropna().unique()
                if str(x).strip()
            ]
        )

    selected_district = st.selectbox(
        "District",
        ["All Districts"] + district_options
    )

    # Filter
    filtered = hospitals.copy()

    if selected_state != "All States":
        filtered = filtered[
            filtered["state"].str.lower()
            == selected_state.lower()
        ]

    if selected_district != "All Districts":
        filtered = filtered[
            filtered["district"].str.lower()
            == selected_district.lower()
        ]

    if search_text.strip():
        q = search_text.strip().lower()

        searchable = (
            filtered["hospital_name"].fillna("")
            + " "
            + filtered["state"].fillna("")
            + " "
            + filtered["district"].fillna("")
            + " "
            + filtered["address"].fillna("")
            + " "
            + filtered["pincode"].fillna("")
        ).str.lower()

        filtered = filtered[searchable.str.contains(q, na=False)]

    # Add bed information.
    filtered = attach_bed_data(filtered)

    # Sort hospitals with coordinates first.
    filtered = filtered.sort_values(
        by=["latitude", "longitude"],
        na_position="last"
    )

    st.success(f"Found {len(filtered):,} matching hospital(s).")

    # Avoid rendering thousands of markers at once.
    MAX_MARKERS = 150

    map_df = filtered[
        filtered["latitude"].notna()
        & filtered["longitude"].notna()
    ].head(MAX_MARKERS).copy()

    if len(filtered) > MAX_MARKERS:
        st.info(
            f"Showing the first {MAX_MARKERS} mapped hospitals to keep the "
            "interactive map fast. Refine your search to see specific hospitals."
        )

    # --------------------------------------------------------
    # MAP
    # --------------------------------------------------------

    st.subheader("📍 Interactive Hospital Map")

    if MAP_AVAILABLE and not map_df.empty:

        center_lat = map_df["latitude"].mean()
        center_lon = map_df["longitude"].mean()

        hospital_map = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=5,
            control_scale=True
        )

        for _, row in map_df.iterrows():

            name = html.escape(normalize_text(row["hospital_name"]))
            state = html.escape(normalize_text(row["state"]))
            district = html.escape(normalize_text(row["district"]))
            address = html.escape(normalize_text(row["address"]))
            pincode = html.escape(normalize_text(row["pincode"]))

            total = safe_int(row["total_beds_display"], 0)
            available = row["available_beds"]
            occupied = row["occupied_beds"]
            status = row["availability_status"]

            if available is None:
                available_text = "Not available"
                occupied_text = "Not available"
            else:
                available_text = str(safe_int(available, 0))
                occupied_text = str(safe_int(occupied, 0))

            popup_html = f""" <div style="width:280px"> <h4>🏥 {name}</h4> <b>State:</b> {state}<br> <b>District:</b> {district}<br> <b>Address:</b> {address}<br> <b>Pincode:</b> {pincode}<br><br> <b>Total Beds:</b> {total}<br> <b>Available Beds:</b> {available_text}<br> <b>Occupied Beds:</b> {occupied_text}<br> <b>Status:</b> {status} </div> """

            folium.Marker(
                location=[
                    float(row["latitude"]),
                    float(row["longitude"])
                ],
                tooltip=name,
                popup=folium.Popup(
                    popup_html,
                    max_width=350
                ),
                icon=folium.Icon(
                    color=get_bed_color(
                        total,
                        available
                    ),
                    icon="plus-sign",
                    prefix="glyphicon"
                )
            ).add_to(hospital_map)

        st_folium(
            hospital_map,
            width=None,
            height=600,
            returned_objects=[]
        )

    elif not map_df.empty:
        # Fallback if folium/streamlit-folium isn't installed.
        st.warning(
            "Interactive map packages are not installed. "
            "The fallback map is being shown."
        )

        st.map(
            map_df.rename(
                columns={
                    "latitude": "lat",
                    "longitude": "lon"
                }
            )[["lat", "lon"]]
        )

    else:
        st.warning(
            "No hospitals with valid latitude/longitude were found "
            "for the current search."
        )

    # --------------------------------------------------------
    # HOSPITAL RESULTS
    # --------------------------------------------------------

    st.subheader("🏥 Hospital Results")

    if filtered.empty:
        st.warning("No hospitals found. Try another search.")
    else:

        display_cols = [
            "hospital_name",
            "state",
            "district",
            "pincode",
            "total_beds_display",
            "available_beds",
            "occupied_beds",
            "availability_status"
        ]

        result_table = filtered[display_cols].copy()

        result_table.columns = [
            "Hospital",
            "State",
            "District",
            "Pincode",
            "Total Beds",
            "Available Beds",
            "Occupied Beds",
            "Status"
        ]

        result_table["Available Beds"] = result_table[
            "Available Beds"
        ].apply(
            lambda x: (
                "Not available"
                if pd.isna(x)
                else int(x)
            )
        )

        result_table["Occupied Beds"] = result_table[
            "Occupied Beds"
        ].apply(
            lambda x: (
                "Not available"
                if pd.isna(x)
                else int(x)
            )
        )

        st.dataframe(
            result_table.head(200),
            use_container_width=True,
            hide_index=True
        )

    st.markdown("---")

    st.caption(
        "📌 Map coordinates come from the hospital directory. "
        "Bed availability is displayed only when corresponding bed "
        "records are available in the database."
    )


# ============================================================
# BED AVAILABILITY
# ============================================================

elif page == "🛏️ Bed Availability":

    st.header("🛏️ Bed Availability")

    current = attach_bed_data(hospitals)

    if current.empty:
        st.warning("No hospital data available.")
    else:

        search = st.text_input(
            "Search hospital",
            placeholder="Enter hospital name"
        )

        if search.strip():
            current = current[
                current["hospital_name"].str.contains(
                    search.strip(),
                    case=False,
                    na=False
                )
            ]

        total_records = len(current)
        known_beds = current["available_beds"].notna().sum()
        full_count = (
            current["availability_status"] == "🔴 Full"
        ).sum()
        critical_count = (
            current["availability_status"] == "🟠 Critical"
        ).sum()
        low_count = (
            current["availability_status"] == "🟡 Low"
        ).sum()

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.metric("Hospitals", f"{total_records:,}")

        with c2:
            st.metric("Bed Records", f"{known_beds:,}")

        with c3:
            st.metric("🔴 Full", f"{full_count:,}")

        with c4:
            st.metric("🟠 Critical", f"{critical_count:,}")

        if known_beds == 0:
            st.info(
                "No matching real/registered bed records were found in "
                "hospital.db. The directory's Total_Num_Beds field is "
                "hospital capacity information, not live available-bed data."
            )

        bed_table = current[
            [
                "hospital_name",
                "state",
                "district",
                "total_beds_display",
                "available_beds",
                "occupied_beds",
                "availability_status"
            ]
        ].copy()

        bed_table.columns = [
            "Hospital",
            "State",
            "District",
            "Total Beds",
            "Available Beds",
            "Occupied Beds",
            "Availability Status"
        ]

        bed_table["Available Beds"] = bed_table[
            "Available Beds"
        ].apply(
            lambda x: (
                "Not available"
                if pd.isna(x)
                else int(x)
            )
        )

        bed_table["Occupied Beds"] = bed_table[
            "Occupied Beds"
        ].apply(
            lambda x: (
                "Not available"
                if pd.isna(x)
                else int(x)
            )
        )

        st.dataframe(
            bed_table.head(500),
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# DOCTOR AVAILABILITY
# ============================================================

elif page == "👨‍⚕️ Doctor Availability":

    st.header("👨‍⚕️ Doctor Availability")

    tab1, tab2 = st.tabs(["➕ Add Doctor", "🔎 Manage Doctors"])

    with tab1:

        with st.form("add_doctor_form"):
            hospital_name = st.text_input("Hospital Name")
            doctor_name = st.text_input("Doctor Name")
            department = st.text_input("Department")
            specialization = st.text_input("Specialization")

            status = st.selectbox(
                "Availability Status",
                ["Available", "Busy", "Unavailable"]
            )

            c1, c2 = st.columns(2)

            with c1:
                available_from = st.text_input(
                    "Available From",
                    value="09:00"
                )

            with c2:
                available_to = st.text_input(
                    "Available To",
                    value="17:00"
                )

            submitted = st.form_submit_button(
                "Add Doctor",
                width="stretch"
            )

            if submitted:

                if not hospital_name.strip() or not doctor_name.strip():
                    st.error(
                        "Hospital name and doctor name are required."
                    )
                else:
                    conn = get_connection()

                    conn.execute(
                        """ INSERT INTO doctors ( hospital_name, doctor_name, department, specialization, availability_status, available_from, available_to, last_updated ) VALUES (?, ?, ?, ?, ?, ?, ?, ?) """,
                        (
                            hospital_name.strip(),
                            doctor_name.strip(),
                            department.strip(),
                            specialization.strip(),
                            status,
                            available_from.strip(),
                            available_to.strip(),
                            datetime.now().isoformat(timespec="seconds")
                        )
                    )

                    conn.commit()
                    conn.close()

                    st.success("Doctor added successfully.")
                    st.rerun()

    with tab2:

        conn = get_connection()

        doctors = pd.read_sql_query(
            "SELECT * FROM doctors ORDER BY doctor_name",
            conn
        )

        conn.close()

        if doctors.empty:
            st.info("No doctors have been added yet.")
        else:

            search = st.text_input(
                "Search Doctor / Hospital"
            )

            if search.strip():
                doctors = doctors[
                    doctors["doctor_name"].str.contains(
                        search,
                        case=False,
                        na=False
                    )
                    |
                    doctors["hospital_name"].str.contains(
                        search,
                        case=False,
                        na=False
                    )
                ]

            st.dataframe(
                doctors,
                use_container_width=True,
                hide_index=True
            )


# ============================================================
# EQUIPMENT AVAILABILITY
# ============================================================

elif page == "🩺 Equipment Availability":

    st.header("🩺 Equipment Availability")

    tab1, tab2 = st.tabs(
        ["➕ Add Equipment", "🔎 View Equipment"]
    )

    with tab1:

        with st.form("add_equipment_form"):

            hospital_name = st.text_input(
                "Hospital Name"
            )

            equipment_name = st.text_input(
                "Equipment Name",
                placeholder="e.g. Ventilator"
            )

            c1, c2 = st.columns(2)

            with c1:
                total_units = st.number_input(
                    "Total Units",
                    min_value=0,
                    step=1
                )

            with c2:
                available_units = st.number_input(
                    "Available Units",
                    min_value=0,
                    step=1
                )

            submitted = st.form_submit_button(
                "Add Equipment",
                width="stretch"
            )

            if submitted:

                if not hospital_name.strip() or not equipment_name.strip():
                    st.error(
                        "Hospital name and equipment name are required."
                    )

                elif available_units > total_units:
                    st.error(
                        "Available units cannot exceed total units."
                    )

                else:
                    conn = get_connection()

                    conn.execute(
                        """ INSERT INTO equipment ( hospital_name, equipment_name, total_units, available_units, last_updated ) VALUES (?, ?, ?, ?, ?) """,
                        (
                            hospital_name.strip(),
                            equipment_name.strip(),
                            int(total_units),
                            int(available_units),
                            datetime.now().isoformat(timespec="seconds")
                        )
                    )

                    conn.commit()
                    conn.close()

                    st.success("Equipment added successfully.")
                    st.rerun()

    with tab2:

        conn = get_connection()

        equipment = pd.read_sql_query(
            "SELECT * FROM equipment ORDER BY equipment_name",
            conn
        )

        conn.close()

        if equipment.empty:
            st.info("No equipment has been added yet.")
        else:

            equipment["status"] = equipment.apply(
                lambda row: (
                    "🔴 Unavailable"
                    if safe_int(row["available_units"]) == 0
                    else (
                        "🟡 Low"
                        if (
                            safe_int(row["total_units"]) > 0
                            and safe_int(row["available_units"])
                            / safe_int(row["total_units"]) <= 0.30
                        )
                        else "🟢 Available"
                    )
                ),
                axis=1
            )

            st.dataframe(
                equipment,
                use_container_width=True,
                hide_index=True
            )


# ============================================================
# RESERVATION MANAGEMENT
# ============================================================

elif page == "📋 Reservation Management":

    st.header("📋 Reservation Management")

    with st.form("reservation_form"):

        c1, c2 = st.columns(2)

        with c1:
            patient_name = st.text_input("Patient Name")
            phone = st.text_input("Phone Number")
            hospital_name = st.text_input("Hospital Name")
            reservation_type = st.selectbox(
                "Reservation Type",
                [
                    "Bed",
                    "Doctor Appointment",
                    "Equipment",
                    "Other"
                ]
            )

        with c2:
            department = st.text_input("Department")
            doctor_name = st.text_input("Doctor Name")
            equipment_name = st.text_input("Equipment Name")
            reservation_date = st.date_input(
                "Date",
                min_value=date.today()
            )
            reservation_time = st.text_input(
                "Time",
                value="10:00"
            )

        notes = st.text_area("Notes")

        submitted = st.form_submit_button(
            "Create Reservation",
            width="stretch"
        )

        if submitted:

            if not patient_name.strip() or not hospital_name.strip():
                st.error(
                    "Patient name and hospital name are required."
                )
            else:

                conn = get_connection()

                conn.execute(
                    """ INSERT INTO reservations ( patient_name, phone, hospital_name, reservation_type, department, doctor_name, equipment_name, reservation_date, reservation_time, notes, status, created_at ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) """,
                    (
                        patient_name.strip(),
                        phone.strip(),
                        hospital_name.strip(),
                        reservation_type,
                        department.strip(),
                        doctor_name.strip(),
                        equipment_name.strip(),
                        str(reservation_date),
                        reservation_time.strip(),
                        notes.strip(),
                        "Pending",
                        datetime.now().isoformat(timespec="seconds")
                    )
                )

                conn.commit()
                conn.close()

                st.success("Reservation request created.")
                st.rerun()

    st.markdown("---")

    conn = get_connection()

    reservations = pd.read_sql_query(
        "SELECT * FROM reservations ORDER BY reservation_id DESC",
        conn
    )

    conn.close()

    if reservations.empty:
        st.info("No reservation requests yet.")
    else:
        st.dataframe(
            reservations,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

elif page == "📊 Admin Dashboard":

    st.header("📊 Admin Dashboard")

    conn = get_connection()

    doctors_count = conn.execute(
        "SELECT COUNT(*) FROM doctors"
    ).fetchone()[0]

    equipment_count = conn.execute(
        "SELECT COUNT(*) FROM equipment"
    ).fetchone()[0]

    reservations_count = conn.execute(
        "SELECT COUNT(*) FROM reservations"
    ).fetchone()[0]

    pending_count = conn.execute(
        "SELECT COUNT(*) FROM reservations WHERE status='Pending'"
    ).fetchone()[0]

    conn.close()

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "🏥 Hospitals",
            f"{len(hospitals):,}"
        )

    with c2:
        st.metric(
            "👨‍⚕️ Doctors",
            f"{doctors_count:,}"
        )

    with c3:
        st.metric(
            "🩺 Equipment Records",
            f"{equipment_count:,}"
        )

    with c4:
        st.metric(
            "📋 Reservations",
            f"{reservations_count:,}"
        )

    st.markdown("---")

    st.subheader("📋 Reservation Summary")

    r1, r2 = st.columns(2)

    with r1:
        st.metric(
            "Pending Reservations",
            f"{pending_count:,}"
        )

    with r2:
        st.metric(
            "Mapped Hospitals",
            f"{hospitals['latitude'].notna().sum():,}"
        )

    st.info(
        "The dashboard summarizes records currently stored in the "
        "application database and hospital directory."
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "🏥 Smart Hospital Bed Availability System | "
    "Streamlit + SQLite + Hospital Directory + Interactive Map"
    )
