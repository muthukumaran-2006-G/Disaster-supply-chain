"""
AI-Based Disaster Supply Chain Optimizer
Full-Stack Edition — MySQL Required
Author: Disaster Relief Tech Team
"""

from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import json, math, os, requests
from datetime import datetime

# ─── Load environment variables ────────────────────────────────────────────────
load_dotenv()  # FIX: moved to top before any os.environ.get() calls

app = Flask(__name__)

# ─── MySQL Configuration (REQUIRED) ────────────────────────────────────────────
DB_HOST     = os.environ.get("DB_HOST")
DB_PORT     = os.environ.get("DB_PORT")
DB_USER     = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_NAME     = os.environ.get("DB_NAME")

# Check for required environment variables
required_vars = {
    "DB_HOST": DB_HOST,
    "DB_USER": DB_USER,
    "DB_PASSWORD": DB_PASSWORD,
    "DB_NAME": DB_NAME,
}
missing_vars = [key for key, value in required_vars.items() if value is None]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}. Please set them in your .env file or environment.")

DATABASE_URL = (
    os.environ.get("DATABASE_URL")
    or f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT or 3306}/{DB_NAME}"  # FIX: DB_PORT or 3306
)

app.config["SQLALCHEMY_DATABASE_URI"]        = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"]      = {
    "pool_pre_ping": True,
    "pool_recycle":  3600,
}

db = SQLAlchemy(app)

# ─── Hugging Face AI Config ─────────────────────────────────────────────────────
HF_API_TOKEN = os.environ.get("HF_API_TOKEN")
HF_MODEL     = "mistralai/Mistral-7B-Instruct-v0.2"
HF_API_URL   = f"https://api-inference.huggingface.co/models/{HF_MODEL}"


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE MODELS
# ══════════════════════════════════════════════════════════════════════════════

