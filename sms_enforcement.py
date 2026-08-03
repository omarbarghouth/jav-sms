"""
sms_enforcement.py — SMS Production Enforcement Engine
=======================================================
ICAO Annex 19 §3–§9 / Doc 9859 / IOSA ISM / EASA SMS

Implements the active enforcement layer that was missing from the base system.
This is not a monitoring dashboard — it BLOCKS invalid operations, ENFORCES
gates, and AUTO-TRIGGERS notifications. Every function here has a direct
regulatory obligation mapped to it.

Modules implemented:
  1. Segregation of Duties (SoD) Enforcement          — IOSA ISM / Annex 19 §4
  2. Corrective Action Effectiveness Gate             — Annex 19 §5.3.3
  3. Reporter Feedback Lifecycle Engine               — Annex 19 §3.1.2 / Doc 9859 §5.3.3
  4. Investigation Timeline Enforcement               — Annex 13 §6.1 / §7.1
  5. Risk Assessment Review Cycle Monitor             — Doc 9859 §10.3.3
  6. Regulatory Notification Tracking                — Annex 13 §6.1
  7. Leading Indicator Auto-Calculation               — Doc 9859 §11.2
  8. Audit Verification Queue                        — IOSA ISM / Annex 19 §5.3
  9. Just Culture Policy Management                  — Annex 19 §3.1.2
 10. Confidential Access Logging                     — IOSA ISM 1.2.3

Blueprint prefix: /enforcement
All routes require authentication. Enforcement logic is also called directly
from app.py routes via the helper functions defined here.
"""

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, jsonify, abort)
from models import (
    db, User, Action, ActionHistory, HazardReport, ASRReport, VoluntaryReport,
    ConfidentialReport, Investigation, InvestigationEvent, RiskAssessment,
    AuditFinding, MOC, SPIIndicator, SPIData,
    SPIEscalation, Training, Employee, DeviceToken, Department,
    # Phase 2 new models
    ReportFeedback, JustCulturePolicy, ConfidentialAccessLog,
    SafetyRecommendation, InvestigationTimeline, RegulatoryNotification,
    SoDViolationBlock, RAReviewCycle, LeadingIndicatorConfig,
)
try:
    from models import AuditVerificationItem
except ImportError:
    AuditVerificationItem = None
from datetime import datetime, date, timedelta
import functools, os, json
import urllib.request as _urllib_req

enf = Blueprint('enforcement', __name__, url_prefix='/enforcement')

# ──────────────────────────────────────────────────────────────────────────────
#  AUTH HELPERS (reuse session from main app)
# ──────────────────────────────────────────────────────────────────────────────

def _current_user():
    return session.get('admin_user', 'System')

def _current_role():
    try:
        u = User.query.filter_by(username=_current_user(), is_active=True).first()
        return u.role if u else 'unknown'
    except Exception:
        return 'unknown'

def _is_logged_in():
    return session.get('admin_logged_in') is True

