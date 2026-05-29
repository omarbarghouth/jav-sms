from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Department(db.Model):
    __tablename__ = 'departments'
    id            = db.Column(db.Integer, primary_key=True)
    code          = db.Column(db.String(10), unique=True, nullable=False)
    name          = db.Column(db.String(100), nullable=False)
    color         = db.Column(db.String(20), default='#1e40af')

class User(db.Model):
    """Safety Admin users — protected access to internal SMS dashboard."""
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name     = db.Column(db.String(100))
    role          = db.Column(db.String(30), default='safety_officer')
    # Roles: admin / safety_manager / safety_officer / auditor
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    is_active     = db.Column(db.Boolean, default=True)
    sag_role      = db.Column(db.String(80))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    last_login    = db.Column(db.DateTime)
    department    = db.relationship('Department', foreign_keys=[department_id])


class VoluntaryReport(db.Model):
    """Voluntary safety report — open to all staff."""
    __tablename__ = 'voluntary_reports'
    id            = db.Column(db.Integer, primary_key=True)
    ref_number    = db.Column(db.String(30))
    reporter_name = db.Column(db.String(100))   # optional
    position      = db.Column(db.String(100))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    date          = db.Column(db.String(20))
    location      = db.Column(db.String(200))
    report_type   = db.Column(db.String(50))    # Safety Concern / Near Miss / Observation
    description   = db.Column(db.Text)
    consequences  = db.Column(db.Text)
    suggestion    = db.Column(db.Text)
    status        = db.Column(db.String(20), default='Submitted')
    is_confidential = db.Column(db.Boolean, default=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    department    = db.relationship('Department', foreign_keys=[department_id])


class ConfidentialReport(db.Model):
    """Confidential safety report — identity protected."""
    __tablename__ = 'confidential_reports'
    id            = db.Column(db.Integer, primary_key=True)
    ref_number    = db.Column(db.String(30))
    # Reporter identity deliberately kept minimal
    position      = db.Column(db.String(100))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    date          = db.Column(db.String(20))
    location      = db.Column(db.String(200))
    report_type   = db.Column(db.String(50))
    description   = db.Column(db.Text)
    consequences  = db.Column(db.Text)
    suggestion    = db.Column(db.Text)
    status        = db.Column(db.String(20), default='Submitted')
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    department    = db.relationship('Department', foreign_keys=[department_id])


class HazardReport(db.Model):
    __tablename__ = 'hazard_reports'
    id            = db.Column(db.String(30), primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    location      = db.Column(db.String(200))
    date          = db.Column(db.String(20))
    description   = db.Column(db.Text)
    classification = db.Column(db.String(50), default='Operational')
    generic_hazard = db.Column(db.String(200))
    consequences  = db.Column(db.Text)
    immediate_action = db.Column(db.Text)
    suggested_mitigation = db.Column(db.Text)
    reporter_severity = db.Column(db.String(20))  # Low/Medium/High/Critical (perception)
    # Keep these for backward compat — no longer required on form
    severity      = db.Column(db.String(2))
    likelihood    = db.Column(db.Integer)
    risk_index    = db.Column(db.String(5))
    reporter      = db.Column(db.String(100), default='Anonymous')
    report_type   = db.Column(db.String(30), default='Hazard Report')  # Hazard Report / ASR / Voluntary / Confidential / Technical Log
    status        = db.Column(db.String(30), default='Submitted')
    # Submitted / Under Assessment / Actioned / Closed
    hazard_id     = db.Column(db.String(30), db.ForeignKey('hazards.id'))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    department    = db.relationship('Department', foreign_keys=[department_id])

class ASRReport(db.Model):
    __tablename__ = 'asr_reports'
    id               = db.Column(db.String(30), primary_key=True)
    report_type      = db.Column(db.String(20), default='Voluntary')
    occurrence_type  = db.Column(db.String(50))
    captain          = db.Column(db.String(100))
    captain_staff_no = db.Column(db.String(20))
    copilot          = db.Column(db.String(100))
    copilot_staff_no = db.Column(db.String(20))
    date             = db.Column(db.String(20))
    time_local       = db.Column(db.String(10))
    time_utc         = db.Column(db.String(10))
    flight_no        = db.Column(db.String(20))
    route_from       = db.Column(db.String(10))
    route_to         = db.Column(db.String(10))
    diverted_to      = db.Column(db.String(10))
    squawk           = db.Column(db.String(10))
    aircraft_type    = db.Column(db.String(30))
    registration     = db.Column(db.String(20))
    pax              = db.Column(db.Integer)
    crew             = db.Column(db.Integer)
    altitude_ft      = db.Column(db.Integer)
    flight_phase     = db.Column(db.String(30))
    weather_wind     = db.Column(db.String(20))
    weather_vis_rvr  = db.Column(db.String(20))
    weather_clouds   = db.Column(db.String(30))
    weather_temp_c   = db.Column(db.Integer)
    weather_qnh      = db.Column(db.Integer)
    runway           = db.Column(db.String(10))
    runway_state     = db.Column(db.String(20))
    event_description = db.Column(db.Text)
    action_taken     = db.Column(db.Text)
    severity         = db.Column(db.String(2))
    likelihood       = db.Column(db.Integer)
    risk_index       = db.Column(db.String(5))
    hazard_id        = db.Column(db.String(30), db.ForeignKey('hazards.id'))
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

class Hazard(db.Model):
    __tablename__ = 'hazards'
    id                     = db.Column(db.String(30), primary_key=True)
    source                 = db.Column(db.String(30))   # Hazard Report / ASR / Audit / MOC / Investigation
    linked_report_id       = db.Column(db.String(30))
    department_id          = db.Column(db.Integer, db.ForeignKey('departments.id'))
    classification         = db.Column(db.String(30))   # Operational/Technical/Human Factors/Environmental/Organizational
    type_of_activity       = db.Column(db.String(100))
    generic_hazard         = db.Column(db.String(200))
    specific_components    = db.Column(db.Text)
    consequences           = db.Column(db.Text)
    status                 = db.Column(db.String(20), default='Open')
    owner                  = db.Column(db.String(100))
    created_at             = db.Column(db.DateTime, default=datetime.utcnow)
    department             = db.relationship('Department', foreign_keys=[department_id])
    risks                  = db.relationship('Risk', backref='hazard', lazy=True, cascade='all, delete-orphan')
    actions                = db.relationship('Action', backref='hazard', lazy=True)
    hazard_reports         = db.relationship('HazardReport', backref='hazard_parent', lazy=True, foreign_keys='HazardReport.hazard_id')

class Risk(db.Model):
    __tablename__ = 'risks'
    id                    = db.Column(db.String(30), primary_key=True)
    hazard_id             = db.Column(db.String(30), db.ForeignKey('hazards.id'), nullable=False)
    description           = db.Column(db.Text)
    initial_likelihood    = db.Column(db.Integer)
    initial_severity      = db.Column(db.String(2))
    initial_risk_index    = db.Column(db.String(5))
    initial_tolerance     = db.Column(db.String(20))
    residual_likelihood   = db.Column(db.Integer)
    residual_severity     = db.Column(db.String(2))
    residual_risk_index   = db.Column(db.String(5))
    residual_tolerance    = db.Column(db.String(20))
    created_at            = db.Column(db.DateTime, default=datetime.utcnow)
    controls              = db.relationship('Control', backref='risk', lazy=True, cascade='all, delete-orphan')

class Control(db.Model):
    __tablename__ = 'controls'
    id            = db.Column(db.String(30), primary_key=True)
    risk_id       = db.Column(db.String(30), db.ForeignKey('risks.id'), nullable=False)
    control_type  = db.Column(db.String(20))   # Preventive / Detective
    description   = db.Column(db.Text)
    owner         = db.Column(db.String(100))
    effectiveness = db.Column(db.String(30))   # Effective / Partially Effective / Ineffective
    review_date   = db.Column(db.String(20))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

class Action(db.Model):
    """
    SIMPLE ACTION TABLE.
    One table. One lifecycle: Open → In Progress → Closed.
    Overdue is automatic when due_date passes.
    Effectiveness is asked only when closing.
    Source tells you WHERE the action came from.
    hazard_id tells you WHICH hazard it belongs to.
    """
    __tablename__ = 'actions'
    id               = db.Column(db.String(30), primary_key=True)
    # WHERE did this action come from?
    source           = db.Column(db.String(40))
    # "Hazard Report" / "ASR" / "Risk Assessment" / "Audit" / "MOC" / "Investigation"
    hazard_id        = db.Column(db.String(30), db.ForeignKey('hazards.id'))
    linked_ref_id    = db.Column(db.String(30))  # e.g. audit finding ID
    # The 5 fields every action needs
    description      = db.Column(db.Text)
    owner            = db.Column(db.String(100))
    due_date         = db.Column(db.String(20))
    priority         = db.Column(db.String(20), default='Medium')  # High / Medium / Low
    status           = db.Column(db.String(50), default='Open')
    # Open / In Progress / Closed / Overdue
    # Effectiveness — only filled when closing
    effectiveness        = db.Column(db.String(30))
    # Effective / Partially Effective / Ineffective
    effectiveness_review = db.Column(db.Text)
    closed_date          = db.Column(db.String(20))
    # SPI lifecycle fields
    spi_id               = db.Column(db.Integer, db.ForeignKey('spi_indicators.id'), nullable=True)
    spi_alert_level      = db.Column(db.String(5))    # L1 / L2 / L3
    spi_trigger_rule     = db.Column(db.String(2))    # A / B / C
    spi_alert_month      = db.Column(db.Integer)      # month alert was triggered (1-12)
    spi_alert_year       = db.Column(db.Integer)      # year alert was triggered
    spi_escalation_id    = db.Column(db.Integer, nullable=True)  # FK to spi_escalations.id
    # Evidence & mitigation
    evidence             = db.Column(db.Text)          # evidence text
    evidence_filename    = db.Column(db.String(200))   # uploaded evidence file
    mitigation_description = db.Column(db.Text)        # what mitigation was done
    corrective_description = db.Column(db.Text)        # corrective action details
    safety_notes         = db.Column(db.Text)          # safety improvement notes
    follow_up_notes      = db.Column(db.Text)          # monitoring notes post-closure
    mitigation_status    = db.Column(db.String(30))    # Active / Completed / Pending
    # Safety Review
    safety_review_notes  = db.Column(db.Text)           # Safety Dept review notes
    safety_reviewer      = db.Column(db.String(100))    # Safety reviewer name
    safety_review_date   = db.Column(db.String(20))
    implementation_date  = db.Column(db.String(20))     # when mitigation was implemented
    # People
    assigned_by          = db.Column(db.String(100))   # who assigned the action
    closure_by           = db.Column(db.String(100))   # who confirmed closure
    verified_by          = db.Column(db.String(100))   # who verified effectiveness
    verified_date        = db.Column(db.String(20))
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)
    # SAG governance fields
    sag_member           = db.Column(db.String(100))   # assigned SAG member username
    department_id        = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    root_cause           = db.Column(db.Text)
    rejection_notes      = db.Column(db.Text)
    reopen_count         = db.Column(db.Integer, default=0)
    action_type          = db.Column(db.String(20), default='Corrective')
    linked_audit_id      = db.Column(db.String(30))
    linked_ra_id         = db.Column(db.String(30))
    linked_risk_id       = db.Column(db.String(30))
    # NOTE: assigned_by declared once above (duplicate removed)
    # Relationship to SPI indicator
    spi_indicator        = db.relationship('SPIIndicator', foreign_keys=[spi_id],
                               backref=db.backref('linked_actions', lazy=True))

class ActionHistory(db.Model):
    """Full audit trail of every action change."""
    __tablename__ = 'action_history'
    id            = db.Column(db.Integer, primary_key=True)
    action_id     = db.Column(db.String(30), db.ForeignKey('actions.id'), nullable=False)
    changed_by    = db.Column(db.String(100))
    changed_at    = db.Column(db.DateTime, default=datetime.utcnow)
    from_status   = db.Column(db.String(50))
    to_status     = db.Column(db.String(50))
    notes         = db.Column(db.Text)
    field_changed = db.Column(db.String(50), default='status')
    action        = db.relationship('Action', backref=db.backref('history',
                        lazy=True, order_by='ActionHistory.changed_at.desc()'))


class Audit(db.Model):
    __tablename__ = 'audits'
    id            = db.Column(db.String(30), primary_key=True)
    title         = db.Column(db.String(200))
    audit_type    = db.Column(db.String(50))   # Internal / External / IOSA / Regulatory
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    planned_date  = db.Column(db.String(20))
    actual_date   = db.Column(db.String(20))
    lead_auditor  = db.Column(db.String(100))
    status        = db.Column(db.String(20), default='Planned')  # Planned / In Progress / Closed
    summary       = db.Column(db.Text)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    department    = db.relationship('Department', foreign_keys=[department_id])
    findings      = db.relationship('Finding', backref='audit', lazy=True, cascade='all, delete-orphan')

class Finding(db.Model):
    __tablename__ = 'findings'
    id              = db.Column(db.String(30), primary_key=True)
    audit_id        = db.Column(db.String(30), db.ForeignKey('audits.id'), nullable=False)
    description     = db.Column(db.Text)
    severity        = db.Column(db.String(20))   # Major / Minor / Observation
    root_cause      = db.Column(db.Text)
    corrective_action = db.Column(db.Text)
    status          = db.Column(db.String(20), default='Open')
    hazard_id       = db.Column(db.String(30))
    action_id       = db.Column(db.String(30))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

class Investigation(db.Model):
    __tablename__ = 'investigations'
    id                  = db.Column(db.String(30), primary_key=True)
    title               = db.Column(db.String(200))
    linked_report_id    = db.Column(db.String(30))
    hazard_id           = db.Column(db.String(30), db.ForeignKey('hazards.id'))
    department_id       = db.Column(db.Integer, db.ForeignKey('departments.id'))
    date_of_occurrence  = db.Column(db.String(20))
    investigator        = db.Column(db.String(100))
    description         = db.Column(db.Text)
    why1 = db.Column(db.Text)
    why2 = db.Column(db.Text)
    why3 = db.Column(db.Text)
    why4 = db.Column(db.Text)
    why5 = db.Column(db.Text)
    root_cause          = db.Column(db.Text)
    human_factors       = db.Column(db.Text)
    technical_factors   = db.Column(db.Text)
    organizational_factors = db.Column(db.Text)
    environmental_factors  = db.Column(db.Text)
    recommendations     = db.Column(db.Text)
    # ICAO Annex 13 / Doc 9859 classification + lifecycle
    classification      = db.Column(db.String(30), default='Incident')
    # Accident / Serious Incident / Incident / Occurrence / Near Miss
    severity_index      = db.Column(db.String(5))
    occurrence_category = db.Column(db.String(50))   # ARC/CFIT/LOC-I/MAC/RE/UIMC/etc.
    phase_of_flight     = db.Column(db.String(50))
    aircraft_type       = db.Column(db.String(50))
    aircraft_reg        = db.Column(db.String(20))
    location            = db.Column(db.String(200))
    # Regulatory notification (ICAO Annex 13 §6.1)
    authority_notified  = db.Column(db.Boolean, default=False)
    notification_date   = db.Column(db.String(20))
    notification_ref    = db.Column(db.String(50))
    # Investigation lifecycle
    lifecycle_stage     = db.Column(db.String(40), default='Notified')
    # Notified → Initial Assessment → Under Investigation →
    # Root Cause Analysis → Recommendations → Pending Closure → Closed
    assigned_date       = db.Column(db.String(20))
    target_close_date   = db.Column(db.String(20))
    final_findings      = db.Column(db.Text)
    closed_date         = db.Column(db.String(20))
    closed_by           = db.Column(db.String(100))
    status              = db.Column(db.String(20), default='Open')
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at          = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    department          = db.relationship('Department', foreign_keys=[department_id])
    timeline            = db.relationship('InvestigationEvent', backref='investigation',
                              lazy=True, order_by='InvestigationEvent.created_at')

class MOC(db.Model):
    __tablename__ = 'moc'
    id                  = db.Column(db.String(30), primary_key=True)
    title               = db.Column(db.String(200))
    description         = db.Column(db.Text)
    department_id       = db.Column(db.Integer, db.ForeignKey('departments.id'))
    change_type         = db.Column(db.String(50))   # Process / Equipment / Personnel / Regulatory
    initiator           = db.Column(db.String(100))
    planned_date        = db.Column(db.String(20))
    pre_change_risk     = db.Column(db.Text)
    approval_status     = db.Column(db.String(30), default='Pending')  # Pending / Approved / Rejected
    approved_by         = db.Column(db.String(100))
    implementation_status = db.Column(db.String(30), default='Not Started')
    post_change_review  = db.Column(db.Text)
    hazard_id           = db.Column(db.String(30))
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)
    department          = db.relationship('Department', foreign_keys=[department_id])

