# ============================================================
# GET REGISTERED HOSPITAL DATA
# ============================================================

def get_hospital_data():

    try:

        conn = get_connection()

        # Check hospitals table columns
        hospital_columns = pd.read_sql_query(
            "PRAGMA table_info(hospitals)",
            conn
        )

        column_names = hospital_columns["name"].tolist()

        # Find hospital ID column
        if "id" in column_names:
            hospital_id_col = "id"

        elif "hospital_id" in column_names:
            hospital_id_col = "hospital_id"

        else:
            conn.close()

            st.error(
                "❌ No hospital ID column found in hospitals table."
            )

            return pd.DataFrame()

        # Find name column
        if "name" in column_names:
            name_col = "name"

        elif "hospital_name" in column_names:
            name_col = "hospital_name"

        else:
            conn.close()

            st.error(
                "❌ No hospital name column found."
            )

            return pd.DataFrame()

        # Find address column
        if "address" in column_names:
            address_col = "address"
        else:
            address_col = None

        # Find phone column
        if "phone" in column_names:
            phone_col = "phone"
        else:
            phone_col = None

        # Build SQL dynamically
        address_sql = (
            f"h.{address_col}"
            if address_col
            else "''"
        )

        phone_sql = (
            f"h.{phone_col}"
            if phone_col
            else "''"
        )

        query = f"""
        SELECT
            h.{hospital_id_col} AS hospital_id,
            h.{name_col} AS name,
            {address_sql} AS address,
            {phone_sql} AS phone,
            COALESCE(
                SUM(b.total_beds), 0
            ) AS total_beds,
            COALESCE(
                SUM(b.available_beds), 0
            ) AS available_beds

        FROM hospitals h

        LEFT JOIN beds b
            ON h.{hospital_id_col} = b.hospital_id

        GROUP BY
            h.{hospital_id_col},
            h.{name_col},
            {address_sql},
            {phone_sql}
        """

        df = pd.read_sql_query(
            query,
            conn
        )

        conn.close()

        return df

    except Exception as e:

        st.error(
            f"❌ Database error: {e}"
        )

        return pd.DataFrame()


# ============================================================
# GET BED DETAILS
# ============================================================

def get_bed_details(hospital_id):

    try:

        conn = get_connection()

        query = """
        SELECT
            bed_type,
            total_beds,
            available_beds,
            last_updated

        FROM beds

        WHERE hospital_id = ?
        """

        df = pd.read_sql_query(
            query,
            conn,
            params=(hospital_id,)
        )

        conn.close()

        return df

    except Exception as e:

        st.error(
            f"❌ Bed details error: {e}"
        )

        return pd.DataFrame()
