from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import json, os, uuid
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "jav-sms-secret-2024")

@app.context_processor
def inject_globals():
    return {"now": datetime.utcnow(), "enumerate": enumerate}

# ─── Load seed data ───────────────────────────────────────────────────────────
DB = {
  "departments": [
    {
      "id": 1,
      "code": "FO",
      "name": "Flight Operations",
      "color": "#1e40af"
    },
    {
      "id": 2,
      "code": "ME",
      "name": "Maintenance / Engineering",
      "color": "#065f46"
    },
    {
      "id": 3,
      "code": "GO",
      "name": "Ground Operations",
      "color": "#92400e"
    },
    {
      "id": 4,
      "code": "CC",
      "name": "Cabin Crew",
      "color": "#6b21a8"
    },
    {
      "id": 5,
      "code": "SD",
      "name": "Safety Department",
      "color": "#be123c"
    }
  ],
  "risk_matrix": {
    "likelihood": [
      {
        "value": 5,
        "label": "Frequent",
        "description": "Likely to occur many times (has occurred frequently)"
      },
      {
        "value": 4,
        "label": "Occasional",
        "description": "Likely to occur sometimes (has occurred infrequently)"
      },
      {
        "value": 3,
        "label": "Remote",
        "description": "Unlikely to occur, but possible (has occurred rarely)"
      },
      {
        "value": 2,
        "label": "Improbable",
        "description": "Very unlikely to occur (not known to have occurred)"
      },
      {
        "value": 1,
        "label": "Extremely Improbable",
        "description": "Almost inconceivable that the event will occur"
      }
    ],
    "severity": [
      {
        "value": "A",
        "label": "Catastrophic",
        "description": "Aircraft/equipment destroyed. Multiple deaths."
      },
      {
        "value": "B",
        "label": "Hazardous",
        "description": "Large reduction in safety margins. Serious injury. Major equipment damage."
      },
      {
        "value": "C",
        "label": "Major",
        "description": "Significant reduction in safety margins. Serious incident. Injury to persons."
      },
      {
        "value": "D",
        "label": "Minor",
        "description": "Nuisance. Operating limitations. Use of emergency procedures. Minor incident."
      },
      {
        "value": "E",
        "label": "Negligible",
        "description": "Few consequences."
      }
    ],
    "tolerance": {
      "INTOLERABLE": [
        "5A",
        "5B",
        "5C",
        "4A",
        "4B",
        "3A"
      ],
      "TOLERABLE": [
        "5D",
        "5E",
        "4C",
        "4D",
        "4E",
        "3B",
        "3C",
        "3D",
        "2A",
        "2B",
        "2C",
        "1A"
      ],
      "ACCEPTABLE": [
        "3E",
        "2D",
        "2E",
        "1B",
        "1C",
        "1D",
        "1E"
      ]
    }
  },
  "spi_indicators": [
    {
      "id": 1,
      "code": "UA",
      "name": "Unstable Approach",
      "department_ids": [
        1
      ],
      "unit": "per 1000 flights",
      "spt_target": 9.4,
      "alert_l1": 13.51,
      "alert_l2": 17.13
    },
    {
      "id": 2,
      "code": "HSRTO",
      "name": "High Speed Rejected Takeoff",
      "department_ids": [
        1
      ],
      "unit": "per 1000 flights",
      "spt_target": 0.83,
      "alert_l1": 2.93,
      "alert_l2": 4.97
    },
    {
      "id": 3,
      "code": "RED",
      "name": "Runway Excursion / Deviation",
      "department_ids": [
        1,
        3
      ],
      "unit": "per 1000 flights",
      "spt_target": 1.38,
      "alert_l1": 4.07,
      "alert_l2": 6.7
    },
    {
      "id": 4,
      "code": "TCAS",
      "name": "TCAS RA Encounter",
      "department_ids": [
        1
      ],
      "unit": "per 1000 flights",
      "spt_target": 3.02,
      "alert_l1": 5.98,
      "alert_l2": 8.78
    },
    {
      "id": 5,
      "code": "GA",
      "name": "Go-Around",
      "department_ids": [
        1
      ],
      "unit": "per 1000 flights",
      "spt_target": 14.58,
      "alert_l1": 18.83,
      "alert_l2": 22.32
    },
    {
      "id": 6,
      "code": "BS",
      "name": "Bird Strike",
      "department_ids": [
        1,
        3
      ],
      "unit": "per 1000 flights",
      "spt_target": 2.15,
      "alert_l1": 5.07,
      "alert_l2": 7.87
    },
    {
      "id": 7,
      "code": "CFIT",
      "name": "CFIT Warning / GPWS Alert",
      "department_ids": [
        1
      ],
      "unit": "per 1000 flights",
      "spt_target": 0.87,
      "alert_l1": 3.06,
      "alert_l2": 5.21
    },
    {
      "id": 8,
      "code": "ATB",
      "name": "Air Turnback",
      "department_ids": [
        1
      ],
      "unit": "per 1000 flights",
      "spt_target": 2.54,
      "alert_l1": 5.47,
      "alert_l2": 8.27
    },
    {
      "id": 9,
      "code": "FCIR",
      "name": "Flight Crew Incident Report",
      "department_ids": [
        1
      ],
      "unit": "per 1000 flights",
      "spt_target": 7.78,
      "alert_l1": 11.07,
      "alert_l2": 13.96
    },
    {
      "id": 10,
      "code": "ME-INJ",
      "name": "Maintenance Injury Rate",
      "department_ids": [
        2
      ],
      "unit": "per 100 staff",
      "spt_target": 2.0,
      "alert_l1": 4.0,
      "alert_l2": 6.0
    },
    {
      "id": 11,
      "code": "RAMP-INC",
      "name": "Ramp Incidents",
      "department_ids": [
        3
      ],
      "unit": "per 1000 turnarounds",
      "spt_target": 5.0,
      "alert_l1": 10.0,
      "alert_l2": 15.0
    },
    {
      "id": 12,
      "code": "CAB-INC",
      "name": "Cabin Safety Incidents",
      "department_ids": [
        4
      ],
      "unit": "per 1000 flights",
      "spt_target": 3.0,
      "alert_l1": 6.0,
      "alert_l2": 9.0
    }
  ],
  "hazards": [
    {
      "id": "HAZ-2024-001",
      "source": "ASR",
      "linked_report_id": "ASR-2024-001",
      "department_id": 1,
      "type_of_activity": "Flight Operations",
      "generic_hazard": "Weather / Visibility",
      "specific_components": "Bad visibility and Low Visibility Procedure in progress during approach",
      "consequences": "Diversion, potential runway excursion, crew workload increase",
      "initial_likelihood": 4,
      "initial_severity": "B",
      "initial_risk_index": "4B",
      "initial_risk_tolerance": "INTOLERABLE",
      "current_defenses": "Low Visibility Procedure (LVP), ATC coordination, crew training",
      "further_mitigations": "Enhanced crew briefing on LVP procedures; real-time ATIS monitoring protocol; alternate aerodrome pre-planning requirement",
      "residual_likelihood": 2,
      "residual_severity": "C",
      "residual_risk_index": "2C",
      "residual_risk_tolerance": "TOLERABLE",
      "status": "Open",
      "owner": "Flight Operations Manager",
      "created_at": "2024-04-30T11:00:00Z"
    },
    {
      "id": "HAZ-2024-002",
      "source": "Hazard Report",
      "linked_report_id": "HR-2024-002",
      "department_id": 3,
      "type_of_activity": "Ground Handling",
      "generic_hazard": "FOD (Foreign Object Debris)",
      "specific_components": "Debris on taxiway near gate B3 following heavy rain",
      "consequences": "Engine ingestion, tyre damage, aircraft damage",
      "initial_likelihood": 3,
      "initial_severity": "B",
      "initial_risk_index": "3B",
      "initial_risk_tolerance": "INTOLERABLE",
      "current_defenses": "Daily FOD walks, ground crew awareness training",
      "further_mitigations": "Post-rain FOD check protocol; designated FOD collection bins at gate areas; supervisor sign-off required before aircraft movement",
      "residual_likelihood": 2,
      "residual_severity": "D",
      "residual_risk_index": "2D",
      "residual_risk_tolerance": "ACCEPTABLE",
      "status": "Open",
      "owner": "Ground Operations Manager",
      "created_at": "2024-04-15T08:30:00Z"
    },
    {
      "id": "HAZ-2024-003",
      "source": "Hazard Report",
      "linked_report_id": "HR-2024-003",
      "department_id": 2,
      "type_of_activity": "Maintenance",
      "generic_hazard": "Ergonomics / Manual Handling",
      "specific_components": "Technicians lifting heavy engine components without mechanical aid",
      "consequences": "Musculoskeletal injury to personnel, dropped equipment causing damage",
      "initial_likelihood": 4,
      "initial_severity": "C",
      "initial_risk_index": "4C",
      "initial_risk_tolerance": "TOLERABLE",
      "current_defenses": "Tooling available, basic manual handling training",
      "further_mitigations": "Mandatory use of engine hoists for components over 20kg; toolbox talk reinforcement; injury reporting culture campaign",
      "residual_likelihood": 2,
      "residual_severity": "D",
      "residual_risk_index": "2D",
      "residual_risk_tolerance": "ACCEPTABLE",
      "status": "Closed",
      "owner": "Maintenance Manager",
      "created_at": "2024-03-10T14:00:00Z"
    }
  ],
  "asr_reports": [
    {
      "id": "ASR-2024-001",
      "report_type": "Voluntary",
      "occurrence_type": "Diversion",
      "event_type": "ASR",
      "captain": "KHALED AL SABBAGH",
      "captain_staff_no": "410",
      "copilot": "MOHAMMAD RAHALL",
      "copilot_staff_no": "3181",
      "date": "2024-04-30",
      "time_local": "14:00",
      "time_utc": "11:00",
      "flight_no": "JAN 1271",
      "route_from": "AMM",
      "route_to": "IST",
      "diverted_to": "ESB",
      "squawk": "5606",
      "aircraft_type": "B737-300",
      "registration": "JY-JAX",
      "pax": 2,
      "crew": 4,
      "altitude_ft": 4000,
      "speed_mach": 220,
      "flight_phase": "Descent",
      "weather_wind": "020/11",
      "weather_vis_rvr": "400/400",
      "weather_clouds": "BKN 200",
      "weather_temp_c": 14,
      "weather_qnh": 1021,
      "runway": "35R",
      "runway_state": "Wet",
      "event_description": "BAD VISIBILITY AND LOW VISIBILITY PROCEDURE IN PROGRESS.",
      "action_taken": "DIVERTED TO LTAC A/P.",
      "department_id": 1,
      "hazard_id": "HAZ-2024-001",
      "created_at": "2024-04-30T15:00:00Z"
    }
  ],
  "hazard_reports": [
    {
      "id": "HR-2024-002",
      "department_id": 3,
      "location": "Gate B3, Taxiway Echo",
      "date": "2024-04-15",
      "hazard_description": "Debris found on taxiway near gate B3 following heavy overnight rain. Multiple pieces of plastic and metal fragments identified.",
      "immediate_action": "Area cordoned off. Ramp supervisor notified. FOD removal team dispatched.",
      "suggested_mitigation": "Implement mandatory post-rain FOD inspections before resuming aircraft operations in affected areas.",
      "severity": "B",
      "likelihood": 3,
      "risk_index": "3B",
      "reporter": "Anonymous",
      "hazard_id": "HAZ-2024-002",
      "created_at": "2024-04-15T08:30:00Z"
    },
    {
      "id": "HR-2024-003",
      "department_id": 2,
      "location": "Hangar 2, Bay C",
      "date": "2024-03-10",
      "hazard_description": "Observed technicians manually lifting an engine accessory gearbox (estimated 35kg) without using available hoist equipment. Risk of injury and component damage.",
      "immediate_action": "Work stopped immediately. Hoist equipment deployed. Safety reminder issued to shift.",
      "suggested_mitigation": "Mandatory mechanical aid for all components over 20kg. Refresher training on manual handling procedures.",
      "severity": "C",
      "likelihood": 4,
      "risk_index": "4C",
      "reporter": "Maintenance Supervisor",
      "hazard_id": "HAZ-2024-003",
      "created_at": "2024-03-10T14:00:00Z"
    }
  ],
  "spi_data": [
    {
      "spi_id": 1,
      "year": 2025,
      "month": 1,
      "events": 6,
      "flights": 175,
      "rate": 11.43
    },
    {
      "spi_id": 1,
      "year": 2025,
      "month": 2,
      "events": 3,
      "flights": 168,
      "rate": 5.95
    },
    {
      "spi_id": 1,
      "year": 2025,
      "month": 3,
      "events": 6,
      "flights": 182,
      "rate": 10.99
    },
    {
      "spi_id": 1,
      "year": 2025,
      "month": 4,
      "events": 3,
      "flights": 179,
      "rate": 5.62
    },
    {
      "spi_id": 1,
      "year": 2025,
      "month": 5,
      "events": 3,
      "flights": 180,
      "rate": 16.67
    },
    {
      "spi_id": 4,
      "year": 2025,
      "month": 1,
      "events": 1,
      "flights": 175,
      "rate": 5.71
    },
    {
      "spi_id": 4,
      "year": 2025,
      "month": 2,
      "events": 1,
      "flights": 168,
      "rate": 5.95
    },
    {
      "spi_id": 4,
      "year": 2025,
      "month": 3,
      "events": 0,
      "flights": 182,
      "rate": 0
    },
    {
      "spi_id": 4,
      "year": 2025,
      "month": 4,
      "events": 1,
      "flights": 179,
      "rate": 5.62
    },
    {
      "spi_id": 4,
      "year": 2025,
      "month": 5,
      "events": 0,
      "flights": 180,
      "rate": 0
    },
    {
      "spi_id": 6,
      "year": 2025,
      "month": 1,
      "events": 0,
      "flights": 175,
      "rate": 0
    },
    {
      "spi_id": 6,
      "year": 2025,
      "month": 2,
      "events": 1,
      "flights": 168,
      "rate": 5.95
    },
    {
      "spi_id": 6,
      "year": 2025,
      "month": 3,
      "events": 0,
      "flights": 182,
      "rate": 0
    },
    {
      "spi_id": 6,
      "year": 2025,
      "month": 4,
      "events": 0,
      "flights": 179,
      "rate": 0
    },
    {
      "spi_id": 6,
      "year": 2025,
      "month": 5,
      "events": 1,
      "flights": 180,
      "rate": 5.56
    }
  ]
}