class SPIIndicator(db.Model):
    """
    Safety Performance Indicator definition.
    Calc types:
      COUNT  : SPI = events (raw count)
      RATE   : SPI = (events / exposure) * 1000
      PERCENT: SPI = (events / total_events) * 100
    Alert logic:
      value >= alert_l3 → RED (Level 3 Critical)
      value >= alert_l2 → ORANGE (Level 2 Warning)
      value >= alert_l1 → YELLOW (Level 1 Watch)
      value > spt_target → BLUE (Exceeds target)
      else              → GREEN (Within target)
    """
    __tablename__ = 'spi_indicators'
    id             = db.Column(db.Integer, primary_key=True)
    code           = db.Column(db.String(20))
    name           = db.Column(db.String(200))
    department_ids = db.Column(db.String(50))   # comma-separated dept ids: "1,2"
    category       = db.Column(db.String(50))   # FOD / ASR / Audit / Training / etc.
    description    = db.Column(db.Text)
    calc_type      = db.Column(db.String(10), default='RATE')  # COUNT / RATE / PERCENT
    exposure_type  = db.Column(db.String(30), default='Flights')  # Flights/Hours/Sectors/Reports
    unit           = db.Column(db.String(50))
    frequency      = db.Column(db.String(20), default='Monthly')
    spt_target     = db.Column(db.Float)   # Safety Performance Target
    alert_l1       = db.Column(db.Float)   # Yellow — Level 1
    alert_l2       = db.Column(db.Float)   # Orange — Level 2
    alert_l3       = db.Column(db.Float)   # Red    — Level 3 Critical
    auto_source      = db.Column(db.String(50))
    auto_category    = db.Column(db.String(50))
    # Statistical monitoring
    baseline_months  = db.Column(db.Integer, default=3)   # months needed before stat mode
    improvement_pct  = db.Column(db.Float, default=5.0)   # target = avg * (1 - improvement/100)
    stat_mode        = db.Column(db.Boolean, default=False) # True once baseline complete
    active           = db.Column(db.Boolean, default=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    data_entries   = db.relationship('SPIData', backref='indicator', lazy=True,
                                     cascade='all, delete-orphan')

class SPIData(db.Model):
    """Monthly SPI data point."""
    __tablename__ = 'spi_data'
    id           = db.Column(db.Integer, primary_key=True)
    spi_id       = db.Column(db.Integer, db.ForeignKey('spi_indicators.id'))
    year         = db.Column(db.Integer)
    month        = db.Column(db.Integer)   # 1-12
    events       = db.Column(db.Integer, default=0)    # numerator
    exposure     = db.Column(db.Float, default=1)      # denominator (flights/hours/reports)
    total_events = db.Column(db.Integer, default=0)    # for PERCENT calc
    value        = db.Column(db.Float)     # calculated SPI value
    source       = db.Column(db.String(20), default='manual')  # manual / auto
    notes        = db.Column(db.Text)
    # legacy compat
    flights      = db.Column(db.Integer)
    rate         = db.Column(db.Float)
    # Statistical metadata (auto-computed, stored for performance)
    mean_at_time = db.Column(db.Float)   # historical mean when this point was recorded
    sd_at_time   = db.Column(db.Float)   # historical SD when recorded

class SPIEscalation(db.Model):
    """
    Persistent record of each SPI escalation event.
    Created automatically when _spi_trigger_detail fires.
    This is the SOURCE RECORD for SPI actions — the action is a RESPONSE,
    the escalation is the CAUSE.
    """
    __tablename__ = 'spi_escalations'
    id             = db.Column(db.Integer, primary_key=True)
    spi_id         = db.Column(db.Integer, db.ForeignKey('spi_indicators.id'))
    # When the threshold was exceeded (the REAL trigger event)
    trigger_month  = db.Column(db.Integer)   # 1-12 calendar month
    trigger_year   = db.Column(db.Integer)
    # What happened
    trigger_rule   = db.Column(db.String(2))  # A / B / C
    alert_level    = db.Column(db.String(5))  # L1 / L2 / L3
    spi_value      = db.Column(db.Float)      # actual SPI value at trigger month
    threshold_value = db.Column(db.Float)     # L1/L2/L3 threshold that was exceeded
    mean_value     = db.Column(db.Float)      # mean at time of trigger
    sd_value       = db.Column(db.Float)      # SD at time of trigger
    description    = db.Column(db.Text)       # e.g. "Rule A: 20.0 > L3 4.8"
    # When this record was created (not the trigger month — those are different)
    detected_at    = db.Column(db.DateTime, default=datetime.utcnow)
    # Status tracking
    status         = db.Column(db.String(20), default='Open')  # Open / Actioned / Closed
    linked_action_id = db.Column(db.String(30))
    # Relationships
    indicator      = db.relationship('SPIIndicator', backref=db.backref('escalations', lazy=True))


class SafetyNewsletter(db.Model):
    """Safety Newsletter — professional communications from Safety Dept."""
    __tablename__ = 'safety_newsletters'
    id             = db.Column(db.Integer, primary_key=True)
    ref_number     = db.Column(db.String(30))    # e.g. NL-2026-001
    title          = db.Column(db.String(200))
    issue_number   = db.Column(db.String(20))
    department_id  = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    issue_date     = db.Column(db.String(20))
    author         = db.Column(db.String(100))
    summary        = db.Column(db.Text)
    content        = db.Column(db.Text)
    status         = db.Column(db.String(20), default='Draft')  # Draft / Published / Archived
    attachment     = db.Column(db.String(200))   # uploaded file
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    department     = db.relationship('Department', foreign_keys=[department_id])


class SafetyCampaign(db.Model):
    """Safety Awareness Campaign."""
    __tablename__ = 'safety_campaigns'
    id             = db.Column(db.Integer, primary_key=True)
    title          = db.Column(db.String(200))
    campaign_type  = db.Column(db.String(50))    # Monthly / Seasonal / FOD / Fatigue / Operational
    department_id  = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    start_date     = db.Column(db.String(20))
    end_date       = db.Column(db.String(20))
    description    = db.Column(db.Text)
    objectives     = db.Column(db.Text)
    status         = db.Column(db.String(20), default='Active')  # Active / Completed / Planned
    attachment     = db.Column(db.String(200))
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    department     = db.relationship('Department', foreign_keys=[department_id])


class SafetySurvey(db.Model):
    """Safety Survey with questions and response tracking."""
    __tablename__ = 'safety_surveys'
    id             = db.Column(db.Integer, primary_key=True)
    title          = db.Column(db.String(200))
    survey_type    = db.Column(db.String(50))    # Safety Culture / Fatigue / Training / Reporting
    department_id  = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    start_date     = db.Column(db.String(20))
    end_date       = db.Column(db.String(20))
    description    = db.Column(db.Text)
    questions      = db.Column(db.Text)          # JSON string of questions
    status         = db.Column(db.String(20), default='Draft')  # Draft / Active / Closed
    target_count   = db.Column(db.Integer, default=0)
    response_count = db.Column(db.Integer, default=0)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    department     = db.relationship('Department', foreign_keys=[department_id])


class LessonLearned(db.Model):
    """Lessons Learned Library."""
    __tablename__ = 'lessons_learned'
    id             = db.Column(db.Integer, primary_key=True)
    ref_number     = db.Column(db.String(30))    # e.g. LL-2026-001
    title          = db.Column(db.String(200))
    category       = db.Column(db.String(50))    # Incident / Audit / Investigation / Operational
    department_id  = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    date           = db.Column(db.String(20))
    author         = db.Column(db.String(100))
    description    = db.Column(db.Text)
    lesson         = db.Column(db.Text)
    recommendations= db.Column(db.Text)
    status         = db.Column(db.String(20), default='Published')
    attachment     = db.Column(db.String(200))
    linked_hazard_id = db.Column(db.String(30), nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    department     = db.relationship('Department', foreign_keys=[department_id])


class SafetyBulletin(db.Model):
    __tablename__ = 'safety_bulletins'
    id            = db.Column(db.String(30), primary_key=True)
    ref_number    = db.Column(db.String(30))
    title         = db.Column(db.String(200))
    bulletin_type = db.Column(db.String(30))
    severity      = db.Column(db.String(20), default='Information')
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    issue_date    = db.Column(db.String(20))
    content       = db.Column(db.Text)
    recommendations = db.Column(db.Text)
    issued_by     = db.Column(db.String(100))
    status        = db.Column(db.String(20), default='Active')
    attachment    = db.Column(db.String(200))
    linked_hazard_id = db.Column(db.String(30), nullable=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    department    = db.relationship('Department', foreign_keys=[department_id])

class Training(db.Model):
    """
    Aviation Safety Training Record.
    Lifecycle: Scheduled → In Progress → Completed → Expired / Overdue
    """
    __tablename__ = 'trainings'
    id               = db.Column(db.Integer, primary_key=True)
    # Employee
    employee_name    = db.Column(db.String(100))
    employee_id      = db.Column(db.String(50))
    department_id    = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    position         = db.Column(db.String(100))
    # Course
    training_type    = db.Column(db.String(50))
    training_program = db.Column(db.String(200))
    course_code      = db.Column(db.String(50))
    instructor       = db.Column(db.String(100))
    location         = db.Column(db.String(100))
    # Dates
    scheduled_date   = db.Column(db.String(20))
    training_date    = db.Column(db.String(20))
    completion_date  = db.Column(db.String(20))
    expiry_date      = db.Column(db.String(20))
    duration_hours   = db.Column(db.Float)
    # Status
    status           = db.Column(db.String(20), default='Scheduled')
    # Files
    certificate      = db.Column(db.String(200))
    evidence         = db.Column(db.String(200))
    # Recurrence
    is_recurrent     = db.Column(db.Boolean, default=False)
    recurrence_months= db.Column(db.Integer)
    notes            = db.Column(db.Text)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    department       = db.relationship('Department', foreign_keys=[department_id])

class AuditPlan(db.Model):
    """Annual audit plan — defines what must be audited in a given year."""
    __tablename__ = 'audit_plans'
    id                 = db.Column(db.String(30), primary_key=True)
    year               = db.Column(db.Integer, nullable=False)
    month              = db.Column(db.Integer)          # 1-12, planned month of execution
    department_id      = db.Column(db.Integer, db.ForeignKey('departments.id'))
    audit_type         = db.Column(db.String(50))   # Internal / Compliance / IOSA / RAMP
    frequency          = db.Column(db.String(30))   # Quarterly / Semi-Annual / Annual / Ad-hoc
    responsible_manager = db.Column(db.String(100))
    scope              = db.Column(db.Text)
    objectives         = db.Column(db.Text)
    iosa_reference     = db.Column(db.String(100))
    auditor_name       = db.Column(db.String(100))   # planned auditor
    planned_week       = db.Column(db.Integer)        # 1-4 (week of month)
    status             = db.Column(db.String(20), default='Planned')
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)
    department         = db.relationship('Department', foreign_keys=[department_id])
    schedules          = db.relationship('AuditSchedule', backref='plan', lazy=True,
                                         cascade='all, delete-orphan')

class AuditSchedule(db.Model):
    """Individual scheduled audit — converted from audit plan."""
    __tablename__ = 'audit_schedules'
    id                 = db.Column(db.String(30), primary_key=True)
    plan_id            = db.Column(db.String(30), db.ForeignKey('audit_plans.id'))
    department_id      = db.Column(db.Integer, db.ForeignKey('departments.id'))
    audit_type         = db.Column(db.String(50))
    scheduled_date     = db.Column(db.String(20))
    actual_date        = db.Column(db.String(20))
    lead_auditor       = db.Column(db.String(100))
    audit_team         = db.Column(db.String(200))   # comma-separated names
    scope              = db.Column(db.Text)
    objectives         = db.Column(db.Text)
    status             = db.Column(db.String(20), default='Planned')
    # Planned / In Progress / Completed / Cancelled
    opening_meeting    = db.Column(db.String(20))    # date
    closing_meeting    = db.Column(db.String(20))    # date
    summary            = db.Column(db.Text)
    closure_date       = db.Column(db.String(20))
    closed_by          = db.Column(db.String(100))
    final_remarks      = db.Column(db.Text)
    audit_result       = db.Column(db.String(80))
    followup_required  = db.Column(db.String(10))
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)
    department         = db.relationship('Department', foreign_keys=[department_id])
    checklist_items    = db.relationship('AuditChecklist', backref='schedule', lazy=True,
                                          cascade='all, delete-orphan')
    findings           = db.relationship('AuditFinding', backref='schedule', lazy=True,
                                          cascade='all, delete-orphan')

class ChecklistTemplate(db.Model):
    """
    Saved, editable checklist template per department.
    When an audit starts, the latest template for that department
    is automatically loaded as the audit checklist.
    """
    __tablename__ = 'checklist_templates'
    id            = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    audit_type    = db.Column(db.String(50), default='Internal')
    name          = db.Column(db.String(100))
    version       = db.Column(db.Integer, default=1)
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    department    = db.relationship('Department', foreign_keys=[department_id])
    items         = db.relationship('ChecklistTemplateItem', backref='template',
                                    lazy=True, cascade='all, delete-orphan',
                                    order_by='ChecklistTemplateItem.sequence')


class ChecklistTemplateItem(db.Model):
    """Single editable line in a checklist template."""
    __tablename__ = 'checklist_template_items'
    id            = db.Column(db.Integer, primary_key=True)
    template_id   = db.Column(db.Integer, db.ForeignKey('checklist_templates.id'))
    category      = db.Column(db.String(100))
    item_ref      = db.Column(db.String(30))    # e.g. FO-2.1
    question      = db.Column(db.Text)
    iosa_ref      = db.Column(db.String(100))   # regulatory reference
    sequence      = db.Column(db.Integer, default=0)


class AuditChecklist(db.Model):
    """
    Dynamic checklist item for each scheduled audit.
    If response = 'No' → finding REQUIRED before audit can be closed.
    """
    __tablename__ = 'audit_checklists'
    id              = db.Column(db.Integer, primary_key=True)
    schedule_id     = db.Column(db.String(30), db.ForeignKey('audit_schedules.id'))
    category        = db.Column(db.String(100))
    item_ref        = db.Column(db.String(30))    # e.g. FO-2.1 / IOSA ISM 1.1.1
    question        = db.Column(db.Text)
    response        = db.Column(db.String(10))    # Yes / No / N/A
    comment         = db.Column(db.Text)          # mandatory when No
    evidence        = db.Column(db.Text)          # evidence notes
    evidence_filename = db.Column(db.String(200)) # uploaded evidence file
    sequence        = db.Column(db.Integer, default=0)
    # Link to Finding generated from this checklist item
    linked_finding_id = db.Column(db.String(30), db.ForeignKey('audit_findings.id'), nullable=True)
    linked_finding    = db.relationship('AuditFinding',
                            foreign_keys=[linked_finding_id],
                            backref=db.backref('source_checklist_item', uselist=False))

class AuditFinding(db.Model):
    """
    Finding raised during an audit.
    Full lifecycle: Open → Assigned → Root Cause Submitted → CAP Submitted
                    → Under Safety Review → Accepted → Closed
    Auditee submits: root cause, corrective action, CAP, evidence.
    Safety reviews and accepts or returns for revision.
    """
    __tablename__ = 'audit_findings'
    id             = db.Column(db.String(30), primary_key=True)
    schedule_id    = db.Column(db.String(30), db.ForeignKey('audit_schedules.id'))
    finding_ref    = db.Column(db.String(30))    # e.g. F-001
    finding_title  = db.Column(db.String(200))   # short NCR title
    description    = db.Column(db.Text)
    category       = db.Column(db.String(50))
    severity       = db.Column(db.String(20))    # Major / Minor / Observation
    standard_ref   = db.Column(db.String(100))
    requirement    = db.Column(db.Text)
    evidence       = db.Column(db.Text)          # Auditor evidence notes
    # Full lifecycle status
    status = db.Column(db.String(40), default='Open')
    # Open / Assigned / Root Cause Submitted / CAP Submitted /
    # Under Safety Review / Accepted / Closed / Returned for Revision / Overdue
    assigned_to    = db.Column(db.String(100))   # auditee responsible person
    assigned_dept  = db.Column(db.String(100))
    assigned_date  = db.Column(db.String(20))
    # ── A. Root Cause (completed by Auditee) ─────────────────────────────
    root_cause          = db.Column(db.Text)
    investigation_notes = db.Column(db.Text)
    contributing_factors= db.Column(db.Text)
    root_cause_submitted_at = db.Column(db.DateTime)
    # ── B. Corrective Action (completed by Auditee) ──────────────────────
    immediate_action    = db.Column(db.Text)
    longterm_action     = db.Column(db.Text)
    # ── C. CAP (Corrective Action Plan) ──────────────────────────────────
    cap_responsible     = db.Column(db.String(100))
    cap_due_date        = db.Column(db.String(20))
    cap_status          = db.Column(db.String(30), default='Pending')
    # Pending / In Progress / Completed / Overdue
    cap_completion_pct  = db.Column(db.Integer, default=0)
    cap_submitted_at    = db.Column(db.DateTime)
    # ── D. Evidence files (filenames, comma-separated) ───────────────────
    evidence_files      = db.Column(db.Text)   # comma-separated filenames
    # ── E. Safety Review ─────────────────────────────────────────────────
    review_notes        = db.Column(db.Text)
    reviewed_by         = db.Column(db.String(100))
    review_date         = db.Column(db.String(20))
    revision_reason     = db.Column(db.Text)   # reason for returning for revision
    # ── F. Closure Verification ──────────────────────────────────────────
    closure_verified_by = db.Column(db.String(100))
    closure_date        = db.Column(db.String(20))
    closure_notes       = db.Column(db.Text)
    # ── G. Signatures ────────────────────────────────────────────────────
    sig_dept_manager    = db.Column(db.String(100))
    sig_auditor         = db.Column(db.String(100))
    sig_safety_manager  = db.Column(db.String(100))
    sig_date            = db.Column(db.String(20))
    # ── Links ─────────────────────────────────────────────────────────────
    hazard_id      = db.Column(db.String(30), db.ForeignKey('hazards.id'), nullable=True)
    linked_action_id = db.Column(db.String(30))   # Action module action
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    actions        = db.relationship('AuditAction', backref='finding', lazy=True,
                                      cascade='all, delete-orphan')

class AuditAction(db.Model):
    """Corrective action generated from an audit finding."""
    __tablename__ = 'audit_actions'
    id                   = db.Column(db.String(30), primary_key=True)
    finding_id           = db.Column(db.String(30), db.ForeignKey('audit_findings.id'))
    hazard_id            = db.Column(db.String(30), db.ForeignKey('hazards.id'), nullable=True)
    description          = db.Column(db.Text)
    action_type          = db.Column(db.String(30))  # Corrective / Preventive / Improvement
    owner                = db.Column(db.String(100))
    due_date             = db.Column(db.String(20))
    priority             = db.Column(db.String(20))  # High / Medium / Low
    status               = db.Column(db.String(20), default='Open')
    # Open / In Progress / Closed / Overdue
    implementation_notes = db.Column(db.Text)
    closed_date          = db.Column(db.String(20))
    # Follow-up / verification
    verified_by          = db.Column(db.String(100))
    verification_date    = db.Column(db.String(20))
    effectiveness        = db.Column(db.String(30))
    # Effective / Partially Effective / Ineffective
    effectiveness_notes  = db.Column(db.Text)
    reopen_reason        = db.Column(db.Text)
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)

