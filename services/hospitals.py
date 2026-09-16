import requests
import math
from functools import lru_cache


# =========================================================
# API URLS
# =========================================================

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter"
]


HEADERS = {
    "User-Agent": (
        "SmartHospitalBedAvailability/1.0 "
        "(educational project)"
    )
}


# =========================================================
# DISTANCE
# =========================================================

def calculate_distance(
    lat1,
    lon1,
    lat2,
    lon2
):
    """
    Calculate distance between two coordinates
    using Haversine formula.

    Returns distance in KM.
    """

    R = 6371.0

    lat1 = math.radians(float(lat1))
    lon1 = math.radians(float(lon1))

    lat2 = math.radians(float(lat2))
    lon2 = math.radians(float(lon2))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        +
        math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    a = min(
        1.0,
        max(0.0, a)
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return R * c


# =========================================================
# GEOCODING
# =========================================================

def geocode_location(location):
    """
    Convert location name into latitude/longitude.
    """

    location = location.strip()

    if not location:
        return None

    queries = [
        f"{location}, West Bengal, India",
        f"{location}, India",
        location
    ]

    for query_text in queries:

        try:

            response = requests.get(
                NOMINATIM_URL,
                params={
                    "q": query_text,
                    "format": "json",
                    "limit": 5,
                    "addressdetails": 1
                },
                headers=HEADERS,
                timeout=20
            )

            response.raise_for_status()

            results = response.json()

            if not results:
                continue

            # Prefer city/town/locality results
            preferred = []

            for result in results:

                result_type = str(
                    result.get("type", "")
                ).lower()

                result_class = str(
                    result.get("class", "")
                ).lower()

                if result_type in [
                    "city",
                    "town",
                    "village",
                    "municipality",
                    "suburb",
                    "county",
                    "administrative"
                ]:

                    preferred.append(result)

                elif result_class in [
                    "place",
                    "boundary"
                ]:

                    preferred.append(result)

            candidates = (
                preferred
                if preferred
                else results
            )

            for result in candidates:

                try:

                    return {
                        "lat": float(
                            result["lat"]
                        ),
                        "lon": float(
                            result["lon"]
                        )
                    }

                except (
                    KeyError,
                    ValueError,
                    TypeError
                ):
                    continue

        except (
            requests.RequestException,
            ValueError
        ):
            continue

    return None


# =========================================================
# OVERPASS SEARCH
# =========================================================

def _overpass_search(
    lat,
    lon,
    radius
):
    """
    Search hospitals using Overpass API.
    """

    query = f"""
    [out:json][timeout:60];

    (
        nwr["amenity"="hospital"]
        (around:{radius},{lat},{lon});

        nwr["healthcare"="hospital"]
        (around:{radius},{lat},{lon});
    );

    out center tags;
    """

    for url in OVERPASS_URLS:

        # -------------------------
        # Try POST
        # -------------------------

        try:

            response = requests.post(
                url,
                data=query,
                headers=HEADERS,
                timeout=75
            )

            response.raise_for_status()

            data = response.json()

            if data.get("elements") is not None:

                return data.get(
                    "elements",
                    []
                )

        except Exception:
            pass


        # -------------------------
        # Try GET
        # -------------------------

        try:

            response = requests.get(
                url,
                params={
                    "data": query
                },
                headers=HEADERS,
                timeout=75
            )

            response.raise_for_status()

            data = response.json()

            if data.get("elements") is not None:

                return data.get(
                    "elements",
                    []
                )

        except Exception:
            pass

    return []


# =========================================================
# NOMINATIM HOSPITAL FALLBACK
# =========================================================

def _nominatim_hospital_search(
    location,
    lat,
    lon,
    radius
):
    """
    Fallback hospital search using Nominatim.

    This is used if Overpass returns no results.
    """

    radius_km = radius / 1000

    search_queries = [
        f"hospital, {location}, West Bengal, India",
        f"hospital, {location}, India",
        f"hospitals near {location}, West Bengal, India"
    ]

    hospitals = []

    seen = set()

    for search_query in search_queries:

        try:

            response = requests.get(
                NOMINATIM_URL,
                params={
                    "q": search_query,
                    "format": "json",
                    "limit": 50,
                    "addressdetails": 1
                },
                headers=HEADERS,
                timeout=25
            )

            response.raise_for_status()

            results = response.json()

        except Exception:
            continue


        for result in results:

            try:

                hospital_lat = float(
                    result["lat"]
                )

                hospital_lon = float(
                    result["lon"]
                )

            except (
                KeyError,
                ValueError,
                TypeError
            ):
                continue


            distance = calculate_distance(
                lat,
                lon,
                hospital_lat,
                hospital_lon
            )


            if distance > radius_km:
                continue


            # -------------------------
            # Name
            # -------------------------

            name = (
                result.get("name")
                or
                result.get("display_name")
                or
                "Hospital"
            )

            name = str(name).strip()


            # -------------------------
            # Duplicate
            # -------------------------

            unique_key = (
                name.lower(),
                round(
                    hospital_lat,
                    4
                ),
                round(
                    hospital_lon,
                    4
                )
            )

            if unique_key in seen:
                continue

            seen.add(unique_key)


            # -------------------------
            # Address
            # -------------------------

            address_data = result.get(
                "address",
                {}
            )

            address_parts = []

            for key in [
                "road",
                "neighbourhood",
                "suburb",
                "city",
                "town",
                "state"
            ]:

                value = address_data.get(
                    key
                )

                if value:
                    address_parts.append(
                        str(value)
                    )

            if address_parts:

                address = ", ".join(
                    address_parts
                )

            else:

                address = (
                    result.get(
                        "display_name"
                    )
                    or
                    "Address not available"
                )


            hospitals.append(
                {
                    "name": name,
                    "address": address,
                    "phone": "Not available",
                    "latitude": hospital_lat,
                    "longitude": hospital_lon,
                    "distance": round(
                        distance,
                        2
                    )
                }
            )

    return hospitals


# =========================================================
# MAIN HOSPITAL SEARCH
# =========================================================

def find_nearby_hospitals(
    lat,
    lon,
    radius=20000,
    location=""
):
    """
    Main nearby hospital search.

    1. Try Overpass.
    2. If no result, use Nominatim fallback.
    """

    try:

        lat = float(lat)
        lon = float(lon)
        radius = int(radius)

    except (
        ValueError,
        TypeError
    ):

        return []


    if radius <= 0:
        return []


    # Maximum 50 KM
    radius = min(
        radius,
        50000
    )


    # =====================================================
    # STEP 1 — OVERPASS
    # =====================================================

    elements = _overpass_search(
        lat,
        lon,
        radius
    )


    hospitals = []

    seen = set()


    for element in elements:

        tags = element.get(
            "tags",
            {}
        )


        # -------------------------
        # Name
        # -------------------------

        name = (
            tags.get("name")
            or
            tags.get("official_name")
            or
            tags.get("short_name")
            or
            "Unnamed Hospital"
        )

        name = str(name).strip()


        # -------------------------
        # Coordinates
        # -------------------------

        hospital_lat = None
        hospital_lon = None


        if (
            element.get("lat") is not None
            and
            element.get("lon") is not None
        ):

            hospital_lat = element.get(
                "lat"
            )

            hospital_lon = element.get(
                "lon"
            )

        elif element.get("center"):

            center = element.get(
                "center",
                {}
            )

            hospital_lat = center.get(
                "lat"
            )

            hospital_lon = center.get(
                "lon"
            )


        if (
            hospital_lat is None
            or
            hospital_lon is None
        ):
            continue


        try:

            hospital_lat = float(
                hospital_lat
            )

            hospital_lon = float(
                hospital_lon
            )

        except (
            ValueError,
            TypeError
        ):

            continue


        # -------------------------
        # Distance
        # -------------------------

        distance = calculate_distance(
            lat,
            lon,
            hospital_lat,
            hospital_lon
        )


        if distance > radius / 1000:
            continue


        # -------------------------
        # Duplicate
        # -------------------------

        unique_key = (
            name.lower(),
            round(
                hospital_lat,
                4
            ),
            round(
                hospital_lon,
                4
            )
        )


        if unique_key in seen:
            continue

        seen.add(
            unique_key
        )


        # -------------------------
        # Address
        # -------------------------

        address_parts = []

        for key in [
            "addr:housenumber",
            "addr:street",
            "addr:place",
            "addr:suburb",
            "addr:city"
        ]:

            value = tags.get(key)

            if value:
                address_parts.append(
                    str(value)
                )


        if address_parts:

            address = ", ".join(
                address_parts
            )

        else:

            address = (
                tags.get("addr:full")
                or
                tags.get("description")
                or
                "Address not available"
            )


        # -------------------------
        # Phone
        # -------------------------

        phone = (
            tags.get("phone")
            or
            tags.get("contact:phone")
            or
            tags.get("contact:mobile")
            or
            "Not available"
        )


        hospitals.append(
            {
                "name": name,
                "address": address,
                "phone": phone,
                "latitude": hospital_lat,
                "longitude": hospital_lon,
                "distance": round(
                    distance,
                    2
                )
            }
        )


    # =====================================================
    # STEP 2 — FALLBACK
    # =====================================================

    if not hospitals and location:

        hospitals = _nominatim_hospital_search(
            location,
            lat,
            lon,
            radius
        )


    # =====================================================
    # SORT
    # =====================================================

    hospitals.sort(
        key=lambda x: x["distance"]
    )


    return hospitals


# =========================================================
# CACHED SEARCH
# =========================================================

@lru_cache(maxsize=100)
def cached_hospital_search(
    lat,
    lon,
    radius,
    location=""
):
    """
    Cached nearby hospital search.
    """

    return find_nearby_hospitals(
        lat,
        lon,
        radius,
        location
    )
