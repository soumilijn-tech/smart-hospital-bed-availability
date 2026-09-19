import math
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Smart Hospital Bed Availability System",
    page_icon="🏥",
    layout="wide"
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

CSV_PATH = BASE_DIR / "hospital_directory.csv"
DB_PATH = BASE_DIR / "database" / "hospital.db"


# ============================================================
# HEADER
# ============================================================

st.title("🏥 Smart Hospital Bed Availability System")

st.caption(
    "Find hospitals across India and view registered bed availability."
)


# ============================================================
# SAFE TEXT
# ============================================================

def safe_text(value, default="Not available"):

    if value is None:
        return default

    try:
        text = str(value).strip()

        if text and text.lower() not in {
            "nan",
            "none",
            "null"
        }:
            return text

    except Exception:
        pass

    return default


# ============================================================
# LOAD HOSPITAL DIRECTORY
# ============================================================

@st.cache_data(show_spinner=False)
def load_hospital_directory():

    if not CSV_PATH.exists():
        return pd.DataFrame()

    for encoding in (
        "utf-8",
        "utf-8-sig",
        "latin1"
    ):

        try:

            df = pd.read_csv(
                CSV_PATH,
                encoding=encoding,
                low_memory=False
            )

            df.columns = (
                df.columns
                .astype(str)
                .str.strip()
                .str.lower()
                .str.replace(
                    r"[^a-z0-9]+",
                    "_",
                    regex=True
                )
                .str.strip("_")
            )

            return df

        except Exception:
            continue

    return pd.DataFrame()


# ============================================================
# FIND COLUMN
# ============================================================

def find_column(df, names):

    if df is None or df.empty:
        return None

    for name in names:

        if name in df.columns:
            return name

    return None


# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def haversine(
    lat1,
    lon1,
    lat2,
    lon2
):

    try:

        lat1, lon1, lat2, lon2 = map(
            float,
            (
                lat1,
                lon1,
                lat2,
                lon2
            )
        )

        radius = 6371.0

        dlat = math.radians(
            lat2 - lat1
        )

        dlon = math.radians(
            lon2 - lon1
        )

        a = (
            math.sin(dlat / 2) ** 2
            +
            math.cos(math.radians(lat1))
            *
            math.cos(math.radians(lat2))
            *
            math.sin(dlon / 2) ** 2
        )

        return (
            radius
            * 2
            * math.atan2(
                math.sqrt(a),
                math.sqrt(1 - a)
            )
        )

    except Exception:

        return None


# ============================================================
# SEARCH HOSPITALS
# ============================================================

