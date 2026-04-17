"""
seed_data.py — Runtime Python Input Script
==========================================
Run this script to interactively add Zones, Depots, and Supplies
into the MySQL database at runtime.

Usage:
    python seed_data.py               # interactive menu
    python seed_data.py --demo        # load demo data silently
    python seed_data.py --clear       # clear all tables

Requirements: .env file with DB credentials (or set env vars manually)
"""

import os
import sys
import argparse
from datetime import datetime

# ─── Load .env ─────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()  # FIX: moved to top before any os.environ.get() calls
except ImportError:
    pass  # dotenv is optional for this script

# ─── Build DB URL ──────────────────────────────────────────────────────────────
DB_HOST     = os.environ.get("DB_HOST")
DB_PORT     = os.environ.get("DB_PORT")
DB_USER     = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_NAME     = os.environ.get("DB_NAME")

# FIX: missing vars check added
missing_vars = [k for k, v in {"DB_HOST": DB_HOST, "DB_USER": DB_USER, "DB_PASSWORD": DB_PASSWORD, "DB_NAME": DB_NAME}.items() if v is None]
if missing_vars:
    print(f"❌  Missing environment variables: {', '.join(missing_vars)}")
    print("    Please check your .env file.")
    sys.exit(1)

DATABASE_URL = (
    os.environ.get("DATABASE_URL")
    or f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT or 3306}/{DB_NAME}"  # FIX: DB_PORT or 3306
)

# ─── SQLAlchemy setup (standalone — not using app.py) ──────────────────────────
from sqlalchemy import create_engine, Column, Integer, String, Numeric, BigInteger, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

Base    = declarative_base()
engine  = None
Session = None


# ══════════════════════════════════════════════════════════════════════════════
# MODELS  (mirror of app.py — keep in sync)
# ══════════════════════════════════════════════════════════════════════════════

class Zone(Base):
    __tablename__ = "zones"
    id         = Column(Integer,       primary_key=True, autoincrement=True)
    name       = Column(String(255),   nullable=False)
    population = Column(Integer,       nullable=False)
    severity   = Column(Integer,       nullable=False)
    latitude   = Column(Numeric(10,8), nullable=False)
    longitude  = Column(Numeric(11,8), nullable=False)
    created_at = Column(DateTime,      default=datetime.utcnow)

    def __repr__(self):
        return f"Zone(id={self.id}, name={self.name!r}, pop={self.population}, sev={self.severity})"


class Depot(Base):
    __tablename__ = "depots"
    id         = Column(Integer,       primary_key=True, autoincrement=True)
    name       = Column(String(255),   nullable=False)
    location   = Column(String(255),   nullable=True)
    latitude   = Column(Numeric(10,8), nullable=False)
    longitude  = Column(Numeric(11,8), nullable=False)
    capacity   = Column(Integer,       default=100000)
    created_at = Column(DateTime,      default=datetime.utcnow)
    supplies   = relationship("Supply", back_populates="depot")

    def __repr__(self):
        return f"Depot(id={self.id}, name={self.name!r}, loc={self.location!r})"


class Supply(Base):
    __tablename__ = "supplies"
    id          = Column(Integer,     primary_key=True, autoincrement=True)
    supply_type = Column(String(100), nullable=False)
    quantity    = Column(BigInteger,  nullable=False)
    unit        = Column(String(50),  nullable=False)
    depot_id    = Column(Integer,     ForeignKey("depots.id"), nullable=True)
    notes       = Column(Text,        nullable=True)
    updated_at  = Column(DateTime,    default=datetime.utcnow)
    depot       = relationship("Depot", back_populates="supplies")

    def __repr__(self):
        return f"Supply(id={self.id}, type={self.supply_type!r}, qty={self.quantity} {self.unit})"


# ══════════════════════════════════════════════════════════════════════════════
# DEMO DATA  (Tamil Nadu disaster scenario)
# ══════════════════════════════════════════════════════════════════════════════

