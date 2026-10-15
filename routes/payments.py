import io
import csv
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from routes.auth import admin_required
from services.payment_service import PaymentService
from services.reservation_service import ReservationService
from database import execute_query

payments_bp = Blueprint('payments', __name__)

@payments_bp.route('/payments')
@admin_required
def list_payments():
    """Display payment history, revenue summary cards, and search/filter controls."""
    search = request.args.get('search', '').strip()
    status = request.args.get('status', 'all')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    payments = PaymentService.get_payments(
        search=search,
        status=status,
        date_from=date_from,
        date_to=date_to
    )

    revenue_summary = PaymentService.get_revenue_summary()

    return render_template(
        'payments.html',
        payments=payments,
        revenue=revenue_summary,
        search=search,
        status=status,
        date_from=date_from,
        date_to=date_to
    )

@payments_bp.route('/payments/process/<int:res_id>', methods=['GET', 'POST'])
@admin_required
def process_payment(res_id):
    """Simulated demo payment gateway view and processor."""
    res = ReservationService.get_reservation_details(res_id)
    if not res:
        flash('Reservation not found.', 'danger')
        return redirect(url_for('reservations.list_reservations'))

    if res['payment_status'] == 'paid':
        flash(f"Reservation {res['reservation_code']} is already paid. Showing payment receipt.", 'info')
        if res.get('payment_id'):
            return redirect(url_for('payments.view_receipt', payment_id=res['payment_id']))
        return redirect(url_for('payments.list_payments'))

    if request.method == 'POST':
        payment_method = request.form.get('payment_method', 'demo_card')
        action_type = request.form.get('action_type', 'success')  # 'success' or 'fail'
        simulate_failure = (action_type == 'fail')
        notes = request.form.get('notes', 'Demo Gateway Sandbox')

        try:
            result = PaymentService.process_demo_payment(
                reservation_id=res_id,
                amount=res['estimated_amount'],
                payment_method=payment_method,
                simulate_failure=simulate_failure,
                notes=notes
            )
            if result['success']:
                flash(f"Payment successful! Transaction Reference: {result['transaction_ref']}", 'success')
                return redirect(url_for('payments.view_receipt', payment_id=result['payment_id']))
            else:
                flash(f"Payment simulation failed as requested. Reference: {result['transaction_ref']}", 'danger')
                return redirect(url_for('payments.list_payments'))
        except ValueError as e:
            flash(f"Payment Error: {str(e)}", 'danger')
            return redirect(url_for('payments.process_payment', res_id=res_id))

    return render_template('payment_process.html', res=res)

@payments_bp.route('/payments/<int:payment_id>/receipt')
@admin_required
def view_receipt(payment_id):
    """Render a printable, professional payment receipt."""
    receipt = PaymentService.get_payment_receipt(payment_id)
    if not receipt:
        flash('Receipt not found.', 'danger')
        return redirect(url_for('payments.list_payments'))
    return render_template('receipt.html', receipt=receipt)

@payments_bp.route('/payments/export')
@admin_required
def export_csv():
    """Export payment transactions to CSV format."""
    payments = PaymentService.get_payments()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Transaction Ref', 'Reservation Code', 'Customer', 'Vehicle Plate',
        'Slot', 'Amount ($)', 'Payment Method', 'Status', 'Date'
    ])
    for p in payments:
        writer.writerow([
            p['transaction_ref'], p['reservation_code'], p['customer_name'],
            p['license_plate'], p['slot_number'], f"{float(p['amount']):.2f}",
            p['payment_method'], p['payment_status'], p['created_at']
        ])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=payment_transactions.csv"}
    )
