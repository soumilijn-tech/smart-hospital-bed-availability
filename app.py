# ============================================================
# SMART HOSPITAL BED AVAILABILITY SYSTEM
# ============================================================

import streamlit as st
import pandas as pd
import sqlite3
import math
from pathlib import Path


# ============================================================
# PAGE CONFIGURATION
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
# TITLE
# ============================================================

st.title("🏥 Smart Hospital Bed Availability System")

st.write(
    "Find hospitals, check bed availability, and identify hospitals "
    "based on current resource availability."
)


# ============================================================
# LOAD HOSPITAL DIRECTORY CSV
# ============================================================

@st.cache_data
def load_hospital_directory():

    if not CSV_PATH.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(CSV_PATH, low_memory=False)

        # Normalize column names
        df.columns = (
            df.columns
            .astype(str)
            .str.strip()
            .str.lower()
            .str.replace(" ", "_")
        )

        return df

    except Exception as e:
        st.error(f"Unable to load hospital directory: {e}")
        return pd.DataFrame()


hospital_directory = load_hospital_directory()


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    return sqlite3.connect(DB_PATH)


# ============================================================
# FIND COLUMN FROM POSSIBLE COLUMN NAMES
# ============================================================

def find_column(df, possible_names):

    for name in possible_names:

        if name in df.columns:
            return name

    return None


# ============================================================
# BED RESOURCE STATUS
# ============================================================

def get_bed_status(total_beds, available_beds):

    try:
        total_beds = float(total_beds)
        available_beds = float(available_beds)

    except Exception:
        return "⚪ Unknown"

    if total_beds <= 0:
        return "⚪ Unknown"

    if available_beds <= 0:
        return "🔴 Full"

    percentage = (available_beds / total_beds) * 100

    if percentage <= 15:
        return "🟠 Critical"

    elif percentage <= 30:
        return "🟡 Low"

    else:
        return "🟢 Available"


# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def haversine_distance(lat1, lon1, lat2, lon2):

    try:

        lat1 = float(lat1)
        lon1 = float(lon1)
        lat2 = float(lat2)
        lon2 = float(lon2)

        radius = 6371

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )

        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return radius * c

    except Exception:
        return None


# ============================================================
# GET BED DATA FROM DATABASE
# ============================================================

def get_hospital_bed_data():

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

        table_names = tables["name"].tolist()

        if "hospitals" not in table_names:

            conn.close()

            return pd.DataFrame()

        hospitals = pd.read_sql_query(
            "SELECT * FROM hospitals",
            conn
        )

        if "beds" in table_names:

            beds = pd.read_sql_query(
                "SELECT * FROM beds",
                conn
            )

        else:

            beds = pd.DataFrame()

        conn.close()

        if hospitals.empty:

            return pd.DataFrame()

        # ----------------------------------------------------
        # Find hospital columns
        # ----------------------------------------------------

        hospital_id_col = find_column(
            hospitals,
            [
                "id",
                "hospital_id",
                "hospitalid"
            ]
        )

        name_col = find_column(
            hospitals,
            [
                "name",
                "hospital_name",
                "hospital"
            ]
        )

        address_col = find_column(
            hospitals,
            [
                "address",
                "location"
            ]
        )

        phone_col = find_column(
            hospitals,
            [
                "phone",
                "phone_number",
                "contact",
                "contact_number"
            ]
        )

        # ----------------------------------------------------
        # Rename hospital columns
        # ----------------------------------------------------

        result = hospitals.copy()

        if hospital_id_col:
            result = result.rename(
                columns={hospital_id_col: "hospital_id"}
            )

        else:

            result["hospital_id"] = range(
                1,
                len(result) + 1
            )

        if name_col:
            result = result.rename(
                columns={name_col: "hospital_name"}
            )

        else:

            result["hospital_name"] = "Hospital"

        if address_col:
            result = result.rename(
                columns={address_col: "address"}
            )

        else:

            result["address"] = "Address not available"

        if phone_col:
            result = result.rename(
                columns={phone_col: "phone"}
            )

        else:

            result["phone"] = "Not available"

        # ----------------------------------------------------
        # Process bed table
        # ----------------------------------------------------

        if not beds.empty:

            bed_hospital_id = find_column(
                beds,
                [
                    "hospital_id",
                    "hospitalid",
                    "hospital"
                ]
            )

            total_col = find_column(
                beds,
                [
                    "total_beds",
                    "total_bed",
                    "total"
                ]
            )

            available_col = find_column(
                beds,
                [
                    "available_beds",
                    "available_bed",
                    "available"
                ]
            )

            if bed_hospital_id and total_col and available_col:

                beds = beds.copy()

                beds[total_col] = pd.to_numeric(
                    beds[total_col],
                    errors="coerce"
                ).fillna(0)

                beds[available_col] = pd.to_numeric(
                    beds[available_col],
                    errors="coerce"
                ).fillna(0)

                bed_summary = (
                    beds
                    .groupby(bed_hospital_id)
                    .agg(
                        total_beds=(total_col, "sum"),
                        available_beds=(available_col, "sum")
                    )
                    .reset_index()
                )

                bed_summary = bed_summary.rename(
                    columns={
                        bed_hospital_id: "hospital_id"
                    }
                )

                result["hospital_id"] = result[
                    "hospital_id"
                ].astype(str)

                bed_summary["hospital_id"] = bed_summary[
                    "hospital_id"
                ].astype(str)

                result = result.merge(
                    bed_summary,
                    on="hospital_id",
                    how="left"
                )

            else:

                result["total_beds"] = 0
                result["available_beds"] = 0

        else:

            result["total_beds"] = 0
            result["available_beds"] = 0

        result["total_beds"] = pd.to_numeric(
            result["total_beds"],
            errors="coerce"
        ).fillna(0)

        result["available_beds"] = pd.to_numeric(
            result["available_beds"],
            errors="coerce"
        ).fillna(0)

        result["occupied_beds"] = (
            result["total_beds"]
            - result["available_beds"]
        ).clip(lower=0)

        result["occupancy_percent"] = 0.0

        mask = result["total_beds"] > 0

        result.loc[mask, "occupancy_percent"] = (
            result.loc[mask, "occupied_beds"]
            / result.loc[mask, "total_beds"]
            * 100
        )

        result["status"] = result.apply(
            lambda row: get_bed_status(
                row["total_beds"],
                row["available_beds"]
            ),
            axis=1
        )

        return result

    except Exception as e:

        st.warning(
            f"Bed database could not be loaded: {e}"
        )

        return pd.DataFrame()


