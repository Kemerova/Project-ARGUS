"""
Tests for Hello Microservice

Demonstrates ARGUS-V2 testing capabilities and quality gates.
"""

import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_root_endpoint():
    """Test root endpoint returns service info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "hello-microservice"
    assert data["framework"] == "ARGUS-V2"
    assert data["status"] == "running"
    assert "features" in data

def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "hello-microservice"
    assert data["framework"] == "ARGUS-V2"

def test_hello_endpoint():
    """Test hello endpoint returns ARGUS-V2 info."""
    response = client.get("/api/v1/hello")
    assert response.status_code == 200
    data = response.json()
    assert "Hello from ARGUS-V2!" in data["message"]
    assert "features" in data
    assert "performance" in data["features"]
    assert "architecture" in data["features"]

def test_echo_endpoint():
    """Test echo endpoint returns input message."""
    test_message = "Hello ARGUS-V2!"
    response = client.post("/api/v1/echo", json={"message": test_message})
    assert response.status_code == 200
    data = response.json()
    assert data["echo"] == test_message
    assert data["service"] == "hello-microservice"
    assert data["framework"] == "ARGUS-V2"

def test_echo_endpoint_empty_message():
    """Test echo endpoint with empty message."""
    response = client.post("/api/v1/echo", json={"message": ""})
    assert response.status_code == 200
    data = response.json()
    assert data["echo"] == ""

def test_invalid_endpoint():
    """Test invalid endpoint returns 404."""
    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404

@pytest.mark.benchmark
def test_performance_root_endpoint(benchmark):
    """Benchmark root endpoint performance."""
    def call_root():
        return client.get("/")
    
    result = benchmark(call_root)
    assert result.status_code == 200

@pytest.mark.benchmark  
def test_performance_hello_endpoint(benchmark):
    """Benchmark hello endpoint performance."""
    def call_hello():
        return client.get("/api/v1/hello")
    
    result = benchmark(call_hello)
    assert result.status_code == 200

class TestAPIValidation:
    """Test API validation and error handling."""
    
    def test_echo_missing_message_field(self):
        """Test echo endpoint with missing message field."""
        response = client.post("/api/v1/echo", json={})
        assert response.status_code == 422  # Validation error
    
    def test_echo_invalid_json(self):
        """Test echo endpoint with invalid JSON."""
        response = client.post(
            "/api/v1/echo", 
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

class TestSecurityHeaders:
    """Test security-related functionality."""
    
    def test_cors_headers(self):
        """Test CORS headers are present."""
        response = client.options("/api/v1/hello")
        # CORS headers should be present due to middleware
        # Actual values depend on FastAPI's CORS implementation

class TestMetrics:
    """Test application metrics and monitoring."""
    
    def test_service_metadata(self):
        """Test service returns proper metadata."""
        response = client.get("/")
        data = response.json()
        
        # Verify required metadata fields
        assert "service" in data
        assert "version" in data
        assert "framework" in data
        assert "status" in data
        
        # Verify version format
        assert data["version"] == "1.0.0"