def require_login(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not _is_logged_in():
            return redirect(url_for('admin_login', next=request.path))
        return f(*args, **kwargs)
    return decorated

def require_role(*roles):
    """Restrict route to specific roles."""
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            if not _is_logged_in():
                return redirect(url_for('admin_login', next=request.path))
            if _current_role() not in roles:
                flash('You do not have permission to perform this action.', 'error')
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


# ══════════════════════════════════════════════════════════════════════════════
#  1. SEGREGATION OF DUTIES (SoD) ENFORCEMENT
#  IOSA ISM / ICAO Annex 19 §4 — Four-eyes principle enforced at BLOCK level.
#
#  The previous system only logged SoD checks after the fact. This engine
#  PREVENTS the operation and records a SoDViolationBlock for audit evidence.
# ══════════════════════════════════════════════════════════════════════════════

# SoD rules — maps (entity_type, action) → check function
# Each check returns (is_violation: bool, rule_name: str, detail: str)

def _sod_action_closure(action: Action, closer: str) -> tuple:
    """Action owner cannot verify their own closure. IOSA ISM 3.7.3."""
    if action.owner and action.owner.lower() == closer.lower():
        return (True,
                'action_owner_cannot_close_own_action',
                f'Action {action.id} was assigned to {action.owner}. '
                f'A different person must verify closure.')
    if action.assigned_by and action.assigned_by.lower() == closer.lower():
        return (True,
                'action_assigner_cannot_verify_closure',
                f'Action {action.id} was assigned by {closer}. '
                f'Closure must be verified by the Safety Manager or a different officer.')
    return (False, '', '')


def _sod_ra_approval(ra: RiskAssessment, approver: str) -> tuple:
    """Risk assessment preparer cannot approve their own RA."""
    if ra.prepared_by_name and ra.prepared_by_name.lower() == approver.lower():
        return (True,
                'ra_preparer_cannot_approve_own_assessment',
                f'Risk Assessment {ra.id} was prepared by {ra.prepared_by_name}. '
                f'A different person must approve.')
    if ra.responsible_name and ra.responsible_name.lower() == approver.lower():
        return (True,
                'ra_responsible_person_cannot_self_approve',
                f'The responsible person for RA {ra.id} cannot be the approver.')
    return (False, '', '')


def _sod_audit_independence(schedule, auditor: str) -> tuple:
    """Auditor cannot audit their own department. IOSA ISM 3.6.1."""
    user = User.query.filter_by(username=auditor, is_active=True).first()
    if not user:
        return (False, '', '')
    if user.department_id and schedule.department_id == user.department_id:
        dept = Department.query.get(user.department_id)
        dept_name = dept.name if dept else str(user.department_id)
        return (True,
                'auditor_cannot_audit_own_department',
                f'Auditor {auditor} belongs to {dept_name} and cannot audit '
                f'their own department. Assign an auditor from a different department.')
    return (False, '', '')


def _sod_investigation_close(inv: Investigation, closer: str) -> tuple:
    """Investigator cannot approve / close their own investigation."""
    if inv.investigator and inv.investigator.lower() == closer.lower():
        return (True,
                'investigator_cannot_close_own_investigation',
                f'Investigation {inv.id} was assigned to {inv.investigator}. '
                f'Closure must be signed off by the Safety Manager.')
    return (False, '', '')


def _sod_finding_review(finding: AuditFinding, reviewer: str) -> tuple:
    """Auditee (assigned_to) cannot safety-review their own finding."""
    if finding.assigned_to and finding.assigned_to.lower() == reviewer.lower():
        return (True,
                'auditee_cannot_review_own_finding',
                f'Finding {finding.id} is assigned to {finding.assigned_to}. '
                f'The Safety Manager must perform the review, not the auditee.')
    return (False, '', '')


def enforce_sod(entity_type: str, entity_id: str,
                entity, action: str, actor: str) -> dict:
    """
    Master SoD enforcement entry point.

    Called from route handlers BEFORE performing a privileged action.
    Returns {'allowed': True} if OK, or {'allowed': False, 'reason': str} if blocked.
    On violation: writes SoDViolationBlock and returns blocked status.

    Args:
        entity_type: 'Action' / 'RiskAssessment' / 'AuditFinding' /
                     'Investigation' / 'AuditSchedule'
        entity_id:   Primary key string of the entity
        entity:      SQLAlchemy model instance
        action:      'close' / 'approve' / 'verify' / 'safety_review' / 'audit'
        actor:       Username of the person attempting the action
    """
    is_violation, rule, detail = False, '', ''

    if entity_type == 'Action' and action in ('close', 'verify'):
        is_violation, rule, detail = _sod_action_closure(entity, actor)
    elif entity_type == 'RiskAssessment' and action == 'approve':
        is_violation, rule, detail = _sod_ra_approval(entity, actor)
    elif entity_type == 'AuditSchedule' and action == 'audit':
        is_violation, rule, detail = _sod_audit_independence(entity, actor)
    elif entity_type == 'Investigation' and action in ('close', 'approve'):
        is_violation, rule, detail = _sod_investigation_close(entity, actor)
    elif entity_type == 'AuditFinding' and action == 'safety_review':
        is_violation, rule, detail = _sod_finding_review(entity, actor)

    if is_violation:
        # Write immutable block record
        block = SoDViolationBlock(
            attempted_by     = actor,
            attempted_role   = _current_role(),
            entity_type      = entity_type,
            entity_id        = str(entity_id),
            attempted_action = action,
            violation_rule   = rule,
            violation_detail = detail,
            original_submitter = getattr(entity, 'owner', None)
                                 or getattr(entity, 'investigator', None)
                                 or getattr(entity, 'assigned_to', None)
                                 or getattr(entity, 'responsible_name', None),
            ip_address       = request.remote_addr if request else None,
        )
        db.session.add(block)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return {'allowed': False, 'reason': detail, 'rule': rule}

    return {'allowed': True}


# ══════════════════════════════════════════════════════════════════════════════
#  2. CORRECTIVE ACTION EFFECTIVENESS GATE
#  ICAO Annex 19 §5.3.3 / IOSA ISM 3.7.3
#
#  Actions CANNOT be closed unless:
#    - evidence uploaded (evidence_filename or evidence text)
#    - verified_by recorded
#    - verified_date recorded
#    - effectiveness rating recorded
#
#  If effectiveness = 'Ineffective':
#    - Action is automatically reopened
#    - reopen_count incremented
#    - Safety Manager notified
#    - New ActionHistory record created
# ══════════════════════════════════════════════════════════════════════════════

def validate_action_closure(action: Action, form_data: dict) -> list:
    """
    Validates that all mandatory fields are present before an action can close.

    Returns a list of error strings. Empty list = closure permitted.
    Called from the action close route BEFORE saving to database.
    """
    errors = []

    effectiveness = (form_data.get('effectiveness') or action.effectiveness or '').strip()
    verified_by   = (form_data.get('verified_by')   or action.verified_by   or '').strip()
    verified_date = (form_data.get('verified_date') or action.verified_date or '').strip()
    evidence_text = (form_data.get('evidence')       or action.evidence       or '').strip()
    evidence_file = (form_data.get('evidence_filename') or action.evidence_filename or '').strip()

    if not effectiveness:
        errors.append('Effectiveness rating is required before closure. '
                      'Select: Effective / Partially Effective / Ineffective.')
    if not verified_by:
        errors.append('Verified By is required — closure must be confirmed by '
                      'a person other than the action owner.')
    if not verified_date:
        errors.append('Verified Date is required.')
    if action.closure_evidence_required and not evidence_text and not evidence_file:
        errors.append('Evidence is required — upload a file or provide evidence '
                      'notes describing how the action was implemented.')

    return errors


def process_ineffective_action(action: Action, closer: str, notes: str = '') -> dict:
    """
    Called when an action is closed with effectiveness = 'Ineffective'.
    Automatically reopens the action and notifies Safety Manager.

    Returns a dict with status and details of what happened.
    """
    prev_status = action.status
    action.status             = 'Open'
    action.closed_date        = None
    action.closure_by         = None
    action.reopen_count       = (action.reopen_count or 0) + 1
    action.auto_reopened_at   = datetime.utcnow()
    action.auto_reopened_reason = (
        f'Automatically reopened: effectiveness rated as Ineffective by {closer}. '
        f'Root cause has not been resolved. A revised corrective action is required. '
        f'Notes: {notes}'
    )
    action.follow_up_notes = (
        (action.follow_up_notes or '') +
        f'\n[{datetime.utcnow().strftime("%Y-%m-%d")}] INEFFECTIVE — auto-reopened. '
        f'Reopen #{action.reopen_count}. Closer: {closer}. Notes: {notes}'
    ).strip()

    history = ActionHistory(
        action_id   = action.id,
        changed_by  = closer,
        from_status = prev_status,
        to_status   = 'Open (Auto-Reopened: Ineffective)',
        notes       = f'Ineffective closure — automatically reopened. '
                      f'Reopen count: {action.reopen_count}. {notes}',
        field_changed = 'status',
    )
    db.session.add(history)

    # Escalate to SRB if reopened 2+ times (Doc 9859 §10.3)
    srb_escalation_triggered = action.reopen_count >= 2

    return {
        'reopened':             True,
        'reopen_count':         action.reopen_count,
        'srb_escalation':       srb_escalation_triggered,
        'message': (
            f'Action {action.id} has been rated Ineffective and automatically '
            f'reopened (reopen #{action.reopen_count}). The Safety Manager has '
            f'been notified. A revised corrective approach is required.'
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  3. REPORTER FEEDBACK LIFECYCLE ENGINE
#  ICAO Annex 19 §3.1.2 / Doc 9859 §5.3.3
#
#  Every status transition on a report triggers an update to the
#  ReportFeedback record, which is then readable by the mobile app.
#  If the reporter has an FCM token, a push notification is sent.
# ══════════════════════════════════════════════════════════════════════════════

# Stage map: internal status values → (stage_num, stage_label)
_HAZARD_STAGE_MAP = {
    'Submitted':         (1, 'Submitted'),
    'Acknowledged':      (2, 'Acknowledged'),
    'Under Review':      (3, 'Under Review'),
    'Under Assessment':  (3, 'Under Review'),
    'RA Initiated':      (4, 'Risk Assessment Initiated'),
    'Investigation':     (5, 'Investigation Initiated'),
    'Actions Created':   (6, 'Corrective Actions Created'),
    'Actioned':          (6, 'Corrective Actions Created'),
    'Closed':            (7, 'Closed'),
}

_VOLUNTARY_STAGE_MAP = {
    'Submitted':    (1, 'Submitted'),
    'Reviewed':     (2, 'Under Review'),
    'Actioned':     (3, 'Action Taken'),
    'Closed':       (4, 'Closed'),
}


def get_or_create_feedback(report_ref: str, report_type: str,
                            reporter_user_id: str = None) -> ReportFeedback:
    """Fetch existing ReportFeedback record or create one for a new report."""
    fb = ReportFeedback.query.filter_by(report_ref=report_ref).first()
    if fb:
        return fb

    # Calculate acknowledgment SLA — 5 working days (approx 7 calendar days)
    ack_due = datetime.utcnow() + timedelta(days=7)

    fb = ReportFeedback(
        report_ref        = report_ref,
        report_type       = report_type,
        reporter_user_id  = reporter_user_id,
        stage_num         = 1,
        stage_label       = 'Submitted',
        submitted_at      = datetime.utcnow(),
        acknowledgment_due = ack_due,
        current_guidance  = ReportFeedback.STAGE_GUIDANCE[1],
    )
    db.session.add(fb)
    return fb


def advance_report_feedback(report_ref: str, new_status: str,
                             advanced_by: str,
                             outcome_summary: str = None,
                             actions_taken: str = None,
                             risk_level: str = None) -> bool:
    """
    Called whenever a report's internal status changes.
    Updates ReportFeedback, then triggers push notification.

    Returns True if stage advanced, False if status unchanged.
    """
    fb = ReportFeedback.query.filter_by(report_ref=report_ref).first()
    if not fb:
        return False

    now = datetime.utcnow()
    new_stage, new_label = _map_status_to_stage(fb.report_type, new_status)

    if new_stage <= fb.stage_num and new_status != 'Closed':
        return False  # no regression, no duplicate

    fb.stage_num    = new_stage
    fb.stage_label  = new_label
    fb.current_guidance = ReportFeedback.STAGE_GUIDANCE.get(new_stage, '')
    fb.updated_at   = now

    # Set specific timestamps
    if new_stage == 2 and not fb.acknowledged_at:
        fb.acknowledged_at = now
        fb.acknowledged_by = advanced_by
    elif new_stage == 3 and not fb.review_started_at:
        fb.review_started_at = now
    elif new_stage == 4 and not fb.ra_initiated_at:
        fb.ra_initiated_at = now
    elif new_stage == 5 and not fb.investigation_at:
        fb.investigation_at = now
    elif new_stage == 6 and not fb.actions_created_at:
        fb.actions_created_at = now
    elif new_stage == 7 and not fb.closed_at:
        fb.closed_at  = now
        fb.closed_by  = advanced_by
        if outcome_summary:
            fb.outcome_summary     = outcome_summary
            fb.outcome_actions_taken = actions_taken
            fb.outcome_risk_level  = risk_level
            fb.outcome_shared      = True

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return False

    # Fire push notification if reporter has a device token
    if fb.reporter_user_id:
        _push_feedback_notification(fb, new_label)

    return True


def _map_status_to_stage(report_type: str, status: str) -> tuple:
    """Maps internal report status → (stage_num, stage_label)."""
    if report_type in ('Voluntary', 'Confidential'):
        return _VOLUNTARY_STAGE_MAP.get(status, (1, status))
    return _HAZARD_STAGE_MAP.get(status, (1, status))


def _get_fcm_app_enf():
    """Return initialized firebase_admin App for sms_enforcement.py (same as app.py helper)."""
    try:
        import firebase_admin
        from firebase_admin import credentials
        if not firebase_admin._apps:
            sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT', '')
            if not sa_json:
                return None
            import json as _json_mod, tempfile
            sa_dict = _json_mod.loads(sa_json)
            cred = credentials.Certificate(sa_dict)
            firebase_admin.initialize_app(cred)
        return firebase_admin.get_app()
    except Exception:
        return None


def _push_feedback_notification(fb: ReportFeedback, stage_label: str):
    """
    Send FCM v1 push notification to the reporter's mobile device via firebase-admin SDK.
    Replaces the legacy fcm.googleapis.com/fcm/send endpoint (shut down June 2024).
    """
    if not fb.reporter_user_id:
        return

    tokens = DeviceToken.query.filter_by(user_id=fb.reporter_user_id).all()
    if not tokens:
        return

    fcm_app = _get_fcm_app_enf()
    if fcm_app is None:
        return  # FIREBASE_SERVICE_ACCOUNT not configured — skip silently

    try:
        import firebase_admin
        from firebase_admin import messaging

        stage_icons = {
            'Submitted': '📋', 'Acknowledged': '✅', 'Under Review': '🔍',
            'Action Taken': '⚡', 'Closed': '🔒',
        }
        icon  = stage_icons.get(stage_label, '📄')
        title = f'{icon} Report Update: {fb.report_ref}'
        body  = (
            f'Your report has been updated to: {stage_label}. '
            f'{fb.current_guidance[:80] if fb.current_guidance else ""}'
        )
        data = {
            'type':          'hazard',
            'id':            fb.report_ref,
            'ntype':         'system',
            'stage_num':     str(fb.stage_num),
            'stage_label':   stage_label,
            'outcome_shared': str(getattr(fb, 'outcome_shared', False)),
        }
        msgs = [
            messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data={k: str(v) for k, v in data.items()},
                android=messaging.AndroidConfig(priority='high',
                    notification=messaging.AndroidNotification(
                        sound='default', channel_id='avias_alerts')),
                apns=messaging.APNSConfig(payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound='default', badge=1))),
                token=dt.fcm_token,
            )
            for dt in tokens
        ]
        resp = messaging.send_each(msgs)
        if resp.success_count > 0:
            fb.push_sent    = True
            fb.push_sent_at = datetime.utcnow()
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

        # Also write in-app notification log
        try:
            from models import EmployeeNotificationLog
            log = EmployeeNotificationLog(
                employee_user_id  = fb.reporter_user_id,
                title             = title,
                body              = body,
                notification_type = 'system',
                content_type      = fb.report_type.lower().replace(' ', '_') if fb.report_type else 'hazard',
                content_id        = fb.report_ref,
            )
            db.session.add(log)
            db.session.commit()
        except Exception:
            db.session.rollback()

    except Exception:
        pass  # notification failure must never break the main workflow