# ═══════════════════════════════════════════════════════════════════════════════
#  SAFETY POLICY & OBJECTIVES MODULE — COMPONENT 1 OF SMS
#  ICAO Annex 19 / Doc 9859 — Added as extension, existing tables unchanged
# ═══════════════════════════════════════════════════════════════════════════════

class DistributionList(db.Model):
    __tablename__ = 'distribution_lists'
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100))
    email         = db.Column(db.String(200), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    position      = db.Column(db.String(100))
    is_active     = db.Column(db.Boolean, default=True)
    sag_role      = db.Column(db.String(80))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    department    = db.relationship('Department', foreign_keys=[department_id])

class EmailLog(db.Model):
    __tablename__ = 'email_logs'
    id              = db.Column(db.Integer, primary_key=True)
    subject         = db.Column(db.String(300))
    content_type    = db.Column(db.String(30))
    content_ref     = db.Column(db.String(50))
    sent_by         = db.Column(db.String(100))
    sent_at         = db.Column(db.DateTime, default=datetime.utcnow)
    recipient_count = db.Column(db.Integer, default=0)
    dept_filter     = db.Column(db.String(200))
    status          = db.Column(db.String(20), default='Sent')
    error_message   = db.Column(db.Text)

class SurveyResponse(db.Model):
    __tablename__ = 'survey_responses'
    id               = db.Column(db.Integer, primary_key=True)
    survey_id        = db.Column(db.Integer, db.ForeignKey('safety_surveys.id'))
    respondent_name  = db.Column(db.String(100))
    respondent_email = db.Column(db.String(200))
    department_id    = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    is_anonymous     = db.Column(db.Boolean, default=False)
    answers          = db.Column(db.Text)
    submitted_at     = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address       = db.Column(db.String(50))
    survey           = db.relationship('SafetySurvey', foreign_keys=[survey_id],
                                       backref=db.backref('responses', lazy=True))
    department       = db.relationship('Department', foreign_keys=[department_id])

class SafetyPolicy(db.Model):
    """Safety Policy Statement — versioned, signed by Accountable Manager."""
    __tablename__ = 'safety_policies'
    id            = db.Column(db.String(30), primary_key=True)
    version       = db.Column(db.String(10))      # REV0, REV1, REV2…
    version_num   = db.Column(db.Integer, default=0)
    title         = db.Column(db.String(200))
    content       = db.Column(db.Text)            # Full policy statement
    approved_by   = db.Column(db.String(100))     # Accountable Manager name
    approved_by_title = db.Column(db.String(100))
    effective_date = db.Column(db.String(20))
    review_date   = db.Column(db.String(20))
    status        = db.Column(db.String(20), default='Draft')
    # Draft / Active / Archived
    change_summary = db.Column(db.Text)           # What changed in this rev
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

class SafetyRole(db.Model):
    """Safety accountability — roles and responsibilities."""
    __tablename__ = 'safety_roles'
    id            = db.Column(db.String(30), primary_key=True)
    role_name     = db.Column(db.String(100))
    # Accountable Manager / Safety Manager / Dept Manager / Safety Officer…
    role_type     = db.Column(db.String(50))
    person_name   = db.Column(db.String(100))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    responsibilities = db.Column(db.Text)
    authority     = db.Column(db.Text)
    contact_email = db.Column(db.String(100))
    contact_phone = db.Column(db.String(50))
    effective_from = db.Column(db.String(20))
    active        = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    department    = db.relationship('Department', foreign_keys=[department_id])

class SafetyPersonnel(db.Model):
    """Key safety personnel database."""
    __tablename__ = 'safety_personnel'
    id            = db.Column(db.String(30), primary_key=True)
    name          = db.Column(db.String(100))
    position      = db.Column(db.String(100))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    sms_role      = db.Column(db.String(100))
    # e.g. Accountable Manager / Safety Manager / SMS Coordinator
    qualifications = db.Column(db.Text)
    contact_email = db.Column(db.String(100))
    contact_phone = db.Column(db.String(50))
    sms_trained   = db.Column(db.Boolean, default=False)
    training_date = db.Column(db.String(20))
    active        = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    department    = db.relationship('Department', foreign_keys=[department_id])

class ERPlan(db.Model):
    """Emergency Response Plan — scenarios, procedures, contacts."""
    __tablename__ = 'erp'
    id              = db.Column(db.String(30), primary_key=True)
    erp_ref         = db.Column(db.String(30))   # e.g. ERP-001
    scenario_type   = db.Column(db.String(50))
    # Accident / Serious Incident / Incident / Crisis / Security / Medical
    title           = db.Column(db.String(200))
    description     = db.Column(db.Text)
    activation_criteria = db.Column(db.Text)
    response_procedures = db.Column(db.Text)     # Step-by-step
    responsible_roles   = db.Column(db.Text)     # comma-separated role IDs / names
    emergency_contacts  = db.Column(db.Text)     # JSON-like text
    resources_required  = db.Column(db.Text)
    notification_list   = db.Column(db.Text)     # Who must be notified
    review_date         = db.Column(db.String(20))
    version             = db.Column(db.String(10), default='REV0')
    status              = db.Column(db.String(20), default='Active')
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)

