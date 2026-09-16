import requests
import math
from functools import lru_cache


# =========================
# CONSTANTS
# =========================

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


# =========================
# DISTANCE CALCULATION
# =========================

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two coordinates in KM.
    Uses the Haversine formula.
    """

    R = 6371.0

    # Convert ALL coordinates to radians
    lat1_rad = math.radians(float(lat1))
    lon1_rad = math.radians(float(lon1))

    lat2_rad = math.radians(float(lat2))
    lon2_rad = math.radians(float(lon2))

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = (
        math.sin(dlat / 2) ** 2
        +
        math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(dlon / 2) ** 2
    )

    # Protect against floating-point errors
    a = min(1.0, max(0.0, a))

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return R * c


# =========================
# GEOCODING
# =========================

def geocode_location(location):
    """
    Convert city/district/locality name
    into latitude and longitude.

    Tries multiple search formats so that
    locations like Kolkata, Tamluk, etc.
    are more reliable.
    """

    location = location.strip()

    if not location:
        return None

    search_queries = [
        location,
        f"{location}, West Bengal, India",
        f"{location}, India"
    ]

    for search_query in search_queries:

        params = {
            "q": search_query,
            "format": "json",
            "limit": 5,
            "addressdetails": 1
        }

        try:

            response = requests.get(
                NOMINATIM_URL,
                params=params,
                headers=HEADERS,
                timeout=15
            )

            response.raise_for_status()

            data = response.json()

            if not data:
                continue

            # Prefer results that look like a city/town/locality
            for result in data:

                try:

                    lat = float(result["lat"])
                    lon = float(result["lon"])

                except (
                    ValueError,
                    KeyError,
                    TypeError
                ):
                    continue

                return {
                    "lat": lat,
                    "lon": lon
                }

        except requests.RequestException:
            continue

        except ValueError:
            continue

    return None


# =========================
# OVERPASS QUERY
# =========================

def _get_overpass_data(
    lat,
    lon,
    radius
):
    """
    Query OpenStreetMap Overpass servers.

    Tries multiple servers if one fails.
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

    for overpass_url in OVERPASS_URLS:

        try:

            response = requests.post(
                overpass_url,
                data=query,
                headers=HEADERS,
                timeout=70
            )

            response.raise_for_status()

            data = response.json()

            if data.get("elements") is not None:
                return data

        except requests.RequestException:
            continue

        except ValueError:
            continue

    return None


# =========================
# NEARBY HOSPITAL SEARCH
# =========================

def find_nearby_hospitals(
    lat,
    lon,
    radius=20000
):
    """
    Find hospitals around a location
    using OpenStreetMap Overpass.

    radius is in meters.
    Default = 20 KM.
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

    # Safety limits
    if radius <= 0:
        return []

    if radius > 50000:
        radius = 50000

    data = _get_overpass_data(
        lat,
        lon,
        radius
    )

    if not data:
        return []

    hospitals = []

    seen = set()

    # =========================
    # PROCESS RESULTS
    # =========================

    for element in data.get(
        "elements",
        []
    ):

        tags = element.get(
            "tags",
            {}
        )

        # =========================
        # HOSPITAL NAME
        # =========================

        name = (
            tags.get("name")
            or
            tags.get("official_name")
            or
            tags.get("short_name")
        )

        if not name:
            name = "Unnamed Hospital"

        name = str(name).strip()

        # =========================
        # COORDINATES
        # =========================

        hospital_lat = None
        hospital_lon = None

        # Node
        if (
            element.get("lat") is not None
            and
            element.get("lon") is not None
        ):

            hospital_lat = element.get("lat")
            hospital_lon = element.get("lon")

        # Way / Relation
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

        # =========================
        # DISTANCE
        # =========================

        distance = calculate_distance(
            lat,
            lon,
            hospital_lat,
            hospital_lon
        )

        # =========================
        # RADIUS CHECK
        # =========================

        if distance > radius / 1000:
            continue

        # =========================
        # DUPLICATE CHECK
        # =========================

        unique_key = (
            name.lower(),
            round(hospital_lat, 4),
            round(hospital_lon, 4)
        )

        if unique_key in seen:
            continue

        seen.add(unique_key)

        # =========================
        # ADDRESS
        # =========================

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

        # =========================
        # PHONE
        # =========================

        phone = (
            tags.get("phone")
            or
            tags.get("contact:phone")
            or
            tags.get("contact:mobile")
            or
            "Not available"
        )

        # =========================
        # HOSPITAL DATA
        # =========================

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

    # =========================
    # SORT BY DISTANCE
    # =========================

    hospitals.sort(
        key=lambda x: x["distance"]
    )

    return hospitals


# =========================
# CACHED HOSPITAL SEARCH
# =========================

@lru_cache(maxsize=100)
def cached_hospital_search(
    lat,
    lon,
    radius
):
    """
    Cached hospital search.

    Same location + radius can reuse
    previously retrieved hospital data.
    """

    return find_nearby_hospitals(
        lat,
        lon,
        radius
        )