# ============================================================
# QUICK ACCESS
# ============================================================

st.subheader("🚀 Quick Access")

col1, col2, col3, col4 = st.columns(4)


with col1:

    if st.button(
        "👤 Patient Login",
        width="stretch"
    ):

        try:
            st.switch_page("pages/patient_login.py")

        except Exception:
            st.info(
                "Patient login page is not available yet."
            )


with col2:

    if st.button(
        "📝 Patient Register",
        width="stretch"
    ):

        try:
            st.switch_page("pages/patient_register.py")

        except Exception:
            st.info(
                "Patient registration page is not available yet."
            )


with col3:

    if st.button(
        "🔐 Admin Login",
        width="stretch"
    ):

        try:
            st.switch_page("pages/admin_login.py")

        except Exception:
            st.info(
                "Admin login page is not available yet."
            )


with col4:

    if st.button(
        "📊 Patient Dashboard",
        width="stretch"
    ):

        try:
            st.switch_page("pages/patient_dashboard.py")

        except Exception:
            st.info(
                "Patient dashboard is not available yet."
            )


st.divider()


# ============================================================
# HOSPITAL SEARCH
# ============================================================

st.header("🔎 Find Hospitals")

if hospital_directory.empty:

    st.warning(
        "hospital_directory.csv was not found. "
        "Please keep it in the same folder as app.py."
    )

else:

    search_text = st.text_input(
        "Search hospital",
        placeholder="Hospital name, state, district or address"
    )

    search_button = st.button(
        "🔍 Search Hospitals",
        width="stretch"
    )

    if search_button:

        if not search_text.strip():

            st.warning(
                "Please enter a hospital name, state, district or address."
            )

        else:

            query = search_text.strip().lower()

            searchable_columns = [
                "hospital_name",
                "state",
                "district",
                "address"
            ]

            available_columns = [
                col
                for col in searchable_columns
                if col in hospital_directory.columns
            ]

            if available_columns:

                mask = pd.Series(
                    False,
                    index=hospital_directory.index
                )

                for col in available_columns:

                    mask = (
                        mask
                        | hospital_directory[col]
                        .astype(str)
                        .str.lower()
                        .str.contains(
                            query,
                            na=False
                        )
                    )

                search_results = hospital_directory[
                    mask
                ].copy()

            else:

                search_results = pd.DataFrame()

            if search_results.empty:

                st.info(
                    "No hospitals found for your search."
                )

            else:

                st.success(
                    f"{len(search_results)} hospital(s) found."
                )

                st.dataframe(
                    search_results.head(100),
                    width="stretch",
                    hide_index=True
                )


