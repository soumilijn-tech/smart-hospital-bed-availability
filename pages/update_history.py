
import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "database" / "hospital.db"

st.set_page_config(
    page_title="Bed Update History",
    page_icon="📋",
    layout="wide"
)

# -----------------------------
# Authentication
# -----------------------------

if not st.session_state.get("admin_logged_in", False):

    st.warning("🔐 Please login as Admin first.")

    if st.button("Go to Admin Login"):
        st.switch_page("pages/admin_login.py")

    st.stop()


st.title("📋 Bed Update History")

st.write(
    f"Admin: **{st.session_state.get('admin_name', 'Admin')}**"
)

st.divider()


# -----------------------------
# Get History
# -----------------------------

conn = sqlite3.connect(DB_PATH)

query = """
SELECT
    h.name AS hospital,
    bu.bed_type AS bed_type,
    bu.old_available AS old_available,
    bu.new_available AS new_available,
    bu.updated_at AS updated_at
FROM bed_updates bu
JOIN hospitals h
    ON bu.hospital_id = h.hospital_id
ORDER BY bu.updated_at DESC
"""

history = pd.read_sql_query(
    query,
    conn
)

conn.close()


# -----------------------------
# Display
# -----------------------------

if history.empty:

    st.info(
        "📭 No bed availability updates yet."
    )

else:

    st.success(
        f"📊 Total Updates: {len(history)}"
    )

    st.dataframe(
        history,
        use_container_width=True,
        hide_index=True
    )


st.divider()


# -----------------------------
# Navigation
# -----------------------------

if st.button("⬅️ Back to Dashboard"):

    st.switch_page(
        "pages/admin_dashboard.py"
    )
