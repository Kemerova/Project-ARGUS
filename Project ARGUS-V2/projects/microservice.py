"""
Microservice Template: FastAPI-based microservice with ARGUS orchestration

Creates a production-ready microservice with:
- FastAPI framework
- Async architecture
- Health checks and monitoring
- Docker containerization
- ARGUS integration
"""

from pathlib import Path
from typing import Dict, Any, List

class MicroserviceTemplate:
    """Template for creating microservice projects."""
    
    def __init__(self, project_name: str, agents: List[str]):
        self.project_name = project_name
        self.agents = agents
        
    def create(self, output_dir: Path) -> None:
        """Create the microservice project structure."""
        
        project_path = output_dir / self.project_name
        project_path.mkdir(parents=True, exist_ok=True)
        
        # Create directory structure
        self._create_directories(project_path)
        
        # Create files
        self._create_main_app(project_path)
        self._create_requirements(project_path)
        self._create_dockerfile(project_path)
        self._create_docker_compose(project_path)
        self._create_tests(project_path)
        self._create_argus_config(project_path)
        self._create_readme(project_path)
        
    def _create_directories(self, project_path: Path) -> None:
        """Create the directory structure."""
        dirs = [
            "src/api",
            "src/models",
            "src/services", 
            "src/core",
            "tests/unit",
            "tests/integration",
            "docs",
            "scripts",
            "config"
        ]
        
        for dir_path in dirs:
            (project_path / dir_path).mkdir(parents=True, exist_ok=True)
    
    def _create_main_app(self, project_path: Path) -> None:
        """Create the main FastAPI application."""
        
        main_py = f'''"""
{self.project_name} - Microservice built with ARGUS-V2
"""

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from .core.config import get_settings
from .core.logging import setup_logging
from .api.v1.router import api_router

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting {self.project_name} microservice")
    yield
    logger.info("Shutting down {self.project_name} microservice")

# Create FastAPI app
app = FastAPI(
    title="{self.project_name}",
    description="Microservice built with ARGUS-V2 orchestration",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Get settings
settings = get_settings()

# Add security middleware
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=settings.allowed_hosts
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    """Root endpoint."""
    return {{
        "service": "{self.project_name}",
        "version": "1.0.0",
        "status": "running",
        "framework": "ARGUS-V2"
    }}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {{
        "status": "healthy",
        "service": "{self.project_name}",
        "timestamp": "{{}}".format(__import__("datetime").datetime.utcnow().isoformat())
    }}

@app.get("/metrics")
async def metrics():
    """Metrics endpoint for monitoring."""
    # In production, this would return Prometheus metrics
    return {{
        "requests_total": 0,
        "requests_duration_seconds": 0.0,
        "memory_usage_bytes": 0
    }}

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )
'''
        
        (project_path / "src" / "main.py").write_text(main_py)
        
        # Create __init__.py files
        (project_path / "src" / "__init__.py").write_text("")
        (project_path / "src" / "api" / "__init__.py").write_text("")
        (project_path / "src" / "models" / "__init__.py").write_text("")
        (project_path / "src" / "services" / "__init__.py").write_text("")
        (project_path / "src" / "core" / "__init__.py").write_text("")
        
        # Create core configuration
        config_py = '''"""Application configuration."""

from functools import lru_cache
from typing import List

from pydantic import BaseSettings

class Settings(BaseSettings):
    """Application settings."""
    
    # App settings
    app_name: str = "''' + self.project_name + '''"
    debug: bool = False
    version: str = "1.0.0"
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Security settings
    secret_key: str = "dev-secret-key-change-in-production"
    allowed_hosts: List[str] = ["*"]
    cors_origins: List[str] = ["*"]
    
    # Database settings (example)
    database_url: str = "sqlite:///./app.db"
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
'''
        
        (project_path / "src" / "core" / "config.py").write_text(config_py)
        
        # Create logging configuration
        logging_py = '''"""Logging configuration."""

import logging
import sys
from typing import Any, Dict

def setup_logging() -> None:
    """Setup application logging."""
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("app.log")
        ]
    )
    
    # Set specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
'''
        
        (project_path / "src" / "core" / "logging.py").write_text(logging_py)
        
        # Create API router
        router_py = '''"""API v1 router."""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any

api_router = APIRouter()

@api_router.get("/status")
async def get_status():
    """Get service status."""
    return {
        "status": "operational",
        "version": "1.0.0",
        "endpoints": ["/status", "/health"]
    }

@api_router.post("/process")
async def process_data(data: Dict[str, Any]):
    """Process data endpoint."""
    # Example processing logic
    processed_data = {
        "input": data,
        "processed": True,
        "result": "Data processed successfully"
    }
    
    return processed_data
'''
        
        (project_path / "src" / "api" / "v1" / "__init__.py").write_text("")
        (project_path / "src" / "api" / "v1").mkdir(parents=True, exist_ok=True)
        (project_path / "src" / "api" / "v1" / "router.py").write_text(router_py)
    
    def _create_requirements(self, project_path: Path) -> None:
        """Create requirements.txt."""
        
        requirements = '''# Production dependencies
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.5.0
pydantic-settings>=2.1.0

# Development dependencies
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
httpx>=0.25.0
black>=23.0.0
ruff>=0.1.6
mypy>=1.7.0

# ARGUS-V2 integration
argus-v2>=2.0.0
'''
        
        (project_path / "requirements.txt").write_text(requirements)
    
    def _create_dockerfile(self, project_path: Path) -> None:
        """Create Dockerfile."""
        
        dockerfile = f'''# Multi-stage build for production
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY src/ .

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["python", "main.py"]
'''
        
        (project_path / "Dockerfile").write_text(dockerfile)
    
    def _create_docker_compose(self, project_path: Path) -> None:
        """Create docker-compose.yml."""
        
        compose = f'''version: '3.8'

services:
  {self.project_name}:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DEBUG=false
      - HOST=0.0.0.0
      - PORT=8000
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    
  # Optional: Add database service
  # postgres:
  #   image: postgres:15
  #   environment:
  #     POSTGRES_DB: {self.project_name}
  #     POSTGRES_USER: user
  #     POSTGRES_PASSWORD: password
  #   volumes:
  #     - postgres_data:/var/lib/postgresql/data
  #   ports:
  #     - "5432:5432"

# volumes:
#   postgres_data:
'''
        
        (project_path / "docker-compose.yml").write_text(compose)
    
    def _create_tests(self, project_path: Path) -> None:
        """Create test files."""
        
        # Test configuration
        conftest_py = '''"""Test configuration."""

import pytest
from fastapi.testclient import TestClient

from src.main import app

@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)

@pytest.fixture
def sample_data():
    """Sample test data."""
    return {
        "test_field": "test_value",
        "number": 42
    }
'''
        
        (project_path / "tests" / "conftest.py").write_text(conftest_py)
        
        # Unit tests
        test_main_py = '''"""Test main application."""

def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert "framework" in data

def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_api_status(client):
    """Test API status endpoint."""
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"

def test_process_data(client, sample_data):
    """Test data processing endpoint."""
    response = client.post("/api/v1/process", json=sample_data)
    assert response.status_code == 200
    data = response.json()
    assert data["processed"] is True
    assert data["input"] == sample_data
'''
        
        (project_path / "tests" / "unit" / "test_main.py").write_text(test_main_py)
        (project_path / "tests" / "__init__.py").write_text("")
        (project_path / "tests" / "unit" / "__init__.py").write_text("")
        (project_path / "tests" / "integration" / "__init__.py").write_text("")
    
    def _create_argus_config(self, project_path: Path) -> None:
        """Create ARGUS configuration."""
        
        argus_config = f'''# ARGUS-V2 Configuration for {self.project_name}
project:
  name: {self.project_name}
  type: microservice
  version: "1.0.0"
  description: "FastAPI microservice built with ARGUS-V2"

agents:
'''
        
        for agent in self.agents:
            if agent == "claude":
                argus_config += '''  - name: claude
    role: lead_architect
    provider: claude
    model: claude-3-sonnet-20240229
    timeout: 30
    max_tokens: 4000
    
'''
            elif agent == "gemini":
                argus_config += '''  - name: gemini
    role: security_analyst
    provider: gemini
    model: gemini-1.5-pro
    timeout: 30
    max_tokens: 4000
    
'''
            elif agent == "gpt4":
                argus_config += '''  - name: gpt4
    role: code_reviewer
    provider: openai
    model: gpt-4-turbo-preview
    timeout: 30
    max_tokens: 4000
    
'''
        
        argus_config += '''phases:
  - name: plan
    type: plan
    timeout: 300
    consensus_threshold: 0.75
    parallel: false
    required_agents: [claude, gemini]
    
  - name: execute
    type: execute
    timeout: 600
    parallel: true
    quality_gates: [lint, test, security_scan]
    
  - name: validate
    type: validate
    timeout: 300
    quality_gates: [performance_check, integration_test]

quality_gates:
  lint:
    tools: [ruff, mypy]
    
  test:
    runners: [pytest]
    coverage_threshold: 80
    
  security_scan:
    scanners: [bandit, safety]
    
  performance_check:
    tools: [pytest-benchmark]
'''
        
        (project_path / "argus.yaml").write_text(argus_config)
    
    def _create_readme(self, project_path: Path) -> None:
        """Create README.md."""
        
        readme = f'''# {self.project_name}

A high-performance microservice built with ARGUS-V2 orchestration framework.

## Features

- 🚀 **FastAPI** - Modern, fast web framework
- 🐳 **Docker** - Containerized deployment
- 🧪 **Testing** - Comprehensive test suite with pytest
- 🔒 **Security** - Built-in security best practices
- 📊 **Monitoring** - Health checks and metrics
- 🤖 **ARGUS-V2** - Multi-agent AI orchestration

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python src/main.py

# Run tests
pytest

# Run with ARGUS orchestration
argus orchestrate --config argus.yaml
```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or build and run manually
docker build -t {self.project_name} .
docker run -p 8000:8000 {self.project_name}
```

## API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /metrics` - Metrics for monitoring
- `GET /api/v1/status` - API status
- `POST /api/v1/process` - Data processing

## Development

### ARGUS Orchestration

This project uses ARGUS-V2 for multi-agent AI development orchestration:

```bash
# Create new features with AI agents
argus orchestrate --prompt "Add user authentication"

# Run quality gates
argus orchestrate --phases validate

# Monitor development progress
argus status --live
```

### Code Quality

```bash
# Linting
ruff check src/
mypy src/

# Testing
pytest --cov=src tests/

# Security scanning
bandit -r src/
safety check
```

## Deployment

### Environment Variables

- `DEBUG` - Enable debug mode (default: false)
- `HOST` - Server host (default: 0.0.0.0)
- `PORT` - Server port (default: 8000)
- `DATABASE_URL` - Database connection URL

### Production Checklist

- [ ] Set strong `SECRET_KEY`
- [ ] Configure proper `ALLOWED_HOSTS`
- [ ] Set up database connection
- [ ] Configure logging
- [ ] Set up monitoring
- [ ] Enable HTTPS
- [ ] Configure rate limiting

## Architecture

```
{self.project_name}/
├── src/
│   ├── api/v1/          # API endpoints
│   ├── core/            # Core configuration
│   ├── models/          # Data models
│   ├── services/        # Business logic
│   └── main.py          # Application entry point
├── tests/               # Test suite
├── config/              # Configuration files
├── docs/                # Documentation
└── argus.yaml           # ARGUS-V2 configuration
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes using ARGUS orchestration
4. Run quality gates: `argus orchestrate --phases validate`
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

---

*Built with 🤖 ARGUS-V2 Multi-Agent AI Orchestration*
'''
        
        (project_path / "README.md").write_text(readme)