DEMO_ZONES = [
    {"name": "Chennai Coastal Zone",    "population": 95000, "severity": 9, "latitude": 13.0827, "longitude": 80.2707},
    {"name": "Tiruchirappalli Central", "population": 55000, "severity": 7, "latitude": 10.7905, "longitude": 78.7047},
    {"name": "Madurai River District",  "population": 72000, "severity": 8, "latitude": 9.9252,  "longitude": 78.1198},
    {"name": "Coimbatore Hill Region",  "population": 38000, "severity": 6, "latitude": 11.0168, "longitude": 76.9558},
    {"name": "Salem Plains Area",       "population": 44000, "severity": 5, "latitude": 11.6643, "longitude": 78.1460},
    {"name": "Thanjavur Delta Zone",    "population": 29000, "severity": 8, "latitude": 10.7870, "longitude": 79.1378},
    {"name": "Vellore Border Camp",     "population": 18000, "severity": 6, "latitude": 12.9165, "longitude": 79.1325},
]

DEMO_DEPOTS = [
    {"name": "Depot Alpha — Chennai",    "location": "North Hub",   "latitude": 13.1500, "longitude": 80.2800, "capacity": 500000},
    {"name": "Depot Beta — Trichy",      "location": "Central Hub", "latitude": 10.8500, "longitude": 78.6900, "capacity": 350000},
    {"name": "Depot Gamma — Coimbatore", "location": "West Base",   "latitude": 11.1000, "longitude": 76.9200, "capacity": 280000},
]

DEMO_SUPPLIES = [
    {"supply_type": "food",      "quantity": 750000, "unit": "kg",    "notes": "Rice, lentils, packaged meals"},
    {"supply_type": "water",     "quantity": 500000, "unit": "liters","notes": "Bottled water + purification tablets"},
    {"supply_type": "medicines", "quantity":  85000, "unit": "units", "notes": "First aid kits, antibiotics, ORS"},
    {"supply_type": "tarpaulins","quantity":  12000, "unit": "units", "notes": "Emergency shelter sheets"},
    {"supply_type": "blankets",  "quantity":  20000, "unit": "units", "notes": "Thermal emergency blankets"},
]


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

COLORS = {
    "red":    "\033[91m",  "green":  "\033[92m",
    "yellow": "\033[93m",  "blue":   "\033[94m",
    "cyan":   "\033[96m",  "bold":   "\033[1m",
    "reset":  "\033[0m",
}

def c(color, text):
    return f"{COLORS.get(color,'')}{text}{COLORS['reset']}"

def header(title):
    print("\n" + c("cyan", "═" * 55))
    print(c("bold", f"  {title}"))
    print(c("cyan", "═" * 55))

def success(msg): print(c("green",  f"  ✅  {msg}"))
def warn(msg):    print(c("yellow", f"  ⚠️   {msg}"))
def error(msg):   print(c("red",    f"  ❌  {msg}"))
def info(msg):    print(c("blue",   f"  ℹ️   {msg}"))

def prompt(label, default=None):
    hint = f" [{default}]" if default is not None else ""
    val = input(f"  {label}{hint}: ").strip()
    return val if val else (str(default) if default is not None else val)

def confirm(msg):
    return input(f"\n  {msg} (y/n): ").strip().lower() == "y"


