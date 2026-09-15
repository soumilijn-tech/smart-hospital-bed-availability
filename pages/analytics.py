
import streamlit as st
import sqlite3
import pandas as pd

from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "database" / "hospital.db"

st.set_page_config(
    page_title="Hospital Analytics",
    page_icon="📊",
    layout="wide"
)

# Authentication
if not st.session_state.get("admin_logged_in", False):

    st.warning("🔐 Please login as Admin first.")

    if st.button("Go to Admin Login"):
        st.switch_page("pages/admin_login.py")

    st.stop()


st.title("📊 Hospital Bed Analytics")
st.write(
    f"Admin: **{st.session_state.get('admin_name', 'Admin')}**"
)

st.divider()


# Get data
conn = sqlite3.connect(DB_PATH)

query = """
SELECT
    h.name AS hospital,
    SUM(b.total_beds) AS total_beds,
    SUM(b.available_beds) AS available_beds
FROM hospitals h
JOIN beds b
    ON h.hospital_id = b.hospital_id
GROUP BY h.hospital_id, h.name
ORDER BY h.name
"""

df = pd.read_sql_query(query, conn)

conn.close()


if df.empty:

    st.warning("No hospital data available.")
    st.stop()


df["occupied_beds"] = (
    df["total_beds"] -
    df["available_beds"]
)

df["occupancy_rate"] = (
    df["occupied_beds"] /
    df["total_beds"] * 100
)


# -----------------------------
# Summary
# -----------------------------

total_beds = int(df["total_beds"].sum())
available_beds = int(df["available_beds"].sum())
occupied_beds = int(df["occupied_beds"].sum())

occupancy_rate = (
    occupied_beds / total_beds * 100
    if total_beds > 0
    else 0
)


col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "🛏️ Total Beds",
        total_beds
    )

with col2:
    st.metric(
        "✅ Available",
        available_beds
    )

with col3:
    st.metric(
        "🔴 Occupied",
        occupied_beds
    )

with col4:
    st.metric(
        "📊 Occupancy Rate",
        f"{occupancy_rate:.1f}%"
    )


st.divider()


# -----------------------------
# Hospital-wise table
# -----------------------------

st.subheader("🏥 Hospital-wise Bed Status")

display_df = df.copy()

display_df["occupancy_rate"] = (
    display_df["occupancy_rate"]
    .round(1)
)

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


st.divider()


# -----------------------------
# Available Beds Chart
# -----------------------------

st.subheader("📈 Available Beds by Hospital")

chart_df = df.set_index("hospital")

st.bar_chart(
    chart_df["available_beds"]
)


# -----------------------------
# Low Bed Hospitals
# -----------------------------

st.subheader("⚠️ Low Bed Availability")

low_beds = df[
    df["available_beds"] <= 3
]

if low_beds.empty:

    st.success(
        "🟢 No hospital currently has critically low beds."
    )

else:

    for _, row in low_beds.iterrows():

        st.warning(
            f"⚠️ {row['hospital']} — "
            f"{int(row['available_beds'])} beds available"
        )


st.divider()


if st.button("⬅️ Back to Dashboard"):

    st.switch_page(
        "pages/admin_dashboard.py"
    )
