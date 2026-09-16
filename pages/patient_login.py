import streamlit as st
import sqlite3
import bcrypt

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
    page_title="Patient Login",
    page_icon="🔐",
    layout="centered"
)


# =========================================================
# HEADER
# =========================================================

st.title("🔐 Patient Login")

st.write(
    "Login to Smart Hospital Bed Availability System"
)

st.divider()


# =========================================================
# LOGIN FORM
# =========================================================

email = st.text_input(
    "📧 Email"
)

password = st.text_input(
    "🔑 Password",
    type="password"
)


# =========================================================
# LOGIN
# =========================================================

if st.button(
    "Login",
    type="primary"
):

    email_clean = email.strip().lower()


    # =====================================================
    # VALIDATION
    # =====================================================

    if not email_clean or not password:

        st.warning(
            "⚠️ Please enter email and password."
        )

    else:

        conn = None

        try:

            conn = sqlite3.connect(
                DB_PATH
            )


            # =================================================
            # FIND PATIENT
            # =================================================

            user = conn.execute(
                """
                SELECT
                    user_id,
                    name,
                    email,
                    password,
                    role
                FROM users
                WHERE LOWER(TRIM(email)) = ?
                AND role = 'PATIENT'
                """,
                (email_clean,)
            ).fetchone()


            if not user:

                st.error(
                    "❌ Invalid email or password."
                )

            else:

                user_id = user[0]
                user_name = user[1]
                user_email = user[2]
                stored_password = user[3]


                password_valid = False


                # =================================================
                # PASSWORD CHECK
                # =================================================

                try:

                    # Convert database value to string
                    stored_password = str(
                        stored_password
                    )


                    # -------------------------------------------------
                    # NEW BCRYPT PASSWORD
                    # -------------------------------------------------

                    if (
                        stored_password.startswith("$2a$")
                        or
                        stored_password.startswith("$2b$")
                        or
                        stored_password.startswith("$2y$")
                    ):

                        password_valid = bcrypt.checkpw(
                            password.encode("utf-8"),
                            stored_password.encode("utf-8")
                        )


                    # -------------------------------------------------
                    # OLD / PLAIN TEXT PASSWORD
                    # -------------------------------------------------

                    else:

                        if stored_password == password:

                            password_valid = True

                            # Upgrade old password to bcrypt
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


                except (
                    ValueError,
                    TypeError,
                    AttributeError
                ):

                    password_valid = False


                # =================================================
                # LOGIN SUCCESS
                # =================================================

                if password_valid:

                    st.session_state[
                        "patient_logged_in"
                    ] = True

                    st.session_state[
                        "patient_id"
                    ] = user_id

                    st.session_state[
                        "patient_name"
                    ] = user_name

                    st.session_state[
                        "patient_email"
                    ] = user_email


                    st.success(
                        f"✅ Welcome, {user_name}!"
                    )


                    st.switch_page(
                        "pages/patient_dashboard.py"
                    )


                # =================================================
                # LOGIN FAILED
                # =================================================

                else:

                    st.error(
                        "❌ Invalid email or password."
                    )


        except sqlite3.Error as e:

            st.error(
                f"❌ Database error: {e}"
            )


        finally:

            if conn:

                conn.close()


# =========================================================
# REGISTRATION LINK
# =========================================================

st.divider()

st.write(
    "Don't have an account?"
)


if st.button(
    "📝 Create Patient Account"
):

    st.switch_page(
        "pages/patient_register.py"
    )