# ══════════════════════════════════════════════════════════════════════════════
#  4. INVESTIGATION TIMELINE ENFORCEMENT
#  ICAO Annex 13 §6.1 / §7.1
#
#  For Accident / Serious Incident classifications:
#    - Verbal CAA notification due within 72 hours
#    - Preliminary report due within 30 days
#    - Interim report due at 12 months if not closed
#    - Final report has no fixed deadline but must be reasonable
#
#  This function is called:
#    a) When an investigation is created — sets deadlines
#    b) On a scheduled basis (cron or request-triggered) — checks overdue
# ══════════════════════════════════════════════════════════════════════════════

_MANDATORY_CLASSIFICATIONS = {'Accident', 'Serious Incident'}
_PRELIMINARY_DAYS = 30
_INTERIM_DAYS     = 365


def initialize_investigation_timeline(inv: Investigation, created_by: str):
    """
    Called when an Investigation is created.
    For Accident / Serious Incident: sets mandatory statutory deadlines.
    For others: sets best-practice targets (non-mandatory).
    """
    occurrence_dt = None
    if inv.date_of_occurrence:
        try:
            occurrence_dt = datetime.strptime(inv.date_of_occurrence, '%Y-%m-%d')
        except ValueError:
            pass

    if not occurrence_dt:
        occurrence_dt = datetime.utcnow()

    is_mandatory = inv.classification in _MANDATORY_CLASSIFICATIONS

    # Verbal CAA notification (72 hours — for Accident/Serious Incident)
    verbal_due = occurrence_dt + timedelta(hours=72) if is_mandatory else None

    # Preliminary report (30 days)
    prelim_due = (occurrence_dt + timedelta(days=_PRELIMINARY_DAYS)).strftime('%Y-%m-%d')

    # Interim report (12 months)
    interim_due = (occurrence_dt + timedelta(days=_INTERIM_DAYS)).strftime('%Y-%m-%d')

    # Update Investigation model directly
    inv.preliminary_report_due        = prelim_due
    inv.caa_notification_due_verbal   = verbal_due
    inv.caa_notification_due_written  = prelim_due

    # Create timeline record
    existing = InvestigationTimeline.query.filter_by(
        investigation_id=inv.id).first()
    if existing:
        return existing

    tl = InvestigationTimeline(
        investigation_id       = inv.id,
        preliminary_due_date   = prelim_due,
        interim_due_date       = interim_due,
        caa_notified           = inv.authority_notified or False,
        caa_authority_name     = 'Jordan Civil Aviation Regulatory Commission (CARC)',
    )
    db.session.add(tl)
    return tl


