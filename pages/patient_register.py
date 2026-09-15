
import streamlit as st
import sqlite3

from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "database" / "hospital.db"

st.set_page_config(
    page_title="Patient Registration",
    page_icon="📝",
    layout="centered"
)

st.title("📝 Patient Registration")
st.write("Create your account")
st.divider()

name = st.text_input("👤 Full Name")
email = st.text_input("📧 Email")
password = st.text_input("🔑 Password", type="password")
confirm_password = st.text_input("🔐 Confirm Password", type="password")

if st.button("Register", type="primary"):

    if not name or not email or not password:
        st.warning("⚠️ Please fill all fields.")

    elif password != confirm_password:
        st.error("❌ Passwords do not match.")

    else:
        conn = sqlite3.connect(DB_PATH)

        try:
            conn.execute("""
                INSERT INTO users
                (name, email, password, role)
                VALUES (?, ?, ?, 'PATIENT')
            """, (name, email, password))

            conn.commit()

            st.success("✅ Registration successful!")
            st.info("You can now login with your email and password.")

        except sqlite3.IntegrityError:
            st.error("❌ This email is already registered.")

        finally:
            conn.close()