def search_hospitals(
    query,
    radius_km=None,
    user_lat=None,
    user_lon=None
):

    df = load_hospital_directory()

    if df.empty:
        return []

    query = safe_text(
        query,
        ""
    ).lower()

    if not query:
        return []

    name_col = find_column(
        df,
        [
            "hospital_name",
            "hospitalname",
            "hospital",
            "name"
        ]
    )

    state_col = find_column(
        df,
        [
            "state",
            "state_name"
        ]
    )

    district_col = find_column(
        df,
        [
            "district",
            "district_name"
        ]
    )

    address_col = find_column(
        df,
        [
            "address",
            "hospital_address",
            "location",
            "hospital_location"
        ]
    )

    phone_col = find_column(
        df,
        [
            "phone",
            "telephone",
            "telephone_no",
            "mobile",
            "contact_number",
            "contact"
        ]
    )

    lat_col = find_column(
        df,
        [
            "latitude",
            "lat"
        ]
    )

    lon_col = find_column(
        df,
        [
            "longitude",
            "lon",
            "lng"
        ]
    )

    if name_col is None:
        return []

    mask = pd.Series(
        False,
        index=df.index
    )

    search_columns = [
        name_col,
        state_col,
        district_col,
        address_col
    ]

    for col in search_columns:

        if col is None:
            continue

        try:

            values = (
                df[col]
                .fillna("")
                .astype(str)
                .str.lower()
            )

            mask |= values.str.contains(
                query,
                regex=False,
                na=False
            )

        except Exception:
            pass

    results = df.loc[mask].copy()

    if results.empty:
        return []

    hospitals = []

    for _, row in results.iterrows():

        try:

            lat = None
            lon = None

            if lat_col:

                try:
                    lat = float(
                        row[lat_col]
                    )
                except Exception:
                    pass

            if lon_col:

                try:
                    lon = float(
                        row[lon_col]
                    )
                except Exception:
                    pass

            distance = None

            if (
                user_lat is not None
                and user_lon is not None
                and lat is not None
                and lon is not None
            ):

                distance = haversine(
                    user_lat,
                    user_lon,
                    lat,
                    lon
                )

            hospitals.append(
                {
                    "name": safe_text(
                        row[name_col]
                    ),
                    "address": (
                        safe_text(
                            row[address_col]
                        )
                        if address_col
                        else "Not available"
                    ),
                    "phone": (
                        safe_text(
                            row[phone_col]
                        )
                        if phone_col
                        else "Not available"
                    ),
                    "state": (
                        safe_text(
                            row[state_col],
                            ""
                        )
                        if state_col
                        else ""
                    ),
                    "district": (
                        safe_text(
                            row[district_col],
                            ""
                        )
                        if district_col
                        else ""
                    ),
                    "latitude": lat,
                    "longitude": lon,
                    "distance": distance
                }
            )

        except Exception:
            continue

    if (
        radius_km is not None
        and user_lat is not None
        and user_lon is not None
    ):

        hospitals = [
            h
            for h in hospitals
            if (
                h["distance"] is None
                or h["distance"] <= radius_km
            )
        ]

        hospitals.sort(
            key=lambda h:
                h["distance"]
                if h["distance"] is not None
                else float("inf")
        )

    return hospitals[:50]


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():

    if not DB_PATH.exists():
        return None

    try:

        return sqlite3.connect(
            DB_PATH,
            timeout=10
        )

    except Exception:

        return None


# ============================================================
# READ DATABASE TABLE
# ============================================================

def table_df(
    conn,
    table_name
):

    try:

        return pd.read_sql_query(
            f'SELECT * FROM "{table_name}"',
            conn
        )

    except Exception:

        return pd.DataFrame()


# ============================================================
# FIND DATABASE COLUMN
# ============================================================

def first_column(
    df,
    names
):

    if df.empty:
        return None

    lower_map = {
        str(c).strip().lower(): c
        for c in df.columns
    }

    for name in names:

        if name in lower_map:
            return lower_map[name]

    return None


# ============================================================
# GET HOSPITAL BED DATA
# ============================================================

