import io
import csv
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from routes.auth import admin_required
from services.reservation_service import ReservationService
from database import execute_query

reservations_bp = Blueprint('reservations', __name__)

@reservations_bp.route('/reservations')
@admin_required
def list_reservations():
    """List all reservations with search, status filtering, and date filtering."""
    search = request.args.get('search', '').strip()
    status = request.args.get('status', 'all')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    reservations = ReservationService.get_reservations(
        search=search,
        status=status,
        date_from=date_from,
        date_to=date_to
    )

    return render_template(
        'reservations.html',
        reservations=reservations,
        search=search,
        status=status,
        date_from=date_from,
        date_to=date_to
    )

@reservations_bp.route('/reservations/new', methods=['GET', 'POST'])
@admin_required
def create_reservation():
    """Create new reservation with real-time fee estimation and strict validation."""
    if request.method == 'POST':
        customer_name = request.form.get('customer_name', '').strip()
        customer_email = request.form.get('customer_email', '').strip()
        customer_phone = request.form.get('customer_phone', '').strip()
        
        license_plate = request.form.get('license_plate', '').strip().upper()
        vehicle_type = request.form.get('vehicle_type', 'Sedan')
        make_model = request.form.get('make_model', '').strip()
        
        slot_id = request.form.get('slot_id')
        start_time_str = request.form.get('start_time', '').strip()
        end_time_str = request.form.get('end_time', '').strip()
        notes = request.form.get('notes', '').strip()

        # Input validation
        if not customer_name:
            flash('Customer full name is required.', 'danger')
            return redirect(url_for('reservations.create_reservation'))
        if not license_plate:
            flash('Vehicle license plate number is required.', 'danger')
            return redirect(url_for('reservations.create_reservation'))
        if not slot_id:
            flash('Please select a parking slot.', 'danger')
            return redirect(url_for('reservations.create_reservation'))
        if not start_time_str or not end_time_str:
            flash('Both reservation start and end times are required.', 'danger')
            return redirect(url_for('reservations.create_reservation'))

        try:
            # Parse datetime formats (HTML5 datetime-local returns YYYY-MM-DDTHH:MM)
            start_time_clean = start_time_str.replace('T', ' ')
            end_time_clean = end_time_str.replace('T', ' ')
            if len(start_time_clean) == 16:
                start_time_clean += ":00"
            if len(end_time_clean) == 16:
                end_time_clean += ":00"
                
            start_dt = datetime.strptime(start_time_clean, "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(end_time_clean, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            flash('Invalid date/time format. Please use the date picker.', 'danger')
            return redirect(url_for('reservations.create_reservation'))

        customer_data = {
            'full_name': customer_name,
            'email': customer_email,
            'phone': customer_phone
        }
        vehicle_data = {
            'license_plate': license_plate,
            'vehicle_type': vehicle_type,
            'make_model': make_model
        }

        try:
            booking = ReservationService.create_reservation(
                customer_data=customer_data,
                vehicle_data=vehicle_data,
                slot_id=int(slot_id),
                start_time_dt=start_dt,
                end_time_dt=end_dt,
                notes=notes
            )
            flash(f"Reservation '{booking['reservation_code']}' confirmed! Estimated Fee: ${booking['estimated_amount']:.2f}. You can now proceed to Demo Payment.", 'success')
            return redirect(url_for('payments.process_payment', res_id=booking['id']))
        except ValueError as e:
            flash(f"Booking Error: {str(e)}", 'danger')
            return redirect(url_for('reservations.create_reservation'))
        except Exception as e:
            flash(f"An unexpected error occurred while saving the reservation: {str(e)}", 'danger')
            return redirect(url_for('reservations.create_reservation'))

    # GET: Prepare form with active slots and default timestamps (now + 15 min to now + 3 hours)
    now = datetime.now()
    default_start = (now + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M")
    default_end = (now + timedelta(hours=3, minutes=15)).strftime("%Y-%m-%dT%H:%M")

    slots = execute_query(
        """
        SELECT s.*, a.name AS area_name, a.floor_level, a.area_code
        FROM parking_slots s
        JOIN parking_areas a ON s.area_id = a.id
        WHERE s.is_active = 1 AND s.status != 'maintenance'
        ORDER BY a.floor_level, s.slot_number
        """,
        fetch='all'
    )

    areas = execute_query("SELECT * FROM parking_areas ORDER BY floor_level", fetch='all')

    return render_template(
        'reservation_form.html',
        slots=slots,
        areas=areas,
        default_start=default_start,
        default_end=default_end
    )

@reservations_bp.route('/reservations/<int:res_id>')
@admin_required
def view_reservation(res_id):
    """View detailed information of a specific reservation."""
    res = ReservationService.get_reservation_details(res_id)
    if not res:
        flash('Reservation not found.', 'danger')
        return redirect(url_for('reservations.list_reservations'))
        
    return render_template('reservation_details.html', res=res)

@reservations_bp.route('/reservations/<int:res_id>/cancel', methods=['POST'])
@admin_required
def cancel_reservation(res_id):
    """Cancel a reservation and release the held slot."""
    reason = request.form.get('reason', 'Cancelled by administrator')
    try:
        success, message = ReservationService.cancel_reservation(res_id, reason=reason)
        flash(message, 'info' if success else 'warning')
    except ValueError as e:
        flash(f"Cancellation Error: {str(e)}", 'danger')
    return redirect(url_for('reservations.list_reservations'))

@reservations_bp.route('/api/reservations/estimate')
@admin_required
def estimate_fee():
    """AJAX endpoint to calculate duration, hourly rate, and estimated amount."""
    slot_id = request.args.get('slot_id')
    start_str = request.args.get('start_time')
    end_str = request.args.get('end_time')

    if not slot_id or not start_str or not end_str:
        return jsonify({'success': False, 'message': 'Missing parameters'}), 400

    try:
        start_clean = start_str.replace('T', ' ')
        end_clean = end_str.replace('T', ' ')
        if len(start_clean) == 16:
            start_clean += ":00"
        if len(end_clean) == 16:
            end_clean += ":00"

        start_dt = datetime.strptime(start_clean, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_clean, "%Y-%m-%d %H:%M:%S")

        duration_hours, total_fee, rate = ReservationService.calculate_fee(int(slot_id), start_dt, end_dt)
        is_avail, avail_reason = ReservationService.check_slot_availability(int(slot_id), start_dt, end_dt)

        return jsonify({
            'success': True,
            'duration_hours': duration_hours,
            'hourly_rate': rate,
            'estimated_amount': total_fee,
            'is_available': is_avail,
            'availability_message': avail_reason
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@reservations_bp.route('/reservations/export')
@admin_required
def export_csv():
    """Export reservation records to CSV."""
    reservations = ReservationService.get_reservations()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Reservation Code', 'Customer Name', 'Phone', 'Vehicle Plate',
        'Slot', 'Area', 'Start Time', 'End Time', 'Duration (Hours)',
        'Estimated Amount ($)', 'Booking Status', 'Payment Status', 'Created At'
    ])
    for r in reservations:
        writer.writerow([
            r['reservation_code'], r['customer_name'], r.get('customer_phone', ''),
            r['license_plate'], r['slot_number'], r['area_name'],
            r['start_time'], r['end_time'], r['duration_hours'],
            f"{float(r['estimated_amount']):.2f}", r['booking_status'],
            r['payment_status'], r['created_at']
        ])
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=parking_reservations.csv"}
    )