class Zone(db.Model):
    __tablename__ = "zones"
    id         = db.Column(db.Integer,       primary_key=True, autoincrement=True)
    name       = db.Column(db.String(255),   nullable=False)
    population = db.Column(db.Integer,       nullable=False)
    severity   = db.Column(db.Integer,       nullable=False)          # 1–10
    latitude   = db.Column(db.Numeric(10,8), nullable=False)
    longitude  = db.Column(db.Numeric(11,8), nullable=False)
    created_at = db.Column(db.DateTime,      default=datetime.utcnow)

    def to_dict(self):
        return {
            "id":         self.id,
            "name":       self.name,
            "population": self.population,
            "severity":   self.severity,
            "latitude":   float(self.latitude),
            "longitude":  float(self.longitude),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Depot(db.Model):
    __tablename__ = "depots"
    id         = db.Column(db.Integer,       primary_key=True, autoincrement=True)
    name       = db.Column(db.String(255),   nullable=False)
    location   = db.Column(db.String(255),   nullable=True)
    latitude   = db.Column(db.Numeric(10,8), nullable=False)
    longitude  = db.Column(db.Numeric(11,8), nullable=False)
    capacity   = db.Column(db.Integer,       default=100000)         # max supply units
    created_at = db.Column(db.DateTime,      default=datetime.utcnow)

    def to_dict(self):
        return {
            "id":         self.id,
            "name":       self.name,
            "location":   self.location,
            "latitude":   float(self.latitude),
            "longitude":  float(self.longitude),
            "capacity":   self.capacity,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Supply(db.Model):
    __tablename__ = "supplies"
    id           = db.Column(db.Integer,     primary_key=True, autoincrement=True)
    supply_type  = db.Column(db.String(100), nullable=False)          # food / water / medicines / etc.
    quantity     = db.Column(db.BigInteger,  nullable=False)
    unit         = db.Column(db.String(50),  nullable=False)          # kg / liters / units
    depot_id     = db.Column(db.Integer,     db.ForeignKey("depots.id"), nullable=True)
    notes        = db.Column(db.Text,        nullable=True)
    updated_at   = db.Column(db.DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)

    depot = db.relationship("Depot", backref="supplies", lazy=True)

    def to_dict(self):
        return {
            "id":          self.id,
            "supply_type": self.supply_type,
            "quantity":    self.quantity,
            "unit":        self.unit,
            "depot_id":    self.depot_id,
            "depot_name":  self.depot.name if self.depot else None,
            "notes":       self.notes,
            "updated_at":  self.updated_at.isoformat() if self.updated_at else None,
        }


# ─── Create all tables on startup ──────────────────────────────────────────────
with app.app_context():
    try:
        db.create_all()
        print(f"[DB] ✅  Connected to MySQL → {DB_NAME} on {DB_HOST}:{DB_PORT}")
    except Exception as exc:
        print(f"[DB] ❌  Failed to connect: {exc}")
        print("[DB]    Make sure MySQL is running and credentials in .env are correct.")
        raise SystemExit(1)


# ══════════════════════════════════════════════════════════════════════════════
# CORE OPTIMIZATION ALGORITHMS
# ══════════════════════════════════════════════════════════════════════════════

def haversine_km(lat1, lng1, lat2, lng2):
    """Real-world great-circle distance in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2)
    return R * 2 * math.asin(math.sqrt(a))


def calculate_demand(zones):
    demands = []
    for z in zones:
        base = z["population"] * z["severity"]
        demands.append({
            "zone":             z["name"],
            "zone_id":          z.get("id"),
            "severity":         z["severity"],
            "population":       z["population"],
            "demand_score":     base,
            "food_needed":      round(base * 0.004),
            "water_needed":     round(base * 0.0025),
            "medicine_needed":  round(base * 0.0004),
        })
    demands.sort(key=lambda d: d["demand_score"], reverse=True)
    return demands


def build_supply_pool(db_supplies):
    """Aggregate DB supply records into {type: {quantity, unit}} dict."""
    pool = {}
    for s in db_supplies:
        key = s["supply_type"].lower()
        if key not in pool:
            pool[key] = {"quantity": 0, "unit": s["unit"]}
        pool[key]["quantity"] += s["quantity"]
    # Ensure standard keys exist
    for k, unit in [("food", "kg"), ("water", "liters"), ("medicines", "units")]:
        if k not in pool:
            pool[k] = {"quantity": 0, "unit": unit}
    return pool


def allocate_supplies(demands, supplies):
    avail_food  = supplies.get("food",      {}).get("quantity", 0)
    avail_water = supplies.get("water",     {}).get("quantity", 0)
    avail_meds  = supplies.get("medicines", {}).get("quantity", 0)
    total_demand = sum(d["demand_score"] for d in demands) or 1

    allocations = []
    for d in demands:
        share = d["demand_score"] / total_demand

        alloc_food  = min(round(avail_food  * share), d["food_needed"])
        alloc_water = min(round(avail_water * share), d["water_needed"])
        alloc_meds  = min(round(avail_meds  * share), d["medicine_needed"])

        food_gap  = max(0, d["food_needed"]     - alloc_food)
        water_gap = max(0, d["water_needed"]    - alloc_water)
        meds_gap  = max(0, d["medicine_needed"] - alloc_meds)

        total_needed = max(d["food_needed"] + d["water_needed"] + d["medicine_needed"], 1)
        gap_ratio = (food_gap + water_gap + meds_gap) / total_needed

        if   gap_ratio > 0.5: risk = "CRITICAL"
        elif gap_ratio > 0.2: risk = "HIGH"
        elif gap_ratio > 0:   risk = "MEDIUM"
        else:                 risk = "LOW"

        alerts = []
        if food_gap  > 0: alerts.append(f"Food shortage: {food_gap:,} kg")
        if water_gap > 0: alerts.append(f"Water shortage: {water_gap:,} L")
        if meds_gap  > 0: alerts.append(f"Medicine shortage: {meds_gap:,} units")

        allocations.append({
            "zone":        d["zone"],
            "zone_id":     d.get("zone_id"),
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


def build_routes(zones, depots):
    """Match each zone to its nearest depot using real lat/lng (haversine)."""
    routes = []
    for z in zones:
        best_depot, best_dist = None, float("inf")
        for dp in depots:
            dist = haversine_km(
                float(z["latitude"]),  float(z["longitude"]),
                float(dp["latitude"]), float(dp["longitude"]),
            )
            if dist < best_dist:
                best_dist, best_depot = dist, dp["name"]

        routes.append({
            "zone":            z["name"],
            "depot":           best_depot or "No depot",
            "distance_km":     round(best_dist, 1),
            "estimated_hours": round(best_dist / 50, 1),   # avg 50 km/h convoy speed
        })
    return routes


def get_ai_suggestions(allocations, routes):
    critical = [a["zone"] for a in allocations if a["risk_level"] == "CRITICAL"]
    high     = [a["zone"] for a in allocations if a["risk_level"] == "HIGH"]
    gaps     = sum(a["food_gap"] + a["water_gap"] + a["meds_gap"] for a in allocations)

    if HF_API_TOKEN:
        prompt = f"""[INST] You are a disaster relief logistics expert AI.
Situation: {len(allocations)} zones affected.
Critical: {', '.join(critical) or 'None'} | High: {', '.join(high) or 'None'}
Total supply gap: {gaps:,} units
Give 4 numbered, actionable recommendations (max 2 sentences each). [/INST]"""
        try:
            resp = requests.post(
                HF_API_URL,
                headers={"Authorization": f"Bearer {HF_API_TOKEN}"},
                json={"inputs": prompt, "parameters": {"max_new_tokens": 350, "temperature": 0.6, "return_full_text": False}},
                timeout=20,
            )
            if resp.status_code == 200:
                raw = resp.json()
                if isinstance(raw, list) and raw:
                    text = raw[0].get("generated_text", "").strip()
                    if text:
                        return {"source": "AI (Hugging Face Mistral-7B)", "text": text}
        except Exception:
            pass

    # Rule-based fallback
    lines = []
    if critical:
        lines.append(f"1. Deploy emergency convoys immediately to {', '.join(critical[:2])} — prioritise water and medicines first.")
    else:
        lines.append("1. No critical zones detected — maintain current schedule and monitor for escalation.")
    lines.append(f"2. Total supply gap is {gaps:,} units. Request additional aid from national reserves or NGO partners within 24 hours." if gaps else
                 "2. Supply coverage is sufficient — focus on timely, equitable distribution.")
    long = [r for r in routes if r["estimated_hours"] > 3]
    lines.append(f"3. Zones {', '.join(r['zone'] for r in long[:2])} have travel times > 3 hrs — pre-position supplies or use air transport." if long else
                 "3. All routes are within 3-hour range — standard ground convoy operations are adequate.")
    lines.append("4. Establish radio check-ins every 6 hours to track progress and dynamically re-route if roads are blocked.")
    return {"source": "Rule-Based Fallback", "text": "\n".join(lines)}


# ══════════════════════════════════════════════════════════════════════════════
# FLASK ROUTES — PAGES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


# ══════════════════════════════════════════════════════════════════════════════
# FLASK ROUTES — STATUS
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/status")
def status():
    zone_count   = Zone.query.count()
    depot_count  = Depot.query.count()
    supply_count = Supply.query.count()
    return jsonify({
        "database":     True,
        "db_name":      DB_NAME,
        "db_host":      DB_HOST,
        "ai_enabled":   bool(HF_API_TOKEN),
        "zone_count":   zone_count,
        "depot_count":  depot_count,
        "supply_count": supply_count,
    })


# ══════════════════════════════════════════════════════════════════════════════
# FLASK ROUTES — ZONES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/zones", methods=["GET"])
def get_zones():
    zones = Zone.query.order_by(Zone.severity.desc()).all()
    return jsonify([z.to_dict() for z in zones])


@app.route("/api/zones", methods=["POST"])
def create_zone():
    d = request.get_json()
    required = ["name", "population", "severity", "latitude", "longitude"]
    if not all(k in d for k in required):
        return jsonify({"error": f"Missing fields: {required}"}), 400
    if not (1 <= int(d["severity"]) <= 10):
        return jsonify({"error": "Severity must be 1–10"}), 400
    zone = Zone(
        name=d["name"], population=int(d["population"]),
        severity=int(d["severity"]),
        latitude=float(d["latitude"]), longitude=float(d["longitude"]),
    )
    db.session.add(zone)
    db.session.commit()
    return jsonify({"message": "Zone saved", "zone": zone.to_dict()}), 201


@app.route("/api/zones/<int:zone_id>", methods=["PUT"])
def update_zone(zone_id):
    zone = db.get_or_404(Zone, zone_id)  # FIX: deprecated query.get_or_404
    d    = request.get_json()
    for field in ["name", "population", "severity", "latitude", "longitude"]:
        if field in d:
            setattr(zone, field, d[field])
    db.session.commit()
    return jsonify({"message": "Zone updated", "zone": zone.to_dict()})


@app.route("/api/zones/<int:zone_id>", methods=["DELETE"])
def delete_zone(zone_id):
    zone = db.get_or_404(Zone, zone_id)  # FIX: deprecated query.get_or_404
    db.session.delete(zone)
    db.session.commit()
    return jsonify({"message": "Zone deleted"})


# ══════════════════════════════════════════════════════════════════════════════
# FLASK ROUTES — DEPOTS
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/depots", methods=["GET"])
def get_depots():
    depots = Depot.query.order_by(Depot.name).all()
    return jsonify([dp.to_dict() for dp in depots])


@app.route("/api/depots", methods=["POST"])
def create_depot():
    d = request.get_json()
    required = ["name", "latitude", "longitude"]
    if not all(k in d for k in required):
        return jsonify({"error": f"Missing fields: {required}"}), 400
    depot = Depot(
        name=d["name"], location=d.get("location", ""),
        latitude=float(d["latitude"]), longitude=float(d["longitude"]),
        capacity=int(d.get("capacity", 100000)),
    )
    db.session.add(depot)
    db.session.commit()
    return jsonify({"message": "Depot saved", "depot": depot.to_dict()}), 201


@app.route("/api/depots/<int:depot_id>", methods=["DELETE"])
def delete_depot(depot_id):
    depot = db.get_or_404(Depot, depot_id)  # FIX: deprecated query.get_or_404
    db.session.delete(depot)
    db.session.commit()
    return jsonify({"message": "Depot deleted"})


# ══════════════════════════════════════════════════════════════════════════════
# FLASK ROUTES — SUPPLIES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/supplies", methods=["GET"])
def get_supplies():
    supplies = Supply.query.order_by(Supply.supply_type).all()
    return jsonify([s.to_dict() for s in supplies])


@app.route("/api/supplies", methods=["POST"])
def create_supply():
    d = request.get_json()
    required = ["supply_type", "quantity", "unit"]
    if not all(k in d for k in required):
        return jsonify({"error": f"Missing fields: {required}"}), 400
    supply = Supply(
        supply_type=d["supply_type"].lower(),
        quantity=int(d["quantity"]),
        unit=d["unit"],
        depot_id=d.get("depot_id"),
        notes=d.get("notes", ""),
    )
    db.session.add(supply)
    db.session.commit()
    return jsonify({"message": "Supply saved", "supply": supply.to_dict()}), 201


@app.route("/api/supplies/<int:supply_id>", methods=["PUT"])
def update_supply(supply_id):
    supply = db.get_or_404(Supply, supply_id)  # FIX: deprecated query.get_or_404
    d      = request.get_json()
    for field in ["supply_type", "quantity", "unit", "depot_id", "notes"]:
        if field in d:
            setattr(supply, field, d[field])
    db.session.commit()
    return jsonify({"message": "Supply updated", "supply": supply.to_dict()})


@app.route("/api/supplies/<int:supply_id>", methods=["DELETE"])
def delete_supply(supply_id):
    supply = db.get_or_404(Supply, supply_id)  # FIX: deprecated query.get_or_404
    db.session.delete(supply)
    db.session.commit()
    return jsonify({"message": "Supply deleted"})


# ══════════════════════════════════════════════════════════════════════════════
# FLASK ROUTES — OPTIMIZATION (uses live DB data)
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/optimize", methods=["POST"])
def optimize():
    """
    Run the full optimization pipeline using live data from MySQL.
    Optionally accepts override data in the POST body.
    """
    body = request.get_json(silent=True) or {}

    # ── Zones ──────────────────────────────────────────────────────────────────
    if body.get("zones"):
        zones = body["zones"]
    else:
        db_zones = Zone.query.all()
        if not db_zones:
            return jsonify({"error": "No zones found. Add zones first via the form or seed_data.py"}), 400
        zones = [z.to_dict() for z in db_zones]

    # ── Depots ─────────────────────────────────────────────────────────────────
    if body.get("depots"):
        depots = body["depots"]
    else:
        db_depots = Depot.query.all()
        if not db_depots:
            return jsonify({"error": "No depots found. Add depots first via the form or seed_data.py"}), 400
        depots = [dp.to_dict() for dp in db_depots]

    # ── Supplies ───────────────────────────────────────────────────────────────
    if body.get("supplies"):
        raw = body["supplies"]
        # FIX: handle both list and dict formats from POST body
        supplies = build_supply_pool(raw) if isinstance(raw, list) else raw
    else:
        db_supplies = [s.to_dict() for s in Supply.query.all()]
        if not db_supplies:
            return jsonify({"error": "No supplies found. Add supplies first via the form or seed_data.py"}), 400
        supplies = build_supply_pool(db_supplies)

    # ── Run algorithm ──────────────────────────────────────────────────────────
    demands     = calculate_demand(zones)
    allocations = allocate_supplies(demands, supplies)
    routes      = build_routes(zones, depots)
    suggestions = get_ai_suggestions(allocations, routes)

    return jsonify({
        "allocations": allocations,
        "routes":      routes,
        "suggestions": suggestions,
        "supply_pool": supplies,
        "summary": {
            "total_zones":      len(zones),
            "critical_zones":   sum(1 for a in allocations if a["risk_level"] == "CRITICAL"),
            "high_risk_zones":  sum(1 for a in allocations if a["risk_level"] == "HIGH"),
            "total_supply_gap": sum(a["food_gap"] + a["water_gap"] + a["meds_gap"] for a in allocations),
        },
    })


# ══════════════════════════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app.run(debug=True)  # FIX: was missing entirely