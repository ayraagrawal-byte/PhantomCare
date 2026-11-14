from api.app import app, health


def test_health() -> None:
    response = health()

    assert response.model_dump() == {"status": "ok", "environment": "development"}


def test_health_route_is_registered() -> None:
    assert "/health" in app.openapi()["paths"]

