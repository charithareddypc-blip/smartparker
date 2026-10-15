from flask import Blueprint, render_template, request, flash, redirect, url_for
from routes.auth import admin_required
from database import execute_query

customers_bp = Blueprint('customers', __name__)

@customers_bp.route('/customers')
@admin_required
def list_customers():
    """List customers with registered vehicles and reservation counts."""
    search = request.args.get('search', '').strip()

    query = """
        SELECT c.*, 
               COUNT(DISTINCT r.id) AS total_reservations,
               COUNT(DISTINCT v.id) AS total_vehicles
        FROM customers c
        LEFT JOIN reservations r ON c.id = r.customer_id
        LEFT JOIN vehicles v ON c.id = v.customer_id
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (c.full_name LIKE %s OR c.email LIKE %s OR c.phone LIKE %s)"
        s_param = f"%{search}%"
        params.extend([s_param, s_param, s_param])

    query += " GROUP BY c.id ORDER BY c.created_at DESC"
    customers = execute_query(query, tuple(params), fetch='all')

    # Fetch vehicles for each customer
    for cust in customers:
        cust['vehicles'] = execute_query(
            "SELECT * FROM vehicles WHERE customer_id = %s",
            (cust['id'],),
            fetch='all'
        )

    return render_template(
        'customers.html',
        customers=customers,
        search=search
    )

@customers_bp.route('/customers/<int:customer_id>')
@admin_required
def customer_details(customer_id):
    """View customer profile, registered vehicles, reservation history, and payments."""
    customer = execute_query("SELECT * FROM customers WHERE id = %s", (customer_id,), fetch='one')
    if not customer:
        flash('Customer not found.', 'danger')
        return redirect(url_for('customers.list_customers'))

    vehicles = execute_query("SELECT * FROM vehicles WHERE customer_id = %s", (customer_id,), fetch='all')

    reservations = execute_query(
        """
        SELECT r.*, s.slot_number, v.license_plate, a.name AS area_name
        FROM reservations r
        JOIN parking_slots s ON r.slot_id = s.id
        JOIN parking_areas a ON s.area_id = a.id
        JOIN vehicles v ON r.vehicle_id = v.id
        WHERE r.customer_id = %s
        ORDER BY r.created_at DESC
        """,
        (customer_id,),
        fetch='all'
    )

    payments = execute_query(
        """
        SELECT p.*, r.reservation_code
        FROM payments p
        JOIN reservations r ON p.reservation_id = r.id
        WHERE r.customer_id = %s
        ORDER BY p.created_at DESC
        """,
        (customer_id,),
        fetch='all'
    )

    return render_template(
        'customer_details.html',
        customer=customer,
        vehicles=vehicles,
        reservations=reservations,
        payments=payments
    )