class SMSDocument(db.Model):
    """Document Control System — full lifecycle with revision history."""
    __tablename__ = 'sms_documents'
    id            = db.Column(db.String(50), primary_key=True)
    # Auto-generated: TYPE-DEPT-YEAR-SEQ-REV e.g. SOP-FO-2026-001-REV0
    doc_type      = db.Column(db.String(10))
    # POL / MAN / SOP / RA / AUD / MOC / INV / TRN / NEWS
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    title         = db.Column(db.String(200))
    description   = db.Column(db.Text)
    content       = db.Column(db.Text)           # Document body / notes
    version       = db.Column(db.String(10))     # REV0, REV1…
    version_num   = db.Column(db.Integer, default=0)
    seq_num       = db.Column(db.Integer, default=1)  # sequential per type+dept+year
    status        = db.Column(db.String(20), default='Draft')
    # Draft / Under Review / Approved / Archived
    created_by    = db.Column(db.String(100))
    reviewed_by   = db.Column(db.String(100))
    approved_by   = db.Column(db.String(100))
    effective_date = db.Column(db.String(20))
    review_due    = db.Column(db.String(20))
    parent_doc_id = db.Column(db.String(50))     # previous version ID
    change_summary = db.Column(db.Text)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    department    = db.relationship('Department', foreign_keys=[department_id])

