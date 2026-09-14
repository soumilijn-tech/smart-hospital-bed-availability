
import streamlit as st
import sqlite3

DB_PATH = "/content/smart_hospital/database/hospital.db"

st.set_page_config(
    page_title="Admin Login",
    page_icon="🔐",
    layout="centered"
)

st.title("🔐 Admin Login")
st.write("Smart Hospital Bed Availability System")

st.divider()

email = st.text_input(
    "📧 Admin Email"
)

password = st.text_input(
    "🔑 Password",
    type="password"
)

if st.button(
    "Login",
    type="primary"
):

    conn = sqlite3.connect(DB_PATH)

    user = conn.execute("""
        SELECT user_id, name, role
        FROM users
        WHERE email = ?
        AND password = ?
        AND role = 'ADMIN'
    """, (
        email,
        password
    )).fetchone()

    conn.close()

    if user:

        st.session_state["admin_logged_in"] = True
        st.session_state["admin_name"] = user[1]

        st.success(
            f"✅ Welcome, {user[1]}!"
        )

        st.switch_page(
            "pages/admin_dashboard.py"
        )

    else:

        st.error(
            "❌ Invalid admin email or password."
        )
