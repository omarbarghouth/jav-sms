"""
Jordan Aviation – Safety Management System (SMS)
Full ICAO Annex 19 / IOSA Compliant Implementation
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import json, os, uuid
from datetime import datetime, date, timedelta
from collections import defaultdict

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "jav-sms-secret-2024")

# ─── In-memory database (replace with SQLite/Postgres for production) ────────
DB = {
    "departments": [
        {"id": 1, "code": "FO",  "name": "Flight Operations",       "color": "#1e40af"},
        {"id": 2, "code": "ME",  "name": "Maintenance / Engineering","color": "#065f46"},
        {"id": 3, "code": "GO",  "name": "Ground Operations",        "color": "#92400e"},
        {"id": 4, "code": "CC",  "name": "Cabin Crew",               "color": "#6b21a8"},
        {"id": 5, "code": "SD",  "name": "Safety Department",        "color": "#be123c"},
        {"id": 6, "code": "QA",  "name": "Quality Assurance",        "color": "#0369a1"},
        {"id": 7, "code": "TR",  "name": "Training",                 "color": "#0f766e"},
        {"id": 8, "code": "OPS", "name": "Operations Control",       "color": "#7c3aed"},
    ],

    "risk_matrix": {
        "likelihood": [
            {"value": 5, "label": "Frequent",             "description": "Likely to occur many times (has occurred frequently)"},
            {"value": 4, "label": "Occasional",           "description": "Likely to occur sometimes (has occurred infrequently)"},
            {"value": 3, "label": "Remote",               "description": "Unlikely to occur, but possible (has occurred rarely)"},
            {"value": 2, "label": "Improbable",           "description": "Very unlikely to occur (not known to have occurred)"},
            {"value": 1, "label": "Extremely Improbable", "description": "Almost inconceivable that the event will occur"},
        ],
        "severity": [
            {"value": "A", "label": "Catastrophic", "description": "Aircraft/equipment destroyed. Multiple deaths."},
            {"value": "B", "label": "Hazardous",    "description": "Large reduction in safety margins. Serious injury."},
            {"value": "C", "label": "Major",        "description": "Significant reduction in safety margins. Serious incident."},
            {"value": "D", "label": "Minor",        "description": "Nuisance. Operating limitations. Minor incident."},
            {"value": "E", "label": "Negligible",   "description": "Few consequences."},
        ],
        "tolerance": {
            "INTOLERABLE": ["5A","5B","5C","4A","4B","3A"],
            "TOLERABLE":   ["5D","5E","4C","4D","4E","3B","3C","3D","2A","2B","2C","1A"],
            "ACCEPTABLE":  ["3E","2D","2E","1B","1C","1D","1E"],
        }
    },

    # ── REPORTS ──
    "hazard_reports": [],
    "asr_reports": [],

    # ── HAZARDS (enhanced) ──
    "hazards": [],

    # ── RISKS (multiple per hazard) ──
    "risks": [],

    # ── CONTROLS (multiple per risk) ──
    "controls": [],

    # ── ACTIONS ──
    "actions": [],

    # ── AUDITS ──
    "audits": [],
    "audit_findings": [],

    # ── INVESTIGATIONS ──
    "investigations": [],

    # ── MOC ──
    "moc": [],

    # ── SPI ──
    "spi_indicators": [
        {"id":1,"code":"UA",    "name":"Unstable Approach",           "department_ids":[1],    "unit":"per 1000 flights","spt_target":9.4, "alert_l1":13.51,"alert_l2":17.13},
        {"id":2,"code":"HSRTO", "name":"High Speed Rejected Takeoff", "department_ids":[1],    "unit":"per 1000 flights","spt_target":0.83,"alert_l1":2.93, "alert_l2":4.97},
        {"id":3,"code":"RED",   "name":"Runway Excursion/Deviation",  "department_ids":[1,3],  "unit":"per 1000 flights","spt_target":1.38,"alert_l1":4.07, "alert_l2":6.7},
        {"id":4,"code":"TCAS",  "name":"TCAS RA Encounter",           "department_ids":[1],    "unit":"per 1000 flights","spt_target":3.02,"alert_l1":5.98, "alert_l2":8.78},
        {"id":5,"code":"GA",    "name":"Go-Around",                   "department_ids":[1],    "unit":"per 1000 flights","spt_target":14.58,"alert_l1":18.83,"alert_l2":22.32},
        {"id":6,"code":"BS",    "name":"Bird Strike",                 "department_ids":[1,3],  "unit":"per 1000 flights","spt_target":2.15,"alert_l1":5.07, "alert_l2":7.87},
        {"id":7,"code":"CFIT",  "name":"CFIT / GPWS Alert",           "department_ids":[1],    "unit":"per 1000 flights","spt_target":0.87,"alert_l1":3.06, "alert_l2":5.21},
        {"id":8,"code":"ATB",   "name":"Air Turnback",                "department_ids":[1],    "unit":"per 1000 flights","spt_target":2.54,"alert_l1":5.47, "alert_l2":8.27},
        {"id":9,"code":"FCIR",  "name":"Flight Crew Incident Report", "department_ids":[1],    "unit":"per 1000 flights","spt_target":7.78,"alert_l1":11.07,"alert_l2":13.96},
        {"id":10,"code":"ME-INJ","name":"Maintenance Injury Rate",    "department_ids":[2],    "unit":"per 100 staff",  "spt_target":2.0, "alert_l1":4.0,  "alert_l2":6.0},
        {"id":11,"code":"GO-INJ","name":"Ground Ops Injury Rate",     "department_ids":[3],    "unit":"per 100 staff",  "spt_target":3.0, "alert_l1":6.0,  "alert_l2":9.0},
        {"id":12,"code":"SR",    "name":"Safety Reports Filed",       "department_ids":[1,2,3,4,5],"unit":"per 1000 ops","spt_target":5.0,"alert_l1":2.0,  "alert_l2":1.0},
    ],
    "spi_data": [
        {"spi_id":1,"year":2025,"month":1,"events":7,"flights":580,"rate":12.07},
        {"spi_id":1,"year":2025,"month":2,"events":5,"flights":520,"rate":9.62},
        {"spi_id":1,"year":2025,"month":3,"events":9,"flights":610,"rate":14.75},
        {"spi_id":1,"year":2025,"month":4,"events":4,"flights":530,"rate":7.55},
        {"spi_id":2,"year":2025,"month":1,"events":1,"flights":580,"rate":1.72},
        {"spi_id":2,"year":2025,"month":2,"events":0,"flights":520,"rate":0.0},
        {"spi_id":3,"year":2025,"month":1,"events":2,"flights":580,"rate":3.45},
        {"spi_id":4,"year":2025,"month":1,"events":3,"flights":580,"rate":5.17},
        {"spi_id":5,"year":2025,"month":1,"events":8,"flights":580,"rate":13.79},
        {"spi_id":5,"year":2025,"month":2,"events":11,"flights":520,"rate":21.15},
        {"spi_id":6,"year":2025,"month":1,"events":2,"flights":580,"rate":3.45},
        {"spi_id":6,"year":2025,"month":2,"events":1,"flights":168,"rate":5.95},
        {"spi_id":6,"year":2025,"month":3,"events":0,"flights":182,"rate":0.0},
    ],

    # ── SAFETY PROMOTION ──
    "training_records": [],
    "safety_bulletins": [],
}

# ─── Seed sample data ────────────────────────────────────────────────────────
def seed():
    now = datetime.utcnow().isoformat() + "Z"
    yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"
    week_ago  = (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z"
    month_ago = (datetime.utcnow() - timedelta(days=30)).isoformat() + "Z"

    # Sample hazards
    DB["hazards"] = [
        {
            "id": "HAZ-2025-AA1B2C", "source": "ASR",
            "linked_report_id": "ASR-2025-XX1YY2",
            "department_id": 1, "type_of_activity": "Flight Operations",
            "classification": "Operational",
            "generic_hazard": "Bird Strike on Final Approach",
            "specific_components": "Engine ingestion risk during approach to OJAI",
            "consequences": "Potential engine damage, forced landing",
            "initial_likelihood": 3, "initial_severity": "B",
            "initial_risk_index": "3B", "initial_risk_tolerance": "TOLERABLE",
            "current_defenses": "Bird scatter programme, wildlife management",
            "further_mitigations": "Enhanced bird radar at OJAI",
            "residual_likelihood": 2, "residual_severity": "C",
            "residual_risk_index": "2C", "residual_risk_tolerance": "TOLERABLE",
            "status": "Open", "owner": "Flight Operations Manager", "created_at": week_ago
        },
        {
            "id": "HAZ-2025-BB3C4D", "source": "Hazard Report",
            "linked_report_id": "HR-2025-CC5D6E",
            "department_id": 2, "type_of_activity": "Maintenance",
            "classification": "Technical",
            "generic_hazard": "Hydraulic System Leak",
            "specific_components": "Landing gear hydraulic line — Hangar 2",
            "consequences": "Landing gear failure, runway excursion",
            "initial_likelihood": 2, "initial_severity": "A",
            "initial_risk_index": "2A", "initial_risk_tolerance": "TOLERABLE",
            "current_defenses": "Pre-flight hydraulic checks",
            "further_mitigations": "Replacement of ageing hydraulic seals fleet-wide",
            "residual_likelihood": 1, "residual_severity": "B",
            "residual_risk_index": "1B", "residual_risk_tolerance": "ACCEPTABLE",
            "status": "Open", "owner": "Chief Engineer", "created_at": month_ago
        },
        {
            "id": "HAZ-2025-CC7D8E", "source": "Audit",
            "linked_report_id": "AUD-2025-FIND01",
            "department_id": 3, "type_of_activity": "Ramp Operations",
            "classification": "Human Factors",
            "generic_hazard": "FOD on Ramp Area",
            "specific_components": "Gate B3 – loose equipment debris",
            "consequences": "Engine FOD ingestion, tyre damage",
            "initial_likelihood": 4, "initial_severity": "C",
            "initial_risk_index": "4C", "initial_risk_tolerance": "TOLERABLE",
            "current_defenses": "Daily FOD walk",
            "further_mitigations": "Increase FOD walk frequency + staff briefing",
            "residual_likelihood": 2, "residual_severity": "D",
            "residual_risk_index": "2D", "residual_risk_tolerance": "ACCEPTABLE",
            "status": "Closed", "owner": "Ground Operations Supervisor", "created_at": month_ago
        },
        {
            "id": "HAZ-2025-INT001", "source": "ASR",
            "linked_report_id": "ASR-2025-EMG01",
            "department_id": 1, "type_of_activity": "Flight Operations",
            "classification": "Organizational",
            "generic_hazard": "GPWS / CFIT Alert During Approach",
            "specific_components": "Approach to HESH in IMC — below MDA",
            "consequences": "Controlled flight into terrain",
            "initial_likelihood": 3, "initial_severity": "A",
            "initial_risk_index": "3A", "initial_risk_tolerance": "INTOLERABLE",
            "current_defenses": "GPWS system fitted, CRM training",
            "further_mitigations": "Enhanced approach briefing SOPs, mandatory FOQA review",
            "residual_likelihood": None, "residual_severity": None,
            "residual_risk_index": None, "residual_risk_tolerance": None,
            "status": "Open", "owner": "Director of Flight Operations", "created_at": yesterday
        },
    ]

    # Sample risks
    DB["risks"] = [
        {
            "id": "RSK-2025-001", "hazard_id": "HAZ-2025-AA1B2C",
            "risk_description": "Bird ingestion causing dual engine failure",
            "likelihood": 2, "severity": "A", "risk_index": "2A", "tolerance": "TOLERABLE",
            "residual_likelihood": 1, "residual_severity": "B",
            "residual_risk_index": "1B", "residual_tolerance": "ACCEPTABLE",
            "created_at": week_ago
        },
        {
            "id": "RSK-2025-002", "hazard_id": "HAZ-2025-AA1B2C",
            "risk_description": "Windscreen damage from bird strike affecting visibility",
            "likelihood": 3, "severity": "C", "risk_index": "3C", "tolerance": "TOLERABLE",
            "residual_likelihood": 2, "residual_severity": "D",
            "residual_risk_index": "2D", "residual_tolerance": "ACCEPTABLE",
            "created_at": week_ago
        },
        {
            "id": "RSK-2025-003", "hazard_id": "HAZ-2025-BB3C4D",
            "risk_description": "Hydraulic failure on landing causing runway excursion",
            "likelihood": 2, "severity": "A", "risk_index": "2A", "tolerance": "TOLERABLE",
            "residual_likelihood": 1, "residual_severity": "C",
            "residual_risk_index": "1C", "residual_tolerance": "ACCEPTABLE",
            "created_at": month_ago
        },
        {
            "id": "RSK-2025-004", "hazard_id": "HAZ-2025-INT001",
            "risk_description": "CFIT event in mountainous terrain during IMC approach",
            "likelihood": 3, "severity": "A", "risk_index": "3A", "tolerance": "INTOLERABLE",
            "residual_likelihood": None, "residual_severity": None,
            "residual_risk_index": None, "residual_tolerance": None,
            "created_at": yesterday
        },
    ]

    # Sample controls
    DB["controls"] = [
        {
            "id": "CTL-001", "risk_id": "RSK-2025-001", "hazard_id": "HAZ-2025-AA1B2C",
            "type": "Preventive", "description": "Wildlife management programme at OJAI",
            "effectiveness": "Effective", "owner": "Ground Ops Manager", "created_at": week_ago
        },
        {
            "id": "CTL-002", "risk_id": "RSK-2025-001", "hazard_id": "HAZ-2025-AA1B2C",
            "type": "Detective", "description": "Bird radar system — active monitoring during approach",
            "effectiveness": "Partially Effective", "owner": "ATC Liaison", "created_at": week_ago
        },
        {
            "id": "CTL-003", "risk_id": "RSK-2025-003", "hazard_id": "HAZ-2025-BB3C4D",
            "type": "Preventive", "description": "Pre-flight hydraulic system check (AMM 29-00)",
            "effectiveness": "Effective", "owner": "Chief Engineer", "created_at": month_ago
        },
    ]

    # Sample actions
    overdue_date = (datetime.utcnow() - timedelta(days=5)).strftime("%Y-%m-%d")
    future_date  = (datetime.utcnow() + timedelta(days=14)).strftime("%Y-%m-%d")
    DB["actions"] = [
        {
            "id": "ACT-2025-001", "source": "Hazard", "linked_id": "HAZ-2025-AA1B2C",
            "description": "Commission enhanced bird radar system at OJAI — Gate B approaches",
            "owner": "Ground Operations Manager", "due_date": overdue_date,
            "priority": "High", "status": "Overdue",
            "effectiveness_review": "", "created_at": month_ago
        },
        {
            "id": "ACT-2025-002", "source": "Hazard", "linked_id": "HAZ-2025-BB3C4D",
            "description": "Replace hydraulic seals on all B737 aircraft per engineering order EO-2025-045",
            "owner": "Chief Engineer", "due_date": future_date,
            "priority": "Critical", "status": "In Progress",
            "effectiveness_review": "", "created_at": month_ago
        },
        {
            "id": "ACT-2025-003", "source": "ASR", "linked_id": "ASR-2025-EMG01",
            "description": "Revise approach briefing SOP for HESH — add mandatory terrain check",
            "owner": "Chief Pilot", "due_date": future_date,
            "priority": "Critical", "status": "Open",
            "effectiveness_review": "", "created_at": yesterday
        },
        {
            "id": "ACT-2025-004", "source": "Audit", "linked_id": "HAZ-2025-CC7D8E",
            "description": "Increase FOD walk frequency at Gate B3 to 3x daily",
            "owner": "Ground Operations Supervisor", "due_date": overdue_date,
            "priority": "Medium", "status": "Closed",
            "effectiveness_review": "FOD incidents reduced to zero after increased frequency.",
            "created_at": month_ago
        },
    ]

    # Sample audits
    DB["audits"] = [
        {
            "id": "AUD-2025-001", "type": "Internal", "title": "Flight Operations Q1 Audit",
            "department_id": 1, "planned_date": "2025-03-15", "actual_date": "2025-03-16",
            "lead_auditor": "Safety Manager", "status": "Closed",
            "scope": "Review of approach procedures, FOQA programme and crew briefing standards",
            "created_at": month_ago
        },
        {
            "id": "AUD-2025-002", "type": "IOSA", "title": "IOSA Audit 2025 — Ground Operations",
            "department_id": 3, "planned_date": "2025-06-10", "actual_date": None,
            "lead_auditor": "IOSA Team Leader", "status": "Planned",
            "scope": "Full IOSA audit of Ground Operations per ISM 7th Edition",
            "created_at": week_ago
        },
    ]

    DB["audit_findings"] = [
        {
            "id": "FND-2025-001", "audit_id": "AUD-2025-001",
            "description": "Approach briefing checklist does not include terrain awareness check for Category C aerodromes",
            "severity": "Major", "root_cause": "Procedure gap — SOP not updated after network expansion",
            "corrective_action": "Revise Approach Briefing SOP — include terrain check item",
            "linked_hazard_id": "HAZ-2025-INT001", "linked_action_id": "ACT-2025-003",
            "status": "Open", "created_at": month_ago
        },
        {
            "id": "FND-2025-002", "audit_id": "AUD-2025-001",
            "description": "FOD inspection log at Gate B3 not completed on 3 of 7 days reviewed",
            "severity": "Minor", "root_cause": "Staff workload during peak operations",
            "corrective_action": "Increase FOD walk frequency and assign dedicated ramp safety officer",
            "linked_hazard_id": "HAZ-2025-CC7D8E", "linked_action_id": "ACT-2025-004",
            "status": "Closed", "created_at": month_ago
        },
    ]

    # Sample investigations
    DB["investigations"] = [
        {
            "id": "INV-2025-001", "title": "GPWS Alert — HESH Approach 14 Jan 2025",
            "linked_hazard_id": "HAZ-2025-INT001", "linked_asr_id": "ASR-2025-EMG01",
            "date_of_event": "2025-01-14", "investigator": "Safety Manager",
            "status": "In Progress",
            "event_description": "During ILS approach to HESH RWY 34, crew received GPWS PULL UP warning at 900ft AAL. Aircraft executed immediate go-around. Investigation initiated.",
            "contributing_factors": {
                "human": "Crew fatigue — early morning departure. Approach briefing incomplete.",
                "technical": "Altimeter cross-check not performed as per SOP.",
                "organizational": "SOP for Cat C aerodrome approach not updated.",
                "environmental": "IMC conditions, low visibility, mountainous terrain."
            },
            "why_analysis": [
                "Why 1: Aircraft descended below MDA — crew did not cross-check altimeters",
                "Why 2: Approach briefing was abbreviated due to ATC hold",
                "Why 3: SOP does not mandate altimeter cross-check at specific fix",
                "Why 4: SOP was not reviewed when Cat C aerodromes added to network",
                "Why 5: Change management process did not trigger SOP review"
            ],
            "recommendations": "1. Revise approach SOP. 2. Mandatory altimeter cross-check at FAF. 3. MOC process review.",
            "created_at": yesterday
        }
    ]

    # Sample MOC
    DB["moc"] = [
        {
            "id": "MOC-2025-001",
            "title": "Introduction of New Aerodrome: HESH (Sharm El Sheikh)",
            "description": "Addition of HESH to the Jordan Aviation route network. Cat C aerodrome with mountainous terrain.",
            "affected_departments": [1, 3],
            "change_type": "Operational",
            "initiated_by": "Network Planning Manager",
            "pre_change_risk": "3B — terrain awareness risk for flight crew unfamiliar with HESH procedures",
            "approval_status": "Approved",
            "approved_by": "Accountable Manager",
            "implementation_date": "2025-01-10",
            "post_change_review": "GPWS alert occurred on 3rd flight — investigation opened",
            "linked_hazard_id": "HAZ-2025-INT001",
            "status": "Under Review",
            "created_at": month_ago
        },
        {
            "id": "MOC-2025-002",
            "title": "Fleet Upgrade: Installation of Bird Radar System",
            "description": "Installation of HALO bird-radar at OJAI main runway approaches",
            "affected_departments": [1, 3],
            "change_type": "Technical",
            "initiated_by": "Safety Manager",
            "pre_change_risk": "2C — minimal operational risk during installation downtime",
            "approval_status": "Pending",
            "approved_by": None,
            "implementation_date": None,
            "post_change_review": None,
            "linked_hazard_id": "HAZ-2025-AA1B2C",
            "status": "Pending Approval",
            "created_at": week_ago
        },
    ]

    # Sample training records
    DB["training_records"] = [
        {"id":"TRN-001","employee":"Capt. Ahmad Al-Hassan","staff_no":"410","department_id":1,"training_type":"CRM","completion_status":"Completed","completion_date":"2025-02-15","expiry_date":"2026-02-15","created_at":month_ago},
        {"id":"TRN-002","employee":"F/O Sara Khalil","staff_no":"425","department_id":1,"training_type":"ATPL Recurrency","completion_status":"Completed","completion_date":"2025-01-20","expiry_date":"2026-01-20","created_at":month_ago},
        {"id":"TRN-003","employee":"Eng. Tariq Nabulsi","staff_no":"203","department_id":2,"training_type":"Safety Management","completion_status":"In Progress","completion_date":None,"expiry_date":None,"created_at":week_ago},
        {"id":"TRN-004","employee":"Ramp Supervisor Hana","staff_no":"301","department_id":3,"training_type":"FOD Awareness","completion_status":"Overdue","completion_date":None,"expiry_date":None,"created_at":month_ago},
    ]

    # Sample safety bulletins
    DB["safety_bulletins"] = [
        {"id":"SB-2025-001","type":"Safety Alert","title":"GPWS Alert — HESH Approach","content":"A GPWS PULL UP warning was triggered during approach to HESH. All crews operating to Cat C aerodromes must review enhanced approach briefing procedures.","department_ids":[1],"issued_by":"Safety Manager","date":"2025-01-15","created_at":month_ago},
        {"id":"SB-2025-002","type":"Safety Bulletin","title":"FOD Awareness — Ramp Gate B3","content":"Increased FOD incidents detected at Gate B3. All ground staff must complete FOD walk before each aircraft movement.","department_ids":[3],"issued_by":"Ground Safety Officer","date":"2025-02-01","created_at":month_ago},
        {"id":"SB-2025-003","type":"Newsletter","title":"SMS Monthly Newsletter — March 2025","content":"This month: Q1 Audit results, new bird radar initiative, updated SPI targets for 2025, and training completion rates.","department_ids":[1,2,3,4,5,6,7,8],"issued_by":"Safety Department","date":"2025-03-01","created_at":week_ago},
    ]

seed()

# ─── Helpers ─────────────────────────────────────────────────────────────────
INTOLERABLE = {"5A","5B","5C","4A","4B","3A"}
TOLERABLE   = {"5D","5E","4C","4D","4E","3B","3C","3D","2A","2B","2C","1A"}

def get_tolerance(risk_index):
    if not risk_index: return None
    if risk_index in INTOLERABLE: return "INTOLERABLE"
    if risk_index in TOLERABLE:   return "TOLERABLE"
    return "ACCEPTABLE"

def new_id(prefix):
    year = datetime.now().year
    short = str(uuid.uuid4())[:6].upper()
    return f"{prefix}-{year}-{short}"

def dept_name(dept_id):
    d = next((x for x in DB["departments"] if x["id"] == int(dept_id or 0)), None)
    return d["name"] if d else "—"

def dept_code(dept_id):
    d = next((x for x in DB["departments"] if x["id"] == int(dept_id or 0)), None)
    return d["code"] if d else "—"

def auto_update_overdue():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    for a in DB["actions"]:
        if a["status"] not in ("Closed",) and a["due_date"] and a["due_date"] < today:
            a["status"] = "Overdue"

@app.context_processor
def inject_globals():
    auto_update_overdue()
    return {"now": datetime.utcnow(), "enumerate": enumerate, "dept_code": dept_code}

# ─── Dashboard ────────────────────────────────────────────────────────────────
@app.route("/")
def dashboard():
    auto_update_overdue()
    total    = len(DB["hazards"])
    open_h   = sum(1 for h in DB["hazards"] if h["status"] == "Open")
    intol    = sum(1 for h in DB["hazards"] if h["initial_risk_tolerance"] == "INTOLERABLE")
    asr_cnt  = len(DB["asr_reports"])
    hr_cnt   = len(DB["hazard_reports"])
    actions  = DB["actions"]
    overdue  = sum(1 for a in actions if a["status"] == "Overdue")
    open_act = sum(1 for a in actions if a["status"] in ("Open","In Progress","Overdue"))
    audits   = len(DB["audits"])
    moc_cnt  = len(DB["moc"])
    inv_cnt  = len(DB["investigations"])

    recent   = sorted(DB["hazards"], key=lambda x: x["created_at"], reverse=True)[:8]
    recent_actions = sorted(DB["actions"], key=lambda x: x["created_at"], reverse=True)[:5]

    # SPI status counts
    spi_critical = 0; spi_warning = 0
    cur_year = datetime.now().year
    for ind in DB["spi_indicators"]:
        rates = [d["rate"] for d in DB["spi_data"] if d["spi_id"]==ind["id"] and d["year"]==cur_year]
        if rates:
            ytd = sum(rates)/len(rates)
            if ytd >= ind["alert_l2"]: spi_critical += 1
            elif ytd >= ind["alert_l1"]: spi_warning += 1

    return render_template("dashboard.html",
        total=total, open_h=open_h, intol=intol,
        asr_cnt=asr_cnt, hr_cnt=hr_cnt,
        overdue=overdue, open_act=open_act,
        audits=audits, moc_cnt=moc_cnt, inv_cnt=inv_cnt,
        spi_critical=spi_critical, spi_warning=spi_warning,
        recent=recent, recent_actions=recent_actions,
        dept_name=dept_name, dept_code=dept_code,
        get_tolerance=get_tolerance)

# ─── Hazard Report ────────────────────────────────────────────────────────────
@app.route("/hazard-report", methods=["GET","POST"])
def hazard_report():
    if request.method == "POST":
        f = request.form
        dept_id    = int(f["department_id"])
        likelihood = int(f["likelihood"])
        severity   = f["severity"]
        risk_index = f"{likelihood}{severity}"
        tolerance  = get_tolerance(risk_index)
        haz_id     = new_id("HAZ")
        rep_id     = new_id("HR")
        now        = datetime.utcnow().isoformat() + "Z"

        hazard = {
            "id": haz_id, "source": "Hazard Report",
            "linked_report_id": rep_id, "department_id": dept_id,
            "type_of_activity": dept_name(dept_id),
            "classification": f.get("classification", "Operational"),
            "generic_hazard": f.get("generic_hazard") or f["hazard_description"][:60],
            "specific_components": f["hazard_description"],
            "consequences": f.get("consequences","To Be Assessed"),
            "initial_likelihood": likelihood, "initial_severity": severity,
            "initial_risk_index": risk_index, "initial_risk_tolerance": tolerance,
            "current_defenses": f.get("immediate_action",""),
            "further_mitigations": f.get("suggested_mitigation",""),
            "residual_likelihood": None, "residual_severity": None,
            "residual_risk_index": None, "residual_risk_tolerance": None,
            "status": "Open", "owner": f.get("owner") or None, "created_at": now
        }
        report = {
            "id": rep_id, "department_id": dept_id,
            "location": f["location"], "date": f["date"],
            "hazard_description": f["hazard_description"],
            "immediate_action": f.get("immediate_action",""),
            "suggested_mitigation": f.get("suggested_mitigation",""),
            "severity": severity, "likelihood": likelihood,
            "risk_index": risk_index,
            "reporter": f.get("reporter","Anonymous") or "Anonymous",
            "hazard_id": haz_id, "created_at": now
        }
        DB["hazards"].append(hazard)
        DB["hazard_reports"].append(report)

        # Auto-create action if intolerable
        if tolerance == "INTOLERABLE":
            act_id = new_id("ACT")
            due = (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%d")
            DB["actions"].append({
                "id": act_id, "source": "Hazard", "linked_id": haz_id,
                "description": f"IMMEDIATE: Assess and mitigate intolerable risk — {hazard['generic_hazard']}",
                "owner": hazard.get("owner") or "Safety Manager",
                "due_date": due, "priority": "Critical", "status": "Open",
                "effectiveness_review": "", "created_at": now
            })

        flash(f"✓ Hazard Report {rep_id} submitted. Hazard: {haz_id} | Risk: {risk_index} — {tolerance}", "success")
        return redirect(url_for("hazard_report"))

    return render_template("hazard_report.html", departments=DB["departments"])

# ─── ASR ─────────────────────────────────────────────────────────────────────
@app.route("/asr", methods=["GET","POST"])
def asr():
    if request.method == "POST":
        f = request.form
        likelihood = int(f.get("likelihood", 3))
        severity   = f.get("severity", "C")
        risk_index = f"{likelihood}{severity}"
        tolerance  = get_tolerance(risk_index)
        haz_id     = new_id("HAZ")
        asr_id     = new_id("ASR")
        now        = datetime.utcnow().isoformat() + "Z"

        hazard = {
            "id": haz_id, "source": "ASR",
            "linked_report_id": asr_id, "department_id": 1,
            "type_of_activity": "Flight Operations",
            "classification": "Operational",
            "generic_hazard": f.get("occurrence_type",""),
            "specific_components": f.get("event_description",""),
            "consequences": "To Be Assessed by Safety Department",
            "initial_likelihood": likelihood, "initial_severity": severity,
            "initial_risk_index": risk_index, "initial_risk_tolerance": tolerance,
            "current_defenses": f.get("action_taken",""),
            "further_mitigations": "",
            "residual_likelihood": None, "residual_severity": None,
            "residual_risk_index": None, "residual_risk_tolerance": None,
            "status": "Open", "owner": "Flight Operations Manager", "created_at": now
        }
        asr_rec = dict(f)
        asr_rec.update({"id": asr_id, "hazard_id": haz_id,
                        "department_id": 1, "created_at": now,
                        "likelihood": likelihood, "severity": severity,
                        "risk_index": risk_index})
        DB["hazards"].append(hazard)
        DB["asr_reports"].append(asr_rec)

        if tolerance == "INTOLERABLE":
            act_id = new_id("ACT")
            due = (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%d")
            DB["actions"].append({
                "id": act_id, "source": "ASR", "linked_id": asr_id,
                "description": f"IMMEDIATE: Review intolerable ASR — {f.get('occurrence_type','')} on {f.get('flight_no','')}",
                "owner": "Chief Pilot", "due_date": due,
                "priority": "Critical", "status": "Open",
                "effectiveness_review": "", "created_at": now
            })

        flash(f"✓ ASR {asr_id} submitted. Hazard: {haz_id} | Risk: {risk_index} — {tolerance}", "success")
        return redirect(url_for("asr"))

    return render_template("asr.html")

# ─── Hazard Log ───────────────────────────────────────────────────────────────
@app.route("/hazard-log")
def hazard_log():
    dept_filter = request.args.get("dept","")
    status_f    = request.args.get("status","")
    tol_f       = request.args.get("tolerance","")
    class_f     = request.args.get("classification","")

    hazards = list(DB["hazards"])
    if dept_filter:     hazards = [h for h in hazards if str(h["department_id"]) == dept_filter]
    if status_f:        hazards = [h for h in hazards if h["status"] == status_f]
    if tol_f:           hazards = [h for h in hazards if h["initial_risk_tolerance"] == tol_f]
    if class_f:         hazards = [h for h in hazards if h.get("classification","") == class_f]
    hazards = sorted(hazards, key=lambda x: x["created_at"], reverse=True)

    return render_template("hazard_log.html",
        hazards=hazards, departments=DB["departments"],
        dept_name=dept_name, dept_code=dept_code,
        dept_filter=dept_filter, status_f=status_f, tol_f=tol_f, class_f=class_f)

@app.route("/hazard-log/<haz_id>")
def hazard_detail(haz_id):
    h = next((x for x in DB["hazards"] if x["id"] == haz_id), None)
    if not h: return "Not found", 404
    risks    = [r for r in DB["risks"]    if r["hazard_id"] == haz_id]
    controls = [c for c in DB["controls"] if c["hazard_id"] == haz_id]
    actions  = [a for a in DB["actions"]  if a["linked_id"] == haz_id]
    return render_template("hazard_detail.html", h=h,
        risks=risks, controls=controls, actions=actions,
        dept_name=dept_name, get_tolerance=get_tolerance)

@app.route("/hazard-log/<haz_id>/update", methods=["POST"])
def hazard_update(haz_id):
    h = next((x for x in DB["hazards"] if x["id"] == haz_id), None)
    if not h: return "Not found", 404
    f = request.form
    h["status"]  = f.get("status", h["status"])
    h["owner"]   = f.get("owner", h["owner"])
    h["further_mitigations"] = f.get("further_mitigations", h["further_mitigations"])
    rl = f.get("residual_likelihood","")
    rs = f.get("residual_severity","")
    if rl and rs:
        h["residual_likelihood"] = int(rl)
        h["residual_severity"]   = rs
        ri = f"{rl}{rs}"
        h["residual_risk_index"]     = ri
        h["residual_risk_tolerance"] = get_tolerance(ri)
    flash("✓ Hazard updated.", "success")
    return redirect(url_for("hazard_detail", haz_id=haz_id))

# ─── Risk Register ────────────────────────────────────────────────────────────
@app.route("/risks")
def risk_register():
    dept_filter = request.args.get("dept","")
    tol_f       = request.args.get("tolerance","")
    risks = []
    for r in DB["risks"]:
        h = next((x for x in DB["hazards"] if x["id"]==r["hazard_id"]), {})
        if dept_filter and str(h.get("department_id","")) != dept_filter: continue
        if tol_f and r.get("tolerance","") != tol_f: continue
        ctrls = [c for c in DB["controls"] if c["risk_id"]==r["id"]]
        risks.append({"risk":r,"hazard":h,"controls":ctrls})
    risks.sort(key=lambda x: x["risk"]["created_at"], reverse=True)
    return render_template("risk_register.html", risks=risks,
        departments=DB["departments"], dept_filter=dept_filter, tol_f=tol_f,
        get_tolerance=get_tolerance)

@app.route("/risks/add", methods=["POST"])
def add_risk():
    f = request.form
    hazard_id = f["hazard_id"]
    likelihood = int(f["likelihood"])
    severity   = f["severity"]
    risk_index = f"{likelihood}{severity}"
    now = datetime.utcnow().isoformat() + "Z"
    DB["risks"].append({
        "id": new_id("RSK"), "hazard_id": hazard_id,
        "risk_description": f["risk_description"],
        "likelihood": likelihood, "severity": severity,
        "risk_index": risk_index, "tolerance": get_tolerance(risk_index),
        "residual_likelihood": None, "residual_severity": None,
        "residual_risk_index": None, "residual_tolerance": None,
        "created_at": now
    })
    flash("✓ Risk added.", "success")
    return redirect(url_for("hazard_detail", haz_id=hazard_id))

@app.route("/controls/add", methods=["POST"])
def add_control():
    f = request.form
    now = datetime.utcnow().isoformat() + "Z"
    DB["controls"].append({
        "id": new_id("CTL"), "risk_id": f["risk_id"], "hazard_id": f["hazard_id"],
        "type": f["type"], "description": f["description"],
        "effectiveness": f.get("effectiveness","Effective"),
        "owner": f.get("owner",""), "created_at": now
    })
    flash("✓ Control measure added.", "success")
    return redirect(url_for("hazard_detail", haz_id=f["hazard_id"]))

# ─── Actions ─────────────────────────────────────────────────────────────────
@app.route("/actions")
def actions():
    auto_update_overdue()
    status_f   = request.args.get("status","")
    priority_f = request.args.get("priority","")
    source_f   = request.args.get("source","")
    acts = list(DB["actions"])
    if status_f:   acts = [a for a in acts if a["status"] == status_f]
    if priority_f: acts = [a for a in acts if a["priority"] == priority_f]
    if source_f:   acts = [a for a in acts if a["source"] == source_f]
    acts.sort(key=lambda x: x["created_at"], reverse=True)
    counts = {
        "total": len(DB["actions"]),
        "open": sum(1 for a in DB["actions"] if a["status"]=="Open"),
        "in_progress": sum(1 for a in DB["actions"] if a["status"]=="In Progress"),
        "overdue": sum(1 for a in DB["actions"] if a["status"]=="Overdue"),
        "closed": sum(1 for a in DB["actions"] if a["status"]=="Closed"),
    }
    return render_template("actions.html", actions=acts, counts=counts,
        status_f=status_f, priority_f=priority_f, source_f=source_f)

@app.route("/actions/add", methods=["POST"])
def add_action():
    f = request.form
    now = datetime.utcnow().isoformat() + "Z"
    DB["actions"].append({
        "id": new_id("ACT"), "source": f.get("source","Manual"),
        "linked_id": f.get("linked_id",""),
        "description": f["description"], "owner": f["owner"],
        "due_date": f["due_date"], "priority": f.get("priority","Medium"),
        "status": "Open", "effectiveness_review": "", "created_at": now
    })
    flash("✓ Action created.", "success")
    return redirect(url_for("actions"))

@app.route("/actions/<act_id>/update", methods=["POST"])
def update_action(act_id):
    a = next((x for x in DB["actions"] if x["id"]==act_id), None)
    if not a: return "Not found", 404
    f = request.form
    a["status"]               = f.get("status", a["status"])
    a["owner"]                = f.get("owner", a["owner"])
    a["due_date"]             = f.get("due_date", a["due_date"])
    a["effectiveness_review"] = f.get("effectiveness_review", a["effectiveness_review"])
    flash("✓ Action updated.", "success")
    return redirect(url_for("actions"))

# ─── Audits ───────────────────────────────────────────────────────────────────
@app.route("/audits")
def audits():
    return render_template("audits.html",
        audits=DB["audits"], findings=DB["audit_findings"],
        departments=DB["departments"], dept_name=dept_name)

@app.route("/audits/add", methods=["POST"])
def add_audit():
    f = request.form
    now = datetime.utcnow().isoformat() + "Z"
    DB["audits"].append({
        "id": new_id("AUD"), "type": f.get("type","Internal"),
        "title": f["title"], "department_id": int(f["department_id"]),
        "planned_date": f["planned_date"], "actual_date": None,
        "lead_auditor": f["lead_auditor"], "status": "Planned",
        "scope": f.get("scope",""), "created_at": now
    })
    flash("✓ Audit scheduled.", "success")
    return redirect(url_for("audits"))

@app.route("/audits/finding/add", methods=["POST"])
def add_finding():
    f = request.form
    now = datetime.utcnow().isoformat() + "Z"
    fnd_id = new_id("FND")
    # Auto-create hazard from finding
    likelihood = int(f.get("likelihood",3))
    severity   = f.get("severity_risk","C")
    if severity in ["Catastrophic","Major","Minor","Negligible"]:
        sev_map = {"Catastrophic":"A","Major":"C","Minor":"D","Negligible":"E"}
        severity = sev_map.get(severity,"C")
    risk_index = f"{likelihood}{severity}"
    haz_id = new_id("HAZ")
    haz_now = now
    dept_id = int(f.get("department_id",5))
    DB["hazards"].append({
        "id": haz_id, "source": "Audit",
        "linked_report_id": fnd_id, "department_id": dept_id,
        "type_of_activity": dept_name(dept_id),
        "classification": "Organizational",
        "generic_hazard": f["description"][:80],
        "specific_components": f["description"],
        "consequences": f.get("root_cause","To Be Assessed"),
        "initial_likelihood": likelihood, "initial_severity": severity,
        "initial_risk_index": risk_index,
        "initial_risk_tolerance": get_tolerance(risk_index),
        "current_defenses": "", "further_mitigations": f.get("corrective_action",""),
        "residual_likelihood": None, "residual_severity": None,
        "residual_risk_index": None, "residual_risk_tolerance": None,
        "status": "Open", "owner": None, "created_at": haz_now
    })
    act_id = new_id("ACT")
    due = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")
    DB["actions"].append({
        "id": act_id, "source": "Audit", "linked_id": fnd_id,
        "description": f.get("corrective_action","Address audit finding: "+f["description"][:60]),
        "owner": f.get("responsible","Safety Manager"),
        "due_date": due, "priority": f.get("severity","Minor"),
        "status": "Open", "effectiveness_review": "", "created_at": now
    })
    DB["audit_findings"].append({
        "id": fnd_id, "audit_id": f["audit_id"],
        "description": f["description"],
        "severity": f.get("severity","Minor"),
        "root_cause": f.get("root_cause",""),
        "corrective_action": f.get("corrective_action",""),
        "linked_hazard_id": haz_id, "linked_action_id": act_id,
        "status": "Open", "created_at": now
    })
    flash(f"✓ Finding {fnd_id} added. Hazard {haz_id} and Action {act_id} auto-created.", "success")
    return redirect(url_for("audits"))

# ─── Investigations ────────────────────────────────────────────────────────────
@app.route("/investigations")
def investigations():
    return render_template("investigations.html",
        investigations=DB["investigations"], hazards=DB["hazards"])

@app.route("/investigations/add", methods=["POST"])
def add_investigation():
    f = request.form
    now = datetime.utcnow().isoformat() + "Z"
    DB["investigations"].append({
        "id": new_id("INV"), "title": f["title"],
        "linked_hazard_id": f.get("linked_hazard_id",""),
        "linked_asr_id": f.get("linked_asr_id",""),
        "date_of_event": f["date_of_event"], "investigator": f["investigator"],
        "status": "Open",
        "event_description": f["event_description"],
        "contributing_factors": {
            "human": f.get("cf_human",""),
            "technical": f.get("cf_technical",""),
            "organizational": f.get("cf_organizational",""),
            "environmental": f.get("cf_environmental",""),
        },
        "why_analysis": [x.strip() for x in f.get("why_analysis","").split("\n") if x.strip()],
        "recommendations": f.get("recommendations",""),
        "created_at": now
    })
    flash("✓ Investigation opened.", "success")
    return redirect(url_for("investigations"))

@app.route("/investigations/<inv_id>")
def investigation_detail(inv_id):
    inv = next((x for x in DB["investigations"] if x["id"]==inv_id), None)
    if not inv: return "Not found", 404
    linked_hazard = next((h for h in DB["hazards"] if h["id"]==inv.get("linked_hazard_id")), None)
    return render_template("investigation_detail.html", inv=inv, linked_hazard=linked_hazard)

# ─── MOC ──────────────────────────────────────────────────────────────────────
@app.route("/moc")
def moc():
    return render_template("moc.html",
        moc_list=DB["moc"], departments=DB["departments"], dept_name=dept_name,
        hazards=DB["hazards"])

@app.route("/moc/add", methods=["POST"])
def add_moc():
    f = request.form
    now = datetime.utcnow().isoformat() + "Z"
    dept_ids = [int(x) for x in f.getlist("affected_departments")]
    # Auto-create a risk/hazard entry
    haz_id = new_id("HAZ")
    moc_id = new_id("MOC")
    DB["hazards"].append({
        "id": haz_id, "source": "MOC", "linked_report_id": moc_id,
        "department_id": dept_ids[0] if dept_ids else 5,
        "type_of_activity": "Management of Change",
        "classification": "Organizational",
        "generic_hazard": f"MOC Risk: {f['title'][:60]}",
        "specific_components": f.get("description",""),
        "consequences": "To Be Assessed",
        "initial_likelihood": 2, "initial_severity": "C",
        "initial_risk_index": "2C", "initial_risk_tolerance": "TOLERABLE",
        "current_defenses": "", "further_mitigations": "",
        "residual_likelihood": None, "residual_severity": None,
        "residual_risk_index": None, "residual_risk_tolerance": None,
        "status": "Open", "owner": f.get("initiated_by",""), "created_at": now
    })
    DB["moc"].append({
        "id": moc_id, "title": f["title"], "description": f.get("description",""),
        "affected_departments": dept_ids,
        "change_type": f.get("change_type","Operational"),
        "initiated_by": f.get("initiated_by",""),
        "pre_change_risk": f.get("pre_change_risk",""),
        "approval_status": "Pending",
        "approved_by": None, "implementation_date": None,
        "post_change_review": None,
        "linked_hazard_id": haz_id,
        "status": "Pending Approval", "created_at": now
    })
    flash(f"✓ MOC {moc_id} created. Hazard {haz_id} auto-created for risk tracking.", "success")
    return redirect(url_for("moc"))

@app.route("/moc/<moc_id>/approve", methods=["POST"])
def approve_moc(moc_id):
    m = next((x for x in DB["moc"] if x["id"]==moc_id), None)
    if not m: return "Not found", 404
    m["approval_status"] = "Approved"
    m["approved_by"] = request.form.get("approved_by","Accountable Manager")
    m["implementation_date"] = request.form.get("implementation_date","")
    m["status"] = "Approved"
    flash("✓ MOC approved.", "success")
    return redirect(url_for("moc"))

# ─── SPI ──────────────────────────────────────────────────────────────────────
@app.route("/spi", methods=["GET","POST"])
def spi():
    if request.method == "POST":
        f = request.form
        spi_id  = int(f["spi_id"])
        year    = int(f["year"])
        month   = int(f["month"])
        events  = int(f["events"])
        flights = int(f["flights"])
        rate    = round((events / flights * 1000), 4) if flights > 0 else 0
        DB["spi_data"].append({"spi_id": spi_id, "year": year,
                               "month": month, "events": events,
                               "flights": flights, "rate": rate})
        flash("✓ SPI data logged.", "success")
        return redirect(url_for("spi"))

    dept_filter = request.args.get("dept","")
    indicators  = DB["spi_indicators"]
    if dept_filter:
        indicators = [i for i in indicators if int(dept_filter) in i["department_ids"]]

    MONTHS   = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    cur_year = datetime.now().year
    table = []
    for ind in indicators:
        month_rates = {}
        for d in DB["spi_data"]:
            if d["spi_id"] == ind["id"] and d["year"] == cur_year:
                month_rates[d["month"]] = d["rate"]
        ytd = round(sum(month_rates.values()) / len(month_rates), 2) if month_rates else 0
        if ytd >= ind["alert_l2"]:    status = ("🔴 CRITICAL","#dc2626")
        elif ytd >= ind["alert_l1"]:  status = ("🟡 WARNING","#d97706")
        elif ytd > ind["spt_target"]: status = ("🟠 WATCH","#ea580c")
        else:                         status = ("🟢 OK","#16a34a")
        depts = [x["code"] for x in DB["departments"] if x["id"] in ind["department_ids"]]
        table.append({"ind": ind, "month_rates": month_rates, "ytd": ytd,
                      "status": status, "depts": ", ".join(depts)})

    return render_template("spi.html", table=table, MONTHS=MONTHS,
        indicators=DB["spi_indicators"], departments=DB["departments"],
        dept_filter=dept_filter, cur_year=cur_year)

# ─── Risk Matrix ──────────────────────────────────────────────────────────────
@app.route("/risk-matrix")
def risk_matrix():
    return render_template("risk_matrix.html", get_tolerance=get_tolerance)

# ─── Safety Promotion ─────────────────────────────────────────────────────────
@app.route("/safety-promotion")
def safety_promotion():
    return render_template("safety_promotion.html",
        training=DB["training_records"],
        bulletins=DB["safety_bulletins"],
        departments=DB["departments"], dept_name=dept_name)

@app.route("/safety-promotion/training/add", methods=["POST"])
def add_training():
    f = request.form
    now = datetime.utcnow().isoformat() + "Z"
    DB["training_records"].append({
        "id": new_id("TRN"),
        "employee": f["employee"], "staff_no": f.get("staff_no",""),
        "department_id": int(f["department_id"]),
        "training_type": f["training_type"],
        "completion_status": f.get("completion_status","In Progress"),
        "completion_date": f.get("completion_date") or None,
        "expiry_date": f.get("expiry_date") or None,
        "created_at": now
    })
    flash("✓ Training record added.", "success")
    return redirect(url_for("safety_promotion"))

@app.route("/safety-promotion/bulletin/add", methods=["POST"])
def add_bulletin():
    f = request.form
    now = datetime.utcnow().isoformat() + "Z"
    dept_ids = [int(x) for x in f.getlist("department_ids")] or list(range(1,9))
    DB["safety_bulletins"].append({
        "id": new_id("SB"),
        "type": f.get("type","Safety Bulletin"),
        "title": f["title"], "content": f["content"],
        "department_ids": dept_ids,
        "issued_by": f.get("issued_by","Safety Department"),
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "created_at": now
    })
    flash("✓ Bulletin published.", "success")
    return redirect(url_for("safety_promotion"))

# ─── API endpoints (JSON) ─────────────────────────────────────────────────────
@app.route("/api/hazards")
def api_hazards():
    return jsonify(DB["hazards"])

@app.route("/api/actions")
def api_actions():
    return jsonify(DB["actions"])

@app.route("/api/spi-data")
def api_spi_data():
    return jsonify(DB["spi_data"])

if __name__ == "__main__":
    app.run(debug=True, port=5000)
