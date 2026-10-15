from datetime import datetime
from database import execute_query, transaction

class OccupancyService:

    @staticmethod
    def get_occupancy_metrics():
        """Calculate live occupancy statistics directly from database."""
        # Total active parking slots
        total_slots_row = execute_query(
            "SELECT COUNT(*) AS total FROM parking_slots WHERE is_active = 1",
            fetch='one'
        )
        total_slots = total_slots_row['total'] if total_slots_row else 0

        # Occupied spaces (slots with active sessions or status = 'occupied')
        occupied_row = execute_query(
            "SELECT COUNT(*) AS occupied FROM parking_slots WHERE is_active = 1 AND status = 'occupied'",
            fetch='one'
        )
        occupied_spaces = occupied_row['occupied'] if occupied_row else 0

        # Reserved spaces
        reserved_row = execute_query(
            "SELECT COUNT(*) AS reserved FROM parking_slots WHERE is_active = 1 AND status = 'reserved'",
            fetch='one'
        )
        reserved_spaces = reserved_row['reserved'] if reserved_row else 0

        # Maintenance spaces
        maintenance_row = execute_query(
            "SELECT COUNT(*) AS maint FROM parking_slots WHERE is_active = 1 AND status = 'maintenance'",
            fetch='one'
        )
        maintenance_spaces = maintenance_row['maint'] if maintenance_row else 0

        # Available spaces
        available_spaces = max(0, total_slots - (occupied_spaces + reserved_spaces + maintenance_spaces))

        # Occupancy Percentage = (Occupied Spaces / Total Parking Spaces) * 100
        occupancy_rate = round((occupied_spaces / total_slots * 100), 1) if total_slots > 0 else 0.0

        # Total lifetime reservations
        res_count_row = execute_query(
            "SELECT COUNT(*) AS count_res FROM reservations",
            fetch='one'
        )
        total_reservations = res_count_row['count_res'] if res_count_row else 0

        return {
            'total_slots': total_slots,
            'occupied_spaces': occupied_spaces,
            'reserved_spaces': reserved_spaces,
            'available_spaces': available_spaces,
            'maintenance_spaces': maintenance_spaces,
            'occupancy_percentage': occupancy_rate,
            'total_reservations': total_reservations
        }

    @staticmethod
    def check_in_vehicle(reservation_id_or_code):
        """
        Check in a vehicle against its reservation.
        Validates reservation eligibility, prevents double occupancy, updates status to Active.
        """
        with transaction():
            res = execute_query(
                """
                SELECT r.*, v.license_plate, s.slot_number, s.status AS slot_status
                FROM reservations r
                JOIN vehicles v ON r.vehicle_id = v.id
                JOIN parking_slots s ON r.slot_id = s.id
                WHERE r.id = %s OR r.reservation_code = %s
                """,
                (reservation_id_or_code, reservation_id_or_code),
                fetch='one'
            )
            if not res:
                raise ValueError("Reservation not found.")
                
            if res['booking_status'] == 'active':
                raise ValueError(f"Vehicle {res['license_plate']} is already checked in.")
            if res['booking_status'] == 'completed':
                raise ValueError("This reservation has already been completed.")
            if res['booking_status'] == 'cancelled':
                raise ValueError("Cannot check in a cancelled reservation.")

            # Check if another vehicle is occupying this slot
            existing_session = execute_query(
                "SELECT id, vehicle_id FROM parking_sessions WHERE slot_id = %s AND status = 'active'",
                (res['slot_id'],),
                fetch='one'
            )
            if existing_session and existing_session['vehicle_id'] != res['vehicle_id']:
                raise ValueError(f"Slot {res['slot_number']} is currently occupied by another vehicle session.")

            now = datetime.now()
            
            # 1. Update reservation to Active
            execute_query(
                "UPDATE reservations SET booking_status = 'active', updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (res['id'],),
                commit=False
            )
            
            # 2. Mark slot as Occupied
            execute_query(
                "UPDATE parking_slots SET status = 'occupied', updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (res['slot_id'],),
                commit=False
            )
            
            # 3. Create or update parking session
            session_id = execute_query(
                """
                INSERT INTO parking_sessions (
                    reservation_id, slot_id, vehicle_id, check_in_time,
                    initial_fee, status, notes
                ) VALUES (%s, %s, %s, %s, %s, 'active', %s)
                """,
                (res['id'], res['slot_id'], res['vehicle_id'], now, res['estimated_amount'], f"Check-in verified: {res['reservation_code']}"),
                commit=False
            )
            
            # 4. Log occupancy event
            execute_query(
                "INSERT INTO occupancy_logs (slot_id, event_type, details) VALUES (%s, 'check_in', %s)",
                (res['slot_id'], f"Vehicle {res['license_plate']} checked into Slot {res['slot_number']} (Ref: {res['reservation_code']})"),
                commit=False
            )
            
            return {
                'session_id': session_id,
                'reservation_code': res['reservation_code'],
                'slot_number': res['slot_number'],
                'license_plate': res['license_plate'],
                'check_in_time': now
            }

    @staticmethod
    def check_out_vehicle(session_id_or_reservation_id):
        """
        Check out an active vehicle session.
        Calculates actual duration, final fee if applicable, releases slot.
        """
        with transaction():
            session = execute_query(
                """
                SELECT ps.*, r.reservation_code, r.start_time, r.estimated_amount,
                       v.license_plate, s.slot_number, s.hourly_rate
                FROM parking_sessions ps
                LEFT JOIN reservations r ON ps.reservation_id = r.id
                JOIN vehicles v ON ps.vehicle_id = v.id
                JOIN parking_slots s ON ps.slot_id = s.id
                WHERE (ps.id = %s OR ps.reservation_id = %s) AND ps.status = 'active'
                """,
                (session_id_or_reservation_id, session_id_or_reservation_id),
                fetch='one'
            )
            if not session:
                raise ValueError("Active parking session not found for this vehicle/reservation.")

            now = datetime.now()
            # Calculate actual duration
            check_in_time = session['check_in_time']
            if isinstance(check_in_time, str):
                check_in_time = datetime.strptime(check_in_time[:19], "%Y-%m-%d %H:%M:%S")
                
            actual_duration = (now - check_in_time).total_seconds() / 3600.0
            billed_hours = max(1.0, round(actual_duration, 2))
            
            rate = float(session['hourly_rate'])
            # Initial estimated fee
            initial_fee = float(session['initial_fee'])
            # Final fee calculation
            calculated_fee = round(billed_hours * rate, 2)
            final_fee = max(initial_fee, calculated_fee)  # Ensure minimum billed amount

            # 1. Complete the parking session
            execute_query(
                """
                UPDATE parking_sessions 
                SET status = 'completed', check_out_time = %s, actual_duration_hours = %s, final_fee = %s
                WHERE id = %s
                """,
                (now, billed_hours, final_fee, session['id']),
                commit=False
            )
            
            # 2. Complete reservation if linked
            if session['reservation_id']:
                execute_query(
                    """
                    UPDATE reservations 
                    SET booking_status = 'completed', actual_amount = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (final_fee, session['reservation_id']),
                    commit=False
                )

            # 3. Check if there is an immediate upcoming reservation holding this slot
            upcoming = execute_query(
                """
                SELECT id FROM reservations 
                WHERE slot_id = %s AND booking_status = 'reserved'
                  AND start_time <= %s AND end_time >= %s
                """,
                (session['slot_id'], now, now),
                fetch='one'
            )
            new_slot_status = 'reserved' if upcoming else 'available'
            execute_query(
                "UPDATE parking_slots SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (new_slot_status, session['slot_id']),
                commit=False
            )

            # 4. Log checkout event
            execute_query(
                "INSERT INTO occupancy_logs (slot_id, event_type, details) VALUES (%s, 'check_out', %s)",
                (session['slot_id'], f"Vehicle {session['license_plate']} checked out from Slot {session['slot_number']} (Duration: {billed_hours}h, Fee: ${final_fee:.2f})"),
                commit=False
            )

            return {
                'session_id': session['id'],
                'slot_number': session['slot_number'],
                'license_plate': session['license_plate'],
                'check_in_time': check_in_time,
                'check_out_time': now,
                'duration_hours': billed_hours,
                'initial_fee': initial_fee,
                'final_fee': final_fee
            }

    @staticmethod
    def get_active_sessions():
        """Retrieve all currently active parking sessions."""
        query = """
            SELECT ps.*, 
                   r.reservation_code,
                   v.license_plate, v.vehicle_type, v.make_model,
                   c.full_name AS customer_name, c.phone AS customer_phone,
                   s.slot_number, s.slot_type, s.hourly_rate,
                   a.name AS area_name, a.floor_level
            FROM parking_sessions ps
            LEFT JOIN reservations r ON ps.reservation_id = r.id
            JOIN vehicles v ON ps.vehicle_id = v.id
            LEFT JOIN customers c ON v.customer_id = c.id
            JOIN parking_slots s ON ps.slot_id = s.id
            JOIN parking_areas a ON s.area_id = a.id
            WHERE ps.status = 'active'
            ORDER BY ps.check_in_time DESC
        """
        return execute_query(query, fetch='all')

    @staticmethod
    def get_occupancy_logs(limit=20):
        """Fetch recent occupancy audit logs."""
        query = """
            SELECT l.*, s.slot_number, a.area_code
            FROM occupancy_logs l
            JOIN parking_slots s ON l.slot_id = s.id
            JOIN parking_areas a ON s.area_id = a.id
            ORDER BY l.logged_at DESC
            LIMIT %s
        """
        return execute_query(query, (limit,), fetch='all')
