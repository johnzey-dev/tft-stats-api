from flask import json
from src.api.routes.stats import get_stats

def test_get_stats(client):
    response = client.get('/api/stats?username=testuser')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'current_rank' in data
    assert 'average_position' in data
    assert 'last_games' in data
    assert len(data['last_games']) == 5

def test_get_stats_invalid_username(client):
    response = client.get('/api/stats?username=invaliduser')
    assert response.status_code == 404
    data = json.loads(response.data)
    assert 'error' in data
    assert data['error'] == 'User not found'