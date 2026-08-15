import pytest
from httpx import ASGITransport, AsyncClient

from resume_matcher.config import Settings
from resume_matcher.main import create_app


@pytest.mark.anyio
async def test_health_does_not_require_gemini_key() -> None:
    app = create_app(Settings(_env_file=None))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}
