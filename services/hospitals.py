import requests
import math
from functools import lru_cache


# =========================
# CONSTANTS
# =========================

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

HEADERS = {
    "User-Agent": "SmartHospitalBedAvailability/1.0"
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

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        +
        math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

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
    Convert city/district/locality name into latitude/longitude.
    """

    location = location.strip()

    if not location:
        return None

    params = {
        "q": location,
        "format": "json",
        "limit": 1,
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
            return None

        result = data[0]

        return {
            "lat": float(result["lat"]),
            "lon": float(result["lon"])
        }

    except requests.RequestException:
        return None

    except (ValueError, KeyError, TypeError):
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
    Find hospitals around a location using OpenStreetMap Overpass.

    radius is in meters.
    Default = 20 KM.
    """

    query = f"""
    [out:json][timeout:60];

    (
        node["amenity"="hospital"]
            (around:{radius},{lat},{lon});

        way["amenity"="hospital"]
            (around:{radius},{lat},{lon});

        relation["amenity"="hospital"]
            (around:{radius},{lat},{lon});

        node["healthcare"="hospital"]
            (around:{radius},{lat},{lon});

        way["healthcare"="hospital"]
            (around:{radius},{lat},{lon});

        relation["healthcare"="hospital"]
            (around:{radius},{lat},{lon});
    );

    out center tags;
    """

    try:

        response = requests.post(
            OVERPASS_URL,
            data=query,
            headers=HEADERS,
            timeout=70
        )

        response.raise_for_status()

        data = response.json()

    except requests.RequestException:
        return []

    except ValueError:
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


        # -------------------------
        # HOSPITAL NAME
        # -------------------------

        name = (
            tags.get("name")
            or
            tags.get("official_name")
            or
            tags.get("short_name")
        )


        if not name:
            name = "Unnamed Hospital"


        # -------------------------
        # COORDINATES
        # -------------------------

        hospital_lat = None
        hospital_lon = None


        if (
            "lat" in element
            and
            "lon" in element
        ):

            hospital_lat = element["lat"]
            hospital_lon = element["lon"]


        elif "center" in element:

            center = element["center"]

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


        # -------------------------
        # DUPLICATE CHECK
        # -------------------------

        unique_key = (
            name.strip().lower(),
            round(
                float(hospital_lat),
                4
            ),
            round(
                float(hospital_lon),
                4
            )
        )


        if unique_key in seen:
            continue


        seen.add(unique_key)


        # -------------------------
        # ADDRESS
        # -------------------------

        address = (
            tags.get("addr:full")
            or
            tags.get("addr:street")
            or
            tags.get("addr:place")
            or
            tags.get("addr:city")
            or
            "Address not available"
        )


        # -------------------------
        # PHONE
        # -------------------------

        phone = (
            tags.get("phone")
            or
            tags.get("contact:phone")
            or
            "Not available"
        )


        # -------------------------
        # DISTANCE
        # -------------------------

        distance = calculate_distance(
            lat,
            lon,
            float(hospital_lat),
            float(hospital_lon)
        )


        hospitals.append(
            {
                "name": name,
                "address": address,
                "phone": phone,
                "latitude": float(
                    hospital_lat
                ),
                "longitude": float(
                    hospital_lon
                ),
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
    Cached version of hospital search.

    Same location + radius will use
    cached data instead of repeatedly
    calling Overpass.
    """

    return find_nearby_hospitals(
        lat,
        lon,
        radius
            )
