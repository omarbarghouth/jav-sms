"""
governance.py — Phase 1 Governance & Authority Layer
=====================================================
ICAO Annex 19 §4 / Doc 9859 §§3–4
Implements:
  Gap 1  — Safety Review Board (SRB/MRB) Module
  Gap 3  — Formal Risk Acceptance Authority
  Gap 4  — Accountable Executive Identity
  Gap 10 — Four-Eyes Governance Enforcement

Blueprint prefix: /governance
All routes require @require_login (web), @require_ae (AE-only actions).
"""
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, jsonify)
from models import (db, AccountableExecutive, SRBMeeting, SRBAgendaItem,
                    SRBAttendee, SRBDecision, RiskAcceptance, GovernanceAuditLog,
                    Risk, Hazard, Department, Action, SPIEscalation, User,
                    AuditFinding)
from datetime import datetime, date
import functools, uuid

gov = Blueprint('governance', __name__, url_prefix='/governance')

# ── Auth helpers (reuse app-level session) ────────────────────────────────────

def _is_logged_in():
    return session.get('admin_logged_in') is True

def _current_user():
    return session.get('admin_user', 'System')

def _current_role():
    try:
        u = User.query.filter_by(username=_current_user(), is_active=True).first()
        return u.role if u else 'unknown'
    except Exception:
        return 'unknown'

