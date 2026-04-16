"""
AI-Based Disaster Supply Chain Optimizer — Integrated Edition
Combines full optimization logic (app v1) + database persistence & Leaflet map (app v2)
"""

from flask import Flask, render_template, request, jsonify
import json
import math
import os
import requests

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────
# Database Configuration
# Supports MySQL (production) or SQLite (local/dev fallback)
# Set DATABASE_URL env var for MySQL:
#   mysql+pymysql://user:password@host/disaster_db
# ─────────────────────────────────────────────────────────────
db_url = os.environ.get("DATABASE_URL", "")

USE_DB = False
db = None

if db_url:
    try:
        from flask_sqlalchemy import SQLAlchemy
        app.config["SQLALCHEMY_DATABASE_URI"] = db_url
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        db = SQLAlchemy(app)

        class Zone(db.Model):
            __tablename__ = "zones"
            id         = db.Column(db.Integer, primary_key=True)
            name       = db.Column(db.String(255))
            population = db.Column(db.Integer)
            severity   = db.Column(db.Integer)
            latitude   = db.Column(db.Numeric(10, 8))
            longitude  = db.Column(db.Numeric(11, 8))

        class Depot(db.Model):
            __tablename__ = "depots"
            id        = db.Column(db.Integer, primary_key=True)
            name      = db.Column(db.String(255))
            latitude  = db.Column(db.Numeric(10, 8))
            longitude = db.Column(db.Numeric(11, 8))

        with app.app_context():
            db.create_all()

        USE_DB = True
        print("[DB] Connected to database:", db_url.split("@")[-1])
    except Exception as e:
        print(f"[DB] Database connection failed ({e}). Running without persistence.")
else:
    print("[DB] No DATABASE_URL set. Running without database persistence.")


# ─────────────────────────────────────────────────────────────
# Hugging Face API config
# Set HF_API_TOKEN env var with your token
# ─────────────────────────────────────────────────────────────
HF_API_TOKEN = os.environ.get("HF_API_TOKEN", "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")
HF_MODEL     = "mistralai/Mistral-7B-Instruct-v0.2"
HF_API_URL   = f"https://api-inference.huggingface.co/models/{HF_MODEL}"


# ─────────────────────────────────────────────────────────────
# SAMPLE DATA  (used by /api/simulate)
# ─────────────────────────────────────────────────────────────
SAMPLE_DATA = {
    "zones": [
        {"name": "Zone A - Coastal City",    "population": 45000, "severity": 9},
        {"name": "Zone B - Hill Village",    "population": 12000, "severity": 7},
        {"name": "Zone C - River Town",      "population": 28000, "severity": 8},
        {"name": "Zone D - Mountain Camp",   "population": 5000,  "severity": 6},
        {"name": "Zone E - Plains District", "population": 33000, "severity": 5},
    ],
    "supplies": {
        "food":      {"quantity": 500000, "unit": "kg"},
        "water":     {"quantity": 300000, "unit": "liters"},
        "medicines": {"quantity": 50000,  "unit": "units"},
    },
    "depots": [
        {"name": "Depot Alpha", "location": "North Hub",   "x": 10, "y": 80},
        {"name": "Depot Beta",  "location": "East Center", "x": 70, "y": 50},
        {"name": "Depot Gamma", "location": "South Base",  "x": 40, "y": 20},
    ],
    "zone_coords": [
        {"x": 20, "y": 90},
        {"x": 30, "y": 60},
        {"x": 60, "y": 75},
        {"x": 15, "y": 40},
        {"x": 80, "y": 30},
    ],
    # Real lat/lng for the Leaflet map (Mumbai-region sample)
    "zone_latlng": [
        {"lat": 19.076,  "lng": 72.878},
        {"lat": 19.295,  "lng": 73.056},
        {"lat": 18.997,  "lng": 73.119},
        {"lat": 19.540,  "lng": 73.211},
        {"lat": 18.521,  "lng": 73.857},
    ],
    "depot_latlng": [
        {"lat": 19.220,  "lng": 72.978},
        {"lat": 19.012,  "lng": 73.029},
        {"lat": 18.620,  "lng": 73.780},
    ],
}


# ─────────────────────────────────────────────────────────────
# CORE ALGORITHM  (unchanged from v1)
# ─────────────────────────────────────────────────────────────

