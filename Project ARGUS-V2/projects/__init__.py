"""
Projects: Project templates and scaffolding for ARGUS-V2

Provides ready-to-use project templates for common application types.
"""

from .microservice import MicroserviceTemplate
from .webapp import WebAppTemplate  
from .cli_app import CLIAppTemplate

__all__ = [
    "MicroserviceTemplate",
    "WebAppTemplate", 
    "CLIAppTemplate"
]