
import requests
import math
from functools import lru_cache


def calculate_distance(lat1, lon1, lat2, lon2):

    R = 6371

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return R * c


def geocode_location(location):

    url = "https://nominatim.openstreetmap.org/search"

    params = {
        "q": location,
        "format": "json",
        "limit": 1
    }

    headers = {
        "User-Agent": "SmartHospitalBedAvailability/1.0"
    }

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    if not data:
        return None

    return {
        "lat": float(data[0]["lat"]),
        "lon": float(data[0]["lon"])
    }


def find_nearby_hospitals(lat, lon, radius=10000):

    query = f"""
    [out:json][timeout:25];

    (
        node["amenity"="hospital"]
        (around:{radius},{lat},{lon});

        way["amenity"="hospital"]
        (around:{radius},{lat},{lon});

        relation["amenity"="hospital"]
        (around:{radius},{lat},{lon});
    );

    out center tags;
    """

    response = requests.post(
        "https://overpass-api.de/api/interpreter",
        data=query,
        headers={
            "User-Agent": "SmartHospitalBedAvailability/1.0"
        },
        timeout=40
    )

    response.raise_for_status()

    data = response.json()

    hospitals = []

    for element in data.get("elements", []):

        tags = element.get("tags", {})

        name = tags.get(
            "name",
            "Unnamed Hospital"
        )

        if "lat" in element:

            hospital_lat = element["lat"]
            hospital_lon = element["lon"]

        elif "center" in element:

            hospital_lat = element["center"]["lat"]
            hospital_lon = element["center"]["lon"]

        else:
            continue

        distance = calculate_distance(
            lat,
            lon,
            hospital_lat,
            hospital_lon
        )

        hospitals.append({
            "name": name,
            "address": tags.get(
                "addr:full",
                tags.get("addr:street", "Address not available")
            ),
            "phone": tags.get(
                "phone",
                "Not available"
            ),
            "latitude": hospital_lat,
            "longitude": hospital_lon,
            "distance": round(distance, 2)
        })

    hospitals.sort(
        key=lambda x: x["distance"]
    )

    return hospitals


@lru_cache(maxsize=50)
def cached_hospital_search(lat, lon, radius):

    return find_nearby_hospitals(
        lat,
        lon,
        radius
    )
