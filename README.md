# AI Disaster Supply Chain Optimizer — Integrated Edition

Combines the full optimization logic from **disaster_optimizer** (v1) with the database
persistence and Leaflet interactive map from **disaster_optimizer_pro** (v2) into a single
professional Flask web application. **No logic was changed.**

---

## What's integrated

| Feature | Source |
|---|---|
| Demand calculation (population × severity) | v1 |
| Greedy supply allocation with risk scoring | v1 |
| Nearest-depot routing algorithm | v1 |
| AI suggestions (Hugging Face + rule fallback) | v1 |
| Canvas grid map with route lines | v1 |
| Simulate Disaster button + sample data | v1 |
| Real-time Leaflet interactive map | v2 |
| SQLAlchemy database models (Zone, Depot) | v2 |
| Save / load zones from MySQL or SQLite | v2 |
| Lat/lng coordinate picking on live map | v2 |
| DB status badge + toast notifications | new |
| Export results as JSON | new |

---

## Quick Start (no database required)

```bash
cd disaster_optimizer_integrated
pip install -r requirements.txt
python app.py
```

Open: http://localhost:5000

The app runs fully without a database — all optimization features work out of the box.

---

## With MySQL database (optional)

```bash
# Create the database first:
mysql -u root -p -e "CREATE DATABASE disaster_db;"

# Then set the environment variable and run:
export DATABASE_URL="mysql+pymysql://root:your_password@localhost/disaster_db"
python app.py
```

The app detects the database on startup and enables the **Save to DB** and **Load from DB** buttons.

---

## With Hugging Face AI (optional)

```bash
export HF_API_TOKEN="hf_your_token_here"
python app.py
```

Without a token, the app automatically falls back to rule-based suggestions.

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | MySQL/SQLite connection string | None (no DB) |
| `HF_API_TOKEN` | Hugging Face API token for AI suggestions | `YOUR_HF_API_TOKEN_HERE` |
| `PORT` | Server port | `5000` |

---

## Project Structure

```
disaster_optimizer_integrated/
├── app.py               # Flask backend — all logic + DB models
├── requirements.txt     # Python dependencies
├── README.md
└── templates/
    └── index.html       # Full-featured frontend (Canvas + Leaflet)
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Main application |
| GET | `/api/simulate` | Load sample disaster scenario |
| POST | `/api/optimize` | Run optimization (main algorithm) |
| GET | `/api/status` | Check DB and AI configuration |
| GET/POST | `/api/zones` | List / create zones (DB required) |
| DELETE | `/api/zones/<id>` | Delete a zone (DB required) |
| GET/POST | `/api/depots` | List / create depots (DB required) |