def connect_db():
    global engine, Session
    try:
        engine  = create_engine(DATABASE_URL, pool_pre_ping=True)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        success(f"Connected to MySQL → {DB_NAME}  on  {DB_HOST}:{DB_PORT or 3306}")
        return True
    except Exception as exc:
        error(f"Cannot connect to MySQL: {exc}")
        print(f"\n  Check your .env file:\n"
              f"    DB_HOST={DB_HOST}\n"
              f"    DB_PORT={DB_PORT}\n"
              f"    DB_USER={DB_USER}\n"
              f"    DB_NAME={DB_NAME}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# ADD FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def add_zone_interactive(session):
    header("ADD NEW ZONE")
    name = prompt("Zone name (e.g. Chennai Coastal Zone)")
    if not name:
        warn("Name cannot be empty.")
        return
    try:
        population = int(prompt("Population affected"))
        severity   = int(prompt("Severity level (1–10)"))
        if not (1 <= severity <= 10):
            raise ValueError
        latitude  = float(prompt("Latitude  (e.g. 13.0827)"))
        longitude = float(prompt("Longitude (e.g. 80.2707)"))
    except ValueError:
        error("Invalid input — please enter correct numbers.")
        return

    zone = Zone(name=name, population=population, severity=severity,
                latitude=latitude, longitude=longitude)
    session.add(zone)
    session.commit()
    success(f"Zone '{name}' saved with ID {zone.id}")


def add_depot_interactive(session):
    header("ADD NEW DEPOT")
    name     = prompt("Depot name (e.g. Depot Alpha — Chennai)")
    location = prompt("Location description (e.g. North Hub)", default="")
    try:
        latitude   = float(prompt("Latitude  (e.g. 13.1500)"))
        longitude  = float(prompt("Longitude (e.g. 80.2800)"))
        capacity   = int(prompt("Storage capacity (units)", default=100000))
    except ValueError:
        error("Invalid input.")
        return

    depot = Depot(name=name, location=location, latitude=latitude,
                  longitude=longitude, capacity=capacity)
    session.add(depot)
    session.commit()
    success(f"Depot '{name}' saved with ID {depot.id}")


def add_supply_interactive(session):
    header("ADD NEW SUPPLY")

    # Show available depots
    depots = session.query(Depot).all()
    depot_id = None
    if depots:
        print(c("cyan", "\n  Available depots:"))
        for dp in depots:
            print(f"    [{dp.id}] {dp.name}")
        raw = prompt("Assign to depot ID (leave blank for unassigned)", default="")
        if raw.isdigit():
            depot_id = int(raw)

    supply_type = prompt("Supply type (food / water / medicines / tarpaulins / blankets)")
    if not supply_type:
        error("Supply type cannot be empty.")
        return
    try:
        quantity = int(prompt("Quantity"))
    except ValueError:
        error("Invalid quantity.")
        return
    unit  = prompt("Unit (kg / liters / units)", default="units")
    notes = prompt("Notes (optional)", default="")

    supply = Supply(supply_type=supply_type.lower(), quantity=quantity,
                    unit=unit, depot_id=depot_id, notes=notes)
    session.add(supply)
    session.commit()
    success(f"Supply '{supply_type}' × {quantity} {unit} saved with ID {supply.id}")


# ══════════════════════════════════════════════════════════════════════════════
# LIST / VIEW FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def list_zones(session):
    zones = session.query(Zone).order_by(Zone.severity.desc()).all()
    header(f"ALL ZONES  ({len(zones)} records)")
    if not zones:
        warn("No zones found.")
        return
    print(f"  {'ID':<4} {'Name':<32} {'Population':>12} {'Sev':>4}  {'Latitude':>10} {'Longitude':>11}")
    print("  " + "─" * 78)
    for z in zones:
        print(f"  {z.id:<4} {z.name:<32} {z.population:>12,} {z.severity:>4}  {float(z.latitude):>10.4f} {float(z.longitude):>11.4f}")


def list_depots(session):
    depots = session.query(Depot).order_by(Depot.name).all()
    header(f"ALL DEPOTS  ({len(depots)} records)")
    if not depots:
        warn("No depots found.")
        return
    print(f"  {'ID':<4} {'Name':<32} {'Location':<18} {'Capacity':>10}")
    print("  " + "─" * 68)
    for dp in depots:
        print(f"  {dp.id:<4} {dp.name:<32} {(dp.location or ''):<18} {dp.capacity:>10,}")


def list_supplies(session):
    supplies = session.query(Supply).order_by(Supply.supply_type).all()
    header(f"ALL SUPPLIES  ({len(supplies)} records)")
    if not supplies:
        warn("No supplies found.")
        return
    print(f"  {'ID':<4} {'Type':<16} {'Quantity':>12} {'Unit':<10} {'Depot':<26} {'Notes'}")
    print("  " + "─" * 85)
    for s in supplies:
        depot_name = s.depot.name if s.depot else "—"
        print(f"  {s.id:<4} {s.supply_type:<16} {s.quantity:>12,} {s.unit:<10} {depot_name:<26} {(s.notes or '')[:30]}")


def db_summary(session):
    header("DATABASE SUMMARY")
    zones   = session.query(Zone).count()
    depots  = session.query(Depot).count()
    sups    = session.query(Supply).all()
    total_pop = session.query(Zone).with_entities(Zone.population).all()
    pop_sum   = sum(z[0] for z in total_pop)
    print(f"  Zones    : {c('green', str(zones))}")
    print(f"  Depots   : {c('green', str(depots))}")
    print(f"  Supplies : {c('green', str(len(sups)))} records")
    print(f"  Total population affected: {c('yellow', f'{pop_sum:,}')}")
    for s in sups:
        print(f"    • {s.supply_type:16} {s.quantity:>12,} {s.unit}")


# ══════════════════════════════════════════════════════════════════════════════
# BULK LOAD DEMO DATA
# ══════════════════════════════════════════════════════════════════════════════

def load_demo_data(session, silent=False):
    if not silent:
        header("LOAD DEMO DATA — Tamil Nadu Disaster Scenario")
        if not confirm("This will INSERT demo zones, depots, and supplies. Continue?"):
            return

    for zd in DEMO_ZONES:
        session.add(Zone(**zd))
    for dd in DEMO_DEPOTS:
        session.add(Depot(**dd))
    session.commit()  # commit depots first so IDs exist

    depots = session.query(Depot).all()
    for i, sd in enumerate(DEMO_SUPPLIES):
        depot_id = depots[i % len(depots)].id if depots else None
        session.add(Supply(**sd, depot_id=depot_id))
    session.commit()

    success(f"Demo data loaded: {len(DEMO_ZONES)} zones, {len(DEMO_DEPOTS)} depots, {len(DEMO_SUPPLIES)} supply records")


# ══════════════════════════════════════════════════════════════════════════════
# CLEAR ALL
# ══════════════════════════════════════════════════════════════════════════════

def clear_all(session):
    header("⚠️  CLEAR ALL DATA")
    if not confirm("This will DELETE all zones, depots, and supplies. Are you sure?"):
        info("Cancelled.")
        return
    session.query(Supply).delete()
    session.query(Zone).delete()
    session.query(Depot).delete()
    session.commit()
    success("All data cleared.")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN MENU
# ══════════════════════════════════════════════════════════════════════════════

MENU = """
  ┌────────────────────────────────────────────┐
  │   AI DISASTER OPTIMIZER — DB SEED TOOL     │
  ├────────────────────────────────────────────┤
  │  [1]  Add a Zone                           │
  │  [2]  Add a Depot                          │
  │  [3]  Add a Supply                         │
  │  [4]  List all Zones                       │
  │  [5]  List all Depots                      │
  │  [6]  List all Supplies                    │
  │  [7]  Database Summary                     │
  │  [8]  Load Demo Data (Tamil Nadu scenario) │
  │  [9]  Clear All Data                       │
  │  [0]  Exit                                 │
  └────────────────────────────────────────────┘
"""

def main():
    parser = argparse.ArgumentParser(description="DB Seed Tool for Disaster Optimizer")
    parser.add_argument("--demo",  action="store_true", help="Load demo data and exit")
    parser.add_argument("--clear", action="store_true", help="Clear all data and exit")
    args = parser.parse_args()

    print(c("bold", "\n🌐  AI Disaster Supply Chain Optimizer — Runtime DB Input"))
    print(f"  Target: {c('cyan', f'mysql://{DB_USER}@{DB_HOST}:{DB_PORT or 3306}/{DB_NAME}')}\n")

    if not connect_db():
        sys.exit(1)

    session = Session()

    try:
        if args.demo:
            load_demo_data(session, silent=True)
            db_summary(session)
            return
        if args.clear:
            clear_all(session)
            return

        # ── Interactive loop ────────────────────────────────────────────────────
        while True:
            print(c("cyan", MENU))
            choice = input("  Enter choice: ").strip()

            if   choice == "1": add_zone_interactive(session)
            elif choice == "2": add_depot_interactive(session)
            elif choice == "3": add_supply_interactive(session)
            elif choice == "4": list_zones(session)
            elif choice == "5": list_depots(session)
            elif choice == "6": list_supplies(session)
            elif choice == "7": db_summary(session)
            elif choice == "8": load_demo_data(session)
            elif choice == "9": clear_all(session)
            elif choice == "0":
                info("Goodbye!")
                break
            else:
                warn("Invalid choice. Enter 0–9.")

    except KeyboardInterrupt:
        print(c("yellow", "\n\n  Interrupted. Goodbye!"))
    finally:
        session.close()
        if engine:
            engine.dispose()


if __name__ == "__main__":
    main()