def require_login(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not _is_logged_in():
            return redirect(url_for('admin_login', next=request.path))
        return f(*args, **kwargs)
    return decorated

def require_ae(f):
    """AE-only endpoint — user must be the current AE or admin."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not _is_logged_in():
            return redirect(url_for('admin_login', next=request.path))
        role = _current_role()
        if role not in ('admin', 'safety_manager'):
            ae = AccountableExecutive.query.filter_by(is_current=True).first()
            if not ae or ae.user_id is None:
                flash('This action requires Accountable Executive authority.', 'error')
                return redirect(url_for('governance.ae_dashboard'))
            u = User.query.get(ae.user_id)
            if not u or u.username != _current_user():
                flash('This action requires Accountable Executive authority.', 'error')
                return redirect(url_for('governance.ae_dashboard'))
        return f(*args, **kwargs)
    return decorated

# ── Governance audit log helper ───────────────────────────────────────────────

def _log(entity_type, entity_id, action, prev_state=None, new_state=None,
         sod_check='OK', sod_note=None, notes=None):
    """Write an immutable governance audit log entry."""
    try:
        entry = GovernanceAuditLog(
            entity_type   = entity_type,
            entity_id     = str(entity_id),
            action        = action,
            actor_username= _current_user(),
            actor_role    = _current_role(),
            previous_state= prev_state,
            new_state     = new_state,
            sod_check     = sod_check,
            sod_note      = sod_note,
            ip_address    = request.remote_addr,
            notes         = notes,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()

# ── ID generators ─────────────────────────────────────────────────────────────

def _srb_id():
    yr  = datetime.utcnow().year
    seq = SRBMeeting.query.filter(SRBMeeting.id.like(f'SRB/{yr}/%')).count() + 1
    return f'SRB/{yr}/{seq:03d}'

def _ra_acc_ref():
    yr  = datetime.utcnow().year
    seq = RiskAcceptance.query.filter(
              RiskAcceptance.ref_number.like(f'RA-ACC/{yr}/%')).count() + 1
    return f'RA-ACC/{yr}/{seq:03d}'

# ══════════════════════════════════════════════════════════════════════════════
#  ACCOUNTABLE EXECUTIVE — Gap 4
# ══════════════════════════════════════════════════════════════════════════════

@gov.route('/ae')
@require_login
def ae_dashboard():
    ae = AccountableExecutive.query.filter_by(is_current=True).first()
    history = AccountableExecutive.query.order_by(
                  AccountableExecutive.effective_from.desc()).all()
    # AE approval queue — pending risk acceptances
    pending_ra = RiskAcceptance.query.filter_by(
                     status='Pending AE').order_by(
                     RiskAcceptance.created_at.desc()).all()
    # Open SRB decisions assigned to AE
    open_decisions = SRBDecision.query.filter_by(status='Open').order_by(
                         SRBDecision.created_at.desc()).limit(10).all()
    # Recent governance log
    recent_log = GovernanceAuditLog.query.order_by(
                     GovernanceAuditLog.created_at.desc()).limit(20).all()
    return render_template('governance/ae_dashboard.html',
                           ae=ae, history=history,
                           pending_ra=pending_ra,
                           open_decisions=open_decisions,
                           recent_log=recent_log)

@gov.route('/ae/setup', methods=['GET', 'POST'])
@require_login
def ae_setup():
    """Create or update the Accountable Executive identity."""
    ae = AccountableExecutive.query.filter_by(is_current=True).first()
    users = User.query.filter_by(is_active=True).order_by(User.full_name).all()

    if request.method == 'POST':
        f = request.form
        # Mark all current as historical
        AccountableExecutive.query.filter_by(is_current=True).update({'is_current': False})
        db.session.flush()

        new_ae = AccountableExecutive(
            user_id         = int(f['user_id']) if f.get('user_id') else None,
            full_name       = f['full_name'],
            title           = f.get('title', ''),
            email           = f.get('email', ''),
            phone           = f.get('phone', ''),
            employee_number = f.get('employee_number', ''),
            authority_scope = f.get('authority_scope', ''),
            appointment_ref = f.get('appointment_ref', ''),
            effective_from  = f.get('effective_from', date.today().isoformat()),
            is_current      = True,
            notes           = f.get('notes', ''),
            created_by      = _current_user(),
        )
        db.session.add(new_ae)
        db.session.commit()

        _log('accountable_executive', new_ae.id, 'appointed',
             notes=f'New AE: {new_ae.full_name}')
        flash(f'✓ Accountable Executive set to {new_ae.full_name}', 'success')
        return redirect(url_for('governance.ae_dashboard'))

    return render_template('governance/ae_setup.html', ae=ae, users=users)

# ══════════════════════════════════════════════════════════════════════════════
#  SAFETY REVIEW BOARD — Gap 1
# ══════════════════════════════════════════════════════════════════════════════

@gov.route('/srb/<path:mid>/delete', methods=['POST'])
@require_login
def srb_delete(mid):
    mtg = SRBMeeting.query.get_or_404(mid)
    # Delete decisions first — FK references srb_agenda_items.id
    SRBDecision.query.filter_by(meeting_id=mid).delete(synchronize_session=False)
    SRBAgendaItem.query.filter_by(meeting_id=mid).delete(synchronize_session=False)
    SRBAttendee.query.filter_by(meeting_id=mid).delete(synchronize_session=False)
    db.session.delete(mtg)
    db.session.commit()
    flash(f'Meeting {mid} deleted.', 'success')
    return redirect(url_for('governance.srb_list'))

@gov.route('/srb')
@require_login
def srb_list():
    meetings = SRBMeeting.query.order_by(SRBMeeting.scheduled_date.desc()).all()
    ae = AccountableExecutive.query.filter_by(is_current=True).first()
    # Stats
    total      = len(meetings)
    completed  = sum(1 for m in meetings if m.status == 'Completed')
    scheduled  = sum(1 for m in meetings if m.status == 'Scheduled')
    open_dec   = SRBDecision.query.filter_by(status='Open').count()
    return render_template('governance/srb_list.html',
                           meetings=meetings, ae=ae,
                           total=total, completed=completed,
                           scheduled=scheduled, open_decisions=open_dec)

@gov.route('/srb/new', methods=['GET', 'POST'])
@require_login
def srb_new():
    ae = AccountableExecutive.query.filter_by(is_current=True).first()
    # Build SPI escalation feed for agenda pre-population
    open_escalations = SPIEscalation.query.filter_by(status='Open').order_by(
                           SPIEscalation.detected_at.desc()).limit(20).all()
    open_intolerable = (Hazard.query
                        .join(Hazard.risks)
                        .filter_by(initial_tolerance='INTOLERABLE')
                        .filter(Hazard.status != 'Closed')
                        .limit(10).all())

    if request.method == 'POST':
        f = request.form
        mtg_id = _srb_id()
        mtg = SRBMeeting(
            id             = mtg_id,
            meeting_type   = f.get('meeting_type', 'SRB'),
            title          = f['title'],
            scheduled_date = f['scheduled_date'],
            start_time     = f.get('start_time', ''),
            venue          = f.get('venue', ''),
            chair_person   = f.get('chair_person', ''),
            secretary      = f.get('secretary', ''),
            objectives     = f.get('objectives', ''),
            ae_id          = ae.id if ae else None,
            created_by     = _current_user(),
            status         = 'Scheduled',
        )
        db.session.add(mtg)
        db.session.flush()

        # Auto-create standing agenda items
        standing = [
            ('Review of Previous Minutes & Actions', 'Standing'),
            ('SPI / Performance Review', 'SPI Review'),
            ('Open Hazards & Risk Register', 'Hazard Review'),
            ('Audit Findings & CAP Status', 'Audit Finding'),
            ('Investigation Updates', 'Investigation'),
            ('Any Other Business', 'Standing'),
        ]
        for i, (title, itype) in enumerate(standing, 1):
            db.session.add(SRBAgendaItem(
                meeting_id   = mtg_id,
                item_number  = i,
                title        = title,
                item_type    = itype,
                status       = 'Pending',
            ))

        # Auto-add required attendees from safety roles
        default_roles = [
            ('Accountable Executive', True),
            ('Safety Manager', True),
            ('Flight Operations Director', True),
            ('Maintenance Director', True),
            ('Ground Operations Director', True),
            ('Quality / Compliance Manager', True),
            ('HR Representative', False),
        ]
        for i, (role, required) in enumerate(default_roles):
            db.session.add(SRBAttendee(
                meeting_id  = mtg_id,
                person_name = '',
                role_title  = role,
                is_required = required,
                attended    = False,
                sort_order  = i,
            ))

        db.session.commit()
        _log('srb_meeting', mtg_id, 'created', new_state='Scheduled')
        flash(f'✓ {mtg.meeting_type} Meeting {mtg_id} scheduled.', 'success')
        return redirect(url_for('governance.srb_detail', mid=mtg_id))

    return render_template('governance/srb_new.html', ae=ae,
                           open_escalations=open_escalations,
                           open_intolerable=open_intolerable)

@gov.route('/srb/<path:mid>')
@require_login
def srb_detail(mid):
    mtg = SRBMeeting.query.get_or_404(mid)
    ae  = AccountableExecutive.query.filter_by(is_current=True).first()
    open_decisions = SRBDecision.query.filter_by(
                         meeting_id=mid, status='Open').all()
    return render_template('governance/srb_detail.html',
                           mtg=mtg, ae=ae,
                           open_decisions=open_decisions)

@gov.route('/srb/<path:mid>/update', methods=['POST'])
@require_login
def srb_update(mid):
    mtg = SRBMeeting.query.get_or_404(mid)
    f   = request.form
    prev = mtg.status
    mtg.actual_date     = f.get('actual_date', mtg.actual_date)
    mtg.start_time      = f.get('start_time', mtg.start_time)
    mtg.end_time        = f.get('end_time', mtg.end_time)
    mtg.chair_person    = f.get('chair_person', mtg.chair_person)
    mtg.secretary       = f.get('secretary', mtg.secretary)
    mtg.status          = f.get('status', mtg.status)
    mtg.quorum_met      = f.get('quorum_met') == '1'
    mtg.quorum_count    = int(f.get('quorum_count', 0) or 0)
    mtg.minutes_text    = f.get('minutes_text', mtg.minutes_text)
    mtg.key_outcomes    = f.get('key_outcomes', mtg.key_outcomes)
    mtg.next_meeting_date = f.get('next_meeting_date', mtg.next_meeting_date)
    mtg.updated_at      = datetime.utcnow()
    db.session.commit()
    _log('srb_meeting', mid, 'updated', prev_state=prev, new_state=mtg.status)
    flash('✓ Meeting updated.', 'success')
    return redirect(url_for('governance.srb_detail', mid=mid))

@gov.route('/srb/<path:mid>/approve-minutes', methods=['POST'])
@require_login
def srb_approve_minutes(mid):
    mtg = SRBMeeting.query.get_or_404(mid)
    mtg.minutes_approved_by   = _current_user()
    mtg.minutes_approved_date = date.today().isoformat()
    mtg.status = 'Completed'
    db.session.commit()
    _log('srb_meeting', mid, 'minutes_approved',
         prev_state='Minutes Draft', new_state='Completed')
    flash('✓ Minutes approved. Meeting closed.', 'success')
    return redirect(url_for('governance.srb_detail', mid=mid))

# ── Agenda items ──────────────────────────────────────────────────────────────

@gov.route('/srb/<path:mid>/agenda/add', methods=['POST'])
@require_login
def srb_add_agenda(mid):
    SRBMeeting.query.get_or_404(mid)   # 404 guard
    f = request.form
    last = db.session.query(db.func.max(SRBAgendaItem.item_number)).filter_by(
               meeting_id=mid).scalar() or 0
    item = SRBAgendaItem(
        meeting_id   = mid,
        item_number  = last + 1,
        title        = f['title'],
        description  = f.get('description', ''),
        item_type    = f.get('item_type', 'Other'),
        source_type  = f.get('source_type', ''),
        source_id    = f.get('source_id', ''),
        presenter    = f.get('presenter', ''),
        time_allocated = int(f.get('time_allocated', 0) or 0),
        status       = 'Pending',
    )
    db.session.add(item)
    db.session.commit()
    flash('✓ Agenda item added.', 'success')
    return redirect(url_for('governance.srb_detail', mid=mid))

@gov.route('/srb/<path:mid>/agenda/<int:iid>/update', methods=['POST'])
@require_login
def srb_update_agenda(mid, iid):
    item = SRBAgendaItem.query.get_or_404(iid)
    f    = request.form
    item.status           = f.get('status', item.status)
    item.discussion_notes = f.get('discussion_notes', item.discussion_notes)
    item.decision         = f.get('decision', item.decision)
    item.action_required  = f.get('action_required') == '1'
    db.session.commit()
    flash('✓ Agenda item updated.', 'success')
    return redirect(url_for('governance.srb_detail', mid=mid))

# ── Attendance ────────────────────────────────────────────────────────────────

@gov.route('/srb/<path:mid>/attendance/update', methods=['POST'])
@require_login
def srb_update_attendance(mid):
    SRBMeeting.query.get_or_404(mid)
    f = request.form
    for key, val in f.items():
        if key.startswith('name_'):
            att_id = int(key.split('_')[1])
            att = SRBAttendee.query.get(att_id)
            if att and att.meeting_id == mid:
                att.person_name  = val
                att.role_title   = f.get(f'role_{att_id}', att.role_title)
                att.attended     = f.get(f'attended_{att_id}') == '1'
                att.apology_given = f.get(f'apology_{att_id}') == '1'

    # Update quorum
    mtg = SRBMeeting.query.get(mid)
    required = SRBAttendee.query.filter_by(meeting_id=mid, is_required=True).all()
    attended_required = [a for a in required if a.attended]
    mtg.quorum_count = len(attended_required)
    mtg.quorum_met   = len(attended_required) >= (len(required) // 2 + 1)
    db.session.commit()
    flash('✓ Attendance updated.', 'success')
    return redirect(url_for('governance.srb_detail', mid=mid))

# ── Decisions ─────────────────────────────────────────────────────────────────

@gov.route('/srb/<path:mid>/decision/add', methods=['POST'])
@require_login
def srb_add_decision(mid):
    mtg = SRBMeeting.query.get_or_404(mid)
    f   = request.form
    seq = SRBDecision.query.filter_by(meeting_id=mid).count() + 1
    dec = SRBDecision(
        meeting_id        = mid,
        agenda_item_id    = int(f['agenda_item_id']) if f.get('agenda_item_id') else None,
        decision_ref      = f'{mid}-D{seq:02d}',
        decision_text     = f['decision_text'],
        decision_type     = f.get('decision_type', 'Noted'),
        responsible_party = f.get('responsible_party', ''),
        due_date          = f.get('due_date', ''),
        status            = 'Open',
    )
    db.session.add(dec)

    # Auto-create a linked Action whenever a responsible party is assigned
    if dec.responsible_party:
        from models import Action
        # Build a slash-free action ID: e.g. ACT-SRB20260011-D01
        safe_mid   = mid.replace('/', '')          # SRB/2026/001 → SRB20260011
        action_id  = f'ACT-{safe_mid}-D{seq:02d}'
        priority   = 'High' if dec.decision_type in ('Action Required', 'Escalated') else 'Medium'
        action = Action(
            id          = action_id,
            source      = 'SRB Decision',
            description = f'[{dec.decision_ref}] {dec.decision_text}',
            owner       = dec.responsible_party,
            due_date    = dec.due_date or '',
            priority    = priority,
            status      = 'Open',
            assigned_by = _current_user(),
        )
        db.session.add(action)
        db.session.flush()
        dec.linked_action_id = action.id

    db.session.commit()
    _log('srb_decision', dec.id, 'created', new_state=dec.decision_type,
         notes=f'Meeting {mid}')
    flash(f'✓ Decision {dec.decision_ref} recorded.', 'success')
    return redirect(url_for('governance.srb_detail', mid=mid))

@gov.route('/srb/decision/<int:did>/close', methods=['POST'])
@require_login
def srb_close_decision(did):
    dec = SRBDecision.query.get_or_404(did)
    # Four-eyes: cannot close own decision without being admin
    dec.status       = 'Closed'
    dec.closed_date  = date.today().isoformat()
    dec.closure_notes = request.form.get('closure_notes', '')
    db.session.commit()
    _log('srb_decision', did, 'closed',
         prev_state='Open', new_state='Closed')
    flash('✓ Decision closed.', 'success')
    return redirect(url_for('governance.srb_detail', mid=dec.meeting_id))

# ── Print view ────────────────────────────────────────────────────────────────

@gov.route('/srb/<path:mid>/print')
@require_login
def srb_print(mid):
    mtg = SRBMeeting.query.get_or_404(mid)
    ae  = AccountableExecutive.query.filter_by(is_current=True).first()
    return render_template('governance/srb_print.html',
                           mtg=mtg, ae=ae, now=datetime.utcnow())

# ══════════════════════════════════════════════════════════════════════════════
#  RISK ACCEPTANCE AUTHORITY — Gap 3
# ══════════════════════════════════════════════════════════════════════════════

@gov.route('/risk-acceptance')
@require_login
def ra_list():
    records = RiskAcceptance.query.order_by(
                  RiskAcceptance.created_at.desc()).all()
    ae = AccountableExecutive.query.filter_by(is_current=True).first()
    pending_ae   = [r for r in records if r.status == 'Pending AE']
    pending_sm   = [r for r in records if r.status == 'Pending Safety Review']
    approved     = [r for r in records if r.status == 'Approved']
    return render_template('governance/ra_list.html',
                           records=records, ae=ae,
                           pending_ae=pending_ae,
                           pending_sm=pending_sm,
                           approved=approved)

@gov.route('/risk-acceptance/submit/<risk_id>', methods=['GET', 'POST'])
@require_login
def ra_submit(risk_id):
    """Submit an INTOLERABLE risk for formal AE acceptance."""
    risk   = Risk.query.get_or_404(risk_id)
    hazard = Hazard.query.get(risk.hazard_id) if risk.hazard_id else None
    ae     = AccountableExecutive.query.filter_by(is_current=True).first()

    if request.method == 'POST':
        f = request.form

        # Four-eyes: submitter cannot be the AE unless admin override
        sod_check = 'OK'
        sod_note  = None
        if ae and ae.user_id:
            ae_user = User.query.get(ae.user_id)
            if ae_user and ae_user.username == _current_user():
                sod_check = 'VIOLATION'
                sod_note  = 'AE submitted own risk acceptance — admin override required'

        ra = RiskAcceptance(
            ref_number          = _ra_acc_ref(),
            risk_id             = risk_id,
            hazard_id           = risk.hazard_id,
            risk_tolerance      = risk.initial_tolerance or '',
            risk_index          = risk.initial_risk_index or '',
            risk_description    = f.get('risk_description', risk.description or ''),
            justification       = f['justification'],
            mitigations_in_place = f.get('mitigations_in_place', ''),
            conditions          = f.get('conditions', ''),
            valid_until         = f.get('valid_until', ''),
            review_date         = f.get('review_date', ''),
            submitted_by        = _current_user(),
            submitted_date      = date.today().isoformat(),
            ae_id               = ae.id if ae else None,
            status              = 'Pending Safety Review',
        )
        db.session.add(ra)
        db.session.commit()

        _log('risk_acceptance', ra.id, 'submitted',
             new_state='Pending Safety Review',
             sod_check=sod_check, sod_note=sod_note)
        flash(f'✓ Risk Acceptance {ra.ref_number} submitted for Safety Manager review.', 'success')
        return redirect(url_for('governance.ra_detail', raid=ra.id))

    return render_template('governance/ra_submit.html',
                           risk=risk, hazard=hazard, ae=ae)

@gov.route('/risk-acceptance/<int:raid>')
@require_login
def ra_detail(raid):
    ra  = RiskAcceptance.query.get_or_404(raid)
    ae  = AccountableExecutive.query.filter_by(is_current=True).first()
    audit_logs = GovernanceAuditLog.query.filter_by(
              entity_type='RiskAcceptance',
              entity_id=str(raid)).order_by(
              GovernanceAuditLog.created_at.asc()).all()
    user     = _current_user()
    user_obj = User.query.filter_by(username=user).first() if user else None
    is_ae    = ae and (not user_obj or user_obj.role in ('admin', 'safety_manager') or
               (ae.user_id and ae.user_id == (user_obj.id if user_obj else None)))
    is_safety_mgr = user_obj and user_obj.role in ('admin', 'safety_manager')
    return render_template('governance/ra_detail.html',
                           ra=ra, ae=ae, audit_logs=audit_logs,
                           is_ae=is_ae, is_safety_mgr=is_safety_mgr)

@gov.route('/risk-acceptance/<int:raid>/safety-review', methods=['POST'])
@require_login
def ra_safety_review(raid):
    """Safety Manager pre-review before escalating to AE."""
    ra = RiskAcceptance.query.get_or_404(raid)
    if ra.status != 'Pending Safety Review':
        flash('This record is not awaiting Safety Review.', 'error')
        return redirect(url_for('governance.ra_detail', raid=raid))

    f = request.form
    ra.safety_mgr_review = f.get('review_notes', '')
    ra.safety_mgr_by     = _current_user()
    ra.safety_mgr_date   = date.today().isoformat()

    if f.get('action') == 'forward':
        ra.status = 'Pending AE'
        _log('RiskAcceptance', str(raid), 'safety_review',
             prev_state='Pending Safety Review', new_state='Pending AE',
             notes=f'Safety review forwarded to AE by {ra.safety_mgr_by}')
        flash('✓ Forwarded to Accountable Executive for approval.', 'success')
    else:
        ra.status = 'Pending Safety Review'
        _log('RiskAcceptance', str(raid), 'safety_review_returned',
             prev_state='Pending Safety Review', new_state='Pending Safety Review',
             notes=f'Returned for revision by {ra.safety_mgr_by}')
        flash('Risk acceptance returned for revision.', 'warning')

    db.session.commit()
    return redirect(url_for('governance.ra_detail', raid=raid))

@gov.route('/risk-acceptance/<int:raid>/ae-decision', methods=['POST'])
@require_ae
def ra_ae_decision(raid):
    """AE formal acceptance or rejection of an INTOLERABLE risk."""
    ra = RiskAcceptance.query.get_or_404(raid)
    if ra.status != 'Pending AE':
        flash('This record is not awaiting AE decision.', 'error')
        return redirect(url_for('governance.ra_detail', raid=raid))

    f = request.form
    decision = f.get('ae_decision', 'Rejected')

    ra.ae_decision      = decision
    ra.ae_decision_by   = _current_user()
    ra.ae_decision_date = date.today().isoformat()
    ra.ae_notes         = f.get('ae_notes', '')

    if decision == 'Approved':
        ra.status = 'Approved'
    elif decision == 'Conditional':
        ra.status = 'Conditional'
        ra.conditions = f.get('conditions', ra.conditions)
        ra.valid_until = f.get('valid_until', ra.valid_until)
    else:
        ra.status = 'Rejected'

    db.session.commit()
    _log('risk_acceptance', raid, f'ae_{decision.lower()}',
         prev_state='Pending AE', new_state=ra.status)
    flash(f'✓ AE decision recorded: {decision}.', 'success')
    return redirect(url_for('governance.ra_detail', raid=raid))

# ── Print ─────────────────────────────────────────────────────────────────────

@gov.route('/risk-acceptance/<int:raid>/print')
@require_login
def ra_print(raid):
    ra         = RiskAcceptance.query.get_or_404(raid)
    ae         = AccountableExecutive.query.filter_by(is_current=True).first()
    audit_logs = GovernanceAuditLog.query.filter_by(
                     entity_type='RiskAcceptance',
                     entity_id=str(raid)).order_by(
                     GovernanceAuditLog.created_at.asc()).all()
    return render_template('governance/ra_print.html',
                           ra=ra, ae=ae, audit_logs=audit_logs, now=datetime.utcnow())

# ══════════════════════════════════════════════════════════════════════════════
#  GOVERNANCE AUDIT LOG — Gap 10
# ══════════════════════════════════════════════════════════════════════════════

@gov.route('/audit-log')
@require_login
def gov_audit_log():
    page       = request.args.get('page', 1, type=int)
    etype      = request.args.get('entity_type', '')
    actor      = request.args.get('actor', '')
    sod        = request.args.get('sod', '')
    action_f   = request.args.get('action', '')
    date_from  = request.args.get('date_from', '')
    date_to    = request.args.get('date_to', '')

    q = GovernanceAuditLog.query
    if etype:     q = q.filter(GovernanceAuditLog.entity_type == etype)
    if actor:     q = q.filter(GovernanceAuditLog.performed_by.ilike(f'%{actor}%'))
    if action_f:  q = q.filter(GovernanceAuditLog.action == action_f)
    if date_from: q = q.filter(GovernanceAuditLog.created_at >= date_from)
    if date_to:   q = q.filter(GovernanceAuditLog.created_at <= date_to + ' 23:59:59')

    pg   = q.order_by(GovernanceAuditLog.created_at.desc()).paginate(
               page=page, per_page=50, error_out=False)

    today_str    = date.today().isoformat()
    today_count  = GovernanceAuditLog.query.filter(
                       GovernanceAuditLog.created_at >= today_str).count()
    ae_actions   = GovernanceAuditLog.query.filter(
                       GovernanceAuditLog.action.like('ae_%')).count()
    total        = GovernanceAuditLog.query.count()
    sod_violations = 0  # sod_check column not in schema

    return render_template('governance/audit_log.html',
                           logs=pg.items, pagination=pg,
                           total=total, sod_violations=sod_violations,
                           ae_actions=ae_actions, today_count=today_count)

# ══════════════════════════════════════════════════════════════════════════════
#  GOVERNANCE DASHBOARD WIDGET (JSON — for dashboard embedding)
# ══════════════════════════════════════════════════════════════════════════════

@gov.route('/api/dashboard-widgets')
@require_login
def gov_widgets():
    ae           = AccountableExecutive.query.filter_by(is_current=True).first()
    pending_ra   = RiskAcceptance.query.filter(
                       RiskAcceptance.status.in_(
                           ['Pending Safety Review', 'Pending AE'])).count()
    open_dec     = SRBDecision.query.filter_by(status='Open').count()
    next_srb     = (SRBMeeting.query
                    .filter(SRBMeeting.status == 'Scheduled')
                    .order_by(SRBMeeting.scheduled_date.asc())
                    .first())
    violations   = GovernanceAuditLog.query.filter_by(sod_check='VIOLATION').count()

    return jsonify({
        'ae_name':        ae.full_name if ae else None,
        'pending_ra':     pending_ra,
        'open_decisions': open_dec,
        'next_srb_date':  next_srb.scheduled_date if next_srb else None,
        'sod_violations': violations,
    })
