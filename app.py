# ============================================================
# SMART HOSPITAL BED AVAILABILITY SYSTEM
# ROBUST VERSION
# ============================================================

import streamlit as st
import pandas as pd
import sqlite3
import math
from pathlib import Path


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

st.write(
    "Find hospitals, view hospital information and check "
    "registered bed availability."
)


# ============================================================
# SAFE CSV LOADER
# ============================================================

@st.cache_data
def load_hospital_directory():

    if not CSV_PATH.exists():
        return pd.DataFrame()

    encodings = [
        "utf-8",
        "utf-8-sig",
        "latin1"
    ]

    for encoding in encodings:

        try:

            df = pd.read_csv(
                CSV_PATH,
                encoding=encoding,
                low_memory=False
            )

            # Normalize column names
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
# COLUMN FINDER
# ============================================================

def find_column(df, possible_names):

    if df is None or df.empty:
        return None

    for name in possible_names:

        if name in df.columns:
            return name

    return None


# ============================================================
# SAFE TEXT
# ============================================================

def safe_text(value, default="Not available"):

    if value is None:
        return default

    try:

        text = str(value).strip()

        if text:
            return text

    except Exception:
        pass

    return default


# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def calculate_distance_km(
    lat1,
    lon1,
    lat2,
    lon2
):

    try:

        lat1 = float(lat1)
        lon1 = float(lon1)
        lat2 = float(lat2)
        lon2 = float(lon2)

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

        c = 2 * math.atan2(
            math.sqrt(a),
            math.sqrt(1 - a)
        )

        return radius * c

    except Exception:

        return None


# ============================================================
# SEARCH HOSPITALS FROM CSV
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

    # --------------------------------------------------------
    # Find columns automatically
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Create search mask
    # --------------------------------------------------------

    mask = pd.Series(
        False,
        index=df.index
    )

    search_columns = []

    if name_col:
        search_columns.append(name_col)

    if state_col:
        search_columns.append(state_col)

    if district_col:
        search_columns.append(district_col)

    if address_col:
        search_columns.append(address_col)

    for col in search_columns:

        try:

            values = (
                df[col]
                .fillna("")
                .astype(str)
                .str.lower()
            )

            mask = (
                mask
                |
                values.str.contains(
                    query,
                    regex=False,
                    na=False
                )
            )

        except Exception:
            continue

    results = df[mask].copy()

    if results.empty:
        return []

    # --------------------------------------------------------
    # Build hospital list
    # --------------------------------------------------------

    hospitals = []

    for _, row in results.iterrows():

        try:

            name = safe_text(
                row[name_col]
            )

            address = (
                safe_text(
                    row[address_col]
                )
                if address_col
                else "Not available"
            )

            phone = (
                safe_text(
                    row[phone_col]
                )
                if phone_col
                else "Not available"
            )

            state = (
                safe_text(
                    row[state_col],
                    ""
                )
                if state_col
                else ""
            )

            district = (
                safe_text(
                    row[district_col],
                    ""
                )
                if district_col
                else ""
            )

            # ------------------------------------------------
            # Latitude
            # ------------------------------------------------

            lat = None

            if lat_col:

                try:

                    value = str(
                        row[lat_col]
                    ).strip()

                    if value:
                        lat = float(value)

                except Exception:
                    lat = None

            # ------------------------------------------------
            # Longitude
            # ------------------------------------------------

            lon = None

            if lon_col:

                try:

                    value = str(
                        row[lon_col]
                    ).strip()

                    if value:
                        lon = float(value)

                except Exception:
                    lon = None

            # ------------------------------------------------
            # Distance
            # ------------------------------------------------

            distance = None

            if (
                user_lat is not None
                and user_lon is not None
                and lat is not None
                and lon is not None
            ):

                distance = calculate_distance_km(
                    user_lat,
                    user_lon,
                    lat,
                    lon
                )

            hospitals.append(
                {
                    "name": name,
                    "address": address,
                    "phone": phone,
                    "state": state,
                    "district": district,
                    "latitude": lat,
                    "longitude": lon,
                    "distance": distance
                }
            )

        except Exception:
            continue

    # --------------------------------------------------------
    # Radius filtering
    # --------------------------------------------------------

    if (
        radius_km is not None
        and user_lat is not None
        and user_lon is not None
    ):

        hospitals_with_distance = [
            h
            for h in hospitals
            if h["distance"] is not None
        ]

        hospitals_without_distance = [
            h
            for h in hospitals
            if h["distance"] is None
        ]

        hospitals_with_distance = [
            h
            for h in hospitals_with_distance
            if h["distance"] <= radius_km
        ]

        hospitals_with_distance.sort(
            key=lambda x: x["distance"]
        )

        hospitals = (
            hospitals_with_distance
            + hospitals_without_distance
        )

    # --------------------------------------------------------
    # Limit results
    # --------------------------------------------------------

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
# GET TABLE COLUMNS
# ============================================================

def get_table_columns(
    conn,
    table_name
):

    try:

        info = pd.read_sql_query(
            f"PRAGMA table_info({table_name})",
            conn
        )

        if info.empty:
            return []

        return info["name"].tolist()

    except Exception:

        return []


# ============================================================
# GET BED DATA SAFELY
# ============================================================

def get_hospital_data():

    conn = get_connection()

    if conn is None:

        return pd.DataFrame()

    try:

        hospital_columns = get_table_columns(
            conn,
            "hospitals"
        )

        bed_columns = get_table_columns(
            conn,
            "beds"
        )

        if not hospital_columns:
            conn.close()
            return pd.DataFrame()

        if not bed_columns:
            conn.close()
            return pd.DataFrame()

        # ----------------------------------------------------
        # Hospital ID
        # ----------------------------------------------------

        hospital_id_col = None

        for col in [
            "id",
            "hospital_id",
            "hospitalid"
        ]:

            if col in hospital_columns:
                hospital_id_col = col
                break

        if hospital_id_col is None:

            conn.close()
            return pd.DataFrame()

        # ----------------------------------------------------
        # Hospital name
        # ----------------------------------------------------

        name_col = None

        for col in [
            "name",
            "hospital_name",
            "hospitalname"
        ]:

            if col in hospital_columns:
                name_col = col
                break

        if name_col is None:

            conn.close()
            return pd.DataFrame()

        # ----------------------------------------------------
        # Bed hospital ID
        # ----------------------------------------------------

        bed_hospital_id_col = None

        for col in [
            "hospital_id",
            "hospitalid",
            "id"
        ]:

            if col in bed_columns:
                bed_hospital_id_col = col
                break

        if bed_hospital_id_col is None:

            conn.close()
            return pd.DataFrame()

        # ----------------------------------------------------
        # Bed columns
        # ----------------------------------------------------

        total_beds_col = None

        for col in [
            "total_beds",
            "total_bed",
            "beds"
        ]:

            if col in bed_columns:
                total_beds_col = col
                break

        available_beds_col = None

        for col in [
            "available_beds",
            "available_bed",
            "available"
        ]:

            if col in bed_columns:
                available_beds_col = col
                break

        if (
            total_beds_col is None
            or available_beds_col is None
        ):

            conn.close()
            return pd.DataFrame()

        # ------------------------------------------------
