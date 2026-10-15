// Dashboard Charts & Live Metric Updating
document.addEventListener('DOMContentLoaded', function () {
    let occupancyChart = null;
    let reservationsChart = null;
    let revenueChart = null;

    async function loadDashboardCharts() {
        try {
            const response = await fetch('/api/dashboard/charts');
            if (!response.ok) return;
            const data = await response.json();

            // 1. Occupancy Doughnut Chart
            const ctxOccupancy = document.getElementById('occupancyDoughnutChart');
            if (ctxOccupancy) {
                if (occupancyChart) occupancyChart.destroy();
                occupancyChart = new Chart(ctxOccupancy, {
                    type: 'doughnut',
                    data: {
                        labels: data.occupancy.labels,
                        datasets: [{
                            data: data.occupancy.data,
                            backgroundColor: data.occupancy.colors,
                            borderWidth: 2,
                            borderColor: '#ffffff',
                            hoverOffset: 4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false }
                        },
                        cutout: '68%'
                    }
                });
            }

            // 2. Daily Reservations Trend
            const ctxRes = document.getElementById('reservationsTrendChart');
            if (ctxRes) {
                if (reservationsChart) reservationsChart.destroy();
                reservationsChart = new Chart(ctxRes, {
                    type: 'bar',
                    data: {
                        labels: data.reservations_trend.labels,
                        datasets: [{
                            label: 'Bookings',
                            data: data.reservations_trend.counts,
                            backgroundColor: '#3b82f6',
                            borderRadius: 6
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: { stepSize: 1 }
                            },
                            x: {
                                grid: { display: false }
                            }
                        },
                        plugins: {
                            legend: { display: false }
                        }
                    }
                });
            }

            // 3. Payment Revenue Trend
            const ctxRev = document.getElementById('revenueTrendChart');
            if (ctxRev) {
                if (revenueChart) revenueChart.destroy();
                revenueChart = new Chart(ctxRev, {
                    type: 'line',
                    data: {
                        labels: data.revenue_trend.labels,
                        datasets: [{
                            label: 'Revenue ($)',
                            data: data.revenue_trend.amounts,
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            fill: true,
                            tension: 0.35,
                            pointRadius: 4,
                            pointBackgroundColor: '#10b981'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    callback: function(val) { return '$' + val; }
                                }
                            },
                            x: {
                                grid: { display: false }
                            }
                        },
                        plugins: {
                            legend: { display: false }
                        }
                    }
                });
            }

        } catch (err) {
            console.error('Failed to load dashboard chart data:', err);
        }
    }

    loadDashboardCharts();
});
