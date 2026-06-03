import os
import math
import httpx
from dotenv import load_dotenv

load_dotenv()

PLACES_API_URL = "https://places.googleapis.com/v1/places:searchNearby"
FIELD_MASK = ",".join([
    "places.displayName",
    "places.formattedAddress",
    "places.websiteUri",
    "places.rating",
    "places.userRatingCount",
    "places.types",
    "places.nationalPhoneNumber",
    "places.reviews",
    "places.location",
])


def search_businesses(
    lat: float,
    lng: float,
    radius_miles: float,
    max_results: int = 20,
    included_types: list[str] | None = None,
) -> list[dict]:
    radius_meters = radius_miles * 1609.34
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": os.environ["GOOGLE_PLACES_API_KEY"],
        "X-Goog-FieldMask": FIELD_MASK,
    }
    body = {
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": radius_meters,
            }
        },
        "maxResultCount": min(max_results, 20),
    }
    if included_types:
        body["includedTypes"] = included_types

    with httpx.Client(timeout=15) as client:
        response = client.post(PLACES_API_URL, json=body, headers=headers)
        response.raise_for_status()

    places = response.json().get("places", [])
    return [_parse_place(p) for p in places]


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 3958.8
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def geocode_location(query: str) -> tuple[float, float]:
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": query, "key": os.environ["GOOGLE_PLACES_API_KEY"]}
    with httpx.Client(timeout=10) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
    results = response.json().get("results", [])
    if not results:
        raise ValueError(f"Could not geocode location: {query}")
    loc = results[0]["geometry"]["location"]
    return loc["lat"], loc["lng"]


def _parse_place(place: dict) -> dict:
    reviews = place.get("reviews", [])
    top_reviews = [r.get("text", {}).get("text", "") for r in reviews[:10] if r.get("text")]

    return {
        "name": place.get("displayName", {}).get("text", ""),
        "address": place.get("formattedAddress", ""),
        "phone": place.get("nationalPhoneNumber", ""),
        "website_url": place.get("websiteUri", ""),
        "category": _primary_category(place.get("types", [])),
        "rating": place.get("rating", 0),
        "review_count": place.get("userRatingCount", 0),
        "reviews": top_reviews,
        "lat": place.get("location", {}).get("latitude", 0),
        "lng": place.get("location", {}).get("longitude", 0),
    }


def _primary_category(types: list[str]) -> str:
    skip = {"point_of_interest", "establishment", "food", "store"}
    for t in types:
        if t not in skip:
            return t.replace("_", " ").title()
    return types[0].replace("_", " ").title() if types else "Business"
