import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path
from datetime import datetime, date


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

BASE_DIR = Path(__file__).resolve().parent

CSV_PATH = BASE_DIR / "hospital_directory.csv"

DB_DIR = BASE_DIR / "database"
DB_DIR.mkdir(exist_ok=True)

DB_PATH = DB_DIR / "hospital.db"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
# INITIALIZE DATABASE
# =========================================================

def initialize_database():

    conn = get_connection()

    # ---------------- DOCTORS ----------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            doctor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_name TEXT NOT NULL,
            doctor_name TEXT NOT NULL,
            department TEXT NOT NULL,
            specialization TEXT,
            availability_status TEXT DEFAULT 'Available',
            available_from TEXT,
            available_to TEXT,
            last_updated TEXT
        )
    """)

    # ---------------- EQUIPMENT ----------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS equipment (
            equipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_name TEXT NOT NULL,
            equipment_name TEXT NOT NULL,
            equipment_type TEXT,
            total_units INTEGER DEFAULT 0,
            available_units INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Available',
            last_updated TEXT
        )
    """)

    # ---------------- RESERVATIONS ----------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            patient_phone TEXT,
            hospital_name TEXT NOT NULL,
            reservation_type TEXT NOT NULL,
            department TEXT,
            doctor_name TEXT,
            equipment_name TEXT,
            requested_date TEXT,
            requested_time TEXT,
            status TEXT DEFAULT 'Pending',
            notes TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


initialize_database()


# =========================================================
# HOSPITAL CSV
# =========================================================

@st.cache_data
def load_hospital_data():

    if not CSV_PATH.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(CSV_PATH)

        # Normalize column names
        df.columns = [
            str(col).strip().lower().replace(" ", "_")
            for col in df.columns
        ]

        return df

    except Exception as e:

        st.error(f"Unable to read hospital_directory.csv: {e}")

        return pd.DataFrame()


hospital_df = load_hospital_data()


# =========================================================
# COLUMN FINDER
# =========================================================

def find_column(df, possible_names):

    for name in possible_names:

        if name in df.columns:
            return name

    return None


hospital_name_col = find_column(
    hospital_df,
    [
        "hospital_name",
        "hospital",
        "name"
    ]
)

state_col = find_column(
    hospital_df,
    [
        "state",
        "state_name"
    ]
)

district_col = find_column(
    hospital_df,
    [
        "district",
        "district_name"
    ]
)

address_col = find_column(
    hospital_df,
    [
        "address",
        "hospital_address"
    ]
)

specialties_col = find_column(
    hospital_df,
    [
        "specialties",
        "speciality",
        "specialty"
    ]
)

facilities_col = find_column(
    hospital_df,
    [
        "facilities",
        "facility"
    ]
)

total_beds_col = find_column(
    hospital_df,
    [
        "total_beds",
        "total_num_beds",
        "number_of_beds",
        "beds"
    ]
)


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def safe_number(value, default=0):

    try:
        if pd.isna(value):
            return default

        return int(float(value))

    except Exception:
        return default


def bed_status(total_beds, available_beds):

    total_beds = safe_number(total_beds)
    available_beds = safe_number(available_beds)

    if total_beds <= 0:
        return "⚪ Unknown"

    if available_beds <= 0:
        return "🔴 Full"

    percentage = (available_beds / total_beds) * 100

    if percentage <= 15:
        return "🟠 Critical"

    elif percentage <= 30:
        return "🟡 Low"

    return "🟢 Available"


# =========================================================
# DOCTOR FUNCTIONS
# =========================================================

