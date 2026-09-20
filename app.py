# ============================================================
# 🏥 SMART HOSPITAL BED AVAILABILITY SYSTEM
# Complete Integrated Version
# ============================================================

import streamlit as st
import pandas as pd
import sqlite3
import math
from pathlib import Path
from datetime import datetime

# Optional ML imports
try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error, r2_score
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False


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

DB_DIR = BASE_DIR / "database"
DB_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DB_DIR / "hospital.db"

ML_DATASET_PATH = BASE_DIR / "bed_availability_prediction_dataset.csv"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    return sqlite3.connect(DB_PATH)


# ============================================================
# INITIALIZE EXTRA TABLES
# ============================================================

def initialize_database():

    try:

        conn = get_connection()
        cursor = conn.cursor()

        # ----------------------------------------------------
        # Doctors
        # ----------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hospital_id INTEGER,
                doctor_name TEXT,
                department TEXT,
                available INTEGER DEFAULT 1,
                phone TEXT
            )
        """)

        # ----------------------------------------------------
        # Equipment
        # ----------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS equipment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hospital_id INTEGER,
                equipment_name TEXT,
                total_quantity INTEGER DEFAULT 0,
                available_quantity INTEGER DEFAULT 0
            )
        """)

        # ----------------------------------------------------
        # Reservations
        # ----------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hospital_id INTEGER,
                patient_name TEXT,
                patient_phone TEXT,
                bed_type TEXT,
                emergency_level TEXT,
                status TEXT DEFAULT 'Pending',
                created_at TEXT
            )
        """)

        conn.commit()
        conn.close()

    except Exception:
        pass


initialize_database()


# ============================================================
# PAGE TITLE
# ============================================================

st.title("🏥 Smart Hospital Bed Availability System")

st.write(
    "Find hospitals, check available resources, search emergency facilities, "
    "request beds, and view hospital resource information."
)


# ============================================================
# CSV LOADER
# ============================================================

@st.cache_data
def load_hospital_directory():

    if not CSV_PATH.exists():
        return pd.DataFrame()

    try:

        df = pd.read_csv(
            CSV_PATH,
            low_memory=False
        )

        df.columns = (
            df.columns
            .astype(str)
            .str.strip()
            .str.lower()
            .str.replace(" ", "_", regex=False)
        )

        return df

    except Exception as e:

        st.error(
            f"Hospital directory could not be loaded: {e}"
        )

        return pd.DataFrame()


hospital_directory = load_hospital_directory()


# ============================================================
# COLUMN FINDER
# ============================================================

def find_column(df, names):

    for name in names:

        if name in df.columns:
            return name

    return None


# ============================================================
# BED STATUS
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

    percentage = (
        available_beds /
        total_beds
    ) * 100

    if percentage <= 15:
        return "🟠 Critical"

    elif percentage <= 30:
        return "🟡 Low"

    else:
        return "🟢 Available"


# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def haversine_distance(
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

        radius = 6371

        dlat = math.radians(
            lat2 - lat1
        )

        dlon = math.radians(
            lon2 - lon1
        )

        a = (
            math.sin(dlat / 2) ** 2
            +
            math.cos(
                math.radians(lat1)
            )
            *
            math.cos(
                math.radians(lat2)
            )
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
# GET REGISTERED HOSPITAL BED DATA
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
        # Hospital columns
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

        result = hospitals.copy()

        if hospital_id_col:

            result.rename(
                columns={
                    hospital_id_col:
                    "hospital_id"
                },
                inplace=True
            )

        else:

            result["hospital_id"] = range(
                1,
                len(result) + 1
            )

        if name_col:

            result.rename(
                columns={
                    name_col:
                    "hospital_name"
                },
                inplace=True
            )

        else:

            result["hospital_name"] = (
                "Hospital"
            )

        if address_col:

            result.rename(
                columns={
                    address_col:
                    "address"
                },
                inplace=True
            )

        else:

            result["address"] = (
                "Address not available"
            )

        if phone_col:

            result.rename(
                columns={
                    phone_col:
                    "phone"
                },
                inplace=True
            )

        else:

            result["phone"] = (
                "Not available"
            )

        # ----------------------------------------------------
        # Beds
        # ----------------------------------------------------

        result["total_beds"] = 0
        result["available_beds"] = 0

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

            if (
                bed_hospital_id
                and total_col
                and available_col
            ):

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
                    .groupby(
                        bed_hospital_id
                    )
                    .agg(
                        total_beds=(
                            total_col,
                            "sum"
                        ),
                        available_beds=(
                            available_col,
                            "sum"
                        )
                    )
                    .reset_index()
                )

                bed_summary.rename(
                    columns={
                        bed_hospital_id:
                        "hospital_id"
                    },
                    inplace=True
                )

                result["hospital_id"] = (
                    result["hospital_id"]
                    .astype(str)
                )

                bed_summary["hospital_id"] = (
                    bed_summary["hospital_id"]
                    .astype(str)
                )

                result = result.drop(
                    columns=[
                        "total_beds",
                        "available_beds"
                    ],
                    errors="ignore"
                )

                result = result.merge(
                    bed_summary,
                    on="hospital_id",
                    how="left"
                )

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
            -
            result["available_beds"]
        ).clip(lower=0)

        result["occupancy_percent"] = 0.0

        mask = (
            result["total_beds"] > 0
        )

        result.loc[
            mask,
            "occupancy_percent"
        ] = (
            result.loc[
                mask,
                "occupied_beds"
            ]
            /
            result.loc[
                mask,
                "total_beds"
            ]
            * 100
        )

        result["status"] = result.apply(
            lambda row:
            get_bed_status(
                row["total_beds"],
                row["available_beds"]
            ),
            axis=1
        )

        return result

    except Exception as e:

        st.warning(
            f"Bed data error: {e}"
        )

        return pd.DataFrame()


# ============================================================
# DOCTOR DATA
# ============================================================

def get_doctors():

    try:

        conn = get_connection()

        df = pd.read_sql_query(
            "SELECT * FROM doctors",
            conn
        )

        conn.close()

        return df

    except Exception:

        return pd.DataFrame()


# ============================================================
# EQUIPMENT DATA
# ============================================================

def get_equipment():

    try:

        conn = get_connection()

        df = pd.read_sql_query(
            "SELECT * FROM equipment",
            conn
        )

        conn.close()

        return df

    except Exception:

        return pd.DataFrame()


# ============================================================
# QUICK ACCESS
# ============================================================

st.subheader("🚀 Quick Access")

q1, q2, q3, q4 = st.columns(4)

with q1:

    if st.button(
        "👤 Patient Login",
        width="stretch"
    ):

        try:

            st.switch_page(
                "pages/patient_login.py"
            )

        except Exception:

            st.info(
                "Patient login page is not available."
            )


with q2:

    if st.button(
        "📝 Patient Register",
        width="stretch"
    ):

        try:

            st.switch_page(
                "pages/patient_register.py"
            )

        except Exception:

            st.info(
                "Patient registration page is not available."
            )


with q3:

    if st.button(
        "🔐 Admin Login",
        width="stretch"
    ):

        try:

            st.switch_page(
                "pages/admin_login.py"
            )

        except Exception:

            st.info(
                "Admin login page is not available."
            )


with q4:

    if st.button(
        "📊 Dashboard",
        width="stretch"
    ):

        try:

            st.switch_page(
                "pages/patient_dashboard.py"
            )

        except Exception:

            st.info(
                "Dashboard page is not available."
            )


st.divider()


# ============================================================
# 1. HOSPITAL SEARCH
# ============================================================

st.header("🔎 1. Hospital Search")

if hospital_directory.empty:

    st.warning(
        "hospital_directory.csv not found."
    )

else:

    search_text = st.text_input(
        "Search hospital, state, district or address",
        placeholder="Example: Kolkata"
    )

    if st.button(
        "🔍 Search",
        width="stretch"
    ):

        if not search_text.strip():

            st.warning(
                "Enter a search term."
            )

        else:

            query = (
                search_text
                .strip()
                .lower()
            )

            search_cols = [
                "hospital_name",
                "state",
                "district",
                "address"
            ]

            available_cols = [
                c
                for c in search_cols
                if c in hospital_directory.columns
            ]

            mask = pd.Series(
                False,
                index=hospital_directory.index
            )

            for col in available_cols:

                mask |= (
                    hospital_directory[col]
                    .astype(str)
                    .str.lower()
                    .str.contains(
                        query,
                        na=False
                    )
                )

            results = hospital_directory[
                mask
            ]

            if results.empty:

                st.info(
                    "No hospital found."
                )

            else:

                st.success(
                    f"{len(results)} hospital(s) found."
                )

                st.dataframe(
                    results.head(100),
                    width="stretch",
                    hide_index=True
                )


st.divider()


# ============================================================
# 2. BED AVAILABILITY
# ============================================================

st.header("🛏️ 2. Bed Availability")

bed_df = get_hospital_bed_data()

if bed_df.empty:

    st.info(
        "No registered hospital bed data available."
    )

else:

    total_beds = int(
        bed_df["total_beds"].sum()
    )

    available_beds = int(
        bed_df["available_beds"].sum()
    )

    occupied_beds = int(
        bed_df["occupied_beds"].sum()
    )

    occupancy = (
        occupied_beds /
        total_beds *
        100
        if total_beds > 0
        else 0
    )

    a, b, c, d = st.columns(4)

    with a:
        st.metric(
            "🛏️ Total Beds",
            f"{total_beds:,}"
        )

    with b:
        st.metric(
            "🟢 Available",
            f"{available_beds:,}"
        )

    with c:
        st.metric(
            "🔴 Occupied",
            f"{occupied_beds:,}"
        )

    with d:
        st.metric(
            "📊 Occupancy",
            f"{occupancy:.1f}%"
        )

    for _, row in bed_df.iterrows():

        name = str(
            row["hospital_name"]
        )

        status = row["status"]

        with st.expander(
            f"🏥 {name} — {status}"
        ):

            x1, x2, x3, x4 = st.columns(4)

            x1.metric(
                "Total",
                int(row["total_beds"])
            )

            x2.metric(
                "Available",
                int(row["available_beds"])
            )

            x3.metric(
                "Occupied",
                int(row["occupied_beds"])
            )

            x4.metric(
                "Occupancy",
                f"{row['occupancy_percent']:.1f}%"
            )

            st.write(
                f"**Status:** {status}"
            )

            st.write(
                f"📍 {row['address']}"
            )

            st.write(
                f"📞 {row['phone']}"
            )


st.divider()


# ============================================================
# 3. EMERGENCY REQUIREMENT SEARCH
# ============================================================

st.header("🚑 3. Emergency Requirement Search")

requirement = st.selectbox(
    "What does the patient need?",
    [
        "General Bed",
        "ICU",
        "Emergency Service",
        "Ventilator",
        "Oxygen Support"
    ]
)

if st.button(
    "🚑 Find Suitable Hospitals",
    width="stretch"
):

    df = hospital_directory.copy()

    if requirement == "General Bed":

        st.info(
            "Showing hospitals with available "
            "registered bed information."
        )

        if not bed_df.empty:

            st.dataframe(
                bed_df[
                    [
                        "hospital_name",
                        "total_beds",
                        "available_beds",
                        "status"
                    ]
                ],
                width="stretch",
                hide_index=True
            )

        else:

            st.info(
                "No current bed data available."
            )

    else:

        search_text = requirement.lower()

        text_columns = [
            "facilities",
            "specialties",
            "emergency_services"
        ]

        mask = pd.Series(
            False,
            index=df.index
        )

        for col in text_columns:

            if col in df.columns:

                mask |= (
                    df[col]
                    .astype(str)
                    .str.lower()
                    .str.contains(
                        search_text,
                        na=False
                    )
                )

        results = df[mask]

        if results.empty:

            st.warning(
                f"No hospital with '{requirement}' "
                "information was found."
            )

        else:

            st.success(
                f"{len(results)} matching hospital(s) found."
            )

            st.dataframe(
                results.head(100),
                width="stretch",
                hide_index=True
            )


st.divider()


# ============================================================
# 4. DOCTOR AVAILABILITY
# ============================================================

st.header("👨‍⚕️ 4. Doctor Availability")

doctors = get_doctors()

if doctors.empty:

    st.info(
        "No doctor records have been added yet."
    )

    st.caption(
        "Doctor data can be added later from the admin panel."
    )

else:

    available_doctors = doctors[
        doctors["available"] == 1
    ]

    st.metric(
        "Available Doctors",
        len(available_doctors)
    )

    st.dataframe(
        available_doctors,
        width="stretch",
        hide_index=True
    )


st.divider()


# ============================================================
# 5. EQUIPMENT AVAILABILITY
# ============================================================

st.header("🩺 5. Equipment Availability")

equipment = get_equipment()

if equipment.empty:

    st.info(
        "No equipment records have been added yet."
    )

else:

    equipment["availability_percent"] = 0.0

    mask = (
        equipment["total_quantity"] > 0
    )

    equipment.loc[
        mask,
        "availability_percent"
    ] = (
        equipment.loc[
            mask,
            "available_quantity"
        ]
        /
        equipment.loc[
            mask,
            "total_quantity"
        ]
        * 100
    )

    st.dataframe(
        equipment,
        width="stretch",
        hide_index=True
    )


st.divider()


# ============================================================
# 6. SMART HOSPITAL MATCHING
# ============================================================

st.header("🔗 6. Smart Hospital Matching")

st.write(
    "Select patient requirements to find suitable hospitals."
)

match_requirement = st.selectbox(
    "Required Service",
    [
        "Any",
        "ICU",
        "Emergency",
        "Ventilator",
        "Oxygen"
    ],
    key="matching_requirement"
)

minimum_beds = st.number_input(
    "Minimum available beds required",
    min_value=0,
    value=1,
    step=1
)

if st.button(
    "🔗 Find Matching Hospitals",
    width="stretch"
):

    if bed_df.empty:

        st.warning(
            "Bed data is not available for matching."
        )

    else:

        matching = bed_df[
            bed_df["available_beds"]
            >= minimum_beds
        ].copy()

        if match_requirement != "Any":

            keyword = match_requirement.lower()

            if (
                "facilities"
                in hospital_directory.columns
            ):

                directory = (
                    hospital_directory[
                        [
                            "hospital_name",
                            "facilities"
                        ]
                    ]
                    .copy()
                )

                directory["hospital_name"] = (
                    directory[
                        "hospital_name"
                    ]
                    .astype(str)
                )

                directory["facilities"] = (
                    directory[
                        "facilities"
                    ]
                    .astype(str)
                    .str.lower()
                )

                directory = directory[
                    directory["facilities"]
                    .str.contains(
                        keyword,
                        na=False
                    )
                ]

                matching = matching[
                    matching["hospital_name"]
                    .isin(
                        directory[
                            "hospital_name"
                        ]
                    )
                ]

        matching = matching.sort_values(
            "available_beds",
            ascending=False
        )

        if matching.empty:

            st.warning(
                "No hospital matches all selected requirements."
            )

        else:

            st.success(
                f"{len(matching)} matching hospital(s) found."
            )

            st.dataframe(
                matching[
                    [
                        "hospital_name",
                        "total_beds",
                        "available_beds",
                        "occupied_beds",
                        "occupancy_percent",
                        "status",
                        "address"
                    ]
                ],
                width="stretch",
                hide_index=True
            )


st.divider()


# ============================================================
# 7. BED RESERVATION / REQUEST
# ============================================================

st.header("📅 7. Bed Request / Reservation")

if bed_df.empty:

    st.info(
        "No hospital bed data is available for reservation."
    )

else:

    hospital_options = (
        bed_df["hospital_name"]
        .astype(str)
        .tolist()
    )

    selected_hospital = st.selectbox(
        "Select Hospital",
        hospital_options
    )

    patient_name = st.text_input(
        "Patient Name"
    )

    patient_phone = st.text_input(
        "Patient Phone"
    )

    bed_type = st.selectbox(
        "Bed Type",
        [
            "General",
            "ICU",
            "Emergency"
        ]
    )

    emergency_level = st.selectbox(
        "Emergency Level",
        [
            "Normal",
            "Urgent",
            "Critical"
        ]
    )

    if st.button(
        "📅 Submit Bed Request",
        width="stretch"
    ):

        if not patient_name.strip():

            st.warning(
                "Enter patient name."
            )

        elif not patient_phone.strip():

            st.warning(
                "Enter patient phone."
            )

        else:

            selected_row = bed_df[
                bed_df["hospital_name"]
                == selected_hospital
            ]

            if not selected_row.empty:

                hospital_id = selected_row.iloc[0][
                    "hospital_id"
                ]

                try:

                    conn = get_connection()

                    conn.execute(
                        """
                        INSERT INTO reservations
                        (
                            hospital_id,
                            patient_name,
                            patient_phone,
                            bed_type,
                            emergency_level,
                            status,
                            created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            int(hospital_id),
                            patient_name,
                            patient_phone,
                            bed_type,
                            emergency_level,
                            "Pending",
                            datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                        )
                    )

                    conn.commit()
                    conn.close()

                    st.success(
                        "✅ Bed request submitted successfully."
                    )

                except Exception as e:

                    st.error(
                        f"Reservation error: {e}"
                    )