def calculate_demand(zones):
    demands = []
    for z in zones:
        base = z["population"] * z["severity"]
        demands.append({
            "zone":        z["name"],
            "severity":    z["severity"],
            "population":  z["population"],
            "demand_score": base,
            "food_needed":     round(base * 0.004),
            "water_needed":    round(base * 0.0025),
            "medicine_needed": round(base * 0.0004),
        })
    demands.sort(key=lambda d: d["demand_score"], reverse=True)
    return demands


def allocate_supplies(demands, supplies):
    avail_food  = supplies["food"]["quantity"]
    avail_water = supplies["water"]["quantity"]
    avail_meds  = supplies["medicines"]["quantity"]

    allocations  = []
    total_demand = sum(d["demand_score"] for d in demands)

    for d in demands:
        share = d["demand_score"] / total_demand if total_demand else 0

        alloc_food  = min(round(avail_food  * share), d["food_needed"])
        alloc_water = min(round(avail_water * share), d["water_needed"])
        alloc_meds  = min(round(avail_meds  * share), d["medicine_needed"])

        food_gap  = max(0, d["food_needed"]     - alloc_food)
        water_gap = max(0, d["water_needed"]    - alloc_water)
        meds_gap  = max(0, d["medicine_needed"] - alloc_meds)

        gap_ratio = (food_gap + water_gap + meds_gap) / max(
            d["food_needed"] + d["water_needed"] + d["medicine_needed"], 1
        )
        if   gap_ratio > 0.5: risk = "CRITICAL"
        elif gap_ratio > 0.2: risk = "HIGH"
        elif gap_ratio > 0:   risk = "MEDIUM"
        else:                 risk = "LOW"

        alerts = []
        if food_gap  > 0: alerts.append(f"Food shortage: {food_gap:,} kg needed")
        if water_gap > 0: alerts.append(f"Water shortage: {water_gap:,} L needed")
        if meds_gap  > 0: alerts.append(f"Medicine shortage: {meds_gap:,} units needed")

        allocations.append({
            "zone":        d["zone"],
            "severity":    d["severity"],
            "population":  d["population"],
            "food_alloc":  alloc_food,
            "water_alloc": alloc_water,
            "meds_alloc":  alloc_meds,
            "food_gap":    food_gap,
            "water_gap":   water_gap,
            "meds_gap":    meds_gap,
            "risk_level":  risk,
            "alerts":      alerts,
        })
    return allocations


def euclidean_distance(p1, p2):
    return math.sqrt((p1["x"] - p2["x"])**2 + (p1["y"] - p2["y"])**2)


def find_nearest_depot(zone_coord, depots):
    best, best_dist = None, float("inf")
    for d in depots:
        dist = euclidean_distance(zone_coord, {"x": d["x"], "y": d["y"]})
        if dist < best_dist:
            best_dist = dist
            best = d["name"]
    return best, round(best_dist, 1)


def build_routes(zones, zone_coords, depots):
    routes = []
    for i, z in enumerate(zones):
        coord = zone_coords[i] if i < len(zone_coords) else {"x": 50, "y": 50}
        depot_name, dist = find_nearest_depot(coord, depots)
        routes.append({
            "zone":            z["name"],
            "depot":           depot_name,
            "distance_km":     dist,
            "estimated_hours": round(dist / 40, 1),
        })
    return routes


def get_ai_suggestions(allocations, routes):
    critical_zones = [a["zone"] for a in allocations if a["risk_level"] == "CRITICAL"]
    high_zones     = [a["zone"] for a in allocations if a["risk_level"] == "HIGH"]
    total_gaps     = sum(a["food_gap"] + a["water_gap"] + a["meds_gap"] for a in allocations)

    prompt = f"""[INST] You are a disaster relief logistics expert AI.

Situation Summary:
- {len(allocations)} affected zones total
- Critical risk zones: {', '.join(critical_zones) if critical_zones else 'None'}
- High risk zones: {', '.join(high_zones) if high_zones else 'None'}
- Total supply gap across all zones: {total_gaps:,} units

Provide 4 concise, actionable recommendations (numbered list) to:
1. Prioritize critical zones
2. Address supply shortages
3. Optimize route logistics
4. Reduce risks

Keep each recommendation under 2 sentences. [/INST]"""

    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 350, "temperature": 0.6, "return_full_text": False},
    }

    try:
        resp = requests.post(HF_API_URL, headers=headers, json=payload, timeout=20)
        if resp.status_code == 200:
            raw = resp.json()
            if isinstance(raw, list) and raw:
                text = raw[0].get("generated_text", "").strip()
                if text:
                    return {"source": "AI (Hugging Face)", "text": text}
    except Exception:
        pass

    # Rule-based fallback
    lines = []
    if critical_zones:
        lines.append(f"1. Immediately dispatch emergency convoys to {', '.join(critical_zones[:2])} as they face critical supply deficits — prioritize water and medicines first.")
    else:
        lines.append("1. All zones are within manageable risk — maintain current allocation schedule and monitor for changes.")

    if total_gaps > 0:
        lines.append(f"2. Total unmet demand of {total_gaps:,} units detected; request additional aid from national reserves or NGO partners within 24 hours.")
    else:
        lines.append("2. Current supply levels are sufficient — focus on equitable and timely distribution.")

    long_routes = [r for r in routes if r["estimated_hours"] > 3]
    if long_routes:
        lines.append(f"3. Zones {', '.join(r['zone'] for r in long_routes[:2])} have travel times exceeding 3 hours — consider pre-positioning supplies or using air transport.")
    else:
        lines.append("3. All route travel times are acceptable — use standard ground convoy operations.")

    lines.append("4. Establish real-time radio check-ins every 6 hours to track delivery progress and dynamically re-route if roads are blocked.")
    return {"source": "Rule-Based Fallback", "text": "\n".join(lines)}


