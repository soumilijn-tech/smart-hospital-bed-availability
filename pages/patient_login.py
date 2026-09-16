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

    # Clean input
    email_clean = email.strip().lower()

    if not email_clean or not password:
        st.warning("⚠️ Please enter email and password.")

    else:
        conn = None

        try:
            conn = sqlite3.connect(DB_PATH)

            user = conn.execute("""
                SELECT user_id, name, email, role
                FROM users
                WHERE LOWER(TRIM(email)) = ?
                AND password = ?
                AND role = 'PATIENT'
            """, (email_clean, password)).fetchone()

            if user:

                # Save login session
                st.session_state["patient_logged_in"] = True
                st.session_state["patient_id"] = user[0]
                st.session_state["patient_name"] = user[1]
                st.session_state["patient_email"] = user[2]

                st.success(f"✅ Welcome, {user[1]}!")

                # Go directly to dashboard
                st.switch_page("pages/patient_dashboard.py")

            else:
                st.error("❌ Invalid email or password.")

        except sqlite3.Error as e:
            st.error(f"❌ Database error: {e}")

        finally:
            if conn:
                conn.close()

st.divider()

st.write("Don't have an account?")

if st.button("📝 Create Patient Account"):
    st.switch_page("pages/patient_register.py")
