# Travel Concierge ✈️

An intelligent, AI-powered travel planning and concierge agent built with the **Google Agent Development Kit (ADK)**. Travel Concierge assists users in discovering destinations, fetching live weather forecasts, converting travel budgets, searching nearby spots, generating scenic images and video clips, and remembering long-term user preferences across sessions.

![Travel Concierge Demo](./demo.gif)

---

## 🌟 Key Capabilities & Integrated Tools

All features listed below are fully implemented in code (`app/agent.py` and `frontend/`):

- **🗄️ Firestore Destination Store**:
  - `list_destinations`: Queries curated travel destinations stored in Google Cloud Firestore.
  - `get_destination_details`: Retrieves comprehensive destination guides, highlights, and local tips.
  - `add_destination`: Allows adding new user-recommended spots directly to Firestore.

- **📍 Google Maps Platform Integration**:
  - `geocode_address`: Geocodes city names and addresses into precise latitude/longitude coordinates.
  - `find_nearby_places`: Searches for nearby points of interest (cafes, restaurants, landmarks) using the Google Maps Places API (New).

- **📸 Gemini Multimodal Asset Generation**:
  - `generate_destination_image`: Uses `gemini-3.1-flash-lite-image` to generate professional travel photographs, saving them to ADK Playground Artifacts and uploading to a public Google Cloud Storage bucket.
  - `generate_destination_video`: Uses Google's Omni model (`gemini-omni-flash-preview`) in the `global` region to generate video previews, saving them as Playground Artifacts and uploading to Google Cloud Storage.

- **🧠 Cross-Session Durable Memory**:
  - **Vertex AI Memory Bank**: Integrated via `PreloadMemoryTool` and callback hooks to automatically retain durable user facts, preferences, and dietary restrictions/allergies across turns.

- **🧮 Sandbox Code Execution**:
  - **Agent Engine Sandbox**: Safely executes Python code in a secure sandbox for complex budget split calculations and itinerary math.

- **🌦️ Live Weather & Currency Tools**:
  - `get_live_weather`: Queries real-time weather forecasts and temperature conditions via Open-Meteo.
  - `convert_currency`: Performs real-time multi-currency exchange rate conversions.

- **🎨 Native A2UI (Agent-to-User Interface) Renderer**:
  - Emits A2UI card schemas (v0.8 Basic Catalog) formatted for structured display (cards, text hierarchy, images, rows, columns).

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Web Chat Frontend                      │
│      (HTML5 / CSS Dialogue Layout + Built-in A2UI Renderer) │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / A2A Protocol
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Proxy Server                    │
│                 (a2a-sdk / Google Auth Passthrough)         │
└──────────────────────────────┬──────────────────────────────┘
                               │ A2A Streaming
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Travel Concierge Agent                   │
│             (ADK / Gemini 2.5 Flash / Omni Models)          │
├─────────────┬─────────────┬─────────────┬───────────────────┤
│  Firestore  │ GCS Bucket  │ Memory Bank │ Sandbox Execution │
└─────────────┴─────────────┴─────────────┴───────────────────┘
```

---

## 🚀 Local Setup & Running Instructions

### Prerequisites

1. **Python 3.11+** and [`uv`](https://github.com/astral-sh/uv) installed.
2. Google Cloud project with Google Maps API and Vertex AI enabled.

### 1. Environment Configuration

Set your Google Maps API key and target project in your environment:

```bash
export GOOGLE_MAPS_API_KEY="YOUR_API_KEY"
export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
```

### 2. Running in ADK Playground

To run the agent in the local ADK Web Playground with Memory Bank support:

```bash
uv run adk web . --port 8080 --reload_agents --memory_service_uri=agentengine://<YOUR_MEMORY_BANK_ID>
```

### 3. Running the Custom Chat Frontend

To start the FastAPI proxy and web chat interface locally:

```bash
cd frontend
pip install -r requirements.txt

AGENT_ENGINE_RESOURCE_NAME="projects/<PROJECT_ID>/locations/<REGION>/reasoningEngines/<ENGINE_ID>" \
AGENT_DIRECTORY="app" \
uvicorn main:app --host 0.0.0.0 --port 8080
```

---

## 🛠️ Project Structure

```
.
├── app/
│   ├── agent.py               # Core ADK agent, tools, system instructions, and callbacks
│   └── a2ui_utils.py          # A2UI schema manager & model callback helpers
├── frontend/
│   ├── main.py                # FastAPI proxy server using A2A client
│   ├── requirements.txt       # Frontend dependencies
│   └── static/
│       └── index.html         # Responsive web chat UI with built-in A2UI card renderer
├── agents-cli-manifest.yaml   # Agent manifest configuration
├── deployment_metadata.json   # Deployment runtime metadata
├── demo.gif                   # Recorded video demo animation
└── README.md                  # Project documentation
```
