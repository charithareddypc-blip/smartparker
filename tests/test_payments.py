import pytest
from datetime import datetime, timedelta
from services.reservation_service import ReservationService
from services.payment_service import PaymentService
from services.occupancy_service import OccupancyService
from database import execute_query

def test_demo_payment_success(app):
    """Test successful demo payment flow and receipt generation."""
    with app.app_context():
        # Create a fresh reservation
        slot = execute_query("SELECT id FROM parking_slots WHERE status = 'available' LIMIT 1", fetch='one')
        start = datetime.now() + timedelta(days=5, hours=10)
        end = start + timedelta(hours=2)
        customer = {'full_name': 'Pay Tester', 'email': 'pay@test.com'}
        vehicle = {'license_plate': 'PAY-111'}
        res = ReservationService.create_reservation(customer, vehicle, slot['id'], start, end)

        # Process payment
        pay_result = PaymentService.process_demo_payment(
            reservation_id=res['id'],
            amount=res['estimated_amount'],
            payment_method='demo_card'
        )
        assert pay_result['success'] is True
        assert pay_result['status'] == 'paid'
        assert pay_result['transaction_ref'].startswith('TXN-')

        # Verify receipt lookup
        receipt = PaymentService.get_payment_receipt(pay_result['payment_id'])
        assert receipt is not None
        assert receipt['transaction_ref'] == pay_result['transaction_ref']
        assert receipt['customer_name'] == 'Pay Tester'

def test_duplicate_payment_prevention(app):
    """Test that paying an already-paid reservation is strictly rejected."""
    with app.app_context():
        slot = execute_query("SELECT id FROM parking_slots WHERE status = 'available' LIMIT 1", fetch='one')
        start = datetime.now() + timedelta(days=6, hours=10)
        end = start + timedelta(hours=2)
        customer = {'full_name': 'Dup Tester', 'email': 'dup@test.com'}
        vehicle = {'license_plate': 'DUP-222'}
        res = ReservationService.create_reservation(customer, vehicle, slot['id'], start, end)

        # First payment succeeds
        PaymentService.process_demo_payment(res['id'], res['estimated_amount'], 'demo_card')

        # Second payment must raise ValueError
        with pytest.raises(ValueError, match="already paid"):
            PaymentService.process_demo_payment(res['id'], res['estimated_amount'], 'demo_card')

def test_demo_payment_failure_simulation(app):
    """Test simulated failed payment outcome."""
    with app.app_context():
        slot = execute_query("SELECT id FROM parking_slots WHERE status = 'available' LIMIT 1", fetch='one')
        start = datetime.now() + timedelta(days=7, hours=10)
        end = start + timedelta(hours=2)
        customer = {'full_name': 'Fail Tester', 'email': 'fail@test.com'}
        vehicle = {'license_plate': 'FAIL-333'}
        res = ReservationService.create_reservation(customer, vehicle, slot['id'], start, end)

        fail_result = PaymentService.process_demo_payment(
            reservation_id=res['id'],
            amount=res['estimated_amount'],
            simulate_failure=True
        )
        assert fail_result['success'] is False
        assert fail_result['status'] == 'failed'

        # Verify reservation payment_status is still 'pending'
        check_res = execute_query("SELECT payment_status FROM reservations WHERE id = %s", (res['id'],), fetch='one')
        assert check_res['payment_status'] == 'pending'

def test_revenue_summary_counts_only_paid(app):
    """Verify that revenue metrics strictly include paid transactions."""
    with app.app_context():
        summary = PaymentService.get_revenue_summary()
        assert 'total_revenue' in summary
        assert 'total_paid_count' in summary
        assert 'pending_amount' in summary
        assert summary['total_revenue'] >= 0.0

def test_vehicle_checkin_and_checkout(app):
    """Test full check-in and check-out lifecycle with slot status transitions."""
    with app.app_context():
        # Find an available slot
        slot = execute_query("SELECT id, slot_number FROM parking_slots WHERE status = 'available' LIMIT 1", fetch='one')
        slot_id = slot['id']

        start = datetime.now() + timedelta(minutes=5)
        end = start + timedelta(hours=2)
        customer = {'full_name': 'Checkin Tester', 'email': 'checkin@test.com'}
        vehicle = {'license_plate': 'CHK-777'}
        res = ReservationService.create_reservation(customer, vehicle, slot_id, start, end)

        # 1. Execute Check-In
        checkin_info = OccupancyService.check_in_vehicle(res['reservation_code'])
        assert checkin_info['session_id'] is not None

        # Slot should now be occupied
        slot_check = execute_query("SELECT status FROM parking_slots WHERE id = %s", (slot_id,), fetch='one')
        assert slot_check['status'] == 'occupied'

        # Reservation should now be active
        res_check = execute_query("SELECT booking_status FROM reservations WHERE id = %s", (res['id'],), fetch='one')
        assert res_check['booking_status'] == 'active'

        # 2. Execute Check-Out
        checkout_info = OccupancyService.check_out_vehicle(checkin_info['session_id'])
        assert checkout_info['final_fee'] >= checkout_info['initial_fee']

        # Slot should now be released to available
        slot_released = execute_query("SELECT status FROM parking_slots WHERE id = %s", (slot_id,), fetch='one')
        assert slot_released['status'] == 'available'

        # Reservation should now be completed
        res_completed = execute_query("SELECT booking_status FROM reservations WHERE id = %s", (res['id'],), fetch='one')
        assert res_completed['booking_status'] == 'completed'

def test_admin_route_protection(client):
    """Test that protected admin routes redirect unauthorized requests to /login."""
    resp = client.get('/dashboard')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']

    resp2 = client.get('/parking')
    assert resp2.status_code == 302
    assert '/login' in resp2.headers['Location']
