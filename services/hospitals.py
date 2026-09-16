import requests
import math
from functools import lru_cache


# =========================================================
# API CONFIGURATION
# =========================================================

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

HEADERS = {
    "User-Agent": "SmartHospitalBedAvailability/1.0"
}


# =========================================================
# DISTANCE CALCULATION
# =========================================================

def calculate_distance(lat1, lon1, lat2, lon2):

    R = 6371.0

    lat1 = math.radians(float(lat1))
    lat2 = math.radians(float(lat2))

    lon1 = math.radians(float(lon1))
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

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return R * c


# =========================================================
# GEOCODING
# =========================================================

def geocode_location(location):

    location = location.strip()

    if not location:
        return None

    queries = [
        location,
        f"{location}, India",
        f"{location}, West Bengal, India"
    ]

    for query in queries:

        params = {
            "q": query,
            "format": "json",
            "limit": 1,
            "addressdetails": 1
        }

        try:

            response = requests.get(
                NOMINATIM_URL,
                params=params,
                headers=HEADERS,
                timeout=20
            )

            response.raise_for_status()

            data = response.json()

            if data:

                result = data[0]

                return {
                    "lat": float(result["lat"]),
                    "lon": float(result["lon"])
                }

        except Exception:
            continue

    return None


# =========================================================
# OVERPASS HOSPITAL SEARCH
# =========================================================

def _overpass_search(lat, lon, radius):

    query = f"""
    [out:json][timeout:90];

    (
        nwr["amenity"="hospital"](around:{int(radius)},{lat},{lon});
        nwr["healthcare"="hospital"](around:{int(radius)},{lat},{lon});
    );

    out center tags;
    """

    for server in OVERPASS_SERVERS:

        try:

            response = requests.post(
                server,
                data=query,
                headers=HEADERS,
                timeout=100
            )

            response.raise_for_status()

            data = response.json()

            elements = data.get(
                "elements",
                []
            )

            if elements:

                return elements

        except Exception:

            continue

    return []


# =========================================================
# CREATE HOSPITAL RESULT
# =========================================================

def _build_hospital_list(
    elements,
    lat,
    lon,
    radius
):

    hospitals = []

    seen = set()

    for element in elements:

        tags = element.get(
            "tags",
            {}
        )

        name = (
            tags.get("name")
            or tags.get("official_name")
            or tags.get("short_name")
        )

        if not name:
            continue


        # =================================================
        # GET COORDINATES
        # =================================================

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

            hospital_lat = center.get("lat")
            hospital_lon = center.get("lon")


        if (
            hospital_lat is None
            or
            hospital_lon is None
        ):

            continue


        hospital_lat = float(
            hospital_lat
        )

        hospital_lon = float(
            hospital_lon
        )


        # =================================================
        # DISTANCE
        # =================================================

        distance = calculate_distance(
            lat,
            lon,
            hospital_lat,
            hospital_lon
        )


        # =================================================
        # RADIUS FILTER
        # =================================================

        if distance > (
            float(radius) / 1000
        ):

            continue


        # =================================================
        # DUPLICATE CHECK
        # =================================================

        unique_key = (
            name.strip().lower(),
            round(hospital_lat, 4),
            round(hospital_lon, 4)
        )

        if unique_key in seen:
            continue

        seen.add(unique_key)


        # =================================================
        # ADDRESS
        # =================================================

        address = (
            tags.get("addr:full")
            or tags.get("addr:street")
            or tags.get("addr:place")
            or tags.get("addr:suburb")
            or tags.get("addr:city")
            or "Address not available"
        )


        # =================================================
        # PHONE
        # =================================================

        phone = (
            tags.get("phone")
            or tags.get("contact:phone")
            or "Not available"
        )


        hospitals.append({

            "name": name.strip(),

            "address": address,

            "phone": phone,

            "latitude": hospital_lat,

            "longitude": hospital_lon,

            "distance": round(
                distance,
                2
            )

        })


    hospitals.sort(
        key=lambda x: x["distance"]
    )

    return hospitals


# =========================================================
# NOMINATIM HOSPITAL FALLBACK
# =========================================================

def _nominatim_hospital_search(
    location,
    lat,
    lon,
    radius
):

    if not location:
        return []


    queries = [
        f"hospital near {location}",
        f"hospitals in {location}",
        f"hospital {location}"
    ]


    hospitals = []

    seen = set()


    for query in queries:

        params = {
            "q": query,
            "format": "json",
            "limit": 50,
            "addressdetails": 1
        }


        try:

            response = requests.get(
                NOMINATIM_URL,
                params=params,
                headers=HEADERS,
                timeout=30
            )

            response.raise_for_status()

            data = response.json()


        except Exception:

            continue


        for result in data:

            try:

                hospital_lat = float(
                    result["lat"]
                )

                hospital_lon = float(
                    result["lon"]
                )

            except (
                ValueError,
                KeyError,
                TypeError
            ):

                continue


            distance = calculate_distance(
                lat,
                lon,
                hospital_lat,
                hospital_lon
            )


            if distance > (
                float(radius) / 1000
            ):

                continue


            name = (
                result.get("display_name")
                or result.get("name")
                or "Hospital"
            )


            address = (
                result.get("display_name")
                or "Address not available"
            )


            unique_key = (
                name.lower(),
                round(hospital_lat, 4),
                round(hospital_lon, 4)
            )


            if unique_key in seen:
                continue


            seen.add(unique_key)


            hospitals.append({

                "name": name,

                "address": address,

                "phone": "Not available",

                "latitude": hospital_lat,

                "longitude": hospital_lon,

                "distance": round(
                    distance,
                    2
                )

            })


    hospitals.sort(
        key=lambda x: x["distance"]
    )


    return hospitals


# =========================================================
# MAIN HOSPITAL SEARCH
# =========================================================

def find_nearby_hospitals(
    lat,
    lon,
    radius=20000,
    location=None
):

    lat = float(lat)
    lon = float(lon)
    radius = float(radius)


    # =================================================
    # FIRST: OVERPASS
    # =================================================

    elements = _overpass_search(
        lat,
        lon,
        radius
    )


    if elements:

        hospitals = _build_hospital_list(
            elements,
            lat,
            lon,
            radius
        )

        if hospitals:

            return hospitals


    # =================================================
    # SECOND: NOMINATIM FALLBACK
    # =================================================

    if location:

        hospitals = _nominatim_hospital_search(
            location,
            lat,
            lon,
            radius
        )

        if hospitals:

            return hospitals


    return []


# =========================================================
# CACHED HOSPITAL SEARCH
# =========================================================

@lru_cache(maxsize=100)
def cached_hospital_search(
    lat,
    lon,
    radius,
    location=None
):

    return find_nearby_hospitals(
        lat,
        lon,
        radius,
        location
    )
