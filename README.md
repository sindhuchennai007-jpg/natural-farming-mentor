# Nammalvar Natural Farming Mentor

A modular, production-grade multi-agent application that guides beginners through establishing small-scale natural farming and diagnosing/curing crop issues using traditional ecological formulations of Dr. G. Nammalvar. 

Built with the **Google Agent Development Kit (ADK)**, **FastMCP**, **Python FastAPI**, and **Docker**, and fully optimized for deployment to **Google Cloud Run (Always-Free Tier)**.

---

## 1. Project Directory Structure
```
├── .agents/
│   └── skills/
│       └── nammalvar-remedies/
│           └── SKILL.md       # Knowledge Vault & Compliance Rules
├── agentic_workflow/
│   └── agent.py               # ADK multi-agent graph definitions
├── web_app/
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css      # Premium organic styling sheet
│   │   └── organic_farm_illustration.png
│   ├── templates/
│   │   └── index.html         # Mobile-responsive web dashboard
│   └── main.py                # FastAPI routes & vision upload handlers
├── weather_mcp.py             # FastMCP weather climate server
├── Dockerfile                 # Cloud Run container configuration
├── requirements.txt           # Python dependencies
└── README.md                  # Development & Deployment guide
```

---

## 2. Stateful Graph Architecture
The system uses a sequential linear ADK topology of three specialized nodes:
1. **ContextResearcherAgent**: Triggers the local `weather_mcp.py` tool via standard input/output to fetch regional climate patterns for the farm's location.
2. **NammalvarAgronomistAgent**: Formulates a custom 30-day crop roadmap and remedies scaled for the farm's acreage, grounded strictly in `.agents/skills/nammalvar-remedies/SKILL.md`.
3. **NaturalGuardrailAgent**: Performs a zero-trust compliance check on the draft plan. If synthetic chemical fertilizers or pesticides (e.g. Urea, DAP, NPK, Glyphosate, GMOs) are detected, it drops the draft, logs a policy violation, and triggers a rewrite loop on the agronomist node.

---

## 3. Local Development Setup

### Prerequisite: Set Gemini API Key
Make sure you have your Gemini API Key available:
```powershell
$env:GOOGLE_API_KEY="your-gemini-api-key"
```

### Step 1: Create Virtual Environment and Install Dependencies
```powershell
# Create environment
python -m venv .venv

# Activate environment
.venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
```

### Step 2: Run the FastAPI Server
To launch the FastAPI server locally:
```powershell
python web_app/main.py
```
Open your browser and navigate to `http://localhost:8080` to access the responsive dashboard.

---

## 4. Google Cloud Run Deployment
You can deploy this containerized application to Google Cloud Run (Always-Free Tier compliant) using the Google Cloud SDK:

```bash
# 1. Enable Google Cloud APIs
gcloud services enable run.googleapis.com artifactregistry.googleapis.com

# 2. Create an Artifact Registry repository
gcloud artifacts repositories create natural-farming-repo \
    --repository-format=docker \
    --location=us-central1 \
    --description="Repository for Nammalvar Farming Mentor App"

# 3. Build and push the container using Google Cloud Build
gcloud builds submit --tag us-central1-docker.pkg.dev/$(gcloud config get-value project)/natural-farming-repo/mentor-app:latest

# 4. Deploy to Google Cloud Run (Always-Free Tier)
gcloud run deploy nammalvar-mentor-app \
    --image us-central1-docker.pkg.dev/$(gcloud config get-value project)/natural-farming-repo/mentor-app:latest \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --set-env-vars GOOGLE_API_KEY=$GOOGLE_API_KEY \
    --memory 512Mi \
    --cpu 1
```

---

## 5. Trace & Verify Agent Logic
The Google ADK includes a web-based developer UI to trace, test, and debug your multi-agent workflows. 

To launch the ADK playground and verify your agentic graphs locally, run the following command in your terminal:
```powershell
# Start the ADK Web interface
adk web
```
This launches a browser session showing your agents, node execution outputs, and the step-by-step stateful corrections made by the guardrail node.