# ─── Helpers ──────────────────────────────────────────────────────────────────
INTOLERABLE = {"5A","5B","5C","4A","4B","3A"}
TOLERABLE   = {"5D","5E","4C","4D","4E","3B","3C","3D","2A","2B","2C","1A"}

def get_tolerance(risk_index):
    if risk_index in INTOLERABLE: return "INTOLERABLE"
    if risk_index in TOLERABLE:   return "TOLERABLE"
    return "ACCEPTABLE"

def new_id(prefix):
    year = datetime.now().year
    short = str(uuid.uuid4())[:6].upper()
    return f"{prefix}-{year}-{short}"

def dept_name(dept_id):
    d = next((x for x in DB["departments"] if x["id"] == dept_id), None)
    return d["name"] if d else "—"

def dept_code(dept_id):
    d = next((x for x in DB["departments"] if x["id"] == dept_id), None)
    return d["code"] if d else "—"

# ─── Dashboard ────────────────────────────────────────────────────────────────
@app.route("/")
def dashboard():
    total   = len(DB["hazards"])
    open_h  = sum(1 for h in DB["hazards"] if h["status"] == "Open")
    intol   = sum(1 for h in DB["hazards"] if h["initial_risk_tolerance"] == "INTOLERABLE")
    asr_cnt = len(DB["asr_reports"])
    hr_cnt  = len(DB["hazard_reports"])
    recent  = sorted(DB["hazards"], key=lambda x: x["created_at"], reverse=True)[:6]
    return render_template("dashboard.html",
        total=total, open_h=open_h, intol=intol,
        asr_cnt=asr_cnt, hr_cnt=hr_cnt,
        recent=recent, dept_name=dept_name, dept_code=dept_code,
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
            "generic_hazard": "To Be Classified",
            "specific_components": f["hazard_description"],
            "consequences": "To Be Assessed",
            "initial_likelihood": likelihood, "initial_severity": severity,
            "initial_risk_index": risk_index,
            "initial_risk_tolerance": tolerance,
            "current_defenses": f.get("immediate_action",""),
            "further_mitigations": f.get("suggested_mitigation",""),
            "residual_likelihood": None, "residual_severity": None,
            "residual_risk_index": None, "residual_risk_tolerance": None,
            "status": "Open", "owner": None, "created_at": now
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
        flash(f"✓ Hazard Report submitted. ID: {rep_id} | Hazard: {haz_id} | Risk: {risk_index} — {tolerance}", "success")
        return redirect(url_for("hazard_report"))

    return render_template("hazard_report.html", departments=DB["departments"])

# ─── ASR (Flight Ops Only) ────────────────────────────────────────────────────
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
            "generic_hazard": f.get("occurrence_type",""),
            "specific_components": f.get("event_description",""),
            "consequences": "To Be Assessed by Safety Department",
            "initial_likelihood": likelihood, "initial_severity": severity,
            "initial_risk_index": risk_index,
            "initial_risk_tolerance": tolerance,
            "current_defenses": f.get("action_taken",""),
            "further_mitigations": "",
            "residual_likelihood": None, "residual_severity": None,
            "residual_risk_index": None, "residual_risk_tolerance": None,
            "status": "Open", "owner": "Flight Operations Manager",
            "created_at": now
        }
        asr_rec = dict(f) 
        asr_rec.update({"id": asr_id, "hazard_id": haz_id,
                        "department_id": 1, "created_at": now,
                        "likelihood": likelihood, "severity": severity,
                        "risk_index": risk_index})
        DB["hazards"].append(hazard)
        DB["asr_reports"].append(asr_rec)
        flash(f"✓ ASR submitted. ID: {asr_id} | Hazard: {haz_id} | Risk: {risk_index} — {tolerance}", "success")
        return redirect(url_for("asr"))

    return render_template("asr.html")

