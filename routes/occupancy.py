from flask import Blueprint, render_template, request, redirect, url_for, flash
from routes.auth import admin_required
from services.occupancy_service import OccupancyService
from database import execute_query

occupancy_bp = Blueprint('occupancy', __name__)

@occupancy_bp.route('/occupancy')
@admin_required
def live_monitor():
    """Live occupancy monitoring dashboard, visual slot grid, active sessions, and check-in/out."""
    metrics = OccupancyService.get_occupancy_metrics()
    active_sessions = OccupancyService.get_active_sessions()
    logs = OccupancyService.get_occupancy_logs(limit=25)

    # Search / filter within active sessions
    search = request.args.get('search', '').strip()
    if search:
        active_sessions = [
            s for s in active_sessions
            if search.lower() in s['license_plate'].lower()
            or search.lower() in s['slot_number'].lower()
            or (s.get('reservation_code') and search.lower() in s['reservation_code'].lower())
        ]

    # Parking slots organized by area for the visual slot map
    areas = execute_query("SELECT * FROM parking_areas ORDER BY floor_level", fetch='all')
    for area in areas:
        area_slots = execute_query(
            "SELECT * FROM parking_slots WHERE area_id = %s AND is_active = 1 ORDER BY slot_number",
            (area['id'],),
            fetch='all'
        )
        area['slots'] = area_slots

    # Pending check-in eligible reservations
    eligible_reservations = execute_query(
        """
        SELECT r.*, c.full_name AS customer_name, v.license_plate, s.slot_number
        FROM reservations r
        JOIN customers c ON r.customer_id = c.id
        JOIN vehicles v ON r.vehicle_id = v.id
        JOIN parking_slots s ON r.slot_id = s.id
        WHERE r.booking_status = 'reserved'
        ORDER BY r.start_time ASC
        """,
        fetch='all'
    )

    return render_template(
        'occupancy.html',
        metrics=metrics,
        active_sessions=active_sessions,
        areas=areas,
        logs=logs,
        eligible_reservations=eligible_reservations,
        search=search
    )

@occupancy_bp.route('/occupancy/checkin', methods=['POST'])
@admin_required
def check_in():
    """Process vehicle arrival check-in."""
    res_input = request.form.get('reservation_input', '').strip()
    if not res_input:
        flash('Please enter or select a valid Reservation Code.', 'danger')
        return redirect(url_for('occupancy.live_monitor'))

    try:
        session_info = OccupancyService.check_in_vehicle(res_input)
        flash(f"Check-in successful! Vehicle {session_info['license_plate']} placed in Slot {session_info['slot_number']}.", 'success')
    except ValueError as e:
        flash(f"Check-in failed: {str(e)}", 'danger')
    except Exception as e:
        flash(f"An unexpected error occurred during check-in: {str(e)}", 'danger')

    return redirect(url_for('occupancy.live_monitor'))

@occupancy_bp.route('/occupancy/checkout/<int:session_id>', methods=['POST'])
@admin_required
def check_out(session_id):
    """Process vehicle departure check-out."""
    try:
        result = OccupancyService.check_out_vehicle(session_id)
        flash(
            f"Check-out complete for Slot {result['slot_number']} ({result['license_plate']}). "
            f"Duration: {result['duration_hours']}h | Total Fee: ${result['final_fee']:.2f}. "
            f"Parking slot has been released.",
            'success'
        )
    except ValueError as e:
        flash(f"Check-out failed: {str(e)}", 'danger')
    except Exception as e:
        flash(f"An unexpected error occurred during check-out: {str(e)}", 'danger')

    return redirect(url_for('occupancy.live_monitor'))