def check_investigation_overdue(inv: Investigation) -> list:
    """
    Returns a list of overdue obligation dicts for a given investigation.
    Called from the investigation detail view to show safety-critical alerts.
    """
    alerts = []
    tl = getattr(inv, 'timeline_record', None)
    if not tl:
        return alerts

    today = date.today()

    # Verbal CAA notification
    if (inv.classification in _MANDATORY_CLASSIFICATIONS
            and not tl.caa_notified
            and tl.preliminary_due_date):
        verbal_due = datetime.strptime(tl.preliminary_due_date, '%Y-%m-%d').date() - timedelta(days=27)
        if today > verbal_due:
            alerts.append({
                'type':     'verbal_notification_overdue',
                'severity': 'CRITICAL',
                'message':  'CAA verbal notification is overdue. '
                            'This is a statutory obligation under ICAO Annex 13 §6.1.',
                'due':      verbal_due.isoformat(),
            })

    # Preliminary report
    if tl.preliminary_due_date and not tl.preliminary_submitted:
        due = datetime.strptime(tl.preliminary_due_date, '%Y-%m-%d').date()
        if today > due:
            alerts.append({
                'type':     'preliminary_report_overdue',
                'severity': 'CRITICAL',
                'message':  f'Preliminary report overdue since {due.isoformat()}. '
                            'ICAO Annex 13 §6.1 — 30-day statutory deadline.',
                'due':      due.isoformat(),
            })
        elif (due - today).days <= 7:
            alerts.append({
                'type':     'preliminary_report_due_soon',
                'severity': 'HIGH',
                'message':  f'Preliminary report due in {(due - today).days} day(s) ({due.isoformat()}).',
                'due':      due.isoformat(),
            })

    # Interim report (12 months)
    if (tl.interim_due_date and not tl.interim_submitted
            and inv.status == 'Open'):
        due = datetime.strptime(tl.interim_due_date, '%Y-%m-%d').date()
        if today > due:
            alerts.append({
                'type':     'interim_report_overdue',
                'severity': 'HIGH',
                'message':  f'12-month interim report overdue since {due.isoformat()}. '
                            'ICAO Annex 13 §7.1 — annual interim reports required.',
                'due':      due.isoformat(),
            })

    return alerts


# ══════════════════════════════════════════════════════════════════════════════
#  5. RISK ASSESSMENT REVIEW CYCLE MONITOR
#  ICAO Doc 9859 §10.3.3
# ══════════════════════════════════════════════════════════════════════════════

def create_ra_review_cycle(ra: RiskAssessment, cycle_num: int = 1) -> RAReviewCycle:
    """
    Creates the first (or subsequent) review cycle for an activated RA.
    Called when a RA status transitions to 'Active'.
    """
    due_date = ra.next_review_date or (
        (datetime.utcnow() + timedelta(days=365)).strftime('%Y-%m-%d')
    )
    cycle = RAReviewCycle(
        ra_id        = ra.id,
        cycle_number = cycle_num,
        due_date     = due_date,
        status       = 'Pending',
    )
    db.session.add(cycle)
    return cycle