st.divider()


# ============================================================
# BED AVAILABILITY
# ============================================================

st.header("🛏️ Current Bed Availability")

refresh = st.button(
    "🔄 Refresh Bed Data",
    width="stretch"
)

if refresh:

    st.cache_data.clear()
    st.rerun()


bed_df = get_hospital_bed_data()


if bed_df.empty:

    st.info(
        "No registered hospital bed data is currently available."
    )

else:

    # --------------------------------------------------------
    # OVERALL METRICS
    # --------------------------------------------------------

    total_beds = int(
        bed_df["total_beds"].sum()
    )

    available_beds = int(
        bed_df["available_beds"].sum()
    )

    occupied_beds = int(
        bed_df["occupied_beds"].sum()
    )

    if total_beds > 0:

        occupancy = (
            occupied_beds
            / total_beds
            * 100
        )

    else:

        occupancy = 0

    m1, m2, m3, m4 = st.columns(4)

    with m1:

        st.metric(
            "🛏️ Total Beds",
            f"{total_beds:,}"
        )

    with m2:

        st.metric(
            "🟢 Available Beds",
            f"{available_beds:,}"
        )

    with m3:

        st.metric(
            "🔴 Occupied Beds",
            f"{occupied_beds:,}"
        )

    with m4:

        st.metric(
            "📊 Occupancy",
            f"{occupancy:.1f}%"
        )

    st.subheader("🏥 Hospital Resource Status")

    # --------------------------------------------------------
    # HOSPITAL CARDS
    # --------------------------------------------------------

    for _, row in bed_df.iterrows():

        name = str(
            row.get(
                "hospital_name",
                "Hospital"
            )
        )

        total = int(
            row.get(
                "total_beds",
                0
            )
        )

        available = int(
            row.get(
                "available_beds",
                0
            )
        )

        occupied = int(
            row.get(
                "occupied_beds",
                0
            )
        )

        occupancy_value = float(
            row.get(
                "occupancy_percent",
                0
            )
        )

        status = row.get(
            "status",
            "⚪ Unknown"
        )

        address = row.get(
            "address",
            "Address not available"
        )

        phone = row.get(
            "phone",
            "Not available"
        )

        with st.expander(
            f"🏥 {name} — {status}"
        ):

            c1, c2, c3, c4 = st.columns(4)

            with c1:

                st.metric(
                    "Total Beds",
                    total
                )

            with c2:

                st.metric(
                    "Available",
                    available
                )

            with c3:

                st.metric(
                    "Occupied",
                    occupied
                )

            with c4:

                st.metric(
                    "Occupancy",
                    f"{occupancy_value:.1f}%"
                )

            st.write(
                f"**Resource Status:** {status}"
            )

            st.write(
                f"📍 **Address:** {address}"
            )

            st.write(
                f"📞 **Phone:** {phone}"
            )


st.divider()


# ============================================================
# RESOURCE STATUS GUIDE
# ============================================================

st.header("📌 Bed Resource Status")

guide1, guide2, guide3, guide4 = st.columns(4)

with guide1:
    st.success(
        "🟢 Available\n\n"
        "More than 30% beds available"
    )

with guide2:
    st.warning(
        "🟡 Low\n\n"
        "15–30% beds available"
    )

with guide3:
    st.warning(
        "🟠 Critical\n\n"
        "1–15% beds available"
    )

with guide4:
    st.error(
        "🔴 Full\n\n"
        "No beds available"
    )


# ============================================================
# SYSTEM INFORMATION
# ============================================================

st.divider()

st.header("ℹ️ System Information")

st.write(
    """
    **Current modules:**

    - 🏥 Hospital Directory
    - 🔎 Hospital Search
    - 🛏️ Bed Availability
    - 📊 Occupancy Calculation
    - 🚦 Bed Resource Status
    - 👤 Patient Login
    - 📝 Patient Registration
    - 🔐 Admin Login
    - 📊 Patient Dashboard

    **Planned advanced modules:**

    - 👨‍⚕️ Doctor Availability
    - 🩺 Equipment Availability
    - 🚑 Emergency Requirement Search
    - 🔗 Hospital Matching Engine
    - ✅ Hospital Confirmation
    - 📅 Bed Reservation
    - 🔄 Improved Real-time Updates
    - 🤖 ML-based Bed Availability Prediction
    """
)


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "🏥 Smart Hospital Bed Availability System | "
    "Academic/Project Prototype"
)

st.caption(
    "Bed availability shown by this application depends on "
    "the registered/demo hospital data available in the system."
            )
