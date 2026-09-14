
import streamlit as st
import sqlite3

DB_PATH = "/content/smart_hospital/database/hospital.db"

st.set_page_config(
    page_title="Hospital Management",
    page_icon="🏥",
    layout="wide"
)

# Login check
if not st.session_state.get("admin_logged_in", False):

    st.warning("🔐 Please login as Admin first.")

    if st.button("Go to Admin Login"):
        st.switch_page("pages/admin_login.py")

    st.stop()


st.title("🏥 Hospital Management")
st.write(
    f"Admin: **{st.session_state.get('admin_name', 'Admin')}**"
)

st.divider()


# =========================
# ADD HOSPITAL
# =========================

st.subheader("➕ Add New Hospital")

name = st.text_input("🏥 Hospital Name")
address = st.text_input("📍 Address")
latitude = st.number_input(
    "Latitude",
    value=22.5726,
    format="%.6f"
)
longitude = st.number_input(
    "Longitude",
    value=88.3639,
    format="%.6f"
)
phone = st.text_input("📞 Phone")
email = st.text_input("📧 Hospital Email")


if st.button(
    "➕ Add Hospital",
    type="primary"
):

    if not name.strip():

        st.warning(
            "⚠️ Hospital name is required."
        )

    else:

        conn = sqlite3.connect(DB_PATH)

        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO hospitals
            (
                name,
                address,
                latitude,
                longitude,
                phone,
                email
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                address,
                latitude,
                longitude,
                phone,
                email
            )
        )

        conn.commit()

        new_hospital_id = cursor.lastrowid

        conn.close()

        st.success(
            f"✅ {name} added successfully!"
        )

        st.info(
            f"Hospital ID: {new_hospital_id}"
        )

        st.rerun()


st.divider()


# =========================
# HOSPITAL LIST
# =========================

st.subheader("📋 Registered Hospitals")

conn = sqlite3.connect(DB_PATH)

hospitals = conn.execute(
    """
    SELECT
        hospital_id,
        name,
        address,
        phone,
        email
    FROM hospitals
    ORDER BY hospital_id
    """
).fetchall()

conn.close()


if not hospitals:

    st.info("No hospitals registered.")

else:

    for hospital in hospitals:

        hospital_id = hospital[0]
        hospital_name = hospital[1]

        with st.container(border=True):

            st.markdown(
                f"### 🏥 {hospital_name}"
            )

            col1, col2 = st.columns(2)

            with col1:

                st.write(
                    f"**Hospital ID:** {hospital_id}"
                )

                st.write(
                    f"📍 **Address:** {hospital[2]}"
                )

                st.write(
                    f"📞 **Phone:** {hospital[3]}"
                )

            with col2:

                st.write(
                    f"📧 **Email:** {hospital[4]}"
                )


st.divider()


if st.button("⬅️ Back to Admin Dashboard"):

    st.switch_page(
        "pages/admin_dashboard.py"
    )