# ─────────────────────────────────────────────────────────────
# FLASK ROUTES
# ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", use_db=USE_DB)


@app.route("/api/simulate", methods=["GET"])
def simulate():
    return jsonify(SAMPLE_DATA)


@app.route("/api/optimize", methods=["POST"])
def optimize():
    data        = request.get_json()
    zones       = data.get("zones", [])
    supplies    = data.get("supplies", {})
    depots      = data.get("depots", [])
    zone_coords = data.get("zone_coords", [])

    if not zones or not supplies or not depots:
        return jsonify({"error": "Missing required data"}), 400

    demands     = calculate_demand(zones)
    allocations = allocate_supplies(demands, supplies)
    routes      = build_routes(zones, zone_coords, depots)
    suggestions = get_ai_suggestions(allocations, routes)

    total_critical = sum(1 for a in allocations if a["risk_level"] == "CRITICAL")
    total_high     = sum(1 for a in allocations if a["risk_level"] == "HIGH")

    return jsonify({
        "allocations": allocations,
        "routes":      routes,
        "suggestions": suggestions,
        "summary": {
            "total_zones":      len(zones),
            "critical_zones":   total_critical,
            "high_risk_zones":  total_high,
            "total_supply_gap": sum(
                a["food_gap"] + a["water_gap"] + a["meds_gap"] for a in allocations
            ),
        },
    })


# ─── Database routes (only active when DB is connected) ───

@app.route("/api/zones", methods=["GET", "POST"])
def manage_zones():
    if not USE_DB:
        return jsonify({"error": "Database not configured. Set DATABASE_URL env var."}), 503

    if request.method == "POST":
        d = request.get_json()
        zone = Zone(
            name=d["name"], population=d["population"],
            severity=d["severity"], latitude=d["latitude"], longitude=d["longitude"],
        )
        db.session.add(zone)
        db.session.commit()
        return jsonify({"id": zone.id, "message": "Zone saved"}), 201

    zones = Zone.query.all()
    return jsonify([
        {"id": z.id, "name": z.name, "lat": float(z.latitude),
         "lng": float(z.longitude), "severity": z.severity, "population": z.population}
        for z in zones
    ])


@app.route("/api/zones/<int:zone_id>", methods=["DELETE"])
def delete_zone(zone_id):
    if not USE_DB:
        return jsonify({"error": "Database not configured."}), 503
    zone = Zone.query.get_or_404(zone_id)
    db.session.delete(zone)
    db.session.commit()
    return jsonify({"message": "Zone deleted"})


@app.route("/api/depots", methods=["GET", "POST"])
def manage_depots():
    if not USE_DB:
        return jsonify({"error": "Database not configured."}), 503

    if request.method == "POST":
        d = request.get_json()
        depot = Depot(name=d["name"], latitude=d["latitude"], longitude=d["longitude"])
        db.session.add(depot)
        db.session.commit()
        return jsonify({"id": depot.id, "message": "Depot saved"}), 201

    depots = Depot.query.all()
    return jsonify([
        {"id": dp.id, "name": dp.name, "lat": float(dp.latitude), "lng": float(dp.longitude)}
        for dp in depots
    ])


@app.route("/api/status", methods=["GET"])
def status():
    return jsonify({"database": USE_DB, "ai_configured": HF_API_TOKEN != "YOUR_HF_API_TOKEN_HERE"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