# ═══════════════════════════════════════════════════════════════════════════════
#  DOCUMENT TRACEABILITY BACKBONE
#  Central linking table — connects SMSDocument to every module in the SMS
#  ICAO Annex 19 §3.5 / IOSA ISM 1.1 — Full auditability
# ═══════════════════════════════════════════════════════════════════════════════

class DocumentLink(db.Model):
    """
    Universal linking table — one document can be linked to many entities
    and one entity can have many documents.

    entity_type values:
        hazard | risk | action | audit_schedule | audit_finding |
        audit_action | moc | investigation | training | erp | spi_indicator
    """
    __tablename__ = 'document_links'
    id            = db.Column(db.Integer, primary_key=True)
    document_id   = db.Column(db.String(50), db.ForeignKey('sms_documents.id'), nullable=False)
    entity_type   = db.Column(db.String(30), nullable=False)
    entity_id     = db.Column(db.String(50), nullable=False)
    link_reason   = db.Column(db.String(200))  # e.g. "SOP referenced in audit checklist"
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    document      = db.relationship('SMSDocument', backref=db.backref('links', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('document_id', 'entity_type', 'entity_id',
                            name='uq_doc_entity'),
    )

# ═══════════════════════════════════════════════════════════════════════════════
#  SAFETY RISK MANAGEMENT (SRM) — EXTENDED MODELS
#  Extends existing Risk + Control + Hazard with SRM-grade fields
#  ICAO Annex 19 §5 / Doc 9859 Ch.5 — Added as extension
# ═══════════════════════════════════════════════════════════════════════════════

class RiskOccurrence(db.Model):
    """Tracks repeated occurrences of the same hazard for trend analysis."""
    __tablename__ = 'risk_occurrences'
    id            = db.Column(db.Integer, primary_key=True)
    hazard_id     = db.Column(db.String(30), db.ForeignKey('hazards.id'), nullable=False)
    occurrence_date = db.Column(db.String(20))
    description   = db.Column(db.Text)
    source        = db.Column(db.String(30))  # Report / ASR / Audit / Investigation
    linked_report_id = db.Column(db.String(30))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

class RiskAction(db.Model):
    """Direct Risk → Action link (separate from hazard-level actions)."""
    __tablename__ = 'risk_actions'
    id            = db.Column(db.String(30), primary_key=True)
    risk_id       = db.Column(db.String(30), db.ForeignKey('risks.id'), nullable=False)
    hazard_id     = db.Column(db.String(30), db.ForeignKey('hazards.id'))
    description   = db.Column(db.Text)
    owner         = db.Column(db.String(100))
    due_date      = db.Column(db.String(20))
    priority      = db.Column(db.String(20), default='Medium')
    status        = db.Column(db.String(20), default='Open')
    # Open / In Progress / Closed / Overdue
    effectiveness = db.Column(db.String(30))
    closed_date   = db.Column(db.String(20))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    risk          = db.relationship('Risk', backref=db.backref('risk_actions', lazy=True))

# ═══════════════════════════════════════════════════════════════════════════════
#  RISK ASSESSMENT MODULE — Jav/SMS/001 Rev 01
#  Exact replica of Jordan Aviation Risk Assessment Form
#  Pages 1-5 of the uploaded form → database structure
# ═══════════════════════════════════════════════════════════════════════════════

class RiskAssessment(db.Model):
    """
    Pages 1 & 2 of the form: Administrator + General Information.
    One RiskAssessment per hazard (the header of the form).
    """
    __tablename__ = 'risk_assessments'
    id                    = db.Column(db.String(30), primary_key=True)
    # Page 1 — Administrator
    control_number        = db.Column(db.String(50))    # e.g. JAV/RA/2024/001
    responsible_name      = db.Column(db.String(100))
    assessors_names       = db.Column(db.String(300))   # comma-separated
    assessment_date       = db.Column(db.String(20))
    next_review_date      = db.Column(db.String(20))
    title                 = db.Column(db.String(200))
    # Page 2 — General Information
    hazard_id             = db.Column(db.String(30), db.ForeignKey('hazards.id'), unique=True)
    department_id         = db.Column(db.Integer, db.ForeignKey('departments.id'))
    general_description   = db.Column(db.Text)
    reasons               = db.Column(db.Text)   # Reasons For Risk Assessment
    risk_level_prior      = db.Column(db.String(20))   # e.g. INTOLERABLE
    risk_level_after      = db.Column(db.String(20))   # e.g. TOLERABLE
    management_acceptance = db.Column(db.String(20))   # Accepted / Not Accepted
    acceptance_date       = db.Column(db.String(20))
    # Signatures
    prepared_by_name      = db.Column(db.String(100))
    prepared_by_position  = db.Column(db.String(100))
    reviewed_by_name      = db.Column(db.String(100))
    reviewed_by_position  = db.Column(db.String(100))
    approved_by_name      = db.Column(db.String(100))
    approved_by_position  = db.Column(db.String(100))
    # Lifecycle Status
    status                = db.Column(db.String(20), default='Draft')
    # Draft → Submitted → Active → Under Review → Closed
    submitted_date        = db.Column(db.String(20))   # when user clicks Submit
    activated_date        = db.Column(db.String(20))   # when RA becomes Active
    closed_date           = db.Column(db.String(20))   # when RA is closed
    revision              = db.Column(db.Integer, default=0)  # REV0, REV1, REV2…
    parent_ra_id          = db.Column(db.String(30))   # previous revision's RA id
    created_at            = db.Column(db.DateTime, default=datetime.utcnow)
    # Relationships
    hazard                = db.relationship('Hazard', backref=db.backref('risk_assessment', uselist=False))
    department            = db.relationship('Department', foreign_keys=[department_id])
    rows                  = db.relationship('RARow', backref='assessment', lazy=True,
                                             cascade='all, delete-orphan',
                                             order_by='RARow.seq_num')
    mitigations           = db.relationship('RAMitigation', backref='assessment', lazy=True,
                                              cascade='all, delete-orphan')
    reviews               = db.relationship('RAReview', backref='assessment', lazy=True,
                                             cascade='all, delete-orphan')

class RARow(db.Model):
    """
    Page 3 — Risk Table rows.
    One row = one risk scenario within the assessment.
    Maps directly to each row of the risk table in the form.
    """
    __tablename__ = 'ra_rows'
    id                        = db.Column(db.Integer, primary_key=True)
    assessment_id             = db.Column(db.String(30), db.ForeignKey('risk_assessments.id'), nullable=False)
    risk_id                   = db.Column(db.String(30), db.ForeignKey('risks.id'), nullable=True)
    seq_num                   = db.Column(db.Integer)        # SEQ column (1, 2, 3…)
    # Form columns — left section
    type_of_activity          = db.Column(db.String(200))    # "Type of Activity" column
    generic_hazard            = db.Column(db.String(200))    # "Generic Hazard" column
    specific_components       = db.Column(db.Text)           # "Specific Components of the Hazard"
    consequences              = db.Column(db.Text)           # "Hazard Related Consequences"
    # Initial risk (before controls)
    likelihood_initial        = db.Column(db.Integer)        # 1-5
    severity_initial          = db.Column(db.String(2))      # A-E
    risk_index_initial        = db.Column(db.String(5))      # e.g. 4B
    risk_tolerance_initial    = db.Column(db.String(20))     # INTOLERABLE/TOLERABLE/ACCEPTABLE
    # Controls
    current_defenses          = db.Column(db.Text)           # "Current Defenses" column
    further_mitigations       = db.Column(db.Text)           # "Further Mitigation Measures" column
    # Residual risk (after controls)
    likelihood_residual       = db.Column(db.Integer)
    severity_residual         = db.Column(db.String(2))
    risk_index_residual       = db.Column(db.String(5))
    risk_tolerance_residual   = db.Column(db.String(20))

class RAMitigation(db.Model):
    """
    Page 4 — Implementation of Mitigations Responsibilities.
    Each row = one mitigation with a responsible manager.
    """
    __tablename__ = 'ra_mitigations'
    id                 = db.Column(db.Integer, primary_key=True)
    assessment_id      = db.Column(db.String(30), db.ForeignKey('risk_assessments.id'), nullable=False)
    hazard_seq         = db.Column(db.String(10))   # "Hazard Seq #" — references RARow.seq_num
    mitigation         = db.Column(db.Text)          # "Mitigations" column
    responsible_manager = db.Column(db.String(100)) # "Responsible Manager"
    due_date           = db.Column(db.String(20))
    action_id          = db.Column(db.String(30))   # linked Action in unified system
    status             = db.Column(db.String(20), default='Open')

class RAReview(db.Model):
    """
    Page 5 — Risk Mitigation Review.
    Tracks effectiveness of each mitigation after implementation.
    """
    __tablename__ = 'ra_reviews'
    id                       = db.Column(db.Integer, primary_key=True)
    assessment_id            = db.Column(db.String(30), db.ForeignKey('risk_assessments.id'), nullable=False)
    risk_mitigation          = db.Column(db.String(200))  # "Risk Mitigation" — which mitigation
    review_of_effectiveness  = db.Column(db.Text)         # "Review Of Mitigation Effectivity"
    effectiveness_rating     = db.Column(db.String(30))   # Effective / Partially Effective / Ineffective
    date_completed           = db.Column(db.String(20))   # "Date Completed"
    actioner                 = db.Column(db.String(100))  # "Actioner"

# ═══════════════════════════════════════════════════════════════════════════════
#  GUIDED RA WORKFLOW — STEP TRACKING
#  Tracks progress through the 6-step risk assessment wizard
# ═══════════════════════════════════════════════════════════════════════════════

class RAChecklistItem(db.Model):
    """Standard control checklist items checked during Step 4."""
    __tablename__ = 'ra_checklist_items'
    id            = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.String(30), db.ForeignKey('risk_assessments.id'))
    row_seq       = db.Column(db.Integer)         # which RARow this belongs to
    category      = db.Column(db.String(50))      # SOP / Training / Monitoring / Equipment / Other
    description   = db.Column(db.String(200))
    checked       = db.Column(db.Boolean, default=False)
    notes         = db.Column(db.Text)


