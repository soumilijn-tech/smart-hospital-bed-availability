
import streamlit as st
import sqlite3

from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "database" / "hospital.db"

st.set_page_config(
    page_title="Patient Login",
    page_icon="🔐",
    layout="centered"
)

st.title("🔐 Patient Login")
st.write("Login to Smart Hospital Bed Availability System")
st.divider()

email = st.text_input("📧 Email")
password = st.text_input("🔑 Password", type="password")

if st.button("Login", type="primary"):

    if not email or not password:
        st.warning("⚠️ Please enter email and password.")

    else:
        conn = sqlite3.connect(DB_PATH)

        user = conn.execute("""
            SELECT user_id, name, email, role
            FROM users
            WHERE email = ?
            AND password = ?
            AND role = 'PATIENT'
        """, (email, password)).fetchone()

        conn.close()

        if user:
            st.session_state["patient_logged_in"] = True
            st.session_state["patient_id"] = user[0]
            st.session_state["patient_name"] = user[1]

            st.success(f"✅ Welcome, {user[1]}!")

        else:
            st.error("❌ Invalid email or password.")

st.divider()

st.write("Don't have an account?")

if st.button("📝 Create Patient Account"):
    st.switch_page("pages/patient_register.py")