st.divider()


# ============================================================
# 8. RESERVATION MANAGEMENT
# ============================================================

st.header("📋 8. Reservation Management")

try:

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

    if reservations.empty:

        st.info(
            "No reservations found."
        )

    else:

        st.dataframe(
            reservations,
            width="stretch",
            hide_index=True
        )

except Exception:

    st.info(
        "Reservation data is not available."
    )


st.divider()


# ============================================================
# 9. OPERATIONS DASHBOARD
# ============================================================

st.header("📊 9. Hospital Operations Dashboard")

if not bed_df.empty:

    total_hospitals = len(bed_df)

    hospitals_with_beds = len(
        bed_df[
            bed_df["available_beds"] > 0
        ]
    )

    critical_hospitals = len(
        bed_df[
            bed_df["status"]
            .isin(
                [
                    "🟠 Critical",
                    "🔴 Full"
                ]
            )
        ]
    )

    d1, d2, d3 = st.columns(3)

    d1.metric(
        "🏥 Registered Hospitals",
        total_hospitals
    )

    d2.metric(
        "🛏️ Hospitals With Beds",
        hospitals_with_beds
    )

    d3.metric(
        "⚠️ Critical / Full",
        critical_hospitals
    )

    st.subheader(
        "Hospital Bed Availability"
    )

    chart_df = bed_df[
        [
            "hospital_name",
            "available_beds"
        ]
    ].copy()

    chart_df = (
        chart_df
        .sort_values(
            "available_beds",
            ascending=False
        )
        .head(20)
    )

    chart_df = chart_df.set_index(
        "hospital_name"
    )

    st.bar_chart(
        chart_df["available_beds"]
    )

