
import streamlit as st
import sqlite3

DB_PATH = "/content/smart_hospital/database/hospital.db"

st.set_page_config(
    page_title="Admin Dashboard",
    page_icon="🏥",
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


# =========================
# HEADER
# =========================

col1, col2 = st.columns([4, 1])

with col1:
    st.title("🏥 Admin Dashboard")
    st.write(
        f"Welcome, **{st.session_state.get('admin_name', 'Admin')}**"
    )

with col2:

    if st.button("🚪 Logout"):

        st.session_state["admin_logged_in"] = False
        st.session_state.pop("admin_name", None)

        st.switch_page("pages/admin_login.py")


st.divider()


# =========================
# ADMIN NAVIGATION
# =========================

st.subheader("⚙️ Management Panel")

col1, col2, col3, col4 = st.columns(4)

with col1:

    if st.button(
        "🏥 Hospital Management",
        use_container_width=True
    ):
        st.switch_page(
            "pages/hospital_management.py"
        )

with col2:

    if st.button(
        "🛏️ Bed Management",
        use_container_width=True
    ):
        st.switch_page(
            "pages/bed_management.py"
        )

with col3:

    if st.button(
        "📋 Update History",
        use_container_width=True
    ):
        st.switch_page(
            "pages/update_history.py"
        )

with col4:

    if st.button(
        "📊 Analytics",
        use_container_width=True
    ):
        st.switch_page(
            "pages/analytics.py"
        )


st.divider()


# =========================
# HOSPITAL SUMMARY
# =========================

st.subheader("🏥 Hospital Bed Summary")

conn = sqlite3.connect(DB_PATH)

query = """
SELECT
    h.hospital_id,
    h.name,
    SUM(b.total_beds) AS total_beds,
    SUM(b.available_beds) AS available_beds
FROM hospitals h
LEFT JOIN beds b
ON h.hospital_id = b.hospital_id
GROUP BY h.hospital_id, h.name
ORDER BY h.name
"""

hospitals = conn.execute(
    query
).fetchall()

conn.close()


if not hospitals:

    st.info("No hospital data available.")

else:

    for hospital in hospitals:

        hospital_id = hospital[0]
        hospital_name = hospital[1]
        total = int(hospital[2] or 0)
        available = int(hospital[3] or 0)
        occupied = total - available

        with st.container(border=True):

            st.markdown(
                f"### 🏥 {hospital_name}"
            )

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "🛏️ Total Beds",
                    total
                )

            with col2:
                st.metric(
                    "✅ Available",
                    available
                )

            with col3:
                st.metric(
                    "🔴 Occupied",
                    occupied
                )


st.divider()

st.info(
    "💡 Use Bed Management to add or update "
    "General, ICU and Emergency bed availability."
)
