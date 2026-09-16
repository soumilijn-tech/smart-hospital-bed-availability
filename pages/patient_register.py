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
st.write("Create your patient account")
st.divider()

name = st.text_input("👤 Full Name")
email = st.text_input("📧 Email")
password = st.text_input("🔑 Password", type="password")
confirm_password = st.text_input("🔐 Confirm Password", type="password")

if st.button("Register", type="primary"):

    # Clean user input
    name_clean = name.strip()
    email_clean = email.strip().lower()

    # Validation
    if not name_clean or not email_clean or not password or not confirm_password:
        st.warning("⚠️ Please fill all fields.")

    elif "@" not in email_clean:
        st.warning("⚠️ Please enter a valid email address.")

    elif password != confirm_password:
        st.error("❌ Passwords do not match.")

    else:
        conn = None

        try:
            conn = sqlite3.connect(DB_PATH)

            # Check whether email already exists
            existing_user = conn.execute("""
                SELECT user_id
                FROM users
                WHERE LOWER(TRIM(email)) = ?
            """, (email_clean,)).fetchone()

            if existing_user:
                st.error("❌ This email is already registered.")

            else:
                conn.execute("""
                    INSERT INTO users
                    (name, email, password, role)
                    VALUES (?, ?, ?, 'PATIENT')
                """, (name_clean, email_clean, password))

                conn.commit()

                st.success("✅ Registration successful!")
                st.info("You can now login with your email and password.")

        except sqlite3.Error as e:
            st.error(f"❌ Database error: {e}")

        finally:
            if conn:
                conn.close()
