
import streamlit as st
import sqlite3
from datetime import datetime

from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "database" / "hospital.db"

st.set_page_config(
    page_title="Bed Management",
    page_icon="🛏️",
    layout="wide"
)

# =========================
# LOGIN CHECK
# =========================

if not st.session_state.get("admin_logged_in", False):

    st.warning("🔐 Please login as Admin first.")

    if st.button("Go to Admin Login"):
        st.switch_page("pages/admin_login.py")

    st.stop()


st.title("🛏️ Bed Management")
st.write(
    f"Admin: **{st.session_state.get('admin_name', 'Admin')}**"
)

st.divider()


# =========================
# SELECT HOSPITAL
# =========================

conn = sqlite3.connect(DB_PATH)

hospitals = conn.execute("""
    SELECT hospital_id, name
    FROM hospitals
    ORDER BY name
""").fetchall()

conn.close()


if not hospitals:

    st.error("❌ No hospitals found.")
    st.stop()


hospital_dict = {
    name: hospital_id
    for hospital_id, name in hospitals
}

selected_hospital = st.selectbox(
    "🏥 Select Hospital",
    list(hospital_dict.keys())
)

hospital_id = hospital_dict[selected_hospital]


# =========================
# ADD / UPDATE BED DATA
# =========================

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


conn = sqlite3.connect(DB_PATH)

existing = conn.execute("""
    SELECT total_beds, available_beds
    FROM beds
    WHERE hospital_id = ?
    AND bed_type = ?
""", (
    hospital_id,
    bed_type
)).fetchone()

conn.close()


if existing:

    current_total = int(existing[0])
    current_available = int(existing[1])

else:

    current_total = 0
    current_available = 0


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


if st.button(
    "💾 Save Bed Data",
    type="primary"
):

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    conn = sqlite3.connect(DB_PATH)

    if existing:

        conn.execute("""
            UPDATE beds
            SET total_beds = ?,
                available_beds = ?,
                last_updated = ?
            WHERE hospital_id = ?
            AND bed_type = ?
        """, (
            total_beds,
            available_beds,
            now,
            hospital_id,
            bed_type
        ))

    else:

        conn.execute("""
            INSERT INTO beds
            (
                hospital_id,
                bed_type,
                total_beds,
                available_beds,
                last_updated
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            hospital_id,
            bed_type,
            total_beds,
            available_beds,
            now
        ))

    conn.commit()
    conn.close()

    st.success(
        f"✅ {bed_type} bed data saved successfully!"
    )

    st.rerun()


st.divider()


# =========================
# CURRENT BED STATUS
# =========================

st.subheader("📊 Current Bed Status")

conn = sqlite3.connect(DB_PATH)

beds = conn.execute("""
    SELECT
        bed_type,
        total_beds,
        available_beds,
        last_updated
    FROM beds
    WHERE hospital_id = ?
    ORDER BY bed_type
""", (hospital_id,)).fetchall()

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
            total = int(bed[1])
            available = int(bed[2])

            st.metric(
                bed_type_name,
                f"{available} / {total}"
            )

            if available == 0:

                st.error("🔴 No Beds")

            elif available <= 2:

                st.warning("🟡 Low")

            else:

                st.success("🟢 Available")

            st.caption(
                f"Updated: {bed[3]}"
            )


st.divider()


if st.button("⬅️ Back to Admin Dashboard"):

    st.switch_page(
        "pages/admin_dashboard.py"
    )
