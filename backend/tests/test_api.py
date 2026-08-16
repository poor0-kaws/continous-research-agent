from fastapi.testclient import TestClient

from research_agent.db import get_session
from research_agent.main import app


def test_topic_and_run_flow(session) -> None:  # type: ignore[no-untyped-def]
    def override_session():  # type: ignore[no-untyped-def]
        yield session

    app.dependency_overrides[get_session] = override_session
    client = TestClient(app)

    response = client.post(
        "/api/topics",
        json={
            "title": "Battery research",
            "question": "What new evidence exists about solid state batteries?",
            "keywords": ["batteries", "energy"],
        },
    )
    assert response.status_code == 201
    topic = response.json()

    first_run = client.post(f"/api/topics/{topic['id']}/runs")
    second_run = client.post(f"/api/topics/{topic['id']}/runs")

    assert first_run.status_code == 202
    assert second_run.json()["id"] == first_run.json()["id"]
    listed_runs = client.get(f"/api/topics/{topic['id']}/runs")
    assert listed_runs.status_code == 200
    assert listed_runs.json()[0]["id"] == first_run.json()["id"]
    app.dependency_overrides.clear()
