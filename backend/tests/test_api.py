"""
API endpoint tests for Planning Precedent AI
"""

import pytest
from httpx import AsyncClient
from fastapi import status

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Create async test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


class TestHealthEndpoints:
    """Test health check endpoints"""

    @pytest.mark.anyio
    async def test_root_endpoint(self, client: AsyncClient):
        """Test root endpoint returns API info"""
        response = await client.get("/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "name" in data
        assert "version" in data

    @pytest.mark.anyio
    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint"""
        response = await client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"


class TestSearchEndpoints:
    """Test search API endpoints"""

    @pytest.mark.anyio
    async def test_search_requires_query(self, client: AsyncClient):
        """Test that search requires a query"""
        response = await client.post(
            "/api/v1/search",
            json={"query": ""}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.anyio
    async def test_search_minimum_query_length(self, client: AsyncClient):
        """Test that search requires minimum query length"""
        response = await client.post(
            "/api/v1/search",
            json={"query": "short"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.anyio
    async def test_quick_search(self, client: AsyncClient):
        """Test quick search endpoint"""
        response = await client.get(
            "/api/v1/search/quick",
            params={"q": "rear extension hampstead"}
        )
        # Should return 200 or 404 (no data)
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ]

    @pytest.mark.anyio
    async def test_development_types(self, client: AsyncClient):
        """Test development types endpoint"""
        response = await client.get("/api/v1/search/development-types")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "development_types" in data
        assert len(data["development_types"]) > 0

    @pytest.mark.anyio
    async def test_conservation_areas(self, client: AsyncClient):
        """Test conservation areas endpoint"""
        response = await client.get("/api/v1/search/conservation-areas")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "conservation_areas" in data


class TestAnalysisEndpoints:
    """Test analysis API endpoints"""

    @pytest.mark.anyio
    async def test_analyse_requires_detailed_query(self, client: AsyncClient):
        """Test that analysis requires detailed query"""
        response = await client.post(
            "/api/v1/analyse",
            json={"query": "short query"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestCasesEndpoints:
    """Test cases API endpoints"""

    @pytest.mark.anyio
    async def test_list_cases(self, client: AsyncClient):
        """Test listing cases"""
        response = await client.get("/api/v1/cases")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "cases" in data
        assert "total" in data
        assert "page" in data

    @pytest.mark.anyio
    async def test_list_cases_pagination(self, client: AsyncClient):
        """Test cases pagination"""
        response = await client.get(
            "/api/v1/cases",
            params={"page": 1, "page_size": 10}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    @pytest.mark.anyio
    async def test_get_nonexistent_case(self, client: AsyncClient):
        """Test getting a case that doesn't exist"""
        response = await client.get("/api/v1/cases/9999%2F9999%2FX")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReferenceEndpoints:
    """Test reference data endpoints"""

    @pytest.mark.anyio
    async def test_get_stats(self, client: AsyncClient):
        """Test database statistics endpoint"""
        response = await client.get("/api/v1/stats")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_decisions" in data

    @pytest.mark.anyio
    async def test_get_wards(self, client: AsyncClient):
        """Test wards endpoint"""
        response = await client.get("/api/v1/wards")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "wards" in data

    @pytest.mark.anyio
    async def test_get_policies(self, client: AsyncClient):
        """Test policies reference endpoint"""
        response = await client.get("/api/v1/policies")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "camden_local_plan" in data
        assert "london_plan" in data
        assert "nppf" in data

    @pytest.mark.anyio
    async def test_api_health(self, client: AsyncClient):
        """Test API health check with components"""
        response = await client.get("/api/v1/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data
        assert "components" in data
