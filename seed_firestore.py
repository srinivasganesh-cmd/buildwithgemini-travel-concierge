"""
Seed script to populate Firestore with sample destination documents.
"""

import google.auth
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-02-ffdf7faada83"
COLLECTION_NAME = "destinations"

SAMPLE_DESTINATIONS = [
    {
        "id": "kyoto-japan",
        "name": "Kyoto",
        "country": "Japan",
        "climate": "Temperate",
        "best_season": "Spring / Autumn",
        "price_per_day": 180,
        "rating": 4.9,
        "description": "Historic city famous for classical Buddhist temples, gardens, imperial palaces, and traditional tea houses.",
        "tags": ["culture", "temples", "food", "nature"],
    },
    {
        "id": "santorini-greece",
        "name": "Santorini",
        "country": "Greece",
        "climate": "Mediterranean",
        "best_season": "Summer",
        "price_per_day": 250,
        "rating": 4.9,
        "description": "Iconic volcanic island featuring whitewashed cliffside villages overlooking the Aegean Sea.",
        "tags": ["beach", "romance", "views", "luxury"],
    },
    {
        "id": "banff-canada",
        "name": "Banff National Park",
        "country": "Canada",
        "climate": "Alpine",
        "best_season": "Summer / Winter",
        "price_per_day": 210,
        "rating": 4.9,
        "description": "Stunning turquoise glacial lakes, majestic mountain peaks, and wild mountain terrain.",
        "tags": ["adventure", "hiking", "mountains", "nature"],
    },
    {
        "id": "reykjavik-iceland",
        "name": "Reykjavik & Golden Circle",
        "country": "Iceland",
        "climate": "Subarctic",
        "best_season": "Winter (Northern Lights) / Summer",
        "price_per_day": 230,
        "rating": 4.8,
        "description": "Land of fire and ice with geothermal hot springs, waterfalls, geysers, and aurora borealis views.",
        "tags": ["geothermal", "nature", "aurora", "adventure"],
    },
]


def get_firestore_client() -> firestore.Client:
    credentials, _ = google.auth.default(
        scopes=[
            "https://www.googleapis.com/auth/datastore",
            "https://www.googleapis.com/auth/cloud-platform",
        ]
    )
    return firestore.Client(project=PROJECT_ID, credentials=credentials)


def seed_database():
    db = get_firestore_client()
    print(f"Connecting to Firestore with project '{PROJECT_ID}'...")

    collection_ref = db.collection(COLLECTION_NAME)

    for item in SAMPLE_DESTINATIONS:
        doc_id = item["id"]
        collection_ref.document(doc_id).set(item)
        print(f"Seeded document: {doc_id} -> {item['name']}")

    print(f"✅ Successfully seeded {len(SAMPLE_DESTINATIONS)} items into collection '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    seed_database()