class Employee(db.Model):
    """Mobile app employees — separate from admin/SAG users."""
    __tablename__ = 'employees'
    id            = db.Column(db.Integer, primary_key=True)
    employee_id   = db.Column(db.String(30), unique=True, nullable=False)  # e.g. JA-001
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name     = db.Column(db.String(120), nullable=False)
    email         = db.Column(db.String(120))
    mobile        = db.Column(db.String(30))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    role          = db.Column(db.String(50), default='employee')  # employee, captain, engineer, etc.
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    last_login    = db.Column(db.DateTime)

    department = db.relationship('Department', foreign_keys=[department_id])

    def __repr__(self):
        return f'<Employee {self.employee_id} {self.full_name}>'


class ApiToken(db.Model):
    """Persistent auth tokens for mobile (Flutter) sessions.

    Replaces the in-memory _token_store dict so tokens survive Render
    spin-down and Gunicorn worker restarts. Token strings are generated
    with secrets.token_urlsafe(32) — same as before. Expired rows are
    cleaned up lazily on each login call.
    """
    __tablename__ = 'api_tokens'
    id         = db.Column(db.Integer, primary_key=True)
    token      = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id    = db.Column(db.String(30), nullable=False)   # 'emp_5' or 'usr_3'
    username   = db.Column(db.String(80), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_expired(self):
        return datetime.utcnow() > self.expires_at


class DeviceToken(db.Model):
    """FCM push-notification tokens for Flutter mobile sessions.

    One row per (user_id, device). Upserted on each login or token refresh
    so a user can have at most one active FCM token per device fingerprint.
    Used by Flask notification helpers to push status updates to the app.
    """
    __tablename__ = 'device_tokens'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.String(30), nullable=False, index=True)  # 'emp_5' or 'usr_3'
    fcm_token  = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'fcm_token', name='uq_device_token'),)


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 1 — GOVERNANCE & AUTHORITY LAYER
#  ICAO Annex 19 §4 / Doc 9859 §§3–4 — Management Commitment & Accountability
#  Gaps: 1 (SRB/MRB), 3 (Risk Acceptance), 4 (AE Identity), 10 (Four-Eyes)
# ═══════════════════════════════════════════════════════════════════════════════

class AccountableExecutive(db.Model):
    """
    ICAO Doc 9859 §3.2 — Accountable Executive (AE).
    The single named individual responsible for effective implementation of SMS.
    Linked to a real User account for approval queue integration.
    """
    __tablename__ = 'accountable_executives'
    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    full_name        = db.Column(db.String(120), nullable=False)
    title            = db.Column(db.String(100))   # e.g. Accountable Manager / CEO / SVP Operations
    email            = db.Column(db.String(120))
    phone            = db.Column(db.String(50))
    employee_number  = db.Column(db.String(30))
    authority_scope  = db.Column(db.Text)          # Documented authority & responsibilities
    appointment_ref  = db.Column(db.String(50))    # e.g. JAV/AE/2026/001
    effective_from   = db.Column(db.String(20))
    effective_to     = db.Column(db.String(20))    # null = current incumbent
    is_current       = db.Column(db.Boolean, default=True)
    appointment_doc  = db.Column(db.String(200))   # uploaded appointment letter filename
    notes            = db.Column(db.Text)
    created_by       = db.Column(db.String(100))
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    user             = db.relationship('User', foreign_keys=[user_id],
                           backref=db.backref('ae_profile', uselist=False))


class SRBMeeting(db.Model):
    """
    Safety Review Board / Management Review Board meeting record.
    ICAO Annex 19 §4.1 — SMS management review.
    Full lifecycle: Scheduled → In Progress → Minutes Draft → Completed / Cancelled.
    """
    __tablename__ = 'srb_meetings'
    id              = db.Column(db.String(30), primary_key=True)   # SRB/2026/001
    meeting_type    = db.Column(db.String(20), default='SRB')
    # SRB (Safety Review Board) / MRB (Management Review Board) / Ad-Hoc / Emergency
    title           = db.Column(db.String(200))
    scheduled_date  = db.Column(db.String(20))
    actual_date     = db.Column(db.String(20))
    start_time      = db.Column(db.String(10))
    end_time        = db.Column(db.String(10))
    venue           = db.Column(db.String(200))
    chair_person    = db.Column(db.String(100))
    secretary       = db.Column(db.String(100))
    status          = db.Column(db.String(20), default='Scheduled')
    # Scheduled / In Progress / Minutes Draft / Completed / Cancelled
    quorum_met      = db.Column(db.Boolean, default=False)
    quorum_count    = db.Column(db.Integer, default=0)
    objectives      = db.Column(db.Text)
    minutes_text    = db.Column(db.Text)          # full narrative minutes
    key_outcomes    = db.Column(db.Text)
    next_meeting_date = db.Column(db.String(20))
    minutes_approved_by = db.Column(db.String(100))
    minutes_approved_date = db.Column(db.String(20))
    ae_id           = db.Column(db.Integer, db.ForeignKey('accountable_executives.id'), nullable=True)
    created_by      = db.Column(db.String(100))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Relationships
    ae              = db.relationship('AccountableExecutive', foreign_keys=[ae_id],
                          backref=db.backref('srb_meetings', lazy=True))
    agenda_items    = db.relationship('SRBAgendaItem', backref='meeting', lazy=True,
                          cascade='all, delete-orphan',
                          order_by='SRBAgendaItem.item_number')
    attendees       = db.relationship('SRBAttendee', backref='meeting', lazy=True,
                          cascade='all, delete-orphan',
                          order_by='SRBAttendee.sort_order')
    decisions       = db.relationship('SRBDecision', backref='meeting', lazy=True,
                          cascade='all, delete-orphan')


