# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
import os
from pathlib import Path
from typing import Any
import urllib.parse
import urllib.request
import uuid
from zoneinfo import ZoneInfo

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
import google.auth
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from .a2ui_utils import a2ui_callback

# Hardcoded constants as required for Agent Platform compatibility
FIRESTORE_PROJECT = "qwiklabs-gcp-02-ffdf7faada83"
COLLECTION_NAME = "destinations"
ASSETS_BUCKET_NAME = "travel-concierge-assets-qwiklabs-gcp-02-ffdf7faada83"


def _get_firestore_client() -> firestore.Client:
    credentials, _ = google.auth.default(
        scopes=[
            "https://www.googleapis.com/auth/datastore",
            "https://www.googleapis.com/auth/cloud-platform",
        ]
    )
    return firestore.Client(project=FIRESTORE_PROJECT, credentials=credentials)


def list_destinations(tag: str = "", max_price: float = 0.0) -> list[dict[str, Any]]:
    """List travel destinations stored in the Firestore database.

    Args:
        tag: Optional tag to filter destinations (e.g., 'nature', 'beach', 'culture').
        max_price: Optional maximum price per day in USD to filter destinations.

    Returns:
        A list of destination dictionaries matching the query criteria.
    """
    db = _get_firestore_client()
    docs = db.collection(COLLECTION_NAME).stream()
    results = []

    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id

        if tag and tag.lower() not in [t.lower() for t in data.get("tags", [])]:
            continue

        if max_price > 0 and data.get("price_per_day", 0) > max_price:
            continue

        results.append(data)

    return results


def get_destination_details(destination_id: str) -> dict[str, Any]:
    """Get full details for a specific travel destination from Firestore by ID.

    Args:
        destination_id: The unique ID string of the destination (e.g. 'kyoto-japan').

    Returns:
        A dictionary containing destination details or an error message if not found.
    """
    db = _get_firestore_client()
    doc_ref = db.collection(COLLECTION_NAME).document(destination_id)
    doc = doc_ref.get()

    if not doc.exists:
        return {"error": f"Destination with ID '{destination_id}' not found."}

    data = doc.to_dict()
    data["id"] = doc.id
    return data


def add_destination(
    destination_id: str,
    name: str,
    country: str,
    climate: str,
    best_season: str,
    price_per_day: float,
    rating: float,
    description: str,
    tags: str,
) -> dict[str, Any]:
    """Add or update a travel destination in the Firestore database.

    Args:
        destination_id: Unique string key (e.g., 'paris-france').
        name: Name of the destination.
        country: Country where the destination is located.
        climate: Climate description (e.g., 'Temperate', 'Tropical').
        best_season: Best time of year to visit.
        price_per_day: Estimated cost per day in USD.
        rating: Rating score out of 5.0.
        description: Summary description of the destination.
        tags: Comma-separated list of tags (e.g. 'romance, food, culture').

    Returns:
        A dictionary confirming the document creation/update.
    """
    db = _get_firestore_client()
    tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]

    item = {
        "id": destination_id,
        "name": name,
        "country": country,
        "climate": climate,
        "best_season": best_season,
        "price_per_day": price_per_day,
        "rating": rating,
        "description": description,
        "tags": tag_list,
    }

    db.collection(COLLECTION_NAME).document(destination_id).set(item)
    return {"status": "success", "destination": item}


def get_live_weather(city: str) -> dict[str, Any]:
    """Fetch live real-time weather and temperature for a destination city.

    Args:
        city: Name of the city or destination to get live weather for (e.g. 'Kyoto', 'Paris', 'Tokyo').

    Returns:
        A dictionary with city name, country, temperature in Celsius, and wind speed.
    """
    try:
        encoded_city = urllib.parse.quote(city)
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_city}&count=1&language=en&format=json"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "TravelConciergeAgent/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            geo_data = json.loads(response.read().decode())

        if not geo_data.get("results"):
            return {"error": f"Could not find coordinates for location '{city}'."}

        location = geo_data["results"][0]
        lat, lon = location["latitude"], location["longitude"]
        country = location.get("country", "")

        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        w_req = urllib.request.Request(weather_url, headers={"User-Agent": "TravelConciergeAgent/1.0"})
        with urllib.request.urlopen(w_req, timeout=5) as response:
            weather_data = json.loads(response.read().decode())

        current = weather_data.get("current_weather", {})
        return {
            "city": location.get("name", city),
            "country": country,
            "temperature_celsius": current.get("temperature"),
            "windspeed_kmh": current.get("windspeed"),
            "is_daytime": current.get("is_day") == 1,
        }
    except Exception as e:
        return {"error": f"Failed to fetch live weather: {str(e)}"}