def add_doctor(
    hospital,
    doctor,
    department,
    specialization,
    status,
    from_time,
    to_time
):

    conn = get_connection()

    conn.execute("""
        INSERT INTO doctors
        (
            hospital_name,
            doctor_name,
            department,
            specialization,
            availability_status,
            available_from,
            available_to,
            last_updated
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        hospital,
        doctor,
        department,
        specialization,
        status,
        from_time,
        to_time,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


def get_doctors():

    conn = get_connection()

    df = pd.read_sql_query(
        "SELECT * FROM doctors ORDER BY hospital_name, doctor_name",
        conn
    )

    conn.close()

    return df


def update_doctor(
    doctor_id,
    status,
    from_time,
    to_time
):

    conn = get_connection()

    conn.execute("""
        UPDATE doctors
        SET
            availability_status = ?,
            available_from = ?,
            available_to = ?,
            last_updated = ?
        WHERE doctor_id = ?
    """, (
        status,
        from_time,
        to_time,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        doctor_id
    ))

    conn.commit()
    conn.close()


def delete_doctor(doctor_id):

    conn = get_connection()

    conn.execute(
        "DELETE FROM doctors WHERE doctor_id = ?",
        (doctor_id,)
    )

    conn.commit()
    conn.close()


# =========================================================
# EQUIPMENT FUNCTIONS
# =========================================================

def add_equipment(
    hospital,
    equipment_name,
    equipment_type,
    total_units,
    available_units
):

    if available_units > total_units:
        available_units = total_units

    if available_units < 0:
        available_units = 0

    if total_units <= 0:
        status = "Unavailable"

    elif available_units == 0:
        status = "Unavailable"

    elif available_units <= max(1, total_units * 0.2):
        status = "Low"

    else:
        status = "Available"

    conn = get_connection()

    conn.execute("""
        INSERT INTO equipment
        (
            hospital_name,
            equipment_name,
            equipment_type,
            total_units,
            available_units,
            status,
            last_updated
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        hospital,
        equipment_name,
        equipment_type,
        total_units,
        available_units,
        status,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


def get_equipment():

    conn = get_connection()

    df = pd.read_sql_query(
        """
        SELECT *
        FROM equipment
        ORDER BY hospital_name, equipment_name
        """,
        conn
    )

    conn.close()

    return df


def update_equipment(
    equipment_id,
    total_units,
    available_units
):

    if available_units > total_units:
        available_units = total_units

    if available_units < 0:
        available_units = 0

    if total_units <= 0 or available_units == 0:
        status = "Unavailable"

    elif available_units <= max(1, total_units * 0.2):
        status = "Low"

    else:
        status = "Available"

    conn = get_connection()

    conn.execute("""
        UPDATE equipment
        SET
            total_units = ?,
            available_units = ?,
            status = ?,
            last_updated = ?
        WHERE equipment_id = ?
    """, (
        total_units,
        available_units,
        status,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        equipment_id
    ))

    conn.commit()
    conn.close()


def delete_equipment(equipment_id):

    conn = get_connection()

    conn.execute(
        "DELETE FROM equipment WHERE equipment_id = ?",
        (equipment_id,)
    )

    conn.commit()
    conn.close()


# =========================================================
# RESERVATION FUNCTIONS
# =========================================================

def create_reservation(
    patient_name,
    patient_phone,
    hospital,
    reservation_type,
    department,
    doctor,
    equipment,
    requested_date,
    requested_time,
    notes
):

    conn = get_connection()

    conn.execute("""
        INSERT INTO reservations
        (
            patient_name,
            patient_phone,
            hospital_name,
            reservation_type,
            department,
            doctor_name,
            equipment_name,
            requested_date,
            requested_time,
            status,
            notes,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        patient_name,
        patient_phone,
        hospital,
        reservation_type,
        department,
        doctor,
        equipment,
        str(requested_date),
        requested_time,
        "Pending",
        notes,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


def get_reservations():

    conn = get_connection()

    df = pd.read_sql_query(
        """
        SELECT *
        FROM reservations
        ORDER BY reservation_id DESC
        """,
        conn
    )

    conn.close()

    return df


def update_reservation_status(
    reservation_id,
    status
):

    conn = get_connection()

    conn.execute("""
        UPDATE reservations
        SET status = ?
        WHERE reservation_id = ?
    """, (
        status,
        reservation_id
    ))

    conn.commit()
    conn.close()


def delete_reservation(reservation_id):

    conn = get_connection()

    conn.execute(
        "DELETE FROM reservations WHERE reservation_id = ?",
        (reservation_id,)
    )

    conn.commit()
    conn.close()


# =========================================================
# HEADER
# =========================================================

st.title("🏥 Smart Hospital Bed Availability System")

st.write(
    "Find hospitals, check bed availability, doctors, equipment "
    "and manage reservation requests."
)


# =========================================================
# SIDEBAR NAVIGATION
# =========================================================

st.sidebar.title("📌 Navigation")

menu = st.sidebar.radio(
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


# =========================================================
# HOME
# =========================================================

if menu == "🏠 Home":

    st.header("🏠 Welcome")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "🏥 Hospitals",
        len(hospital_df)
    )

    doctor_df = get_doctors()
    equipment_df = get_equipment()
    reservation_df = get_reservations()

    col2.metric(
        "👨‍⚕️ Doctors",
        len(doctor_df)
    )

    col3.metric(
        "🩺 Equipment",
        len(equipment_df)
    )

    col4.metric(
        "📋 Reservations",
        len(reservation_df)
    )

    st.divider()

    st.subheader("✨ System Features")

    f1, f2, f3 = st.columns(3)

    with f1:

        st.markdown("""
        ### 🏥 Hospital Search

        Search hospitals by:

        - Hospital name
        - State
        - District
        - Address
        """)

    with f2:

        st.markdown("""
        ### 🛏️ Bed Availability

        Check:

        - Total beds
        - Available beds
        - Occupied beds
        - Availability status
        """)

    with f3:

        st.markdown("""
        ### 👨‍⚕️ Healthcare Resources

        Check:

        - Doctors
        - Equipment
        - Reservation requests
        """)


# =========================================================
# HOSPITAL SEARCH
# =========================================================

elif menu == "🏥 Hospital Search":

    st.header("🏥 Hospital Search")

    if hospital_df.empty:

        st.error(
            "hospital_directory.csv not found."
        )

    else:

        search = st.text_input(
            "🔎 Search hospital",
            placeholder="Hospital name, state, district..."
        )

        result = hospital_df.copy()

        if search.strip():

            text = search.strip().lower()

            mask = pd.Series(
                False,
                index=result.index
            )

            for col in [
                hospital_name_col,
                state_col,
                district_col,
                address_col
            ]:

                if col and col in result.columns:

                    mask = mask | (
                        result[col]
                        .fillna("")
                        .astype(str)
                        .str.lower()
                        .str.contains(
                            text,
                            na=False
                        )
                    )

            result = result[mask]

        st.write(
            f"### Hospitals Found: {len(result)}"
        )

        for _, row in result.head(50).iterrows():

            name = (
                row[hospital_name_col]
                if hospital_name_col
                else "Hospital"
            )

            with st.container(border=True):

                st.subheader(
                    f"🏥 {name}"
                )

                if state_col:
                    st.write(
                        f"📍 State: {row[state_col]}"
                    )

                if district_col:
                    st.write(
                        f"📍 District: {row[district_col]}"
                    )

                if address_col:
                    st.write(
                        f"🏠 Address: {row[address_col]}"
                    )

                if total_beds_col:

                    st.write(
                        f"🛏️ Listed Beds: "
                        f"{row[total_beds_col]}"
                    )


# =========================================================
# BED AVAILABILITY
# =========================================================

elif menu == "🛏️ Bed Availability":

    st.header("🛏️ Bed Availability")

    conn = get_connection()

    tables = pd.read_sql_query(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        """,
        conn
    )

    conn.close()

    table_names = tables["name"].tolist()

    if "hospitals" in table_names:

        conn = get_connection()

        try:

            bed_df = pd.read_sql_query(
                "SELECT * FROM hospitals",
                conn
            )

        except Exception:

            bed_df = pd.DataFrame()

        conn.close()

    else:

        bed_df = pd.DataFrame()


    if bed_df.empty:

        st.info(
            "No bed availability records are currently "
            "available in the database."
        )

        st.caption(
            "Your hospital_directory.csv can still be used "
            "for hospital search."
        )

    else:

        st.dataframe(
            bed_df,
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# 👨‍⚕️ DOCTOR AVAILABILITY
# =========================================================

elif menu == "👨‍⚕️ Doctor Availability":

    st.header("👨‍⚕️ Doctor Availability")

    st.info(
        "Doctor availability is based on registered/demo data "
        "and may not represent live hospital availability."
    )

    # ---------------- ADD DOCTOR ----------------

    with st.expander(
        "➕ Add Doctor",
        expanded=False
    ):

        c1, c2 = st.columns(2)

        with c1:

            hospital = st.text_input(
                "🏥 Hospital Name",
                key="doctor_hospital"
            )

            doctor = st.text_input(
                "👨‍⚕️ Doctor Name",
                placeholder="Dr. John Doe",
                key="doctor_name"
            )

            department = st.selectbox(
                "🩺 Department",
                [
                    "General Medicine",
                    "Cardiology",
                    "Neurology",
                    "Orthopedics",
                    "Pediatrics",
                    "Dermatology",
                    "Gynecology",
                    "ENT",
                    "Ophthalmology",
                    "Oncology",
                    "Pulmonology",
                    "Gastroenterology",
                    "Nephrology",
                    "Urology",
                    "Emergency Medicine",
                    "Other"
                ],
                key="doctor_department"
            )

        with c2:

            specialization = st.text_input(
                "🔬 Specialization",
                key="doctor_specialization"
            )

            status = st.selectbox(
                "📌 Status",
                [
                    "Available",
                    "Busy",
                    "Unavailable"
                ],
                key="doctor_status"
            )

            from_time = st.text_input(
                "⏰ Available From",
                placeholder="10:00 AM",
                key="doctor_from"
            )

            to_time = st.text_input(
                "⏰ Available To",
                placeholder="02:00 PM",
                key="doctor_to"
            )

        if st.button(
            "➕ Add Doctor",
            type="primary",
            width="stretch"
        ):

            if not hospital.strip():

                st.error(
                    "Please enter hospital name."
                )

            elif not doctor.strip():

                st.error(
                    "Please enter doctor name."
                )

            else:

                add_doctor(
                    hospital,
                    doctor,
                    department,
                    specialization,
                    status,
                    from_time,
                    to_time
                )

                st.success(
                    "Doctor added successfully."
                )

                st.rerun()


    # ---------------- DOCTOR LIST ----------------

    doctor_df = get_doctors()

    if doctor_df.empty:

        st.warning(
            "No doctor records found."
        )

    else:

        st.subheader("🔎 Search Doctor")

        c1, c2, c3 = st.columns(3)

        with c1:

            doctor_search = st.text_input(
                "Doctor / Hospital",
                key="doctor_search"
            )

        with c2:

            dept_list = [
                "All"
            ] + sorted(
                doctor_df["department"]
                .dropna()
                .unique()
                .tolist()
            )

            dept_filter = st.selectbox(
                "Department",
                dept_list,
                key="doctor_dept_filter"
            )

        with c3:

            status_filter = st.selectbox(
                "Status",
                [
                    "All",
                    "Available",
                    "Busy",
                    "Unavailable"
                ],
                key="doctor_status_filter"
            )


        filtered = doctor_df.copy()


        if doctor_search.strip():

            text = doctor_search.strip().lower()

            filtered = filtered[
                filtered["doctor_name"]
                .fillna("")
                .str.lower()
                .str.contains(text, na=False)
                |
                filtered["hospital_name"]
                .fillna("")
                .str.lower()
                .str.contains(text, na=False)
            ]


        if dept_filter != "All":

            filtered = filtered[
                filtered["department"] == dept_filter
            ]


        if status_filter != "All":

            filtered = filtered[
                filtered["availability_status"]
                == status_filter
            ]


        st.write(
            f"### 👨‍⚕️ Doctors Found: {len(filtered)}"
        )


        for _, row in filtered.iterrows():

            status = row["availability_status"]

            if status == "Available":

                icon = "🟢"

            elif status == "Busy":

                icon = "🟡"

            else:

                icon = "🔴"


            with st.container(border=True):

                c1, c2 = st.columns([4, 1])

                with c1:

                    st.subheader(
                        f"👨‍⚕️ {row['doctor_name']}"
                    )

                    st.write(
                        f"🏥 **Hospital:** "
                        f"{row['hospital_name']}"
                    )

                    st.write(
                        f"🩺 **Department:** "
                        f"{row['department']}"
                    )

                    st.write(
                        f"🔬 **Specialization:** "
                        f"{row['specialization'] or 'Not specified'}"
                    )

                    st.write(
                        f"⏰ **Time:** "
                        f"{row['available_from'] or '-'} "
                        f"to "
                        f"{row['available_to'] or '-'}"
                    )

                with c2:

                    st.markdown(
                        f"## {icon}"
                    )

                    st.write(status)


                with st.expander(
                    "✏️ Update Status"
                ):

                    new_status = st.selectbox(
                        "Status",
                        [
                            "Available",
                            "Busy",
                            "Unavailable"
                        ],
                        index=[
                            "Available",
                            "Busy",
                            "Unavailable"
                        ].index(status),
                        key=f"ds_{row['doctor_id']}"
                    )

                    a, b = st.columns(2)

                    with a:

                        new_from = st.text_input(
                            "From",
                            value=row["available_from"] or "",
                            key=f"df_{row['doctor_id']}"
                        )

                    with b:

                        new_to = st.text_input(
                            "To",
                            value=row["available_to"] or "",
                            key=f"dt_{row['doctor_id']}"
                        )


                    if st.button(
                        "💾 Update",
                        key=f"du_{row['doctor_id']}"
                    ):

                        update_doctor(
                            row["doctor_id"],
                            new_status,
                            new_from,
                            new_to
                        )

                        st.success(
                            "Doctor updated."
                        )

                        st.rerun()


                if st.button(
                    "🗑️ Delete",
                    key=f"dd_{row['doctor_id']}"
                ):

                    delete_doctor(
                        row["doctor_id"]
                    )

                    st.success(
                        "Doctor deleted."
                    )

                    st.rerun()


# =========================================================
# 🩺 EQUIPMENT AVAILABILITY
# =========================================================

elif menu == "🩺 Equipment Availability":

    st.header("🩺 Equipment Availability")

    st.info(
        "Equipment information is based on registered/demo "
        "hospital data and is not guaranteed to be real-time."
    )


    # ---------------- ADD EQUIPMENT ----------------

    with st.expander(
        "➕ Add Equipment",
        expanded=False
    ):

        c1, c2 = st.columns(2)

        with c1:

            hospital = st.text_input(
                "🏥 Hospital Name",
                key="equipment_hospital"
            )

            equipment_name = st.text_input(
                "🩺 Equipment Name",
                placeholder="Ventilator",
                key="equipment_name"
            )

            equipment_type = st.text_input(
                "📦 Equipment Type",
                placeholder="Critical Care",
                key="equipment_type"
            )

        with c2:

            total_units = st.number_input(
                "Total Units",
                min_value=0,
                value=1,
                step=1,
                key="equipment_total"
            )

            available_units = st.number_input(
                "Available Units",
                min_value=0,
                value=1,
                step=1,
                key="equipment_available"
            )


        if st.button(
            "➕ Add Equipment",
            type="primary",
            width="stretch"
        ):

            if not hospital.strip():

                st.error(
                    "Please enter hospital name."
                )

            elif not equipment_name.strip():

                st.error(
                    "Please enter equipment name."
                )

            elif available_units > total_units:

                st.error(
                    "Available units cannot be greater "
                    "than total units."
                )

            else:

                add_equipment(
                    hospital,
                    equipment_name,
                    equipment_type,
                    int(total_units),
                    int(available_units)
                )

                st.success(
                    "Equipment added successfully."
                )

                st.rerun()


    # ---------------- EQUIPMENT LIST ----------------

    equipment_df = get_equipment()


    if equipment_df.empty:

        st.warning(
            "No equipment records found."
        )

    else:

        c1, c2 = st.columns(2)

        with c1:

            equipment_search = st.text_input(
                "🔎 Search Equipment",
                key="equipment_search"
            )

        with c2:

            equipment_status = st.selectbox(
                "Status",
                [
                    "All",
                    "Available",
                    "Low",
                    "Unavailable"
                ],
                key="equipment_status"
            )


        filtered_equipment = equipment_df.copy()


        if equipment_search.strip():

            text = equipment_search.strip().lower()

            filtered_equipment = filtered_equipment[
                filtered_equipment["equipment_name"]
                .fillna("")
                .str.lower()
                .str.contains(text, na=False)
                |
                filtered_equipment["hospital_name"]
                .fillna("")
                .str.lower()
                .str.contains(text, na=False)
            ]


        if equipment_status != "All":

            filtered_equipment = filtered_equipment[
                filtered_equipment["status"]
                == equipment_status
            ]


        st.write(
            f"### 🩺 Equipment Found: "
            f"{len(filtered_equipment)}"
        )


        for _, row in filtered_equipment.iterrows():

            status = row["status"]

            if status == "Available":

                icon = "🟢"

            elif status == "Low":

                icon = "🟡"

            else:

                icon = "🔴"


            with st.container(border=True):

                c1, c2 = st.columns([4, 1])

                with c1:

                    st.subheader(
                        f"🩺 {row['equipment_name']}"
                    )

                    st.write(
                        f"🏥 **Hospital:** "
                        f"{row['hospital_name']}"
                    )

                    st.write(
                        f"📦 **Type:** "
                        f"{row['equipment_type'] or '-'}"
                    )

                    st.write(
                        f"📊 **Available:** "
                        f"{row['available_units']} / "
                        f"{row['total_units']}"
                    )

                    st.caption(
                        f"Last Updated: "
                        f"{row['last_updated']}"
                    )

                with c2:

                    st.markdown(
                        f"## {icon}"
                    )

                    st.write(status)


                with st.expander(
                    "✏️ Update Equipment"
                ):

                    new_total = st.number_input(
                        "Total Units",
                        min_value=0,
                        value=int(row["total_units"]),
                        step=1,
                        key=f"et_{row['equipment_id']}"
                    )

                    new_available = st.number_input(
                        "Available Units",
                        min_value=0,
                        value=int(row["available_units"]),
                        step=1,
                        key=f"ea_{row['equipment_id']}"
                    )


                    if st.button(
                        "💾 Update",
                        key=f"eu_{row['equipment_id']}"
                    ):

                        if new_available > new_total:

                            st.error(
                                "Available units cannot exceed total."
                            )

                        else:

                            update_equipment(
                                row["equipment_id"],
                                int(new_total),
                                int(new_available)
                            )

                            st.success(
                                "Equipment updated."
                            )

                            st.rerun()


                if st.button(
                    "🗑️ Delete",
                    key=f"ed_{row['equipment_id']}"
                ):

                    delete_equipment(
                        row["equipment_id"]
                    )

                    st.success(
                        "Equipment deleted."
                    )

                    st.rerun()


# =========================================================
# 📋 RESERVATION MANAGEMENT
# =========================================================

elif menu == "📋 Reservation Management":

    st.header("📋 Reservation Management")

    st.info(
        "Reservations are requests for this project prototype. "
        "They do not represent confirmed real-world hospital bookings."
    )


    # =====================================================
    # CREATE RESERVATION
    # =====================================================

    with st.expander(
        "➕ Create Reservation Request",
        expanded=True
    ):

        c1, c2 = st.columns(2)

        with c1:

            patient_name = st.text_input(
                "👤 Patient Name",
                key="reservation_patient"
            )

            patient_phone = st.text_input(
                "📱 Phone Number",
                key="reservation_phone"
            )

            hospital = st.text_input(
                "🏥 Hospital Name",
                key="reservation_hospital"
            )

            reservation_type = st.selectbox(
                "📋 Reservation Type",
                [
                    "Bed",
                    "Doctor Appointment",
                    "Equipment",
                    "Emergency"
                ],
                key="reservation_type"
            )


        with c2:

            department = st.text_input(
                "🩺 Department",
                key="reservation_department"
            )

            doctor = st.text_input(
                "👨‍⚕️ Doctor Name",
                key="reservation_doctor"
            )

            equipment = st.text_input(
                "🩺 Equipment",
                key="reservation_equipment"
            )

            requested_date = st.date_input(
                "📅 Requested Date",
                min_value=date.today(),
                key="reservation_date"
            )

            requested_time = st.text_input(
                "⏰ Requested Time",
                placeholder="10:30 AM",
                key="reservation_time"
            )


        notes = st.text_area(
            "📝 Notes",
            placeholder="Additional information..."
        )


        if st.button(
            "📤 Submit Reservation",
            type="primary",
            width="stretch"
        ):

            if not patient_name.strip():

                st.error(
                    "Please enter patient name."
                )

            elif not hospital.strip():

                st.error(
                    "Please enter hospital name."
                )

            else:

                create_reservation(
                    patient_name,
                    patient_phone,
                    hospital,
                    reservation_type,
                    department,
                    doctor,
                    equipment,
                    requested_date,
                    requested_time,
                    notes
                )

                st.success(
                    "✅ Reservation request submitted successfully."
                )

                st.rerun()


    # =====================================================
    # RESERVATION LIST
    # =====================================================

    reservation_df = get_reservations()

    st.divider()

    st.subheader("📋 Reservation Requests")


    if reservation_df.empty:

        st.info(
            "No reservation requests yet."
        )

    else:

        status_filter = st.selectbox(
            "Filter by Status",
            [
                "All",
                "Pending",
                "Confirmed",
                "Rejected",
                "Cancelled"
            ]
        )


        display_df = reservation_df.copy()


        if status_filter != "All":

            display_df = display_df[
                display_df["status"]
                == status_filter
            ]


        st.write(
            f"### Requests: {len(display_df)}"
        )


        for _, row in display_df.iterrows():

            status = row["status"]

            if status == "Pending":

                icon = "🟡"

            elif status == "Confirmed":

                icon = "🟢"

            elif status == "Rejected":

                icon = "🔴"

            else:

                icon = "⚪"


            with st.container(border=True):

                st.subheader(
                    f"{icon} Reservation "
                    f"#{row['reservation_id']}"
                )

                c1, c2 = st.columns(2)

                with c1:

                    st.write(
                        f"👤 **Patient:** "
                        f"{row['patient_name']}"
                    )

                    st.write(
                        f"📱 **Phone:** "
                        f"{row['patient_phone'] or '-'}"
                    )

                    st.write(
                        f"🏥 **Hospital:** "
                        f"{row['hospital_name']}"
                    )

                    st.write(
                        f"📋 **Type:** "
                        f"{row['reservation_type']}"
                    )

                with c2:

                    st.write(
                        f"📅 **Date:** "
                        f"{row['requested_date']}"
                    )

                    st.write(
                        f"⏰ **Time:** "
                        f"{row['requested_time'] or '-'}"
                    )

                    st.write(
                        f"👨‍⚕️ **Doctor:** "
                        f"{row['doctor_name'] or '-'}"
                    )

                    st.write(
                        f"🩺 **Equipment:** "
                        f"{row['equipment_name'] or '-'}"
                    )

                if row["department"]:

                    st.write(
                        f"🩺 **Department:** "
                        f"{row['department']}"
                    )

                if row["notes"]:

                    st.write(
                        f"📝 **Notes:** "
                        f"{row['notes']}"
                    )


                st.markdown(
                    f"### Status: {icon} {status}"
                )


                # ---------------- UPDATE ----------------

                new_status = st.selectbox(
                    "Change Status",
                    [
                        "Pending",
                        "Confirmed",
                        "Rejected",
                        "Cancelled"
                    ],
                    index=[
                        "Pending",
                        "Confirmed",
                        "Rejected",
                        "Cancelled"
                    ].index(status),
                    key=f"rs_{row['reservation_id']}"
                )


                c1, c2 = st.columns(2)


                with c1:

                    if st.button(
                        "💾 Update Status",
                        key=f"ru_{row['reservation_id']}"
                    ):

                        update_reservation_status(
                            row["reservation_id"],
                            new_status
                        )

                        st.success(
                            "Reservation status updated."
                        )

                        st.rerun()


                with c2:

                    if st.button(
                        "🗑️ Delete",
                        key=f"rd_{row['reservation_id']}"
                    ):

                        delete_reservation(
                            row["reservation_id"]
                        )

                        st.success(
                            "Reservation deleted."
                        )

                        st.rerun()


# =========================================================
# 📊 ADMIN DASHBOARD
# =========================================================

elif menu == "📊 Admin Dashboard":

    st.header("📊 Admin Dashboard")

    doctor_df = get_doctors()
    equipment_df = get_equipment()
    reservation_df = get_reservations()


    # ---------------- SUMMARY ----------------

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "🏥 Hospitals",
        len(hospital_df)
    )

    c2.metric(
        "👨‍⚕️ Doctors",
        len(doctor_df)
    )

    c3.metric(
        "🩺 Equipment",
        len(equipment_df)
    )

    c4.metric(
        "📋 Reservations",
        len(reservation_df)
    )


    st.divider()


    # ---------------- DOCTORS ----------------

    st.subheader("👨‍⚕️ Doctor Statistics")

    if not doctor_df.empty:

        available = len(
            doctor_df[
                doctor_df["availability_status"]
                == "Available"
            ]
        )

        busy = len(
            doctor_df[
                doctor_df["availability_status"]
                == "Busy"
            ]
        )

        unavailable = len(
            doctor_df[
                doctor_df["availability_status"]
                == "Unavailable"
            ]
        )

        a, b, c = st.columns(3)

        a.metric(
            "🟢 Available",
            available
        )

        b.metric(
            "🟡 Busy",
            busy
        )

        c.metric(
            "🔴 Unavailable",
            unavailable
        )


    # ---------------- EQUIPMENT ----------------

    st.subheader("🩺 Equipment Statistics")

    if not equipment_df.empty:

        available_eq = len(
            equipment_df[
                equipment_df["status"]
                == "Available"
            ]
        )

        low_eq = len(
            equipment_df[
                equipment_df["status"]
                == "Low"
            ]
        )

        unavailable_eq = len(
            equipment_df[
                equipment_df["status"]
                == "Unavailable"
            ]
        )

        a, b, c = st.columns(3)

        a.metric(
            "🟢 Available",
            available_eq
        )

        b.metric(
            "🟡 Low",
            low_eq
        )

        c.metric(
            "🔴 Unavailable",
            unavailable_eq
        )


    # ---------------- RESERVATIONS ----------------

    st.subheader("📋 Reservation Statistics")

    if not reservation_df.empty:

        pending = len(
            reservation_df[
                reservation_df["status"]
                == "Pending"
            ]
        )

        confirmed = len(
            reservation_df[
                reservation_df["status"]
                == "Confirmed"
            ]
        )

        rejected = len(
            reservation_df[
                reservation_df["status"]
                == "Rejected"
            ]
        )

        a, b, c = st.columns(3)

        a.metric(
            "🟡 Pending",
            pending
        )

        b.metric(
            "🟢 Confirmed",
            confirmed
        )

        c.metric(
            "🔴 Rejected",
            rejected
        )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "🏥 Smart Hospital Bed Availability System | "
    "Project Prototype | Hospital and healthcare-resource "
    "availability may be demo/registered data."
            )