else:

    st.info(
        "Operations dashboard needs registered bed data."
    )


st.divider()


# ============================================================
# 10. ML BED AVAILABILITY PREDICTION
# ============================================================

st.header("🤖 10. Next-Day Bed Availability Prediction")

st.write(
    "The ML module predicts next-day available beds using "
    "historical bed availability data."
)

if not SKLEARN_AVAILABLE:

    st.warning(
        "scikit-learn is not installed. "
        "Add scikit-learn to requirements.txt."
    )

elif not ML_DATASET_PATH.exists():

    st.info(
        "ML dataset is not available yet."
    )

    st.caption(
        "Add bed_availability_prediction_dataset.csv "
        "to the repository to activate this module."
    )

else:

    try:

        ml_df = pd.read_csv(
            ML_DATASET_PATH
        )

        required_features = [
            "total_beds",
            "occupied_beds",
            "available_beds",
            "occupancy_rate",
            "admissions_24h",
            "discharges_24h",
            "emergency_admissions_24h",
            "icu_beds",
            "icu_available_beds",
            "is_weekend",
            "month",
            "previous_day_available_beds",
            "previous_day_occupancy_rate",
            "rolling_7d_avg_available_beds"
        ]

        target = (
            "target_next_day_available_beds"
        )

        missing = [
            col
            for col in required_features + [target]
            if col not in ml_df.columns
        ]

        if missing:

            st.warning(
                "ML dataset is missing columns: "
                + ", ".join(missing)
            )

        else:

            ml_df = ml_df.dropna(
                subset=required_features + [target]
            )

            X = ml_df[
                required_features
            ]

            y = ml_df[target]

            X_train, X_test, y_train, y_test = (
                train_test_split(
                    X,
                    y,
                    test_size=0.20,
                    random_state=42
                )
            )

            model = RandomForestRegressor(
                n_estimators=150,
                random_state=42,
                n_jobs=-1
            )

            model.fit(
                X_train,
                y_train
            )

            predictions = model.predict(
                X_test
            )

            mae = mean_absolute_error(
                y_test,
                predictions
            )

            r2 = r2_score(
                y_test,
                predictions
            )

            m1, m2 = st.columns(2)

            m1.metric(
                "MAE",
                f"{mae:.2f}"
            )

            m2.metric(
                "R² Score",
                f"{r2:.3f}"
            )

            st.success(
                "✅ Random Forest ML model trained successfully."
            )

            st.caption(
                "This prediction is based on the historical ML dataset. "
                "It should not be interpreted as real-time hospital data."
            )

    except Exception as e:

        st.warning(
            f"ML model could not be trained: {e}"
        )