class SRBAgendaItem(db.Model):
    """
    Individual agenda item within an SRB/MRB meeting.
    Can be sourced from an SPI escalation, hazard, audit finding, or standing item.
    """
    __tablename__ = 'srb_agenda_items'
    id               = db.Column(db.Integer, primary_key=True)
    meeting_id       = db.Column(db.String(30), db.ForeignKey('srb_meetings.id'), nullable=False)
    item_number      = db.Column(db.Integer)          # 1, 2, 3…
    title            = db.Column(db.String(200))
    description      = db.Column(db.Text)
    item_type        = db.Column(db.String(30), default='Standing')
    # Standing / SPI Review / Hazard Review / Audit Finding / Investigation /
    # Risk Acceptance / CAP Review / Action Review / Other
    source_type      = db.Column(db.String(30))       # spi_escalation / hazard / audit / investigation
    source_id        = db.Column(db.String(50))       # linked record ID
    presenter        = db.Column(db.String(100))
    time_allocated   = db.Column(db.Integer)          # minutes
    status           = db.Column(db.String(20), default='Pending')
    # Pending / Discussed / Deferred / Withdrawn
    discussion_notes = db.Column(db.Text)
    decision         = db.Column(db.Text)
    action_required  = db.Column(db.Boolean, default=False)
    deferred_to_meeting_id = db.Column(db.String(30), nullable=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)


class SRBAttendee(db.Model):
    """Attendance record for an SRB/MRB meeting."""
    __tablename__ = 'srb_attendees'
    id              = db.Column(db.Integer, primary_key=True)
    meeting_id      = db.Column(db.String(30), db.ForeignKey('srb_meetings.id'), nullable=False)
    person_name     = db.Column(db.String(100))
    role_title      = db.Column(db.String(100))       # e.g. Safety Manager / Flight Ops Director
    department      = db.Column(db.String(100))
    is_required     = db.Column(db.Boolean, default=True)   # quorum member?
    attended        = db.Column(db.Boolean, default=False)
    apology_given   = db.Column(db.Boolean, default=False)
    proxy_for       = db.Column(db.String(100))       # if attending as proxy for someone
    sort_order      = db.Column(db.Integer, default=0)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)


class SRBDecision(db.Model):
    """
    Formal decision recorded at an SRB/MRB meeting.
    Each decision generates an auditable action item.
    """
    __tablename__ = 'srb_decisions'
    id              = db.Column(db.Integer, primary_key=True)
    meeting_id      = db.Column(db.String(30), db.ForeignKey('srb_meetings.id'), nullable=False)
    agenda_item_id  = db.Column(db.Integer, db.ForeignKey('srb_agenda_items.id'), nullable=True)
    decision_ref    = db.Column(db.String(30))        # e.g. SRB/2026/001-D01
    decision_text   = db.Column(db.Text)
    decision_type   = db.Column(db.String(20), default='Noted')
    # Approved / Rejected / Deferred / Noted / Action Required / Escalated
    responsible_party = db.Column(db.String(100))
    due_date        = db.Column(db.String(20))
    linked_action_id = db.Column(db.String(30), nullable=True)   # FK to actions.id
    status          = db.Column(db.String(20), default='Open')   # Open / In Progress / Closed
    closed_date     = db.Column(db.String(20))
    closure_notes   = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    agenda_item     = db.relationship('SRBAgendaItem', foreign_keys=[agenda_item_id],
                          backref=db.backref('decisions', lazy=True))


class RiskAcceptance(db.Model):
    """
    ICAO Doc 9859 §5.5 — Formal risk acceptance authority.
    INTOLERABLE risks MUST be formally accepted by the AE with documented justification.
    Creates an immutable governance record with full audit trail.
    """
    __tablename__ = 'risk_acceptances'
    id               = db.Column(db.Integer, primary_key=True)
    ref_number       = db.Column(db.String(30))       # e.g. RA-ACC/2026/001
    risk_id          = db.Column(db.String(30), db.ForeignKey('risks.id'), nullable=True)
    hazard_id        = db.Column(db.String(30), db.ForeignKey('hazards.id'), nullable=True)
    risk_tolerance   = db.Column(db.String(20))       # INTOLERABLE / TOLERABLE
    risk_index       = db.Column(db.String(5))
    risk_description = db.Column(db.Text)
    justification    = db.Column(db.Text)             # Why acceptance is warranted
    mitigations_in_place = db.Column(db.Text)         # What controls are already active
    conditions       = db.Column(db.Text)             # Conditions attached to acceptance
    valid_until      = db.Column(db.String(20))       # Expiry of acceptance
    review_date      = db.Column(db.String(20))
    # Workflow
    submitted_by     = db.Column(db.String(100))
    submitted_date   = db.Column(db.String(20))
    safety_mgr_review = db.Column(db.Text)            # Safety Manager pre-review
    safety_mgr_by    = db.Column(db.String(100))
    safety_mgr_date  = db.Column(db.String(20))
    ae_id            = db.Column(db.Integer, db.ForeignKey('accountable_executives.id'), nullable=True)
    ae_decision      = db.Column(db.String(20))       # Approved / Rejected / Conditional
    ae_decision_by   = db.Column(db.String(100))      # AE full name on record
    ae_decision_date = db.Column(db.String(20))
    ae_notes         = db.Column(db.Text)
    status           = db.Column(db.String(30), default='Pending Safety Review')
    # Pending Safety Review / Pending AE / Approved / Rejected / Conditional / Expired
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    # Relationships
    risk             = db.relationship('Risk', foreign_keys=[risk_id],
                           backref=db.backref('acceptance_record', uselist=False))
    hazard           = db.relationship('Hazard', foreign_keys=[hazard_id],
                           backref=db.backref('risk_acceptances', lazy=True))
    ae               = db.relationship('AccountableExecutive', foreign_keys=[ae_id],
                           backref=db.backref('risk_acceptances', lazy=True))


class GovernanceAuditLog(db.Model):
    """
    ICAO Doc 9859 §3.4 — Four-eyes governance enforcement log.
    Immutable audit trail of every governance decision: who did what, when,
    and whether segregation-of-duties was respected.
    Reporter cannot self-close. Submitter cannot approve.
    """
    __tablename__ = 'governance_audit_log'
    id              = db.Column(db.Integer, primary_key=True)
    entity_type    = db.Column(db.String(50))    # SRBMeeting / RiskAcceptance / AccountableExecutive
    entity_id      = db.Column(db.String(50))
    action         = db.Column(db.String(50))    # Created / Updated / Approved / Rejected / Deleted
    performed_by   = db.Column(db.String(100))
    detail         = db.Column(db.Text)
    ip_address     = db.Column(db.String(45))
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)


class InvestigationEvent(db.Model):
    """
    Immutable audit trail for every lifecycle stage transition in an investigation.
    ICAO Doc 9859 §6.3 — investigation progress must be formally documented.
    """
    __tablename__ = 'investigation_events'
    id              = db.Column(db.Integer, primary_key=True)
    investigation_id = db.Column(db.String(30), db.ForeignKey('investigations.id'), nullable=False)
    event_type      = db.Column(db.String(30))   # stage_advance / note / notification / closure
    from_stage      = db.Column(db.String(40))
    to_stage        = db.Column(db.String(40))
    note            = db.Column(db.Text)
    performed_by   = db.Column(db.String(100))
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)


class ERPDrill(db.Model):
    """
    ICAO Annex 19 §8.3 / Doc 9859 §9 — Emergency drill records.
    Drills must be conducted periodically and outcomes documented to verify ERP effectiveness.
    """
    __tablename__ = 'erp_drills'
    id              = db.Column(db.Integer, primary_key=True)
    erp_id          = db.Column(db.String(30), db.ForeignKey('erp.id'), nullable=False)
    drill_ref       = db.Column(db.String(30))         # e.g. DRILL-2026-001
    drill_type      = db.Column(db.String(30), default='Table-Top')
    # Table-Top / Full-Scale / Partial / Communications / Notification
    drill_date      = db.Column(db.String(20))
    duration_min    = db.Column(db.Integer)            # Duration in minutes
    facilitator     = db.Column(db.String(100))
    participants    = db.Column(db.Text)               # Names / departments involved
    participant_count = db.Column(db.Integer, default=0)
    scenario_brief  = db.Column(db.Text)               # What was simulated
    objectives      = db.Column(db.Text)               # What was being tested
    observations    = db.Column(db.Text)               # What was observed during
    strengths       = db.Column(db.Text)               # What worked well
    deficiencies    = db.Column(db.Text)               # Gaps found
    recommendations = db.Column(db.Text)               # Improvement actions
    action_items    = db.Column(db.Text)               # Specific follow-up items
    erp_update_required = db.Column(db.Boolean, default=False)
    erp_updated_date    = db.Column(db.String(20))
    outcome         = db.Column(db.String(20), default='Satisfactory')
    # Satisfactory / Needs Improvement / Unsatisfactory
    next_drill_due  = db.Column(db.String(20))
    created_by      = db.Column(db.String(100))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    erp             = db.relationship('ERPlan', foreign_keys=[erp_id],
                          backref=db.backref('drills', lazy=True, order_by='ERPDrill.drill_date.desc()'))


