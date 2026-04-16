# 🌐 AI Disaster Supply Chain Optimizer — Full-Stack Edition

> **MySQL · Flask · Leaflet · Mistral AI**  
> Complete production-ready showcase application

---

## 🚀 Quick Start (5 steps)

### 1 — Clone & install dependencies
```bash
cd disaster_optimizer
pip install -r requirements.txt
```

### 2 — Configure your .env file
```bash
cp .env.example .env
# Edit .env with your MySQL credentials
```

### 3 — Create the MySQL database
```sql
mysql -u root -p
CREATE DATABASE disaster_db;
EXIT;
```

### 4 — Seed data into MySQL (pick one method)
```bash
# Method A — Interactive CLI menu (recommended for showcase)
python seed_data.py

# Method B — Auto-load Tamil Nadu demo scenario
python seed_data.py --demo

# Method C — Add data manually via the web form (after step 5)
```

### 5 — Run the application
```bash
python app.py
# Open: http://localhost:5000
```

---

## 🗄️ Database Schema

```
┌──────────────┐        ┌──────────────┐        ┌──────────────────┐
│    zones     │        │    depots    │        │    supplies      │
├──────────────┤        ├──────────────┤        ├──────────────────┤
│ id (PK)      │        │ id (PK)      │◄───────│ depot_id (FK)    │
│ name         │        │ name         │        │ id (PK)          │
│ population   │        │ location     │        │ supply_type      │
│ severity 1-10│        │ latitude     │        │ quantity         │
│ latitude     │        │ longitude    │        │ unit             │
│ longitude    │        │ capacity     │        │ notes            │
│ created_at   │        │ created_at   │        │ updated_at       │
└──────────────┘        └──────────────┘        └──────────────────┘
```

---

## 🔧 Environment Variables (.env)

| Variable      | Description                        | Default     |
|---------------|------------------------------------|-------------|
| `DB_HOST`     | MySQL host                         | `localhost` |
| `DB_PORT`     | MySQL port                         | `3306`      |
| `DB_USER`     | MySQL username                     | `root`      |
| `DB_PASSWORD` | MySQL password                     | *(blank)*   |
| `DB_NAME`     | Database name                      | `disaster_db`|
| `HF_API_TOKEN`| Hugging Face token for Mistral AI  | *(rule-based fallback)* |
| `PORT`        | Flask server port                  | `5000`      |

---

## 📡 API Reference

### Zones
| Method | Endpoint              | Description            |
|--------|-----------------------|------------------------|
| GET    | `/api/zones`          | List all zones         |
| POST   | `/api/zones`          | Create a zone          |
| PUT    | `/api/zones/<id>`     | Update a zone          |
| DELETE | `/api/zones/<id>`     | Delete a zone          |

### Depots
| Method | Endpoint              | Description            |
|--------|-----------------------|------------------------|
| GET    | `/api/depots`         | List all depots        |
| POST   | `/api/depots`         | Create a depot         |
| DELETE | `/api/depots/<id>`    | Delete a depot         |

### Supplies
| Method | Endpoint              | Description            |
|--------|-----------------------|------------------------|
| GET    | `/api/supplies`       | List all supplies      |
| POST   | `/api/supplies`       | Add a supply record    |
| PUT    | `/api/supplies/<id>`  | Update a supply        |
| DELETE | `/api/supplies/<id>`  | Delete a supply        |

### Core Operations
| Method | Endpoint              | Description                               |
|--------|-----------------------|-------------------------------------------|
| POST   | `/api/optimize`       | Run optimization (reads live DB data)     |
| GET    | `/api/dashboard`      | Summary stats for dashboard               |
| GET    | `/api/status`         | DB + AI connection status                 |
| GET    | `/api/export`         | Export all DB data as JSON                |

---

## 🧠 Algorithm Overview

```
zones (MySQL)  +  supplies (MySQL)  +  depots (MySQL)
       │                                    │
       ▼                                    │
  calculate_demand()                        │
  (population × severity → demand score)   │
       │                                    │
       ▼                                    │
  allocate_supplies()  ◄────────────────────┘
  (proportional + cap, gap detection)
       │
       ├── build_routes()
       │   (haversine distance → nearest depot)
       │
       └── get_ai_suggestions()
           (Mistral-7B or rule-based fallback)
```

---

## 🌲 Project Structure

```
disaster_optimizer/
├── app.py              # Flask backend + MySQL + all API endpoints
├── seed_data.py        # Runtime CLI tool to input data into MySQL
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
├── README.md
└── templates/
    └── index.html      # Single-page frontend (Tailwind + Leaflet)
```

---

## ✨ Features

- ✅ **MySQL always-on** — no SQLite fallback, production-grade
- ✅ **Three-table schema** — Zones, Depots, Supplies with FK relationships
- ✅ **Runtime Python CLI** — interactive seed_data.py with colored menus
- ✅ **Demo data loader** — Tamil Nadu disaster scenario (`--demo` flag)
- ✅ **Live optimization** — reads from MySQL, runs algorithms, shows results
- ✅ **Haversine routing** — real-world km distance to nearest depot
- ✅ **AI suggestions** — Mistral-7B via Hugging Face, rule-based fallback
- ✅ **Interactive Leaflet map** — click-to-set coordinates, risk color markers
- ✅ **Full CRUD via web UI** — add/delete zones, depots, supplies from browser
- ✅ **JSON export** — download entire DB snapshot
- ✅ **Toast notifications** — every action gives instant feedback
