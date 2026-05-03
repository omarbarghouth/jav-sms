from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Department(db.Model):
    __tablename__ = 'departments'
    id            = db.Column(db.Integer, primary_key=True)
    code          = db.Column(db.String(10), unique=True, nullable=False)
    name          = db.Column(db.String(100), nullable=False)
    color         = db.Column(db.String(20), default='#1e40af')

class HazardReport(db.Model):
    __tablename__ = 'hazard_reports'
    id            = db.Column(db.String(30), primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    location      = db.Column(db.String(200))
    date          = db.Column(db.String(20))
    description   = db.Column(db.Text)
    immediate_action = db.Column(db.Text)
    suggested_mitigation = db.Column(db.Text)
    severity      = db.Column(db.String(2))
    likelihood    = db.Column(db.Integer)
    risk_index    = db.Column(db.String(5))
    reporter      = db.Column(db.String(100), default='Anonymous')
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
    Central action table — every action MUST have a source.
    Lifecycle: Open → In Progress → Completed → Verified → Closed
    Overdue is set automatically when due_date passes.
    """
    __tablename__ = 'actions'
    id               = db.Column(db.String(30), primary_key=True)
    # Source traceability — where did this action come from?
    source           = db.Column(db.String(40))
    # Hazard Report / ASR / Risk Assessment / Audit / MOC / Investigation
    linked_ref_id    = db.Column(db.String(30))   # finding ID, risk ID, MOC ID etc.
    # Direct FK links for full traceability
    hazard_id        = db.Column(db.String(30), db.ForeignKey('hazards.id'))
    linked_risk_id   = db.Column(db.String(30), db.ForeignKey('risks.id'), nullable=True)
    linked_audit_id  = db.Column(db.String(30), db.ForeignKey('audit_schedules.id'), nullable=True)
    linked_ra_id     = db.Column(db.String(30), db.ForeignKey('risk_assessments.id'), nullable=True)
    department_id    = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    # Action details
    description      = db.Column(db.Text)
    action_type      = db.Column(db.String(20), default='Corrective')
    # Corrective / Preventive / Improvement
    owner            = db.Column(db.String(100))
    due_date         = db.Column(db.String(20))
    priority         = db.Column(db.String(20), default='Medium')   # High / Medium / Low
    # Full lifecycle status
    status           = db.Column(db.String(20), default='Open')
    # Open → In Progress → Completed → Verified → Closed   (Overdue = auto)
    completed_date   = db.Column(db.String(20))
    closed_date      = db.Column(db.String(20))
    # Effectiveness (filled after completion)
    effectiveness    = db.Column(db.String(30))
    # Effective / Partially Effective / Ineffective
    effectiveness_review = db.Column(db.Text)
    verified_by      = db.Column(db.String(100))
    verified_date    = db.Column(db.String(20))
    # If ineffective — reopen tracking
    reopen_count     = db.Column(db.Integer, default=0)
    reopen_reason    = db.Column(db.Text)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    # Relationships
    department       = db.relationship('Department', foreign_keys=[department_id])
    linked_risk      = db.relationship('Risk', foreign_keys=[linked_risk_id], backref=db.backref('linked_actions', lazy=True))
    linked_audit     = db.relationship('AuditSchedule', foreign_keys=[linked_audit_id], backref=db.backref('linked_actions', lazy=True))
    linked_ra        = db.relationship('RiskAssessment', foreign_keys=[linked_ra_id], backref=db.backref('linked_actions', lazy=True))

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
    status              = db.Column(db.String(20), default='Open')
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)
    department          = db.relationship('Department', foreign_keys=[department_id])

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
    __tablename__ = 'spi_indicators'
    id             = db.Column(db.Integer, primary_key=True)
    code           = db.Column(db.String(20))
    name           = db.Column(db.String(200))
    department_ids = db.Column(db.String(50))   # comma-separated: "1,2"
    unit           = db.Column(db.String(50))
    spt_target     = db.Column(db.Float)
    alert_l1       = db.Column(db.Float)
    alert_l2       = db.Column(db.Float)
    data_entries   = db.relationship('SPIData', backref='indicator', lazy=True)

class SPIData(db.Model):
    __tablename__ = 'spi_data'
    id       = db.Column(db.Integer, primary_key=True)
    spi_id   = db.Column(db.Integer, db.ForeignKey('spi_indicators.id'))
    year     = db.Column(db.Integer)
    month    = db.Column(db.Integer)
    events   = db.Column(db.Integer)
    flights  = db.Column(db.Integer)
    rate     = db.Column(db.Float)

class SafetyBulletin(db.Model):
    __tablename__ = 'safety_bulletins'
    id            = db.Column(db.String(30), primary_key=True)
    title         = db.Column(db.String(200))
    bulletin_type = db.Column(db.String(30))   # Bulletin / Alert / Newsletter
    content       = db.Column(db.Text)
    issued_by     = db.Column(db.String(100))
    department_ids = db.Column(db.String(100), default='all')
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

class Training(db.Model):
    __tablename__ = 'trainings'
    id             = db.Column(db.Integer, primary_key=True)
    employee_name  = db.Column(db.String(100))
    department_id  = db.Column(db.Integer, db.ForeignKey('departments.id'))
    training_type  = db.Column(db.String(100))
    training_date  = db.Column(db.String(20))
    expiry_date    = db.Column(db.String(20))
    status         = db.Column(db.String(20), default='Completed')  # Completed / Due / Overdue
    notes          = db.Column(db.Text)
    department     = db.relationship('Department', foreign_keys=[department_id])

# ═══════════════════════════════════════════════════════════════════════════════
#  AUDIT MANAGEMENT MODULE — ADDED TO EXISTING SMS
#  Follows ICAO Annex 19, Doc 9859, IOSA ISM Standards
# ═══════════════════════════════════════════════════════════════════════════════

class AuditPlan(db.Model):
    """Annual audit plan — defines what must be audited in a given year."""
    __tablename__ = 'audit_plans'
    id                 = db.Column(db.String(30), primary_key=True)
    year               = db.Column(db.Integer, nullable=False)
    department_id      = db.Column(db.Integer, db.ForeignKey('departments.id'))
    audit_type         = db.Column(db.String(50))   # Internal / Compliance / IOSA-style
    frequency          = db.Column(db.String(30))   # Quarterly / Semi-Annual / Annual
    responsible_manager = db.Column(db.String(100))
    scope              = db.Column(db.Text)          # What will be audited
    objectives         = db.Column(db.Text)
    status             = db.Column(db.String(20), default='Active')  # Active / Completed / Cancelled
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
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)
    department         = db.relationship('Department', foreign_keys=[department_id])
    checklist_items    = db.relationship('AuditChecklist', backref='schedule', lazy=True,
                                          cascade='all, delete-orphan')
    findings           = db.relationship('AuditFinding', backref='schedule', lazy=True,
                                          cascade='all, delete-orphan')

class AuditChecklist(db.Model):
    """Dynamic checklist items for each scheduled audit."""
    __tablename__ = 'audit_checklists'
    id             = db.Column(db.Integer, primary_key=True)
    schedule_id    = db.Column(db.String(30), db.ForeignKey('audit_schedules.id'))
    category       = db.Column(db.String(100))   # SOP / Training / Safety Reporting / Operations / Risk Mgmt
    item_ref       = db.Column(db.String(30))    # e.g. IOSA ISM 1.1.1
    question       = db.Column(db.Text)
    response       = db.Column(db.String(10))    # Yes / No / N/A
    comment        = db.Column(db.Text)
    evidence       = db.Column(db.Text)
    sequence       = db.Column(db.Integer, default=0)

class AuditFinding(db.Model):
    """Finding raised during an audit — linked to actions and hazards."""
    __tablename__ = 'audit_findings'
    id             = db.Column(db.String(30), primary_key=True)
    schedule_id    = db.Column(db.String(30), db.ForeignKey('audit_schedules.id'))
    finding_ref    = db.Column(db.String(30))    # e.g. F-001 within the audit
    description    = db.Column(db.Text)
    category       = db.Column(db.String(50))    # Operational / Technical / Human Factors / Organizational
    severity       = db.Column(db.String(20))    # Major / Minor / Observation
    standard_ref   = db.Column(db.String(100))   # e.g. IOSA ISM 1.2.3 / ICAO Annex 19
    root_cause     = db.Column(db.Text)
    evidence       = db.Column(db.Text)
    requirement    = db.Column(db.Text)          # What the standard requires
    status         = db.Column(db.String(20), default='Open')  # Open / Actioned / Closed / Verified
    # Auto-linked to SMS modules
    hazard_id      = db.Column(db.String(30), db.ForeignKey('hazards.id'), nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    # Actions linked via Action.linked_ref_id = finding.id
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
