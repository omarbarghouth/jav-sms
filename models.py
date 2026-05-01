from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# ─── Departments ──────────────────────────────────────────────────────────────
class Department(db.Model):
    __tablename__ = 'departments'
    id    = db.Column(db.Integer, primary_key=True)
    code  = db.Column(db.String(10), unique=True)
    name  = db.Column(db.String(100))
    color = db.Column(db.String(20), default='#1e40af')

# ─── Audit Plan (Annual) ──────────────────────────────────────────────────────
class AuditPlan(db.Model):
    __tablename__ = 'audit_plans'
    id                 = db.Column(db.String(30), primary_key=True)
    year               = db.Column(db.Integer, nullable=False)
    department_id      = db.Column(db.Integer, db.ForeignKey('departments.id'))
    audit_type         = db.Column(db.String(50))   # Internal / Compliance / IOSA-style
    frequency          = db.Column(db.String(30))   # Quarterly / Semi-Annual / Annual
    responsible_manager = db.Column(db.String(100))
    scope              = db.Column(db.Text)
    status             = db.Column(db.String(20), default='Active')  # Active / Cancelled
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)
    department         = db.relationship('Department', foreign_keys=[department_id])
    schedules          = db.relationship('AuditSchedule', backref='plan', lazy=True, cascade='all, delete-orphan')

# ─── Audit Schedule ───────────────────────────────────────────────────────────
class AuditSchedule(db.Model):
    __tablename__ = 'audit_schedules'
    id             = db.Column(db.String(30), primary_key=True)
    plan_id        = db.Column(db.String(30), db.ForeignKey('audit_plans.id'))
    department_id  = db.Column(db.Integer, db.ForeignKey('departments.id'))
    audit_type     = db.Column(db.String(50))
    title          = db.Column(db.String(200))
    scheduled_date = db.Column(db.String(20))
    actual_date    = db.Column(db.String(20))
    lead_auditor   = db.Column(db.String(100))
    co_auditor     = db.Column(db.String(100))
    status         = db.Column(db.String(20), default='Planned')  # Planned / In Progress / Completed / Cancelled
    opening_meeting_date = db.Column(db.String(20))
    closing_meeting_date = db.Column(db.String(20))
    closure_date   = db.Column(db.String(20))
    closed_by      = db.Column(db.String(100))
    final_remarks  = db.Column(db.Text)
    can_close      = db.Column(db.Boolean, default=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    department     = db.relationship('Department', foreign_keys=[department_id])
    checklist_items = db.relationship('ChecklistItem', backref='audit', lazy=True, cascade='all, delete-orphan')
    findings       = db.relationship('AuditFinding', backref='audit', lazy=True, cascade='all, delete-orphan')

# ─── Audit Checklist ──────────────────────────────────────────────────────────
class ChecklistItem(db.Model):
    __tablename__ = 'checklist_items'
    id          = db.Column(db.Integer, primary_key=True)
    audit_id    = db.Column(db.String(30), db.ForeignKey('audit_schedules.id'))
    category    = db.Column(db.String(50))   # SOP / Training / Safety Reporting / Operational / Risk Management
    reference   = db.Column(db.String(50))   # e.g. ICAO Annex 19, IOSA ISM 1.1.1
    question    = db.Column(db.Text)
    response    = db.Column(db.String(10))   # Yes / No / N/A
    comment     = db.Column(db.Text)
    finding_generated = db.Column(db.Boolean, default=False)

# ─── Audit Findings ───────────────────────────────────────────────────────────
class AuditFinding(db.Model):
    __tablename__ = 'audit_findings'
    id              = db.Column(db.String(30), primary_key=True)
    audit_id        = db.Column(db.String(30), db.ForeignKey('audit_schedules.id'))
    checklist_item_id = db.Column(db.Integer, db.ForeignKey('checklist_items.id'), nullable=True)
    description     = db.Column(db.Text)
    category        = db.Column(db.String(30))   # Operational / Technical / Human Factors / Organizational
    severity        = db.Column(db.String(20))   # Major / Minor / Observation
    root_cause      = db.Column(db.Text)
    evidence        = db.Column(db.Text)
    requirement_ref = db.Column(db.String(100))  # e.g. IOSA ISM 1.1.2
    status          = db.Column(db.String(20), default='Open')  # Open / Action Raised / Verified / Closed
    hazard_id       = db.Column(db.String(30), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    actions         = db.relationship('AuditAction', backref='finding', lazy=True, cascade='all, delete-orphan')

# ─── Corrective Actions ───────────────────────────────────────────────────────
class AuditAction(db.Model):
    __tablename__ = 'audit_actions'
    id                   = db.Column(db.String(30), primary_key=True)
    finding_id           = db.Column(db.String(30), db.ForeignKey('audit_findings.id'))
    hazard_id            = db.Column(db.String(30), nullable=True)
    description          = db.Column(db.Text)
    owner                = db.Column(db.String(100))
    due_date             = db.Column(db.String(20))
    priority             = db.Column(db.String(20))   # High / Medium / Low
    status               = db.Column(db.String(20), default='Open')  # Open / In Progress / Closed / Overdue
    completion_date      = db.Column(db.String(20))
    completion_evidence  = db.Column(db.Text)
    effectiveness_review = db.Column(db.String(30))   # Effective / Partially Effective / Ineffective
    effectiveness_notes  = db.Column(db.Text)
    verified_by          = db.Column(db.String(100))
    verification_date    = db.Column(db.String(20))
    reopened             = db.Column(db.Boolean, default=False)
    reopen_reason        = db.Column(db.Text)
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)

# ─── Hazard (linked from findings) ───────────────────────────────────────────
class Hazard(db.Model):
    __tablename__ = 'hazards'
    id                  = db.Column(db.String(30), primary_key=True)
    source              = db.Column(db.String(30))
    linked_report_id    = db.Column(db.String(30))
    department_id       = db.Column(db.Integer, db.ForeignKey('departments.id'))
    classification      = db.Column(db.String(30))
    generic_hazard      = db.Column(db.String(200))
    specific_components = db.Column(db.Text)
    consequences        = db.Column(db.Text)
    initial_likelihood  = db.Column(db.Integer)
    initial_severity    = db.Column(db.String(2))
    initial_risk_index  = db.Column(db.String(5))
    initial_tolerance   = db.Column(db.String(20))
    status              = db.Column(db.String(20), default='Open')
    owner               = db.Column(db.String(100))
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)
    department          = db.relationship('Department', foreign_keys=[department_id])
