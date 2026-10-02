"""뼈대 확인: 네 화면과 세 API 가 응답한다. DB 없이 돈다."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_pages_open():
    for path in ["/", "/r/demo", "/r/demo/add", "/r/demo/board"]:
        res = client.get(path)
        assert res.status_code == 200, path
        assert "text/html" in res.headers["content-type"]


def test_lane_apis_respond():
    for path in ["/api/rooms", "/api/expenses", "/api/board", "/api/health"]:
        assert client.get(path).status_code == 200, path
