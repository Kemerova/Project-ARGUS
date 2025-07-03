# Hello Microservice - ARGUS-V2 Sample

A "Hello World" microservice demonstrating ARGUS-V2 capabilities.

## Features

- 🚀 **FastAPI** - Modern, fast web framework
- 🤖 **ARGUS-V2** - Multi-agent AI orchestration
- ⚡ **High Performance** - Optimized startup and runtime
- 🔧 **Quality Gates** - Automated testing and validation

## Quick Start

```bash
# Run the microservice
python src/main.py

# Test endpoints
curl http://localhost:8000/
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/hello

# Run with ARGUS orchestration
argus orchestrate --config argus.yaml
```

## API Endpoints

- `GET /` - Service info
- `GET /health` - Health check  
- `GET /api/v1/hello` - Hello endpoint
- `POST /api/v1/echo` - Echo endpoint

## ARGUS-V2 Demonstration

This sample demonstrates key ARGUS-V2 features:

### Multi-Agent Orchestration
- **Claude**: Lead architect and system design
- **Gemini**: Security analysis and performance
- **GPT-4**: Code review and quality assurance

### Performance Benchmarks
- CLI cold start: <200ms
- Build time: <30s
- Memory usage: <250MB
- Test coverage: >90%

### Quality Gates
- **Lint**: Code quality with ruff/mypy
- **Test**: Automated testing with pytest
- **Security**: Vulnerability scanning
- **Performance**: Benchmark validation

---

*Built with 🤖 ARGUS-V2 Framework*