def get_hospital_data():

    conn = get_connection()

    if conn is None:
        return pd.DataFrame()

    try:

        hospitals = table_df(
            conn,
            "hospitals"
        )

        beds = table_df(
            conn,
            "beds"
        )

    finally:

        conn.close()

    if hospitals.empty or beds.empty:
        return pd.DataFrame()

    hospital_id = first_column(
        hospitals,
        [
            "id",
            "hospital_id",
            "hospitalid"
        ]
    )

    hospital_name = first_column(
        hospitals,
        [
            "name",
            "hospital_name",
            "hospitalname"
        ]
    )

    hospital_address = first_column(
        hospitals,
        [
            "address",
            "hospital_address"
        ]
    )

    hospital_phone = first_column(
        hospitals,
        [
            "phone",
            "telephone",
            "contact",
            "contact_number"
        ]
    )

    bed_hospital_id = first_column(
        beds,
        [
            "hospital_id",
            "hospitalid",
            "h_id"
        ]
    )

    total_beds = first_column(
        beds,
        [
            "total_beds",
            "total_bed",
            "beds"
        ]
    )

    available_beds = first_column(
        beds,
        [
            "available_beds",
            "available_bed",
            "available"
        ]
    )

    if (
        hospital_id is None
        or hospital_name is None
        or bed_hospital_id is None
        or total_beds is None
        or available_beds is None
    ):

        return pd.DataFrame()

    beds[total_beds] = pd.to_numeric(
        beds[total_beds],
        errors="coerce"
    ).fillna(0)

    beds[available_beds] = pd.to_numeric(
        beds[available_beds],
        errors="coerce"
    ).fillna(0)

    summary = (
        beds
        .groupby(
            bed_hospital_id,
            dropna=False
        )
        .agg(
            total_beds=(
                total_beds,
                "sum"
            ),
            available_beds=(
                available_beds,
                "sum"
            )
        )
        .reset_index()
    )

    summary = summary.rename(
        columns={
            bed_hospital_id:
                "hospital_key"
        }
    )

    hospitals = hospitals.copy()

    hospitals["hospital_key"] = (
        hospitals[hospital_id]
        .astype(str)
    )

    summary["hospital_key"] = (
        summary["hospital_key"]
        .astype(str)
    )

    selected_columns = [
        "hospital_key",
        hospital_name
    ]

    if hospital_address is not None:

        selected_columns.append(
            hospital_address
        )

    if hospital_phone is not None:

        selected_columns.append(
            hospital_phone
        )

    hospital_info = hospitals[
        selected_columns
    ]

    result = hospital_info.merge(
        summary,
        on="hospital_key",
        how="inner"
    )

    result = result.rename(
        columns={
            hospital_name: "name"
        }
    )

    if hospital_address is not None:

        result = result.rename(
            columns={
                hospital_address:
                    "address"
            }
        )

    else:

        result["address"] = (
            "Not available"
        )

    if hospital_phone is not None:

        result = result.rename(
            columns={
                hospital_phone:
                    "phone"
            }
        )

    else:

        result["phone"] = (
            "Not available"
        )

    return result[
        [
            "name",
            "address",
            "phone",
            "total_beds",
            "available_beds"
        ]
    ]


# ============================================================
# QUICK ACCESS
# ============================================================

st.subheader("🔐 Quick Access")

col1, col2, col3, col4 = st.columns(4)

with col1:

    if st.button(
        "👤 Patient Login",
        width="stretch"
    ):

        try:

            st.switch_page(
                "pages/patient_login.py"
            )

        except Exception as e:

            st.error(
                f"Patient login page not available: {e}"
            )


with col2:

    if st.button(
        "📝 Patient Register",
        width="stretch"
    ):

        try:

            st.switch_page(
                "pages/patient_register.py"
            )

        except Exception as e:

            st.error(
                f"Patient register page not available: {e}"
            )


with col3:

    if st.button(
        "🛠️ Admin Login",
        width="stretch"
    ):

        try:

            st.switch_page(
                "pages/admin_login.py"
            )

        except Exception as e:

            st.error(
                f"Admin login page not available: {e}"
            )


with col4:

    if st.button(
        "📊 Patient Dashboard",
        width="stretch"
    ):

        try:

            st.switch_page(
                "pages/patient_dashboard.py"
            )

        except Exception as e:

            st.error(
                f"Patient dashboard page not available: {e}"
            )


st.divider()


# ============================================================
# HOSPITAL SEARCH
# ============================================================

st.subheader("🔎 Find Hospitals")

location = st.text_input(
    "Enter city, district, state or hospital name",
    placeholder="Example: Kolkata"
)

radius = st.slider(
    "Search Radius (KM)",
    1,
    100,
    10
)


