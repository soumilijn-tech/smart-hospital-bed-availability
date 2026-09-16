import streamlit as st
import sqlite3
import bcrypt
from pathlib import Path

DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "database"
    / "hospital.db"
)

st.set_page_config(
    page_title="Admin Login",
    page_icon="🔐",
    layout="centered"
)

st.title("🔐 Admin Login")
st.write("Smart Hospital Bed Availability System")
st.divider()

email = st.text_input(
    "📧 Admin Email",
    value="admin@hospital.com"
)

password = st.text_input(
    "🔑 Password",
    type="password"
)

if st.button("Login", type="primary"):

    email_clean = email.strip().lower()

    if not email_clean or not password:
        st.warning("⚠️ Please enter email and password.")
        st.stop()

    conn = None

    try:
        conn = sqlite3.connect(DB_PATH)

        # Make sure users table exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL
            )
        """)

        conn.commit()

        # Find admin
        admin = conn.execute(
            """
            SELECT
                user_id,
                name,
                email,
                password,
                role
            FROM users
            WHERE LOWER(TRIM(email)) = ?
            AND UPPER(role) = 'ADMIN'
            LIMIT 1
            """,
            (email_clean,)
        ).fetchone()

        # If admin does not exist, create default admin
        if not admin:

            password_hash = bcrypt.hashpw(
                password.encode("utf-8"),
                bcrypt.gensalt()
            ).decode("utf-8")

            conn.execute(
                """
                INSERT INTO users
                (
                    name,
                    email,
                    password,
                    role
                )
                VALUES (?, ?, ?, 'ADMIN')
                """,
                (
                    "Hospital Admin",
                    email_clean,
                    password_hash
                )
            )

            conn.commit()

            admin = conn.execute(
                """
                SELECT
                    user_id,
                    name,
                    email,
                    password,
                    role
                FROM users
                WHERE LOWER(TRIM(email)) = ?
                AND UPPER(role) = 'ADMIN'
                LIMIT 1
                """,
                (email_clean,)
            ).fetchone()

        user_id = admin[0]
        user_name = admin[1]
        stored_password = str(admin[3])

        password_valid = False

        # Check bcrypt password
        if (
            stored_password.startswith("$2a$")
            or stored_password.startswith("$2b$")
            or stored_password.startswith("$2y$")
        ):
            try:
                password_valid = bcrypt.checkpw(
                    password.encode("utf-8"),
                    stored_password.encode("utf-8")
                )
            except Exception:
                password_valid = False

        # Check old plain-text password
        else:
            if stored_password == password:
                password_valid = True

                # Upgrade to bcrypt
                new_hash = bcrypt.hashpw(
                    password.encode("utf-8"),
                    bcrypt.gensalt()
                ).decode("utf-8")

                conn.execute(
                    """
                    UPDATE users
                    SET password = ?
                    WHERE user_id = ?
                    """,
                    (
                        new_hash,
                        user_id
                    )
                )

                conn.commit()

        if password_valid:

            st.session_state["admin_logged_in"] = True
            st.session_state["admin_id"] = user_id
            st.session_state["admin_name"] = user_name

            st.success(
                f"✅ Welcome, {user_name}!"
            )

            st.switch_page(
                "pages/admin_dashboard.py"
            )

        else:

            st.error(
                "❌ Invalid admin email or password."
            )

    except sqlite3.Error as e:

        st.error(
            f"❌ Database error: {e}"
        )

    finally:

        if conn:
            conn.close()
