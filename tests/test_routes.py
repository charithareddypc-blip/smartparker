import pytest

def test_all_pages_render(auth_client):
    """Verify that all core dashboard and management pages render successfully (HTTP 200)."""
    endpoints = [
        '/',
        '/dashboard',
        '/parking',
        '/reservations',
        '/reservations/new',
        '/payments',
        '/occupancy',
        '/customers',
        '/api/dashboard/charts'
    ]
    for endpoint in endpoints:
        resp = auth_client.get(endpoint)
        assert resp.status_code == 200, f"Endpoint {endpoint} failed with status {resp.status_code}"