if st.button(
    "🔍 Search Hospitals",
    type="primary",
    width="stretch"
):

    with st.spinner(
        "Searching hospital directory..."
    ):

        results = search_hospitals(
            location,
            radius_km=radius
        )

    if not results:

        if not CSV_PATH.exists():

            st.error(
                f"hospital_directory.csv was not found at: {CSV_PATH}"
            )

        else:

            st.warning(
                "No matching hospitals found. "
                "Try a city, district, state or hospital name."
            )

    else:

        st.success(
            f"Found {len(results)} hospital(s)."
        )

        map_rows = []

        for hospital in results:

            lat = hospital["latitude"]
            lon = hospital["longitude"]

            if (
                lat is not None
                and lon is not None
            ):

                map_rows.append(
                    {
                        "latitude": lat,
                        "longitude": lon
                    }
                )

            with st.container(
                border=True
            ):

                st.markdown(
                    f"### 🏥 {hospital['name']}"
                )

                st.write(
                    f"📍 **Address:** "
                    f"{hospital['address']}"
                )

                st.write(
                    f"📞 **Phone:** "
                    f"{hospital['phone']}"
                )

                if (
                    hospital["state"]
                    or hospital["district"]
                ):

                    st.write(
                        f"🗺️ **Location:** "
                        f"{hospital['district']}, "
                        f"{hospital['state']}"
                    )

                if (
                    hospital["distance"]
                    is not None
                ):

                    st.write(
                        f"📏 **Distance:** "
                        f"{hospital['distance']:.2f} km"
                    )

                if (
                    lat is not None
                    and lon is not None
                ):

                    maps_url = (
                        "https://www.google.com/maps/dir/"
                        "?api=1"
                        f"&destination={lat},{lon}"
                    )

                    st.link_button(
                        "🧭 Get Directions",
                        maps_url,
                        width="stretch"
                    )

        if map_rows:

            st.subheader(
                "🗺️ Hospital Map"
            )

            st.map(
                pd.DataFrame(map_rows),
                latitude="latitude",
                longitude="longitude"
            )


st.divider()


# ============================================================
# BED AVAILABILITY
# ============================================================

st.subheader(
    "🛏️ Registered Hospital Bed Availability"
)


if st.button(
    "🔄 Refresh Bed Data",
    width="stretch"
):

    st.rerun()


bed_df = get_hospital_data()


if bed_df.empty:

    if not DB_PATH.exists():

        st.info(
            "No hospital database found yet. "
            "Directory search is still available."
        )

    else:

        st.info(
            "No compatible registered hospital "
            "bed data is available in the database yet."
        )

else:

    total_beds = int(
        pd.to_numeric(
            bed_df["total_beds"],
            errors="coerce"
        )
        .fillna(0)
        .sum()
    )

    available_beds = int(
        pd.to_numeric(
            bed_df["available_beds"],
            errors="coerce"
        )
        .fillna(0)
        .sum()
    )

    occupied_beds = max(
        total_beds - available_beds,
        0
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

    for _, row in bed_df.iterrows():

        available = int(
            row["available_beds"]
        )

        total = int(
            row["total_beds"]
        )

        if available == 0:

            status = (
                "🔴 No bed available"
            )

        elif available <= 2:

            status = (
                "🟠 Low availability"
            )

        else:

            status = (
                "🟢 Available"
            )

        with st.container(
            border=True
        ):

            st.markdown(
                f"### 🏥 {safe_text(row['name'])}"
            )

            st.write(
                f"📍 {safe_text(row['address'])}"
            )

            st.write(
                f"📞 {safe_text(row['phone'])}"
            )

            st.write(
                f"🛏️ **{available} / {total} "
                f"beds available**"
            )

            st.write(status)


st.divider()


# ============================================================
# SYSTEM INFORMATION
# ============================================================

with st.expander(
    "ℹ️ System Information"
):

    st.write(
        f"**Hospital directory:** "
        f"{CSV_PATH.name}"
    )

    st.write(
        f"**Directory available:** "
        f"{'Yes' if CSV_PATH.exists() else 'No'}"
    )

    st.write(
        f"**Database available:** "
        f"{'Yes' if DB_PATH.exists() else 'No'}"
    )

    directory_df = (
        load_hospital_directory()
    )

    if not directory_df.empty:

        st.write(
            f"**Hospital directory records:** "
            f"{len(directory_df):,}"
        )

    st.caption(
        "Hospital directory information is for "
        "informational/search purposes. "
        "Bed availability shown in the registered "
        "section comes from the application's database."
    )


st.caption(
    "© Smart Hospital Bed Availability System"
)