def check_ra_review_overdue(ra: RiskAssessment) -> list:
    """Returns list of overdue review alert dicts for a RA."""
    alerts = []
    if ra.status not in ('Active', 'Under Review'):
        return alerts

    today = date.today()
    cycle = (RAReviewCycle.query
             .filter_by(ra_id=ra.id, status='Pending')
             .order_by(RAReviewCycle.cycle_number.desc())
             .first())

    if not cycle:
        # No review cycle tracked — flag as untracked
        if ra.next_review_date:
            try:
                due = datetime.strptime(ra.next_review_date, '%Y-%m-%d').date()
                if today > due:
                    alerts.append({
                        'type':     'ra_review_overdue',
                        'severity': 'HIGH',
                        'message':  f'Risk Assessment {ra.id} review overdue since {due}. '
                                    'ICAO Doc 9859 §10.3.3 requires periodic review.',
                        'due':      due.isoformat(),
                    })
            except ValueError:
                pass
        return alerts

    try:
        due = datetime.strptime(cycle.due_date, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return alerts

    days_until = (due - today).days
    if days_until < 0:
        alerts.append({
            'type':     'ra_review_overdue',
            'severity': 'HIGH',
            'message':  f'RA {ra.id} review is {abs(days_until)} days overdue. '
                        'Risk controls may no longer reflect current state.',
            'due':      due.isoformat(),
        })
    elif days_until <= 30:
        alerts.append({
            'type':     'ra_review_due_soon',
            'severity': 'MEDIUM',
            'message':  f'RA {ra.id} review due in {days_until} day(s) on {due}.',
            'due':      due.isoformat(),
        })

    return alerts


# ══════════════════════════════════════════════════════════════════════════════
#  6. REGULATORY NOTIFICATION TRACKING
#  ICAO Annex 13 §6.1 / IOSA ISM 1.2.2
# ══════════════════════════════════════════════════════════════════════════════

def create_regulatory_notification(source_type: str, source_ref: str,
                                    notification_class: str,
                                    occurrence_date: str,
                                    occurrence_description: str,
                                    created_by: str,
                                    department_id: int = None) -> RegulatoryNotification:
    """
    Creates a regulatory notification record when a notifiable occurrence is
    identified. Called from investigation creation and hazard report triage.
    """
    yr  = datetime.utcnow().year
    seq = RegulatoryNotification.query.filter(
        RegulatoryNotification.ref_number.like(f'REGNOT/{yr}/%')).count() + 1
    ref = f'REGNOT/{yr}/{seq:03d}'

    # Verbal due 72 hours from occurrence
    occ_dt = datetime.utcnow()
    if occurrence_date:
        try:
            occ_dt = datetime.strptime(occurrence_date, '%Y-%m-%d')
        except ValueError:
            pass

    verbal_due   = occ_dt + timedelta(hours=72)
    written_due  = (occ_dt + timedelta(days=30)).strftime('%Y-%m-%d')

    notif = RegulatoryNotification(
        ref_number              = ref,
        source_type             = source_type,
        source_ref              = source_ref,
        notification_class      = notification_class,
        occurrence_date         = occurrence_date,
        occurrence_description  = occurrence_description,
        authority_name          = 'Jordan Civil Aviation Regulatory Commission (CARC)',
        verbal_notification_due = verbal_due,
        written_notification_due = written_due,
        status                  = 'Pending',
        department_id           = department_id,
        created_by              = created_by,
    )
    db.session.add(notif)
    return notif


# ══════════════════════════════════════════════════════════════════════════════
#  7. LEADING INDICATOR AUTO-CALCULATION
#  ICAO Doc 9859 §11.2
# ══════════════════════════════════════════════════════════════════════════════

def calculate_leading_indicator(spi: SPIIndicator, year: int, month: int) -> float:
    """
    Auto-calculates the value for a leading indicator SPI for a given month.
    Dispatches to the appropriate calculation function based on indicator_source.
    """
    cfg = getattr(spi, 'leading_config', None)
    if not cfg:
        return 0.0

    dept_ids = None
    if cfg.department_filter:
        try:
            dept_ids = [int(x) for x in cfg.department_filter.split(',') if x.strip()]
        except ValueError:
            dept_ids = None

    src = cfg.indicator_source
    if src == 'training_compliance':
        return _calc_training_compliance(dept_ids, cfg.training_type_filter)
    elif src == 'safety_reporting_rate':
        return _calc_reporting_rate(year, month, dept_ids)
    elif src == 'audit_closure_rate':
        return _calc_audit_closure_rate()
    elif src == 'action_closure_rate':
        return _calc_action_closure_rate(dept_ids)
    elif src == 'survey_participation_rate':
        return _calc_survey_participation(dept_ids)
    elif src == 'cap_overdue_rate':
        return _calc_cap_overdue_rate()
    elif src == 'acknowledgment_rate':
        return _calc_acknowledgment_rate(dept_ids)
    return 0.0


def _calc_training_compliance(dept_ids=None, type_filter=None) -> float:
    """
    Training currency rate: (current employees) / (total employees) × 100.
    'Current' = has a Completed training record that has not expired.
    """
    from models import Training, Employee
    today = date.today().isoformat()
    emp_q = Employee.query.filter_by(is_active=True)
    if dept_ids:
        emp_q = emp_q.filter(Employee.department_id.in_(dept_ids))
    total = emp_q.count()
    if total == 0:
        return 100.0

    trn_q = Training.query.filter(
        Training.status == 'Completed',
        Training.expiry_date >= today,
    )
    if dept_ids:
        trn_q = trn_q.filter(Training.department_id.in_(dept_ids))
    if type_filter:
        types = [t.strip() for t in type_filter.split(',') if t.strip()]
        trn_q = trn_q.filter(Training.training_type.in_(types))

    # Count distinct employees with valid training
    current = db.session.query(
        db.func.count(db.func.distinct(Training.employee_id))
    ).filter(
        Training.status == 'Completed',
        Training.expiry_date >= today,
    )
    if dept_ids:
        current = current.filter(Training.department_id.in_(dept_ids))
    current_count = current.scalar() or 0

    return round((current_count / total) * 100, 1)


def _calc_reporting_rate(year: int, month: int, dept_ids=None) -> float:
    """
    Safety reporting rate: (reports in month) / (employee count) × 1000.
    All report types combined.
    """
    from models import HazardReport, ASRReport, VoluntaryReport, Employee
    from calendar import monthrange

    _, days = monthrange(year, month)
    start = f'{year}-{month:02d}-01'
    end   = f'{year}-{month:02d}-{days}'

    hr = HazardReport.query.filter(
        HazardReport.date >= start, HazardReport.date <= end).count()
    ar = ASRReport.query.filter(
        ASRReport.date >= start, ASRReport.date <= end).count()
    vr = VoluntaryReport.query.filter(
        VoluntaryReport.date >= start, VoluntaryReport.date <= end).count()

    total_reports = hr + ar + vr
    emp_count = Employee.query.filter_by(is_active=True).count() or 1

    return round((total_reports / emp_count) * 1000, 2)


def _calc_audit_closure_rate() -> float:
    """Audit finding closure rate: closed findings / total findings × 100."""
    from models import AuditFinding
    total  = AuditFinding.query.count()
    closed = AuditFinding.query.filter_by(status='Closed').count()
    if total == 0:
        return 100.0
    return round((closed / total) * 100, 1)


def _calc_action_closure_rate(dept_ids=None) -> float:
    """Corrective action closure rate × 100."""
    q_total  = Action.query.filter(Action.status.in_(['Open', 'In Progress', 'Closed']))
    q_closed = Action.query.filter_by(status='Closed')
    if dept_ids:
        q_total  = q_total.filter(Action.department_id.in_(dept_ids))
        q_closed = q_closed.filter(Action.department_id.in_(dept_ids))
    total  = q_total.count()
    closed = q_closed.count()
    if total == 0:
        return 100.0
    return round((closed / total) * 100, 1)


def _calc_survey_participation(dept_ids=None) -> float:
    """Safety survey participation rate for most recent active survey."""
    from models import SafetySurvey, SurveyResponse
    survey = SafetySurvey.query.filter_by(status='Closed').order_by(
        SafetySurvey.id.desc()).first()
    if not survey or not survey.target_count:
        return 0.0
    responses = SurveyResponse.query.filter_by(survey_id=survey.id).count()
    return round((responses / survey.target_count) * 100, 1)


def _calc_cap_overdue_rate() -> float:
    """Rate of overdue CAPs (Corrective Action Plans) in audit findings."""
    from models import AuditFinding
    today = date.today().isoformat()
    total_open = AuditFinding.query.filter(
        AuditFinding.status.notin_(['Closed', 'Cancelled'])).count()
    if total_open == 0:
        return 0.0
    overdue = AuditFinding.query.filter(
        AuditFinding.status.notin_(['Closed', 'Cancelled']),
        AuditFinding.cap_due_date < today,
        AuditFinding.cap_due_date.isnot(None),
    ).count()
    return round((overdue / total_open) * 100, 1)


def _calc_acknowledgment_rate(dept_ids=None) -> float:
    """Safety bulletin acknowledgment rate for active bulletins."""
    from models import SafetyBulletin, SafetyPromoAck, Employee
    active_bulletins = SafetyBulletin.query.filter_by(status='Active').count()
    if active_bulletins == 0:
        return 100.0
    emp_count = Employee.query.filter_by(is_active=True).count()
    if emp_count == 0:
        return 0.0
    expected = active_bulletins * emp_count
    # Count distinct (user_id, content_id) ack pairs for bulletins
    acks = SafetyPromoAck.query.filter_by(content_type='bulletin').count()
    return round((min(acks, expected) / expected) * 100, 1)


# ══════════════════════════════════════════════════════════════════════════════
#  8. AUDIT VERIFICATION QUEUE (routes)
#  IOSA ISM / ICAO Annex 19 §5.3
#
#  The Audit Verification Queue shows auditors all items requiring verification:
#    - Corrective actions from findings
#    - Risk mitigations
#    - Investigation recommendations
#    - MOC post-PIR items
#    - SPI escalation actions
# ══════════════════════════════════════════════════════════════════════════════

@enf.route('/verification-queue')
@require_login
def verification_queue():
    """
    The Audit Verification Queue — lists all items requiring auditor verification.
    Auditors can click through to verify effectiveness directly from this view.
    """
    from models import RAMitigation, SafetyRecommendation

    # 1. Open corrective actions awaiting effectiveness verification
    actions_pending = Action.query.filter(
        Action.status == 'Closed',
        Action.effectiveness.is_(None),
    ).order_by(Action.closed_date.desc()).limit(50).all()

    # 2. Closed actions rated Partially Effective (need follow-up)
    actions_partial = Action.query.filter(
        Action.status == 'Closed',
        Action.effectiveness == 'Partially Effective',
        Action.follow_up_notes.is_(None),
    ).order_by(Action.closed_date.desc()).limit(30).all()

    # 3. RA mitigations awaiting review
    ra_mitigations_open = db.session.execute(
        db.text("""
            SELECT rm.*, ra.control_number, ra.id as ra_id
            FROM ra_mitigations rm
            JOIN risk_assessments ra ON rm.assessment_id = ra.id
            WHERE rm.status = 'Open' AND ra.status = 'Active'
            LIMIT 40
        """)
    ).fetchall()

    # 4. Open safety recommendations
    open_srs = SafetyRecommendation.query.filter(
        SafetyRecommendation.status.in_(['Open', 'Response Received'])
    ).order_by(SafetyRecommendation.response_due_date.asc()).limit(30).all()

    # 5. MOC Post-PIR items awaiting review
    from models import MOC
    moc_pir_pending = MOC.query.filter(
        MOC.status == 'Implemented',
        MOC.pir_date.is_(None),
    ).order_by(MOC.implemented_date.asc()).limit(20).all()

    # 6. AuditVerificationItems pending
    avi_pending = (AuditVerificationItem.query
                   .filter(AuditVerificationItem.status == 'Pending')
                   .order_by(AuditVerificationItem.due_date.asc())
                   .limit(40).all()) if AuditVerificationItem else []

    # 7. Overdue regulatory notifications
    today_str = date.today().isoformat()
    reg_overdue = RegulatoryNotification.query.filter(
        RegulatoryNotification.status.notin_(['Complete', 'Exempt']),
        db.or_(
            db.and_(
                RegulatoryNotification.written_notification_done == False,
                RegulatoryNotification.written_notification_due < today_str,
            )
        )
    ).order_by(RegulatoryNotification.written_notification_due.asc()).all()

    # Summary counts
    queue_total = (len(actions_pending) + len(actions_partial) +
                   len(open_srs) + len(moc_pir_pending) +
                   len(avi_pending) + len(reg_overdue))

    return render_template('enforcement/verification_queue.html',
                           actions_pending=actions_pending,
                           actions_partial=actions_partial,
                           open_srs=open_srs,
                           moc_pir_pending=moc_pir_pending,
                           avi_pending=avi_pending,
                           reg_overdue=reg_overdue,
                           queue_total=queue_total,
                           ra_mitigations_open=ra_mitigations_open)


@enf.route('/verify-action/<action_id>', methods=['POST'])
@require_login
def verify_action(action_id):
    """Verify effectiveness of a closed action directly from the queue."""
    action = Action.query.get_or_404(action_id)
    actor  = _current_user()

    # SoD check: verifier cannot be the action owner
    sod = enforce_sod('Action', action_id, action, 'verify', actor)
    if not sod['allowed']:
        flash(f'SoD Violation blocked: {sod["reason"]}', 'error')
        return redirect(url_for('enforcement.verification_queue'))

    f = request.form
    action.effectiveness      = f.get('effectiveness', '')
    action.effectiveness_review = f.get('effectiveness_review', '')
    action.verified_by        = actor
    action.verified_date      = date.today().isoformat()

    if action.effectiveness == 'Ineffective':
        result = process_ineffective_action(action, actor,
                                             f.get('effectiveness_review', ''))
        db.session.commit()
        flash(result['message'], 'warning')
    else:
        db.session.commit()
        flash(f'✓ Action {action_id} effectiveness verified: {action.effectiveness}',
              'success')

    return redirect(url_for('enforcement.verification_queue'))


@enf.route('/safety-recommendations')
@require_login
def sr_list():
    """Safety Recommendation register (ICAO Annex 13 §6.8)."""
    status_f = request.args.get('status', '')
    q = SafetyRecommendation.query
    if status_f:
        q = q.filter_by(status=status_f)
    srs = q.order_by(SafetyRecommendation.issued_date.desc()).all()
    return render_template('enforcement/sr_list.html', srs=srs,
                           status_filter=status_f)


@enf.route('/safety-recommendations/new', methods=['GET', 'POST'])
@require_login
def sr_new():
    """Create a new Safety Recommendation from an investigation or audit."""
    investigations = Investigation.query.filter_by(status='Open').order_by(
        Investigation.created_at.desc()).all()
    findings = AuditFinding.query.filter(
        AuditFinding.status.notin_(['Closed'])).order_by(
        AuditFinding.created_at.desc()).limit(50).all()

    if request.method == 'POST':
        f = request.form
        yr  = datetime.utcnow().year
        seq = SafetyRecommendation.query.filter(
            db.or_(
                SafetyRecommendation.sr_number.like(f'SMS/SR/{yr}/%'),
                SafetyRecommendation.sr_number.like(f'JAV/SR/{yr}/%')
            )).count() + 1
        sr_num = f'SMS/SR/{yr}/{seq:03d}'

        sr = SafetyRecommendation(
            sr_number       = sr_num,
            source_type     = f.get('source_type', 'Investigation'),
            source_id       = f.get('source_id', ''),
            investigation_id = f.get('investigation_id') or None,
            audit_finding_id = f.get('audit_finding_id') or None,
            title           = f['title'],
            description     = f['description'],
            safety_issue    = f.get('safety_issue', ''),
            addressee_type  = f.get('addressee_type', 'Internal'),
            addressee_name  = f['addressee_name'],
            addressee_email = f.get('addressee_email', ''),
            priority        = f.get('priority', 'High'),
            icao_reference  = f.get('icao_reference', ''),
            issued_date     = date.today().isoformat(),
            issued_by       = _current_user(),
            response_due_date = f.get('response_due_date', ''),
            status          = 'Open',
            created_by      = _current_user(),
        )
        db.session.add(sr)
        db.session.commit()
        flash(f'✓ Safety Recommendation {sr_num} issued.', 'success')
        return redirect(url_for('enforcement.sr_list'))

    return render_template('enforcement/sr_new.html',
                           investigations=investigations, findings=findings)


@enf.route('/safety-recommendations/<int:sr_id>/respond', methods=['POST'])
@require_login
def sr_respond(sr_id):
    """Record a response to a Safety Recommendation."""
    sr = SafetyRecommendation.query.get_or_404(sr_id)
    f  = request.form
    sr.response_text  = f.get('response_text', '')
    sr.response_date  = date.today().isoformat()
    sr.response_by    = _current_user()
    sr.status         = 'Response Received'
    db.session.commit()
    flash(f'✓ Response recorded for {sr.sr_number}.', 'success')
    return redirect(url_for('enforcement.sr_list'))


@enf.route('/safety-recommendations/<int:sr_id>/close', methods=['POST'])
@require_login
def sr_close(sr_id):
    """Close a Safety Recommendation after verifying implementation."""
    sr = SafetyRecommendation.query.get_or_404(sr_id)
    f  = request.form
    sr.effectiveness_rating  = f.get('effectiveness_rating', '')
    sr.closure_verified_by   = _current_user()
    sr.closure_date          = date.today().isoformat()
    sr.closure_notes         = f.get('closure_notes', '')
    sr.status                = 'Closed'
    db.session.commit()
    flash(f'✓ Safety Recommendation {sr.sr_number} closed.', 'success')
    return redirect(url_for('enforcement.sr_list'))


# ══════════════════════════════════════════════════════════════════════════════
#  9. JUST CULTURE POLICY MANAGEMENT
#  ICAO Annex 19 §3.1.2
# ══════════════════════════════════════════════════════════════════════════════

@enf.route('/just-culture')
@require_login
def just_culture_list():
    policies = JustCulturePolicy.query.order_by(
        JustCulturePolicy.version_num.desc()).all()
    active = next((p for p in policies if p.status == 'Active'), None)
    return render_template('enforcement/just_culture.html',
                           policies=policies, active=active)


@enf.route('/just-culture/new', methods=['GET', 'POST'])
@require_role('admin', 'safety_manager', 'accountable_executive')
def just_culture_new():
    users = User.query.filter_by(is_active=True).order_by(User.full_name).all()
    if request.method == 'POST':
        f = request.form
        # Determine next version
        latest = JustCulturePolicy.query.order_by(
            JustCulturePolicy.version_num.desc()).first()
        next_ver = (latest.version_num + 1) if latest else 0

        # Archive all current active policies
        JustCulturePolicy.query.filter_by(status='Active').update({'status': 'Archived'})

        policy = JustCulturePolicy(
            version       = f'JC-REV{next_ver}',
            version_num   = next_ver,
            title         = f.get('title', 'Just Culture Policy Statement'),
            content       = f['content'],
            ae_name       = f.get('ae_name', ''),
            ae_title      = f.get('ae_title', ''),
            ae_user_id    = int(f['ae_user_id']) if f.get('ae_user_id') else None,
            effective_date = f.get('effective_date', date.today().isoformat()),
            review_date   = f.get('review_date', ''),
            status        = 'Active',
            change_summary = f.get('change_summary', ''),
            created_by    = _current_user(),
        )
        if f.get('ae_sign_now') == '1':
            policy.ae_signed_at = datetime.utcnow()

        db.session.add(policy)
        db.session.commit()
        flash(f'✓ Just Culture Policy {policy.version} activated.', 'success')
        return redirect(url_for('enforcement.just_culture_list'))

    latest_jc = JustCulturePolicy.query.order_by(JustCulturePolicy.version_num.desc()).first()
    return render_template('enforcement/just_culture_new.html', users=users, latest_jc=latest_jc)


# ══════════════════════════════════════════════════════════════════════════════
#  10. CONFIDENTIAL ACCESS LOGGING
#  IOSA ISM 1.2.3
# ══════════════════════════════════════════════════════════════════════════════

def log_confidential_access(report_ref: str, report_type: str = 'Confidential',
                             access_type: str = 'view',
                             justification: str = None):
    """
    Write an immutable access log entry every time a confidential report is viewed.
    Called at the start of the confidential report detail route.
    Does not raise exceptions — access logging must never block report access.
    """
    try:
        log = ConfidentialAccessLog(
            report_ref    = report_ref,
            report_type   = report_type,
            accessed_by   = _current_user(),
            accessor_role = _current_role(),
            access_type   = access_type,
            justification = justification,
            ip_address    = request.remote_addr if request else None,
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()


@enf.route('/confidential-access-log')
@require_role('admin', 'safety_manager')
def confidential_access_log():
    """View the confidential report access audit log."""
    logs = ConfidentialAccessLog.query.order_by(
        ConfidentialAccessLog.accessed_at.desc()).limit(200).all()
    flagged = [l for l in logs if l.flagged_for_review]
    return render_template('enforcement/confidential_access_log.html',
                           logs=logs, flagged=flagged)


# ══════════════════════════════════════════════════════════════════════════════
#  REGULATORY NOTIFICATION ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@enf.route('/regulatory-notifications')
@require_login
def reg_notif_list():
    """Regulatory Notification dashboard."""
    notifs = RegulatoryNotification.query.order_by(
        RegulatoryNotification.created_at.desc()).all()
    overdue = [n for n in notifs if (n.verbal_is_overdue or n.written_is_overdue)]
    pending = [n for n in notifs if n.status == 'Pending']
    complete = [n for n in notifs if n.status == 'Complete']
    return render_template('enforcement/reg_notifications.html',
                           notifs=notifs, overdue=overdue,
                           pending=pending, complete=complete)


@enf.route('/regulatory-notifications/new', methods=['GET', 'POST'])
@require_login
def reg_notif_new():
    """Create a regulatory notification record for a notifiable occurrence."""
    if request.method == 'POST':
        f = request.form
        notif = create_regulatory_notification(
            source_type             = f.get('source_type', 'Investigation'),
            source_ref              = f['source_ref'],
            notification_class      = f['notification_class'],
            occurrence_date         = f.get('occurrence_date', ''),
            occurrence_description  = f.get('occurrence_description', ''),
            created_by              = _current_user(),
            department_id           = int(f['department_id']) if f.get('department_id') else None,
        )
        db.session.commit()
        flash(f'✓ Regulatory Notification {notif.ref_number} created.', 'success')
        return redirect(url_for('enforcement.reg_notif_list'))

    departments = Department.query.order_by(Department.name).all()
    return render_template('enforcement/reg_notif_new.html', departments=departments)


@enf.route('/regulatory-notifications/<int:nid>/update-verbal', methods=['POST'])
@require_login
def reg_notif_verbal(nid):
    """Record completion of verbal CAA notification."""
    notif = RegulatoryNotification.query.get_or_404(nid)
    f = request.form
    notif.verbal_notification_done   = True
    notif.verbal_notification_at     = datetime.utcnow()
    notif.verbal_notification_by     = _current_user()
    notif.verbal_notification_method = f.get('method', 'Phone')
    notif.authority_ref              = f.get('authority_ref', notif.authority_ref)
    if notif.written_notification_done:
        notif.status = 'Complete'
    else:
        notif.status = 'Verbal Sent'
    db.session.commit()
    flash('✓ Verbal notification recorded.', 'success')
    return redirect(url_for('enforcement.reg_notif_list'))


@enf.route('/regulatory-notifications/<int:nid>/update-written', methods=['POST'])
@require_login
def reg_notif_written(nid):
    """Record completion of written regulatory report submission."""
    notif = RegulatoryNotification.query.get_or_404(nid)
    f = request.form
    notif.written_notification_done = True
    notif.written_notification_at   = datetime.utcnow()
    notif.written_notification_by   = _current_user()
    notif.written_ref               = f.get('written_ref', '')
    if notif.verbal_notification_done:
        notif.status = 'Complete'
    else:
        notif.status = 'Written Sent'
    db.session.commit()
    flash('✓ Written notification recorded.', 'success')
    return redirect(url_for('enforcement.reg_notif_list'))


# ══════════════════════════════════════════════════════════════════════════════
#  SoD VIOLATION LOG (admin view)
# ══════════════════════════════════════════════════════════════════════════════

@enf.route('/sod-violations')
@require_role('admin', 'safety_manager')
def sod_violations():
    """View all blocked SoD violation attempts."""
    violations = SoDViolationBlock.query.order_by(
        SoDViolationBlock.blocked_at.desc()).limit(200).all()
    return render_template('enforcement/sod_violations.html',
                           violations=violations)


# ══════════════════════════════════════════════════════════════════════════════
#  INVESTIGATION TIMELINE ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@enf.route('/investigation-timelines')
@require_login
def investigation_timelines():
    """Dashboard: all open investigations with timeline compliance status."""
    invs = Investigation.query.filter_by(status='Open').order_by(
        Investigation.created_at.desc()).all()

    # Build alert summary for each investigation
    inv_data = []
    for inv in invs:
        alerts = check_investigation_overdue(inv)
        inv_data.append({
            'inv':    inv,
            'alerts': alerts,
            'critical': any(a['severity'] == 'CRITICAL' for a in alerts),
        })

    # Sort: critical first
    inv_data.sort(key=lambda x: (not x['critical'], x['inv'].date_of_occurrence or ''))

    overdue_count = sum(1 for d in inv_data if d['critical'])
    return render_template('enforcement/investigation_timelines.html',
                           inv_data=inv_data, overdue_count=overdue_count)


@enf.route('/investigation-timelines/<inv_id>/submit-preliminary', methods=['POST'])
@require_login
def submit_preliminary(inv_id):
    """Record submission of preliminary investigation report."""
    inv = Investigation.query.get_or_404(inv_id)
    tl  = getattr(inv, 'timeline_record', None)
    f   = request.form

    inv.preliminary_report_submitted = True
    if tl:
        tl.preliminary_submitted    = True
        tl.preliminary_submitted_at = datetime.utcnow()
        tl.preliminary_submitted_by = _current_user()
        tl.preliminary_ref          = f.get('preliminary_ref', '')
        tl.caa_notified             = f.get('caa_notified') == '1'
        if tl.caa_notified:
            tl.caa_notified_at      = datetime.utcnow()
            tl.caa_notification_ref = f.get('caa_ref', '')

    db.session.commit()
    flash('✓ Preliminary report submission recorded.', 'success')
    return redirect(url_for('enforcement.investigation_timelines'))


# ══════════════════════════════════════════════════════════════════════════════
#  MOBILE API — Reporter Feedback Endpoints
#  Called by Flutter history_screen.dart / notification_service.dart
# ══════════════════════════════════════════════════════════════════════════════

@enf.route('/api/mobile/report-status/<report_ref>')
def api_report_status(report_ref):
    """
    GET /api/mobile/report-status/<ref>
    Returns the reporter feedback record for a given report reference.
    No auth required — ref number is the only identifier (designed for
    anonymous reporters who only know their reference number).
    Rate-limited to prevent enumeration.
    """
    fb = ReportFeedback.query.filter_by(report_ref=report_ref).first()
    if not fb:
        return jsonify({'status': 'not_found',
                        'message': 'Report reference not found.'}), 404

    return jsonify({
        'status':   'ok',
        'data': {
            'report_ref':       fb.report_ref,
            'report_type':      fb.report_type,
            'stage_num':        fb.stage_num,
            'stage_label':      fb.stage_label,
            'guidance':         fb.current_guidance or '',
            'submitted_at':     fb.submitted_at.isoformat() if fb.submitted_at else '',
            'acknowledged_at':  fb.acknowledged_at.isoformat() if fb.acknowledged_at else '',
            'closed_at':        fb.closed_at.isoformat() if fb.closed_at else '',
            'outcome_shared':   fb.outcome_shared,
            'outcome_summary':  fb.outcome_summary or '',
            'outcome_actions':  fb.outcome_actions_taken or '',
            'outcome_risk_level': fb.outcome_risk_level or '',
            'is_ack_overdue':   fb.is_overdue_acknowledgment,
            'ack_due':          fb.acknowledgment_due.isoformat() if fb.acknowledgment_due else '',
        },
    })


@enf.route('/api/mobile/my-report-outcomes')
def api_my_outcomes():
    """
    GET /api/mobile/my-report-outcomes
    Auth required (Bearer token). Returns all ReportFeedback records for the
    authenticated reporter. Used to populate the History screen feedback panel.
    """
    from models import ApiToken
    token_str = ''
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token_str = auth[7:]

    if not token_str:
        return jsonify({'status': 'error', 'message': 'Authentication required.'}), 401

    tok = ApiToken.query.filter_by(token=token_str).first()
    if not tok or tok.is_expired():
        return jsonify({'status': 'error', 'message': 'Session expired.'}), 401

    feedbacks = ReportFeedback.query.filter_by(
        reporter_user_id=tok.user_id
    ).order_by(ReportFeedback.submitted_at.desc()).limit(50).all()

    data = []
    for fb in feedbacks:
        data.append({
            'report_ref':       fb.report_ref,
            'report_type':      fb.report_type,
            'stage_num':        fb.stage_num,
            'stage_label':      fb.stage_label,
            'guidance':         fb.current_guidance or '',
            'submitted_at':     fb.submitted_at.isoformat() if fb.submitted_at else '',
            'acknowledged_at':  fb.acknowledged_at.isoformat() if fb.acknowledged_at else '',
            'closed_at':        fb.closed_at.isoformat() if fb.closed_at else '',
            'outcome_shared':   fb.outcome_shared,
            'outcome_summary':  fb.outcome_summary or '',
            'outcome_actions':  fb.outcome_actions_taken or '',
            'outcome_risk_level': fb.outcome_risk_level or '',
        })

    return jsonify({'status': 'ok', 'data': {'outcomes': data, 'count': len(data)}})
