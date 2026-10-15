from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from routes.auth import admin_required
from database import execute_query, transaction

parking_bp = Blueprint('parking', __name__)

@parking_bp.route('/parking')
@admin_required
def slots_list():
    """View parking spaces list & grid with search and filter controls."""
    search = request.args.get('search', '').strip()
    area_filter = request.args.get('area', '')
    type_filter = request.args.get('type', '')
    status_filter = request.args.get('status', '')

    query = """
        SELECT s.*, a.name AS area_name, a.floor_level, a.area_code
        FROM parking_slots s
        JOIN parking_areas a ON s.area_id = a.id
        WHERE s.is_active = 1
    """
    params = []

    if search:
        query += " AND s.slot_number LIKE %s"
        params.append(f"%{search}%")
    if area_filter and area_filter != 'all':
        query += " AND s.area_id = %s"
        params.append(area_filter)
    if type_filter and type_filter != 'all':
        query += " AND s.slot_type = %s"
        params.append(type_filter)
    if status_filter and status_filter != 'all':
        query += " AND s.status = %s"
        params.append(status_filter)

    query += " ORDER BY a.floor_level, s.slot_number"
    slots = execute_query(query, tuple(params), fetch='all')

    areas = execute_query("SELECT * FROM parking_areas ORDER BY floor_level", fetch='all')

    return render_template(
        'parking_slots.html',
        slots=slots,
        areas=areas,
        search=search,
        selected_area=area_filter,
        selected_type=type_filter,
        selected_status=status_filter
    )

@parking_bp.route('/parking/add', methods=['POST'])
@admin_required
def add_slot():
    """Add a new parking slot with validation preventing duplicates."""
    area_id = request.form.get('area_id')
    slot_number = request.form.get('slot_number', '').strip().upper()
    slot_type = request.form.get('slot_type', 'regular')
    hourly_rate = request.form.get('hourly_rate', 5.0)

    if not area_id or not slot_number:
        flash('Area and Slot Number are required.', 'danger')
        return redirect(url_for('parking.slots_list'))

    try:
        rate = float(hourly_rate)
        if rate <= 0:
            flash('Hourly rate must be greater than zero.', 'danger')
            return redirect(url_for('parking.slots_list'))
    except ValueError:
        flash('Invalid hourly rate provided.', 'danger')
        return redirect(url_for('parking.slots_list'))

    # Check for duplicate slot number in the specified area
    existing = execute_query(
        "SELECT id FROM parking_slots WHERE area_id = %s AND slot_number = %s AND is_active = 1",
        (area_id, slot_number),
        fetch='one'
    )
    if existing:
        flash(f"Slot number '{slot_number}' already exists in this parking area.", 'danger')
        return redirect(url_for('parking.slots_list'))

    # Insert slot
    execute_query(
        """
        INSERT INTO parking_slots (area_id, slot_number, slot_type, hourly_rate, status, is_active)
        VALUES (%s, %s, %s, %s, 'available', 1)
        """,
        (area_id, slot_number, slot_type, rate),
        commit=True
    )
    flash(f"Parking Slot '{slot_number}' successfully created.", 'success')
    return redirect(url_for('parking.slots_list'))

@parking_bp.route('/parking/edit/<int:slot_id>', methods=['POST'])
@admin_required
def edit_slot(slot_id):
    """Edit parking slot details."""
    slot = execute_query("SELECT * FROM parking_slots WHERE id = %s", (slot_id,), fetch='one')
    if not slot:
        flash('Parking slot not found.', 'danger')
        return redirect(url_for('parking.slots_list'))

    slot_type = request.form.get('slot_type', slot['slot_type'])
    hourly_rate = request.form.get('hourly_rate', slot['hourly_rate'])
    status = request.form.get('status', slot['status'])

    try:
        rate = float(hourly_rate)
        if rate <= 0:
            flash('Hourly rate must be greater than zero.', 'danger')
            return redirect(url_for('parking.slots_list'))
    except ValueError:
        flash('Invalid hourly rate.', 'danger')
        return redirect(url_for('parking.slots_list'))

    # Prevent marking as maintenance if occupied
    if status == 'maintenance' and slot['status'] == 'occupied':
        flash('Cannot set slot to maintenance while currently occupied by a vehicle.', 'warning')
        return redirect(url_for('parking.slots_list'))

    execute_query(
        """
        UPDATE parking_slots 
        SET slot_type = %s, hourly_rate = %s, status = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (slot_type, rate, status, slot_id),
        commit=True
    )
    flash(f"Parking Slot '{slot['slot_number']}' details updated.", 'success')
    return redirect(url_for('parking.slots_list'))

@parking_bp.route('/parking/delete/<int:slot_id>', methods=['POST'])
@admin_required
def delete_slot(slot_id):
    """
    Delete a parking slot only when it has no active reservation or occupancy.
    Strictly prevents deleting reserved or occupied slots.
    """
    slot = execute_query("SELECT * FROM parking_slots WHERE id = %s", (slot_id,), fetch='one')
    if not slot:
        flash('Parking slot not found.', 'danger')
        return redirect(url_for('parking.slots_list'))

    # 1. Check if slot is occupied
    if slot['status'] == 'occupied':
        flash(f"Cannot delete Slot '{slot['slot_number']}': The slot is currently OCCUPIED by a parked vehicle.", 'danger')
        return redirect(url_for('parking.slots_list'))

    # 2. Check if slot has active sessions
    active_session = execute_query(
        "SELECT id FROM parking_sessions WHERE slot_id = %s AND status = 'active'",
        (slot_id,),
        fetch='one'
    )
    if active_session:
        flash(f"Cannot delete Slot '{slot['slot_number']}': An active parking session is currently ongoing.", 'danger')
        return redirect(url_for('parking.slots_list'))

    # 3. Check if slot has active or pending reservations
    active_res = execute_query(
        "SELECT id, reservation_code FROM reservations WHERE slot_id = %s AND booking_status IN ('reserved', 'active', 'pending')",
        (slot_id,),
        fetch='one'
    )
    if active_res:
        flash(f"Cannot delete Slot '{slot['slot_number']}': Active reservation '{active_res['reservation_code']}' is assigned to this slot.", 'danger')
        return redirect(url_for('parking.slots_list'))

    # Soft delete (mark inactive) so historical records maintain integrity
    execute_query("UPDATE parking_slots SET is_active = 0, status = 'maintenance' WHERE id = %s", (slot_id,), commit=True)
    flash(f"Parking Slot '{slot['slot_number']}' was safely removed.", 'success')
    return redirect(url_for('parking.slots_list'))
