"""
ARGUS-V2: High-Performance Multi-Agent AI Orchestration Framework

A lean, modern rewrite focused on:
- Performance: ≤200ms CLI cold start, ≤30s builds
- Simplicity: Clean APIs, intuitive workflows  
- Extensibility: Plugin-based architecture
- Reliability: 90%+ test coverage, zero critical CVEs
"""

__version__ = "2.0.0"
__author__ = "ARGUS Framework Team"
__email__ = "argus@example.com"

from .gateway import AgentGateway
from .orchestrator import Orchestrator
from .scheduler import AsyncScheduler

__all__ = [
    "AgentGateway",
    "Orchestrator", 
    "AsyncScheduler",
    "__version__",
]