st.divider()


# ============================================================
# 11. STATUS GUIDE
# ============================================================

st.header("📌 Bed Status Guide")

s1, s2, s3, s4 = st.columns(4)

with s1:

    st.success(
        "🟢 Available\n\n"
        "More than 30% beds available"
    )

with s2:

    st.warning(
        "🟡 Low\n\n"
        "15–30% beds available"
    )

with s3:

    st.warning(
        "🟠 Critical\n\n"
        "1–15% beds available"
    )

with s4:

    st.error(
        "🔴 Full\n\n"
        "0 beds available"
    )


st.divider()


# ============================================================
# SYSTEM INFORMATION
# ============================================================

st.header("ℹ️ System Modules")

st.write(
    """
    ### Current / Integrated Modules

    ✅ Hospital Directory  
    ✅ Hospital Search  
    ✅ Bed Availability  
    ✅ Occupancy Calculation  
    ✅ Bed Resource Status  
    ✅ Emergency Requirement Search  
    ✅ Doctor Availability Database  
    ✅ Equipment Availability Database  
    ✅ Smart Hospital Matching  
    ✅ Bed Request / Reservation  
    ✅ Reservation Management  
    ✅ Hospital Operations Dashboard  
    ✅ ML Bed Availability Prediction  

    ### Existing Application Pages

    👤 Patient Login  
    📝 Patient Registration  
    🔐 Admin Login  
    📊 Patient Dashboard  
    """
)


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "🏥 Smart Hospital Bed Availability System | "
    "Academic / Project Prototype"
)

st.caption(
    "⚠️ Bed availability and resource information depends "
    "on the data available in the system and should not be "
    "treated as guaranteed real-time medical availability."
        )