def convert_currency(
    amount: float, from_currency: str = "USD", to_currency: str = "EUR"
) -> dict[str, Any]:
    """Convert a travel budget amount from one currency to another using real exchange rates.

    Args:
        amount: The numerical amount of money to convert (e.g. 200.0).
        from_currency: 3-letter currency code to convert from (e.g. 'USD', 'EUR', 'GBP').
        to_currency: 3-letter currency code to convert to (e.g. 'JPY', 'EUR', 'CAD', 'GBP').

    Returns:
        A dictionary containing the converted amount, exchange rate, and base currencies.
    """
    api_key = os.getenv("EXCHANGE_RATE_API_KEY")
    try:
        from_curr = from_currency.upper().strip()
        to_curr = to_currency.upper().strip()

        if api_key:
            url = f"https://v6.exchangerate-api.com/v6/{api_key}/pair/{from_curr}/{to_curr}/{amount}"
        else:
            url = f"https://api.frankfurter.app/latest?amount={amount}&from={from_curr}&to={to_curr}"

        req = urllib.request.Request(url, headers={"User-Agent": "TravelConciergeAgent/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())

        if api_key:
            converted = data.get("conversion_result", amount)
            rate = data.get("conversion_rate", 1.0)
        else:
            rates = data.get("rates", {})
            converted = rates.get(to_curr)
            rate = round(converted / amount, 4) if converted and amount > 0 else None

        return {
            "original_amount": amount,
            "from_currency": from_curr,
            "to_currency": to_curr,
            "converted_amount": converted,
            "exchange_rate": rate,
        }
    except Exception as e:
        return {"error": f"Failed to convert currency: {str(e)}"}


def geocode_address(address: str) -> dict[str, Any]:
    """Convert a street address or location name into geographical coordinates (latitude and longitude).

    Args:
        address: The address or place name to geocode (e.g. 'Eiffel Tower, Paris').

    Returns:
        A dictionary containing the formatted address, latitude, and longitude.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return {"error": "GOOGLE_MAPS_API_KEY environment variable is not set."}

    try:
        encoded_address = urllib.parse.quote(address)
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"
        req = urllib.request.Request(url, headers={"User-Agent": "TravelConciergeAgent/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())

        if not data.get("results"):
            return {"error": f"No geocoding results found for '{address}'."}

        result = data["results"][0]
        loc = result["geometry"]["location"]
        return {
            "formatted_address": result.get("formatted_address", address),
            "latitude": loc.get("lat"),
            "longitude": loc.get("lng"),
        }
    except Exception as e:
        return {"error": f"Failed to geocode address: {str(e)}"}


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "tourist_attraction",
    radius: float = 1000.0,
    max_count: int = 5,
) -> dict[str, Any]:
    """Find nearby points of interest using Google Places API (New).

    Args:
        latitude: Latitude coordinate of the search center.
        longitude: Longitude coordinate of the search center.
        place_type: Type of place to search for (e.g. 'restaurant', 'tourist_attraction', 'museum', 'cafe').
        radius: Search radius in meters (default: 1000.0).
        max_count: Maximum number of places to return (default: 5).

    Returns:
        A dictionary containing a list of nearby places with name, address, and location coordinates.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return {"error": "GOOGLE_MAPS_API_KEY environment variable is not set."}

    try:
        url = "https://places.googleapis.com/v1/places:searchNearby"
        payload = {
            "includedTypes": [place_type],
            "maxResultCount": min(max_count, 20),
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": radius,
                }
            },
        }

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
            "User-Agent": "TravelConciergeAgent/1.0",
        }

        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())

        places_list = []
        for place in data.get("places", []):
            display_name = place.get("displayName", {}).get("text", "")
            formatted_address = place.get("formattedAddress", "")
            loc = place.get("location", {})
            places_list.append(
                {
                    "name": display_name,
                    "address": formatted_address,
                    "location": {
                        "latitude": loc.get("latitude"),
                        "longitude": loc.get("longitude"),
                    },
                }
            )

        return {"places": places_list}
    except Exception as e:
        return {"error": f"Failed to find nearby places: {str(e)}"}


def generate_destination_image(
    destination_name: str, prompt: str, tool_context: ToolContext
) -> dict[str, Any]:
    """Generate a scenic preview image for a travel destination using Gemini, save it as a Playground artifact, and upload to public Cloud Storage.

    Args:
        destination_name: Name of the destination (e.g. 'Kyoto', 'Paris').
        prompt: Detailed visual description of the scenic view or landmark to generate.
        tool_context: ADK ToolContext instance provided automatically by the framework.

    Returns:
        A dictionary containing the public HTTPS URL of the uploaded image and the saved artifact filename.
    """
    try:
        client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT, location="global")
        full_prompt = f"A beautiful, high-quality professional travel photograph of {destination_name}: {prompt}"

        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=full_prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        if not response.candidates or not response.candidates[0].content.parts:
            return {"error": "No image was returned by the model."}

        image_part = response.candidates[0].content.parts[0]
        if not image_part.inline_data:
            return {"error": "Model response did not contain inline image data."}

        image_bytes = image_part.inline_data.data
        mime_type = image_part.inline_data.mime_type or "image/jpeg"

        # 1. Save artifact in Playground's Artifacts panel
        safe_name = "".join(c if c.isalnum() else "_" for c in destination_name.lower()).strip("_")
        filename = f"{safe_name}_{uuid.uuid4().hex[:6]}.jpg"

        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload image bytes directly to public GCS bucket (no local file)
        credentials, _ = google.auth.default(
            scopes=[
                "https://www.googleapis.com/auth/devstorage.full_control",
                "https://www.googleapis.com/auth/cloud-platform",
            ]
        )
        storage_client = storage.Client(project=FIRESTORE_PROJECT, credentials=credentials)
        bucket = storage_client.bucket(ASSETS_BUCKET_NAME)

        blob_name = f"destinations/{filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{ASSETS_BUCKET_NAME}/{blob_name}"

        return {
            "status": "success",
            "destination_name": destination_name,
            "public_url": public_url,
            "artifact_filename": filename,
        }
    except Exception as e:
        return {"error": f"Failed to generate destination image: {str(e)}"}


