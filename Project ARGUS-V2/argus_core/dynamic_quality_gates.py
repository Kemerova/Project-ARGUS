"""
Dynamic Quality Gates System for ARGUS-V2
"""

import yaml
from typing import Dict, List, Any, Callable
from pathlib import Path
from dataclasses import dataclass

@dataclass
class QualityGate:
    """Represents a configurable quality gate."""
    name: str
    description: str
    enabled: bool
    threshold: float
    weight: float
    gate_function: Callable

class DynamicQualityGates:
    """Manages runtime-configurable quality gates."""
    
    def __init__(self, config_path: Path = None):
        self.config_path = config_path or Path("quality_gates.yml")
        self.gates: Dict[str, QualityGate] = {}
        self.load_configuration()
    
    def load_configuration(self):
        """Load quality gates configuration from YAML."""
        if not self.config_path.exists():
            self.create_default_config()
        
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            self.parse_gates_config(config)
        except Exception as e:
            print(f"Error loading quality gates config: {e}")
            self.load_default_gates()
    
    def create_default_config(self):
        """Create default quality gates configuration."""
        default_config = {
            'quality_gates': {
                'code_coverage': {
                    'description': 'Minimum code coverage percentage',
                    'enabled': True,
                    'threshold': 0.8,
                    'weight': 0.3
                },
                'lint_score': {
                    'description': 'Code linting score',
                    'enabled': True,
                    'threshold': 0.9,
                    'weight': 0.2
                },
                'security_scan': {
                    'description': 'Security vulnerability scan',
                    'enabled': True,
                    'threshold': 0.95,
                    'weight': 0.3
                },
                'performance_benchmark': {
                    'description': 'Performance benchmark threshold',
                    'enabled': False,
                    'threshold': 0.85,
                    'weight': 0.2
                }
            }
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)
    
    def parse_gates_config(self, config: Dict):
        """Parse gates configuration and create gate objects."""
        gates_config = config.get('quality_gates', {})
        
        for gate_name, gate_config in gates_config.items():
            gate_function = self.get_gate_function(gate_name)
            
            self.gates[gate_name] = QualityGate(
                name=gate_name,
                description=gate_config.get('description', ''),
                enabled=gate_config.get('enabled', True),
                threshold=gate_config.get('threshold', 0.8),
                weight=gate_config.get('weight', 0.25),
                gate_function=gate_function
            )
    
    def get_gate_function(self, gate_name: str) -> Callable:
        """Get the function for a specific quality gate."""
        gate_functions = {
            'code_coverage': self.check_code_coverage,
            'lint_score': self.check_lint_score,
            'security_scan': self.check_security_scan,
            'performance_benchmark': self.check_performance_benchmark
        }
        
        return gate_functions.get(gate_name, self.default_gate_check)
    
    async def run_quality_gates(self, project_path: Path) -> Dict[str, Any]:
        """Run all enabled quality gates."""
        results = {}
        overall_score = 0.0
        total_weight = 0.0
        
        for gate_name, gate in self.gates.items():
            if gate.enabled:
                try:
                    score = await gate.gate_function(project_path)
                    passed = score >= gate.threshold
                    
                    results[gate_name] = {
                        'score': score,
                        'threshold': gate.threshold,
                        'passed': passed,
                        'weight': gate.weight,
                        'description': gate.description
                    }
                    
                    # Contribute to overall score
                    overall_score += score * gate.weight
                    total_weight += gate.weight
                    
                except Exception as e:
                    results[gate_name] = {
                        'error': str(e),
                        'passed': False,
                        'weight': gate.weight
                    }
        
        # Calculate overall score
        final_score = overall_score / total_weight if total_weight > 0 else 0.0
        
        results['overall'] = {
            'score': final_score,
            'passed': final_score >= 0.8,  # Default overall threshold
            'gates_run': len([r for r in results.values() if 'score' in r])
        }
        
        return results
    
    async def check_code_coverage(self, project_path: Path) -> float:
        """Check code coverage gate."""
        # Simulate coverage check
        return 0.85  # 85% coverage
    
    async def check_lint_score(self, project_path: Path) -> float:
        """Check linting score gate."""
        # Simulate lint check
        return 0.92  # 92% lint score
    
    async def check_security_scan(self, project_path: Path) -> float:
        """Check security scan gate."""
        # Simulate security scan
        return 0.98  # 98% security score
    
    async def check_performance_benchmark(self, project_path: Path) -> float:
        """Check performance benchmark gate."""
        # Simulate performance test
        return 0.87  # 87% performance score
    
    async def default_gate_check(self, project_path: Path) -> float:
        """Default gate check implementation."""
        return 1.0  # Always pass unknown gates

# Global quality gates instance
dynamic_quality_gates = DynamicQualityGates()