# ─── Hazard Log ───────────────────────────────────────────────────────────────
@app.route("/hazard-log")
def hazard_log():
    dept_filter = request.args.get("dept","")
    status_f    = request.args.get("status","")
    tol_f       = request.args.get("tolerance","")

    hazards = list(DB["hazards"])
    if dept_filter:
        hazards = [h for h in hazards if str(h["department_id"]) == dept_filter]
    if status_f:
        hazards = [h for h in hazards if h["status"] == status_f]
    if tol_f:
        hazards = [h for h in hazards if h["initial_risk_tolerance"] == tol_f]

    hazards = sorted(hazards, key=lambda x: x["created_at"], reverse=True)
    return render_template("hazard_log.html",
        hazards=hazards, departments=DB["departments"],
        dept_name=dept_name, dept_code=dept_code,
        dept_filter=dept_filter, status_f=status_f, tol_f=tol_f)

@app.route("/hazard-log/<haz_id>")
def hazard_detail(haz_id):
    h = next((x for x in DB["hazards"] if x["id"] == haz_id), None)
    if not h: return "Not found", 404
    return render_template("hazard_detail.html", h=h,
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
    flash("✓ Hazard updated successfully.", "success")
    return redirect(url_for("hazard_detail", haz_id=haz_id))

# ─── SPI ─────────────────────────────────────────────────────────────────────
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

    MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    cur_year = datetime.now().year

    table = []
    for ind in indicators:
        month_rates = {}
        for d in DB["spi_data"]:
            if d["spi_id"] == ind["id"] and d["year"] == cur_year:
                month_rates[d["month"]] = d["rate"]
        ytd = round(sum(month_rates.values()) / len(month_rates), 2) if month_rates else 0
        if ytd >= ind["alert_l2"]:   status = ("🔴 CRITICAL","#dc2626")
        elif ytd >= ind["alert_l1"]: status = ("🟡 WARNING","#d97706")
        elif ytd > ind["spt_target"]:status = ("🟠 WATCH","#ea580c")
        else:                        status = ("🟢 OK","#16a34a")
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

if __name__ == "__main__":
    app.run(debug=True, port=5000)
