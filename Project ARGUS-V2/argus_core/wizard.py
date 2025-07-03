"""
Interactive Project Creation Wizard for ARGUS-V2
"""

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
import asyncio

class ProjectWizard:
    """Interactive wizard for creating ARGUS projects."""
    
    def __init__(self):
        self.console = Console()
    
    async def run_wizard(self):
        """Run the complete project creation wizard."""
        self.console.print(Panel.fit(
            "🧙 Welcome to the ARGUS-V2 Project Wizard!\n"
            "Let's create an amazing project together.",
            title="✨ Project Wizard"
        ))
        
        # Gather project information
        project_info = await self.gather_project_info()
        
        # Show configuration summary
        await self.show_summary(project_info)
        
        # Confirm and create
        if Confirm.ask("Create this project?"):
            await self.create_project(project_info)
            return project_info
        else:
            self.console.print("❌ Project creation cancelled.")
            return None
    
    async def gather_project_info(self):
        """Gather project information interactively."""
        info = {}
        
        # Project name
        info['name'] = Prompt.ask("🏷️ Project name")
        
        # Project type
        self.console.print("\n📦 Available project types:")
        types_table = Table()
        types_table.add_column("Type", style="cyan")
        types_table.add_column("Description", style="white")
        
        project_types = {
            "microservice": "FastAPI-based microservice",
            "webapp": "Flask-based web application", 
            "cli": "Typer-based command-line tool",
            "library": "Python package/library"
        }
        
        for ptype, desc in project_types.items():
            types_table.add_row(ptype, desc)
        
        self.console.print(types_table)
        
        info['type'] = Prompt.ask(
            "\n🎯 Choose project type",
            choices=list(project_types.keys()),
            default="microservice"
        )
        
        # Features selection
        self.console.print("\n⚡ Select features to include:")
        
        features = {
            "testing": "Comprehensive test suite",
            "docker": "Docker containerization",
            "ci_cd": "GitHub Actions CI/CD",
            "monitoring": "Built-in monitoring",
            "docs": "Auto-generated documentation"
        }
        
        info['features'] = []
        for feature, description in features.items():
            if Confirm.ask(f"Include {feature}? ({description})"):
                info['features'].append(feature)
        
        return info
    
    async def show_summary(self, info):
        """Show project configuration summary."""
        summary_table = Table(title="📋 Project Configuration Summary")
        summary_table.add_column("Setting", style="cyan")
        summary_table.add_column("Value", style="green")
        
        summary_table.add_row("Name", info['name'])
        summary_table.add_row("Type", info['type'])
        summary_table.add_row("Features", ", ".join(info['features']) or "None")
        
        self.console.print("\n")
        self.console.print(summary_table)
    
    async def create_project(self, info):
        """Create the project with progress indication."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            
            task = progress.add_task("Creating project...", total=None)
            
            # Simulate project creation steps
            steps = [
                "Creating project structure",
                "Generating template files", 
                "Setting up dependencies",
                "Configuring features",
                "Initializing git repository"
            ]
            
            for step in steps:
                progress.update(task, description=step)
                await asyncio.sleep(0.5)  # Simulate work
            
            progress.update(task, description="✅ Project created successfully!")
        
        self.console.print(f"\n🎉 Project '{info['name']}' created successfully!")
        self.console.print(f"📁 Next steps:")
        self.console.print(f"   cd {info['name']}")
        self.console.print(f"   argus orchestrate")

# Global wizard instance
project_wizard = ProjectWizard()