def generate_destination_video(
    destination_name: str, prompt: str, tool_context: ToolContext
) -> dict[str, Any]:
    """Generate a short video preview for a travel destination using Google's Omni model (gemini-omni-flash-preview) in the global region, save it as a Playground artifact, and upload to public Cloud Storage.

    Args:
        destination_name: Name of the destination (e.g. 'Kyoto', 'Paris').
        prompt: Detailed visual description of the scene or landmark to generate as a video.
        tool_context: ADK ToolContext instance provided automatically by the framework.

    Returns:
        A dictionary containing the public HTTPS URL of the uploaded video and the saved artifact filename.
    """
    try:
        client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT, location="global")
        full_prompt = f"A beautiful, high-quality video clip of {destination_name}: {prompt}"

        interaction = client.interactions.create(
            model="gemini-omni-flash-preview",
            input=full_prompt,
        )

        if not interaction.output_video or not interaction.output_video.data:
            return {"error": "No video was returned by the model."}

        raw_data = interaction.output_video.data
        if isinstance(raw_data, str):
            video_bytes = base64.b64decode(raw_data)
        else:
            video_bytes = raw_data

        mime_type = "video/mp4"

        # 1. Save artifact in Playground's Artifacts panel
        safe_name = "".join(c if c.isalnum() else "_" for c in destination_name.lower()).strip("_")
        filename = f"{safe_name}_{uuid.uuid4().hex[:6]}.mp4"

        artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
        tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload video bytes directly to public GCS bucket (no local file)
        credentials, _ = google.auth.default(
            scopes=[
                "https://www.googleapis.com/auth/devstorage.full_control",
                "https://www.googleapis.com/auth/cloud-platform",
            ]
        )
        storage_client = storage.Client(project=FIRESTORE_PROJECT, credentials=credentials)
        bucket = storage_client.bucket(ASSETS_BUCKET_NAME)

        blob_name = f"videos/{filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{ASSETS_BUCKET_NAME}/{blob_name}"

        return {
            "status": "success",
            "destination_name": destination_name,
            "public_url": public_url,
            "artifact_filename": filename,
        }
    except Exception as e:
        return {"error": f"Failed to generate destination video: {str(e)}"}


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        query: City name.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


DEPLOYMENT_METADATA_PATH = Path(__file__).resolve().parent.parent / "deployment_metadata.json"


def _get_agent_engine_resource_name() -> str:
    if DEPLOYMENT_METADATA_PATH.exists():
        try:
            with open(DEPLOYMENT_METADATA_PATH, "r") as f:
                meta = json.load(f)
                engine_id = meta.get("remote_agent_runtime_id")
                if engine_id:
                    return engine_id
        except Exception:
            pass
    return "projects/826243101344/locations/us-east1/reasoningEngines/1482192251776925696"


agent_engine_id = _get_agent_engine_resource_name()
code_executor = AgentEngineSandboxCodeExecutor(agent_engine_resource_name=agent_engine_id)


async def generate_memories_callback(callback_context: CallbackContext):
    """Callback to extract durable user facts and preferences to Memory Bank after each turn."""
    try:
        await callback_context.add_session_to_memory()
    except Exception:
        pass
    return None


def memory_bank_service_builder():
    """Build Memory Bank service for deployed container."""
    memory_bank_id = agent_engine_id.split("/")[-1]
    return VertexAiMemoryBankService(
        project=FIRESTORE_PROJECT,
        location="us-east1",
        agent_engine_id=memory_bank_id,
    )


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description="You are Travel Concierge, an AI agent helping travelers discover and plan trips. Use your tools to query destinations from Firestore, geocode addresses, find nearby places, fetch live weather forecasts, convert travel budgets, generate scenic destination images, safely execute Python code in your sandbox for budget and split calculations, and add new recommended spots.",
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects. "
        "IMPORTANT MEMORY GUIDELINES: Pay special attention to remembering all user allergies "
        "(e.g., peanuts, gluten, shellfish, dairy, nuts), dietary restrictions, and health preferences across sessions."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    code_executor=code_executor,
    tools=[
        PreloadMemoryTool(),
        list_destinations,
        get_destination_details,
        add_destination,
        get_live_weather,
        convert_currency,
        geocode_address,
        find_nearby_places,
        generate_destination_image,
        generate_destination_video,
        get_current_time,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
