import pytest
from datetime import datetime, timedelta
from services.reservation_service import ReservationService
from database import execute_query

def test_fee_calculation(app):
    """Test parking fee calculation formula."""
    with app.app_context():
        # Slot 1 hourly rate is $8.00 (from schema)
        start = datetime.now() + timedelta(hours=1)
        end = start + timedelta(hours=3)
        duration, fee, rate = ReservationService.calculate_fee(1, start, end)
        assert duration == 3.0
        assert fee == 24.00
        assert rate == 8.00

def test_invalid_times_rejection(app):
    """Test rejection of invalid or past reservation times."""
    with app.app_context():
        # End time earlier than start time
        start = datetime.now() + timedelta(hours=2)
        end = datetime.now() + timedelta(hours=1)
        with pytest.raises(ValueError, match="End time must be later than start time"):
            ReservationService.calculate_fee(1, start, end)

        # Past start time rejection
        past_start = datetime.now() - timedelta(hours=2)
        future_end = datetime.now() + timedelta(hours=1)
        customer = {'full_name': 'Test User', 'email': 'test@example.com'}
        vehicle = {'license_plate': 'TEST-999'}
        with pytest.raises(ValueError, match="Reservation start time cannot be in the past"):
            ReservationService.create_reservation(customer, vehicle, 1, past_start, future_end)

def test_successful_reservation_creation(app):
    """Test creating a valid reservation."""
    with app.app_context():
        # Find an available slot
        slot = execute_query("SELECT id FROM parking_slots WHERE status = 'available' LIMIT 1", fetch='one')
        assert slot is not None
        slot_id = slot['id']

        start = datetime.now() + timedelta(days=2, hours=10)
        end = start + timedelta(hours=4)

        customer = {'full_name': 'Samantha Fox', 'email': 'samantha@test.com', 'phone': '555-4321'}
        vehicle = {'license_plate': 'FOX-101', 'vehicle_type': 'SUV', 'make_model': 'Audi Q5'}

        res = ReservationService.create_reservation(customer, vehicle, slot_id, start, end, notes="Test booking")
        assert res['id'] is not None
        assert res['reservation_code'].startswith('RES-')
        assert res['duration_hours'] == 4.0
        assert res['estimated_amount'] > 0

def test_overlapping_reservation_rejection(app):
    """Test strict prevention of overlapping reservations for the same slot."""
    with app.app_context():
        # Slot 6
        slot_id = 6
        # Existing booking: from Day 3 10:00 to 14:00
        base_start = datetime.now() + timedelta(days=3, hours=10)
        base_end = base_start + timedelta(hours=4)

        customer1 = {'full_name': 'Driver One', 'email': 'd1@test.com'}
        vehicle1 = {'license_plate': 'D1-1111'}
        res1 = ReservationService.create_reservation(customer1, vehicle1, slot_id, base_start, base_end)
        assert res1['id'] is not None

        # Conflict 1: Overlaps partially (starts at 12:00, ends at 16:00)
        conflict_start1 = base_start + timedelta(hours=2)
        conflict_end1 = conflict_start1 + timedelta(hours=4)
        customer2 = {'full_name': 'Driver Two', 'email': 'd2@test.com'}
        vehicle2 = {'license_plate': 'D2-2222'}

        with pytest.raises(ValueError, match="already booked"):
            ReservationService.create_reservation(customer2, vehicle2, slot_id, conflict_start1, conflict_end1)

        # Conflict 2: Engulfs the whole window (starts at 09:00, ends at 15:00)
        conflict_start2 = base_start - timedelta(hours=1)
        conflict_end2 = base_end + timedelta(hours=1)
        with pytest.raises(ValueError, match="already booked"):
            ReservationService.create_reservation(customer2, vehicle2, slot_id, conflict_start2, conflict_end2)

def test_reservation_cancellation(app):
    """Test cancelling an eligible reservation and releasing slot."""
    with app.app_context():
        slot_id = 8
        start = datetime.now() + timedelta(days=4, hours=8)
        end = start + timedelta(hours=3)

        customer = {'full_name': 'Cancel Tester', 'email': 'cancel@test.com'}
        vehicle = {'license_plate': 'CAN-000'}
        res = ReservationService.create_reservation(customer, vehicle, slot_id, start, end)

        success, msg = ReservationService.cancel_reservation(res['id'], reason="Test cancellation")
        assert success is True

        # Verify booking status changed to cancelled
        updated = execute_query("SELECT booking_status FROM reservations WHERE id = %s", (res['id'],), fetch='one')
        assert updated['booking_status'] == 'cancelled'

def test_slot_creation_and_duplicate_prevention(auth_client):
    """Test adding a slot and preventing duplicate slot numbers in same area."""
    # Create slot TEST-99 in area 1
    resp = auth_client.post('/parking/add', data={
        'area_id': '1',
        'slot_number': 'TEST-99',
        'slot_type': 'compact',
        'hourly_rate': '4.50'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"successfully created" in resp.data

    # Attempt to create identical slot in same area -> must be rejected
    dup_resp = auth_client.post('/parking/add', data={
        'area_id': '1',
        'slot_number': 'TEST-99',
        'slot_type': 'compact',
        'hourly_rate': '4.50'
    }, follow_redirects=True)
    assert b"already exists in this parking area" in dup_resp.data

def test_delete_occupied_slot_protection(app, auth_client):
    """Test that deleting an occupied slot is strictly rejected."""
    with app.app_context():
        occupied_slot = execute_query("SELECT id, slot_number FROM parking_slots WHERE status = 'occupied' LIMIT 1", fetch='one')
        assert occupied_slot is not None
        slot_id = occupied_slot['id']

    resp = auth_client.post(f'/parking/delete/{slot_id}', follow_redirects=True)
    assert b"Cannot delete Slot" in resp.data
