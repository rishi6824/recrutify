import pytest
from interview_app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_devtools_probe(client):
    r = client.get('/.well-known/appspecific/com.chrome.devtools.json')
    assert r.status_code in (200, 204)


def test_get_role_questions(client):
    r = client.get('/api/questions/software_engineer')
    assert r.status_code == 200
    data = r.get_json()
    assert data['role'] == 'software_engineer'
    assert 'questions' in data


def test_session_questions_empty(client):
    r = client.get('/api/session/questions')
    assert r.status_code == 404


def test_questions_source_no_session(client):
    r = client.get('/api/questions_source')
    assert r.status_code == 200
    data = r.get_json()
    assert data['questions_source'] is None


def test_well_known_catch_all(client):
    # Any /.well-known/* path should return 200 and not 404
    r = client.get('/.well-known/this/is/a/test.json')
    assert r.status_code == 200
    assert r.get_data(as_text=True).strip() in ('{}', '')
