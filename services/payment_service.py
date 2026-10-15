import uuid
from datetime import datetime
from database import execute_query, transaction

class PaymentService:

    @staticmethod
    def process_demo_payment(reservation_id, amount, payment_method="demo_card", simulate_failure=False, notes=""):
        """
        Process a simulated payment for a reservation.
        Guarantees duplicate payment prevention and logs transaction.
        """
        res = execute_query(
            "SELECT id, reservation_code, estimated_amount, actual_amount, payment_status, booking_status FROM reservations WHERE id = %s",
            (reservation_id,),
            fetch='one'
        )
        if not res:
            raise ValueError("Reservation does not exist.")
            
        if res['payment_status'] == 'paid':
            raise ValueError(f"Reservation {res['reservation_code']} is already paid. Duplicate payment prevented.")
            
        # Check if already paid in payments table
        existing_paid = execute_query(
            "SELECT id, transaction_ref FROM payments WHERE reservation_id = %s AND payment_status = 'paid'",
            (reservation_id,),
            fetch='one'
        )
        if existing_paid:
            raise ValueError(f"Payment already completed under Transaction Reference {existing_paid['transaction_ref']}.")

        # Generate unique transaction reference
        timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
        random_suffix = uuid.uuid4().hex[:6].upper()
        transaction_ref = f"TXN-{timestamp_str}-{random_suffix}"
        
        status = 'failed' if simulate_failure else 'paid'
        paid_at = None if simulate_failure else datetime.now()
        payment_notes = f"Simulated Demo Gateway: {notes}" if notes else "Simulated Gateway Payment"
        if simulate_failure:
            payment_notes += " [Declined: Simulated Test Failure]"

        with transaction():
            payment_id = execute_query(
                """
                INSERT INTO payments (
                    reservation_id, amount, payment_method, transaction_ref,
                    payment_status, notes, paid_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (reservation_id, float(amount), payment_method, transaction_ref, status, payment_notes, paid_at),
                commit=False
            )
            
            if not simulate_failure:
                execute_query(
                    """
                    UPDATE reservations 
                    SET payment_status = 'paid', actual_amount = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (float(amount), reservation_id),
                    commit=False
                )
                
        return {
            'payment_id': payment_id,
            'transaction_ref': transaction_ref,
            'amount': float(amount),
            'status': status,
            'payment_method': payment_method,
            'paid_at': paid_at,
            'success': not simulate_failure
        }

    @staticmethod
    def get_payment_receipt(payment_id_or_ref):
        """Fetch all details required to generate a printable payment receipt."""
        query = """
            SELECT p.*,
                   r.reservation_code, r.start_time, r.end_time, r.duration_hours, r.booking_status,
                   c.full_name AS customer_name, c.email AS customer_email, c.phone AS customer_phone,
                   v.license_plate, v.vehicle_type, v.make_model,
                   s.slot_number, s.slot_type, s.hourly_rate,
                   a.name AS area_name, a.floor_level
            FROM payments p
            JOIN reservations r ON p.reservation_id = r.id
            JOIN customers c ON r.customer_id = c.id
            JOIN vehicles v ON r.vehicle_id = v.id
            JOIN parking_slots s ON r.slot_id = s.id
            JOIN parking_areas a ON s.area_id = a.id
            WHERE p.id = %s OR p.transaction_ref = %s
        """
        return execute_query(query, (payment_id_or_ref, payment_id_or_ref), fetch='one')

    @staticmethod
    def get_payments(search=None, status=None, date_from=None, date_to=None):
        """Fetch list of all payment transactions with filters."""
        query = """
            SELECT p.*,
                   r.reservation_code,
                   c.full_name AS customer_name,
                   v.license_plate,
                   s.slot_number
            FROM payments p
            JOIN reservations r ON p.reservation_id = r.id
            JOIN customers c ON r.customer_id = c.id
            JOIN vehicles v ON r.vehicle_id = v.id
            JOIN parking_slots s ON r.slot_id = s.id
            WHERE 1=1
        """
        params = []
        if search:
            query += " AND (p.transaction_ref LIKE %s OR r.reservation_code LIKE %s OR c.full_name LIKE %s OR v.license_plate LIKE %s)"
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param, search_param])
        if status and status != 'all':
            query += " AND p.payment_status = %s"
            params.append(status)
        if date_from:
            query += " AND p.created_at >= %s"
            params.append(f"{date_from} 00:00:00")
        if date_to:
            query += " AND p.created_at <= %s"
            params.append(f"{date_to} 23:59:59")
            
        query += " ORDER BY p.created_at DESC"
        return execute_query(query, tuple(params), fetch='all')

    @staticmethod
    def get_revenue_summary():
        """Compute total collected revenue, transaction counts, and breakdown."""
        # Total revenue strictly from 'paid' status
        total_paid_row = execute_query(
            "SELECT COALESCE(SUM(amount), 0) AS total_revenue, COUNT(*) AS count_paid FROM payments WHERE payment_status = 'paid'",
            fetch='one'
        )
        total_revenue = float(total_paid_row['total_revenue']) if total_paid_row else 0.0
        total_paid_count = total_paid_row['count_paid'] if total_paid_row else 0

        # Pending amount from reservations that have pending payment
        pending_row = execute_query(
            "SELECT COALESCE(SUM(estimated_amount), 0) AS pending_amount, COUNT(*) AS count_pending FROM reservations WHERE payment_status = 'pending' AND booking_status != 'cancelled'",
            fetch='one'
        )
        pending_amount = float(pending_row['pending_amount']) if pending_row else 0.0
        pending_count = pending_row['count_pending'] if pending_row else 0

        # Failed transactions
        failed_row = execute_query(
            "SELECT COUNT(*) AS count_failed FROM payments WHERE payment_status = 'failed'",
            fetch='one'
        )
        failed_count = failed_row['count_failed'] if failed_row else 0

        return {
            'total_revenue': total_revenue,
            'total_paid_count': total_paid_count,
            'pending_amount': pending_amount,
            'pending_count': pending_count,
            'failed_count': failed_count
        }
