import streamlit as st
import sqlite3
from datetime import datetime
from pathlib import Path


# =========================================================
# DATABASE PATH
# =========================================================

DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "database"
    / "hospital.db"
)


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Bed Management",
    page_icon="🛏️",
    layout="wide"
)


# =========================================================
# ADMIN LOGIN CHECK
# =========================================================

if not st.session_state.get(
    "admin_logged_in",
    False
):

    st.warning(
        "🔐 Please login as Admin first."
    )

    if st.button(
        "Go to Admin Login"
    ):

        st.switch_page(
            "pages/admin_login.py"
        )

    st.stop()


# =========================================================
# HEADER
# =========================================================

st.title("🛏️ Bed Management")

st.write(
    f"Admin: **{st.session_state.get('admin_name', 'Admin')}**"
)

st.divider()


# =========================================================
# SELECT HOSPITAL
# =========================================================

conn = sqlite3.connect(DB_PATH)

hospitals = conn.execute(
    """
    SELECT
        hospital_id,
        name
    FROM hospitals
    ORDER BY name
    """
).fetchall()

conn.close()


if not hospitals:

    st.error(
        "❌ No hospitals found."
    )

    st.stop()


hospital_dict = {
    name: hospital_id
    for hospital_id, name in hospitals
}


selected_hospital = st.selectbox(
    "🏥 Select Hospital",
    list(hospital_dict.keys())
)


hospital_id = hospital_dict[
    selected_hospital
]


# =========================================================
# BED CONFIGURATION
# =========================================================

st.subheader(
    f"🛏️ Bed Configuration — {selected_hospital}"
)


bed_type = st.selectbox(
    "Bed Type",
    [
        "GENERAL",
        "ICU",
        "EMERGENCY"
    ]
)


# =========================================================
# GET EXISTING BED DATA
# =========================================================

conn = sqlite3.connect(DB_PATH)

existing = conn.execute(
    """
    SELECT
        total_beds,
        available_beds
    FROM beds
    WHERE hospital_id = ?
    AND bed_type = ?
    """,
    (
        hospital_id,
        bed_type
    )
).fetchone()

conn.close()


if existing:

    current_total = int(
        existing[0]
    )

    current_available = int(
        existing[1]
    )

else:

    current_total = 0
    current_available = 0


# =========================================================
# BED INPUT
# =========================================================

col1, col2 = st.columns(2)


with col1:

    total_beds = st.number_input(
        "🛏️ Total Beds",
        min_value=0,
        value=current_total,
        step=1
    )


with col2:

    available_beds = st.number_input(
        "✅ Available Beds",
        min_value=0,
        max_value=int(total_beds),
        value=min(
            current_available,
            int(total_beds)
        ),
        step=1
    )


# =========================================================
# SAVE BED DATA
# =========================================================

if st.button(
    "💾 Save Bed Data",
    type="primary"
):

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    conn = sqlite3.connect(
        DB_PATH
    )


    try:

        # =====================================================
        # CREATE HISTORY TABLE IF NEEDED
        # =====================================================

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bed_updates (

                update_id INTEGER PRIMARY KEY AUTOINCREMENT,

                hospital_id INTEGER NOT NULL,

                bed_type TEXT NOT NULL,

                old_available INTEGER NOT NULL,

                new_available INTEGER NOT NULL,

                updated_at TEXT NOT NULL

            )
            """
        )


        # =====================================================
        # SAVE OLD VALUE
        # =====================================================

        old_available = current_available


        # =====================================================
        # UPDATE EXISTING BED
        # =====================================================

        if existing:

            conn.execute(
                """
                UPDATE beds
                SET
                    total_beds = ?,
                    available_beds = ?,
                    last_updated = ?
                WHERE hospital_id = ?
                AND bed_type = ?
                """,
                (
                    int(total_beds),
                    int(available_beds),
                    now,
                    hospital_id,
                    bed_type
                )
            )


        # =====================================================
        # INSERT NEW BED
        # =====================================================

        else:

            conn.execute(
                """
                INSERT INTO beds
                (
                    hospital_id,
                    bed_type,
                    total_beds,
                    available_beds,
                    last_updated
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    hospital_id,
                    bed_type,
                    int(total_beds),
                    int(available_beds),
                    now
                )
            )


        # =====================================================
        # SAVE UPDATE HISTORY
        # =====================================================

        conn.execute(
            """
            INSERT INTO bed_updates
            (
                hospital_id,
                bed_type,
                old_available,
                new_available,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                hospital_id,
                bed_type,
                int(old_available),
                int(available_beds),
                now
            )
        )


        # =====================================================
        # COMMIT
        # =====================================================

        conn.commit()


        st.success(
            f"✅ {bed_type} bed data saved successfully!"
        )

        st.info(
            f"🕐 Update History saved: "
            f"{old_available} → {available_beds}"
        )


    except sqlite3.Error as e:

        conn.rollback()

        st.error(
            f"❌ Database error: {e}"
        )


    finally:

        conn.close()


    st.rerun()


# =========================================================
# CURRENT BED STATUS
# =========================================================

st.divider()

st.subheader(
    "📊 Current Bed Status"
)


conn = sqlite3.connect(
    DB_PATH
)

beds = conn.execute(
    """
    SELECT
        bed_type,
        total_beds,
        available_beds,
        last_updated
    FROM beds
    WHERE hospital_id = ?
    ORDER BY bed_type
    """,
    (hospital_id,)
).fetchall()

conn.close()


if not beds:

    st.info(
        "No bed data has been added for this hospital."
    )

else:

    cols = st.columns(3)


    for i, bed in enumerate(beds):

        with cols[i % 3]:

            bed_type_name = bed[0]

            total = int(
                bed[1]
            )

            available = int(
                bed[2]
            )


            st.metric(
                bed_type_name,
                f"{available} / {total}"
            )


            if available == 0:

                st.error(
                    "🔴 No Beds"
                )

            elif available <= 2:

                st.warning(
                    "🟡 Low"
                )

            else:

                st.success(
                    "🟢 Available"
                )


            st.caption(
                f"Updated: {bed[3]}"
            )


# =========================================================
# NAVIGATION
# =========================================================

st.divider()


if st.button(
    "⬅️ Back to Admin Dashboard"
):

    st.switch_page(
        "pages/admin_dashboard.py"
            )
