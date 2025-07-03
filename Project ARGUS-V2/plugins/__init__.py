"""
Plugins: Extensible plugin system for ARGUS-V2

Provides core plugins and infrastructure for custom extensions.
"""

from .quality_gates import *
from .agent_providers import *

__all__ = [
    "LintQualityGate",
    "TestQualityGate", 
    "SecurityScanGate",
    "PerformanceCheckGate",
    "CustomAgentProvider"
]