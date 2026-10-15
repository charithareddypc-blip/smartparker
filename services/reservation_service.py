import uuid
from datetime import datetime, timedelta
import math
from database import execute_query, transaction, get_db

class ReservationService:

    @staticmethod
    def calculate_fee(slot_id, start_time_dt, end_time_dt):
        """Calculate parking fee based on duration and slot's hourly rate."""
        slot = execute_query(
            "SELECT id, hourly_rate FROM parking_slots WHERE id = %s",
            (slot_id,),
            fetch='one'
        )
        if not slot:
            raise ValueError("Parking slot not found.")
        
        duration = end_time_dt - start_time_dt
        duration_hours = duration.total_seconds() / 3600.0
        if duration_hours <= 0:
            raise ValueError("End time must be later than start time.")
        
        # Round duration up to 2 decimal places with minimum 1 hour billing
        billed_hours = max(1.0, round(duration_hours, 2))
        rate = float(slot['hourly_rate'])
        total_fee = round(billed_hours * rate, 2)
        return billed_hours, total_fee, rate

    @staticmethod
    def check_slot_availability(slot_id, start_time_dt, end_time_dt, exclude_reservation_id=None):
        """
        Check whether a parking slot is available for the given time interval.
        Returns: (is_available: bool, reason: str)
        """
        # 1. Check if slot exists and is active/not maintenance
        slot = execute_query(
            "SELECT id, slot_number, status, is_active FROM parking_slots WHERE id = %s",
            (slot_id,),
            fetch='one'
        )
        if not slot:
            return False, "Selected parking slot does not exist."
        if not slot['is_active'] or slot['status'] == 'maintenance':
            return False, f"Slot {slot['slot_number']} is currently under maintenance or inactive."
        
        # 2. Check overlapping reservations
        # Overlap rule: (existing_start < requested_end) AND (existing_end > requested_start)
        query = """
            SELECT id, reservation_code, start_time, end_time, booking_status
            FROM reservations
            WHERE slot_id = %s
              AND booking_status IN ('reserved', 'active')
              AND start_time < %s
              AND end_time > %s
        """
        params = [slot_id, end_time_dt, start_time_dt]
        if exclude_reservation_id:
            query += " AND id != %s"
            params.append(exclude_reservation_id)
            
        overlapping = execute_query(query, tuple(params), fetch='all')
        if overlapping:
            conflict = overlapping[0]
            start_str = str(conflict['start_time'])[:16]
            end_str = str(conflict['end_time'])[:16]
            return False, f"Slot {slot['slot_number']} is already booked ({conflict['reservation_code']}) from {start_str} to {end_str}."
        
        return True, "Slot is available."

    @staticmethod
    def get_available_slots(start_time_dt, end_time_dt, area_id=None, slot_type=None):
        """Fetch all slots available for the given timeframe with optional area and type filters."""
        query = """
            SELECT s.*, a.name AS area_name, a.floor_level, a.area_code
            FROM parking_slots s
            JOIN parking_areas a ON s.area_id = a.id
            WHERE s.is_active = 1 AND s.status != 'maintenance'
        """
        params = []
        if area_id:
            query += " AND s.area_id = %s"
            params.append(area_id)
        if slot_type:
            query += " AND s.slot_type = %s"
            params.append(slot_type)
            
        slots = execute_query(query, tuple(params), fetch='all')
        available_slots = []
        for slot in slots:
            is_avail, _ = ReservationService.check_slot_availability(slot['id'], start_time_dt, end_time_dt)
            if is_avail:
                available_slots.append(slot)
        return available_slots

    @staticmethod
    def create_reservation(customer_data, vehicle_data, slot_id, start_time_dt, end_time_dt, notes=""):
        """
        Creates customer, vehicle, and reservation within a database transaction.
        Enforces time validation and strict overlap prevention.
        """
        # Validate time ordering
        now = datetime.now()
        # Allow up to 10 minutes past time for clock skew, but reject past reservations
        if start_time_dt < (now - timedelta(minutes=15)):
            raise ValueError("Reservation start time cannot be in the past.")
        if end_time_dt <= start_time_dt:
            raise ValueError("Reservation end time must be later than start time.")
        
        duration_hours, estimated_amount, _ = ReservationService.calculate_fee(slot_id, start_time_dt, end_time_dt)
        
        with transaction():
            # Concurrency check: Re-verify availability inside transaction
            is_avail, reason = ReservationService.check_slot_availability(slot_id, start_time_dt, end_time_dt)
            if not is_avail:
                raise ValueError(reason)
            
            # Find or create customer
            customer = None
            if customer_data.get('email'):
                customer = execute_query("SELECT id FROM customers WHERE email = %s", (customer_data['email'],), fetch='one')
            elif customer_data.get('phone'):
                customer = execute_query("SELECT id FROM customers WHERE phone = %s", (customer_data['phone'],), fetch='one')
                
            if customer:
                customer_id = customer['id']
                # Update contact details if provided
                execute_query(
                    "UPDATE customers SET full_name = %s, phone = COALESCE(%s, phone) WHERE id = %s",
                    (customer_data['full_name'], customer_data.get('phone'), customer_id),
                    commit=False
                )
            else:
                customer_id = execute_query(
                    "INSERT INTO customers (full_name, email, phone) VALUES (%s, %s, %s)",
                    (customer_data['full_name'], customer_data.get('email'), customer_data.get('phone')),
                    commit=False
                )
            
            # Find or create vehicle
            plate = vehicle_data['license_plate'].strip().upper()
            vehicle = execute_query("SELECT id FROM vehicles WHERE license_plate = %s", (plate,), fetch='one')
            if vehicle:
                vehicle_id = vehicle['id']
            else:
                vehicle_id = execute_query(
                    "INSERT INTO vehicles (customer_id, license_plate, vehicle_type, make_model) VALUES (%s, %s, %s, %s)",
                    (customer_id, plate, vehicle_data.get('vehicle_type', 'Sedan'), vehicle_data.get('make_model', '')),
                    commit=False
                )
            
            # Generate unique reservation code: RES-YYYYMMDD-XXXX
            unique_suffix = uuid.uuid4().hex[:5].upper()
            date_prefix = datetime.now().strftime("%Y%m%d")
            res_code = f"RES-{date_prefix}-{unique_suffix}"
            
            res_id = execute_query(
                """
                INSERT INTO reservations (
                    reservation_code, customer_id, vehicle_id, slot_id,
                    start_time, end_time, duration_hours, estimated_amount,
                    booking_status, payment_status, notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'reserved', 'pending', %s)
                """,
                (res_code, customer_id, vehicle_id, slot_id, start_time_dt, end_time_dt, duration_hours, estimated_amount, notes),
                commit=False
            )
            
            # If the reservation start time is within the next 30 minutes, update slot status display to 'reserved'
            if start_time_dt <= (now + timedelta(minutes=30)):
                execute_query(
                    "UPDATE parking_slots SET status = 'reserved' WHERE id = %s AND status = 'available'",
                    (slot_id,),
                    commit=False
                )
            
            # Log event
            execute_query(
                "INSERT INTO occupancy_logs (slot_id, event_type, details) VALUES (%s, 'reservation_hold', %s)",
                (slot_id, f"Reservation {res_code} confirmed for vehicle {plate}"),
                commit=False
            )
            
            return {
                'id': res_id,
                'reservation_code': res_code,
                'customer_id': customer_id,
                'vehicle_id': vehicle_id,
                'slot_id': slot_id,
                'duration_hours': duration_hours,
                'estimated_amount': estimated_amount
            }

    @staticmethod
    def cancel_reservation(reservation_id, reason="Customer cancelled"):
        """Cancel an eligible reservation and release the slot."""
        with transaction():
            res = execute_query(
                "SELECT * FROM reservations WHERE id = %s",
                (reservation_id,),
                fetch='one'
            )
            if not res:
                raise ValueError("Reservation not found.")
            if res['booking_status'] == 'cancelled':
                return True, "Reservation is already cancelled."
            if res['booking_status'] in ('active', 'completed'):
                raise ValueError("Cannot cancel an active or completed reservation.")
            
            execute_query(
                "UPDATE reservations SET booking_status = 'cancelled', notes = CONCAT(COALESCE(notes, ''), ' [Cancelled: ', %s, ']') WHERE id = %s",
                (reason, reservation_id),
                commit=False
            )
            
            # Check if any other active reservation holds this slot right now
            now = datetime.now()
            other_active = execute_query(
                """
                SELECT id FROM reservations 
                WHERE slot_id = %s AND booking_status IN ('reserved', 'active')
                  AND start_time <= %s AND end_time >= %s AND id != %s
                """,
                (res['slot_id'], now, now, reservation_id),
                fetch='one'
            )
            
            if not other_active:
                execute_query(
                    "UPDATE parking_slots SET status = 'available' WHERE id = %s AND status = 'reserved'",
                    (res['slot_id'],),
                    commit=False
                )
            
            execute_query(
                "INSERT INTO occupancy_logs (slot_id, event_type, details) VALUES (%s, 'cancellation', %s)",
                (res['slot_id'], f"Reservation {res['reservation_code']} cancelled: {reason}"),
                commit=False
            )
            
            return True, "Reservation successfully cancelled and parking slot released."

    @staticmethod
    def get_reservation_details(reservation_id_or_code):
        """Fetch complete reservation details including customer, vehicle, slot, area, and payment info."""
        query = """
            SELECT r.*, 
                   c.full_name AS customer_name, c.email AS customer_email, c.phone AS customer_phone,
                   v.license_plate, v.vehicle_type, v.make_model,
                   s.slot_number, s.slot_type, s.hourly_rate,
                   a.name AS area_name, a.floor_level, a.area_code,
                   p.id AS payment_id, p.transaction_ref, p.payment_method, p.paid_at
            FROM reservations r
            JOIN customers c ON r.customer_id = c.id
            JOIN vehicles v ON r.vehicle_id = v.id
            JOIN parking_slots s ON r.slot_id = s.id
            JOIN parking_areas a ON s.area_id = a.id
            LEFT JOIN payments p ON r.id = p.reservation_id AND p.payment_status = 'paid'
            WHERE r.id = %s OR r.reservation_code = %s
        """
        return execute_query(query, (reservation_id_or_code, reservation_id_or_code), fetch='one')

    @staticmethod
    def get_reservations(search=None, status=None, date_from=None, date_to=None):
        """Fetch list of reservations with flexible search and filtering."""
        query = """
            SELECT r.*, 
                   c.full_name AS customer_name, c.phone AS customer_phone,
                   v.license_plate,
                   s.slot_number,
                   a.name AS area_name, a.floor_level
            FROM reservations r
            JOIN customers c ON r.customer_id = c.id
            JOIN vehicles v ON r.vehicle_id = v.id
            JOIN parking_slots s ON r.slot_id = s.id
            JOIN parking_areas a ON s.area_id = a.id
            WHERE 1=1
        """
        params = []
        if search:
            query += " AND (r.reservation_code LIKE %s OR c.full_name LIKE %s OR v.license_plate LIKE %s OR s.slot_number LIKE %s)"
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param, search_param])
        if status and status != 'all':
            query += " AND r.booking_status = %s"
            params.append(status)
        if date_from:
            query += " AND r.start_time >= %s"
            params.append(f"{date_from} 00:00:00")
        if date_to:
            query += " AND r.start_time <= %s"
            params.append(f"{date_to} 23:59:59")
            
        query += " ORDER BY r.created_at DESC"
        return execute_query(query, tuple(params), fetch='all')
