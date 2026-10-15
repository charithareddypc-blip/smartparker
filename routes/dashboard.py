from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify, request
from routes.auth import admin_required
from services.occupancy_service import OccupancyService
from services.payment_service import PaymentService
from services.reservation_service import ReservationService
from database import execute_query, get_db_status_info

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@admin_required
def index():
    """Main management dashboard page."""
    metrics = OccupancyService.get_occupancy_metrics()
    revenue_summary = PaymentService.get_revenue_summary()
    
    # Recent reservations (last 5)
    recent_reservations = ReservationService.get_reservations()[:6]
    
    # Latest payments (last 5)
    latest_payments = PaymentService.get_payments()[:6]
    
    # Active parking sessions
    active_sessions = OccupancyService.get_active_sessions()[:6]
    
    # Parking slot overview
    slots_overview = execute_query(
        """
        SELECT s.*, a.area_code, a.floor_level
        FROM parking_slots s
        JOIN parking_areas a ON s.area_id = a.id
        WHERE s.is_active = 1
        ORDER BY a.id, s.slot_number
        LIMIT 18
        """,
        fetch='all'
    )
    
    db_info = get_db_status_info()
    
    return render_template(
        'dashboard.html',
        metrics=metrics,
        revenue=revenue_summary,
        recent_reservations=recent_reservations,
        latest_payments=latest_payments,
        active_sessions=active_sessions,
        slots_overview=slots_overview,
        db_info=db_info
    )

@dashboard_bp.route('/api/dashboard/charts')
@admin_required
def chart_data():
    """API endpoint providing real-time chart data for Chart.js."""
    # 1. Occupancy Breakdown (Doughnut)
    metrics = OccupancyService.get_occupancy_metrics()
    occupancy_chart = {
        'labels': ['Available', 'Reserved', 'Occupied', 'Maintenance'],
        'data': [
            metrics['available_spaces'],
            metrics['reserved_spaces'],
            metrics['occupied_spaces'],
            metrics['maintenance_spaces']
        ],
        'colors': ['#10b981', '#f59e0b', '#ef4444', '#64748b']
    }

    # 2. Daily Reservations (Past 7 days)
    today = datetime.now().date()
    dates = [(today - timedelta(days=i)) for i in range(6, -1, -1)]
    date_labels = [d.strftime('%b %d') for d in dates]
    
    reservation_counts = []
    revenue_daily = []
    
    for d in dates:
        day_str = d.strftime('%Y-%m-%d')
        # Reservations for this day
        res_row = execute_query(
            "SELECT COUNT(*) AS cnt FROM reservations WHERE DATE(created_at) = %s",
            (day_str,),
            fetch='one'
        )
        reservation_counts.append(res_row['cnt'] if res_row else 0)
        
        # Revenue collected for this day
        rev_row = execute_query(
            "SELECT COALESCE(SUM(amount), 0) AS daily_rev FROM payments WHERE payment_status = 'paid' AND DATE(paid_at) = %s",
            (day_str,),
            fetch='one'
        )
        revenue_daily.append(float(rev_row['daily_rev']) if rev_row else 0.0)

    return jsonify({
        'occupancy': occupancy_chart,
        'reservations_trend': {
            'labels': date_labels,
            'counts': reservation_counts
        },
        'revenue_trend': {
            'labels': date_labels,
            'amounts': revenue_daily
        },
        'metrics': metrics
    })