class ERPActivation(db.Model):
    """
    Record of actual ERP activations (real emergencies).
    ICAO Doc 9859 §9.3 — actual activation history must be maintained.
    """
    __tablename__ = 'erp_activations'
    id              = db.Column(db.Integer, primary_key=True)
    erp_id          = db.Column(db.String(30), db.ForeignKey('erp.id'), nullable=False)
    activation_ref  = db.Column(db.String(30))         # e.g. ACT-2026-001
    investigation_id = db.Column(db.String(30), db.ForeignKey('investigations.id'), nullable=True)
    activated_at    = db.Column(db.DateTime)
    activated_by    = db.Column(db.String(100))
    activation_reason = db.Column(db.Text)
    # Notification tracking
    caa_notified    = db.Column(db.Boolean, default=False)
    caa_notified_at = db.Column(db.DateTime, nullable=True)
    caa_ref         = db.Column(db.String(50))
    icao_notified   = db.Column(db.Boolean, default=False)
    icao_notified_at = db.Column(db.DateTime, nullable=True)
    media_statement  = db.Column(db.Boolean, default=False)
    nok_notified     = db.Column(db.Boolean, default=False)   # Next of Kin (accidents)
    # Timeline
    deactivated_at   = db.Column(db.DateTime, nullable=True)
    deactivated_by   = db.Column(db.String(100))
    duration_hours   = db.Column(db.Float)
    # Post-activation
    actions_taken    = db.Column(db.Text)
    effectiveness    = db.Column(db.String(30))   # Effective / Partially Effective / Ineffective
    lessons_learned  = db.Column(db.Text)
    erp_update_required = db.Column(db.Boolean, default=False)
    status          = db.Column(db.String(20), default='Active')
    # Active / Deactivated / Closed
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    erp             = db.relationship('ERPlan', foreign_keys=[erp_id],
                          backref=db.backref('activations', lazy=True))
    investigation   = db.relationship('Investigation', foreign_keys=[investigation_id],
                          backref=db.backref('erp_activations', lazy=True))


class ComplianceObligation(db.Model):
    """
    Regulatory Compliance Register — ICAO Doc 9859 §4.1 / Annex 19 §2.
    Tracks mandatory regulatory requirements, their compliance status, and evidence.
    Covers: ICAO Standards, CAA regulations, IOSA standards, EASA/FAA if applicable.
    """
    __tablename__ = 'compliance_obligations'
    id              = db.Column(db.Integer, primary_key=True)
    ref_number      = db.Column(db.String(30), unique=True)    # e.g. COMP-2026-001
    regulation_body = db.Column(db.String(50))    # ICAO / JCAR / EASA / FAA / IOSA / Internal
    standard_ref    = db.Column(db.String(100))   # e.g. ICAO Annex 19 §3.1.1
    requirement_title = db.Column(db.String(200))
    requirement_text  = db.Column(db.Text)
    applicability   = db.Column(db.String(200))   # Which operations / departments
    obligation_type = db.Column(db.String(30), default='Ongoing')
    # Ongoing / Periodic / One-Time / Conditional
    compliance_status = db.Column(db.String(30), default='Under Review')
    # Compliant / Non-Compliant / Partially Compliant / Under Review / Not Applicable / Exempt
    evidence_description = db.Column(db.Text)    # What evidence demonstrates compliance
    evidence_location    = db.Column(db.String(200))  # Where to find evidence
    responsible_person   = db.Column(db.String(100))
    department_id   = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    review_frequency = db.Column(db.String(20), default='Annual')
    # Monthly / Quarterly / Semi-Annual / Annual / Event-Based
    last_reviewed   = db.Column(db.String(20))
    next_review_due = db.Column(db.String(20))
    finding_ref     = db.Column(db.String(30))    # linked CAA finding if non-compliant
    linked_action_id = db.Column(db.String(30))   # corrective action if gap exists
    notes           = db.Column(db.Text)
    priority        = db.Column(db.String(20), default='Medium')  # Critical / High / Medium / Low
    created_by      = db.Column(db.String(100))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    department      = db.relationship('Department', foreign_keys=[department_id],
                          backref=db.backref('compliance_obligations', lazy=True))

class SPIEventLink(db.Model):
    """
    ICAO Annex 19 / Doc 9859 — Operational event linked to SPI indicator.
    Created automatically by the SPI Intelligence Mapper when events occur.
    Purely additive — never modifies existing SPI calculations.
    """
    __tablename__ = 'spi_event_links'
    id            = db.Column(db.Integer, primary_key=True)
    spi_id        = db.Column(db.Integer, db.ForeignKey('spi_indicators.id'), nullable=False)
    # Source event
    event_type    = db.Column(db.String(30))   # hazard_report / asr / investigation / audit_finding
                                               # risk_assessment / erp_activation / action / safety_promo
    event_id      = db.Column(db.String(50))   # e.g. HR-SMS-01 / ASR-001 / INV-SMS-01
    event_title   = db.Column(db.String(200))  # human-readable summary
    event_date    = db.Column(db.String(20))   # YYYY-MM-DD
    # Context
    department_id = db.Column(db.Integer)
    category      = db.Column(db.String(100))  # occurrence category / hazard class
    severity      = db.Column(db.String(20))   # Critical / High / Medium / Low
    match_reason  = db.Column(db.String(300))  # why it was linked — e.g. "keyword:runway"
    # Audit
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    # Relationship back to indicator
    indicator     = db.relationship('SPIIndicator',
                        backref=db.backref('event_links', lazy='dynamic'))


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTERPRISE CONTINUOUS COMPLIANCE & AUDIT VERIFICATION ENGINE
#  ICAO Annex 19 / Doc 9859 / IOSA ISM / EASA SMS Oversight
#  Additive only — no existing tables modified
# ═══════════════════════════════════════════════════════════════════════════════

class AuditVerificationItem(db.Model):
    """
    Audit Verification Item (AVI) — the core record of the continuous
    compliance engine.  Created automatically when any corrective action,
    mitigation, investigation recommendation, SPI exceedance, or governance
    action is generated anywhere in the SMS.  Survives until an auditor
    confirms operational effectiveness during a real audit cycle.

    Lifecycle:
      Pending → Scheduled → In Verification → Verified Effective
                                             → Verified Ineffective → Reopened
                                             → Escalated
    """
    __tablename__ = 'audit_verification_items'

    id              = db.Column(db.Integer, primary_key=True)

    # ── Origin ────────────────────────────────────────────────────────────────
    source_module       = db.Column(db.String(50))   # asr / hazard / investigation /
                                                     # risk / action / spi / erp /
                                                     # audit_finding / moc / safety_promo / cap
    source_record_id    = db.Column(db.String(50))   # FK to originating record (string ID)
    source_description  = db.Column(db.Text)         # human-readable trigger summary

    # ── Cross-module linkage ───────────────────────────────────────────────────
    linked_report_id        = db.Column(db.String(30))   # HazardReport / ASRReport
    linked_hazard_id        = db.Column(db.String(30))
    linked_investigation_id = db.Column(db.String(30))
    linked_spi_id           = db.Column(db.Integer, db.ForeignKey('spi_indicators.id'), nullable=True)
    linked_action_id        = db.Column(db.String(30))
    linked_audit_id         = db.Column(db.String(30))   # AuditSchedule id
    linked_finding_id       = db.Column(db.String(30))   # AuditFinding id
    linked_risk_id          = db.Column(db.String(30))   # RiskAssessment id

    # ── Verification specification ─────────────────────────────────────────────
    verification_area       = db.Column(db.String(100))  # e.g. "Flight Operations"
    verification_objective  = db.Column(db.Text)         # what must be verified
    required_evidence       = db.Column(db.Text)         # evidence auditor must collect
    effectiveness_criteria  = db.Column(db.Text)         # pass/fail criteria
    operational_risk        = db.Column(db.String(20), default='Medium')  # Critical/High/Medium/Low

    # ── Scheduling ─────────────────────────────────────────────────────────────
    department_id           = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    due_audit_cycle         = db.Column(db.String(30))   # e.g. "Q3-2026" or "2026-Annual"
    due_date                = db.Column(db.String(20))   # YYYY-MM-DD deadline

    # ── Status lifecycle ────────────────────────────────────────────────────────
    status = db.Column(db.String(30), default='Pending')
    # Pending / Scheduled / In Verification / Verified Effective /
    # Verified Ineffective / Escalated / Closed / Cancelled

    # ── Recurrence intelligence ─────────────────────────────────────────────────
    recurrence_flag         = db.Column(db.Boolean, default=False)
    recurrence_count        = db.Column(db.Integer, default=0)
    is_systemic             = db.Column(db.Boolean, default=False)
    recurrence_notes        = db.Column(db.Text)

    # ── Verification outcome (filled by auditor) ────────────────────────────────
    verified_by             = db.Column(db.String(100))
    verified_at             = db.Column(db.DateTime)
    scheduled_audit_id      = db.Column(db.String(30))   # AuditSchedule where it was verified
    effectiveness_result    = db.Column(db.String(30))   # Effective / Partially / Ineffective
    effectiveness_notes     = db.Column(db.Text)
    evidence_collected      = db.Column(db.Text)

    # ── Follow-up / escalation ──────────────────────────────────────────────────
    followup_required       = db.Column(db.Boolean, default=False)
    followup_notes          = db.Column(db.Text)
    escalation_required     = db.Column(db.Boolean, default=False)
    escalated_to_srb        = db.Column(db.Boolean, default=False)
    escalation_date         = db.Column(db.String(20))

    # ── Metadata ────────────────────────────────────────────────────────────────
    created_at              = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at              = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by              = db.Column(db.String(100))

    # ── Relationships ────────────────────────────────────────────────────────────
    department  = db.relationship('Department', foreign_keys=[department_id],
                      backref=db.backref('verification_items', lazy='dynamic'))
    linked_spi  = db.relationship('SPIIndicator', foreign_keys=[linked_spi_id],
                      backref=db.backref('verification_items', lazy='dynamic'))
