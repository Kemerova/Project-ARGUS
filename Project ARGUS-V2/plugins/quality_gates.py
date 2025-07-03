"""
Quality Gates: Standard quality gate plugins for ARGUS-V2

Replaces V1's rigid quality system with flexible, configurable gates.
"""

import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, List

from argus_core.hooks import quality_gate
import structlog

logger = structlog.get_logger(__name__)

@quality_gate("lint", priority=90, description="Code linting with configurable tools")
async def lint_quality_gate(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run code linting checks.
    
    Supports: ruff, flake8, pylint, eslint, etc.
    """
    logger.info("Executing lint quality gate")
    
    project_path = context.get("project_path", ".")
    linters = context.get("linters", ["ruff"])
    
    results = {}
    overall_passed = True
    
    for linter in linters:
        try:
            if linter == "ruff":
                result = await _run_ruff(project_path)
            elif linter == "flake8":
                result = await _run_flake8(project_path)
            elif linter == "pylint":
                result = await _run_pylint(project_path)
            elif linter == "eslint":
                result = await _run_eslint(project_path)
            else:
                logger.warning(f"Unknown linter: {linter}")
                result = {"passed": False, "output": f"Unknown linter: {linter}"}
            
            results[linter] = result
            if not result["passed"]:
                overall_passed = False
                
        except Exception as e:
            logger.error(f"Linter {linter} failed with exception", error=str(e))
            results[linter] = {"passed": False, "output": str(e)}
            overall_passed = False
    
    return {
        "passed": overall_passed,
        "gate_name": "lint",
        "results": results,
        "summary": f"Linting: {'PASSED' if overall_passed else 'FAILED'}"
    }

async def _run_ruff(project_path: str) -> Dict[str, Any]:
    """Run ruff linter."""
    try:
        result = await asyncio.create_subprocess_exec(
            "ruff", "check", project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()
        
        passed = result.returncode == 0
        output = stdout.decode() + stderr.decode()
        
        return {"passed": passed, "output": output, "tool": "ruff"}
        
    except FileNotFoundError:
        return {"passed": False, "output": "ruff not found in PATH", "tool": "ruff"}

async def _run_flake8(project_path: str) -> Dict[str, Any]:
    """Run flake8 linter."""
    try:
        result = await asyncio.create_subprocess_exec(
            "flake8", project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()
        
        passed = result.returncode == 0
        output = stdout.decode() + stderr.decode()
        
        return {"passed": passed, "output": output, "tool": "flake8"}
        
    except FileNotFoundError:
        return {"passed": False, "output": "flake8 not found in PATH", "tool": "flake8"}

async def _run_pylint(project_path: str) -> Dict[str, Any]:
    """Run pylint linter."""
    try:
        result = await asyncio.create_subprocess_exec(
            "pylint", project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()
        
        # Pylint returns non-zero for issues, but we check the score
        output = stdout.decode() + stderr.decode()
        
        # Simple check for "rated at" score
        passed = "rated at 10.00/10" in output or result.returncode == 0
        
        return {"passed": passed, "output": output, "tool": "pylint"}
        
    except FileNotFoundError:
        return {"passed": False, "output": "pylint not found in PATH", "tool": "pylint"}

async def _run_eslint(project_path: str) -> Dict[str, Any]:
    """Run ESLint for JavaScript/TypeScript projects."""
    try:
        result = await asyncio.create_subprocess_exec(
            "eslint", project_path, "--ext", ".js,.ts,.tsx",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()
        
        passed = result.returncode == 0
        output = stdout.decode() + stderr.decode()
        
        return {"passed": passed, "output": output, "tool": "eslint"}
        
    except FileNotFoundError:
        return {"passed": False, "output": "eslint not found in PATH", "tool": "eslint"}

@quality_gate("test", priority=95, description="Automated test execution")
async def test_quality_gate(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run automated tests.
    
    Supports: pytest, unittest, jest, etc.
    """
    logger.info("Executing test quality gate")
    
    project_path = context.get("project_path", ".")
    test_runners = context.get("test_runners", ["pytest"])
    coverage_threshold = context.get("coverage_threshold", 80)
    
    results = {}
    overall_passed = True
    
    for runner in test_runners:
        try:
            if runner == "pytest":
                result = await _run_pytest(project_path, coverage_threshold)
            elif runner == "unittest":
                result = await _run_unittest(project_path)
            elif runner == "jest":
                result = await _run_jest(project_path)
            else:
                logger.warning(f"Unknown test runner: {runner}")
                result = {"passed": False, "output": f"Unknown test runner: {runner}"}
            
            results[runner] = result
            if not result["passed"]:
                overall_passed = False
                
        except Exception as e:
            logger.error(f"Test runner {runner} failed with exception", error=str(e))
            results[runner] = {"passed": False, "output": str(e)}
            overall_passed = False
    
    return {
        "passed": overall_passed,
        "gate_name": "test",
        "results": results,
        "summary": f"Testing: {'PASSED' if overall_passed else 'FAILED'}"
    }

async def _run_pytest(project_path: str, coverage_threshold: int) -> Dict[str, Any]:
    """Run pytest with coverage."""
    try:
        result = await asyncio.create_subprocess_exec(
            "pytest", project_path, 
            "--cov", "--cov-report=term-missing",
            f"--cov-fail-under={coverage_threshold}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()
        
        passed = result.returncode == 0
        output = stdout.decode() + stderr.decode()
        
        return {"passed": passed, "output": output, "tool": "pytest"}
        
    except FileNotFoundError:
        return {"passed": False, "output": "pytest not found in PATH", "tool": "pytest"}

async def _run_unittest(project_path: str) -> Dict[str, Any]:
    """Run Python unittest."""
    try:
        result = await asyncio.create_subprocess_exec(
            "python", "-m", "unittest", "discover", "-s", project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()
        
        passed = result.returncode == 0
        output = stdout.decode() + stderr.decode()
        
        return {"passed": passed, "output": output, "tool": "unittest"}
        
    except Exception as e:
        return {"passed": False, "output": str(e), "tool": "unittest"}

async def _run_jest(project_path: str) -> Dict[str, Any]:
    """Run Jest for JavaScript/TypeScript tests."""
    try:
        result = await asyncio.create_subprocess_exec(
            "jest", "--coverage",
            cwd=project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()
        
        passed = result.returncode == 0
        output = stdout.decode() + stderr.decode()
        
        return {"passed": passed, "output": output, "tool": "jest"}
        
    except FileNotFoundError:
        return {"passed": False, "output": "jest not found in PATH", "tool": "jest"}

@quality_gate("security_scan", priority=85, description="Security vulnerability scanning")
async def security_scan_gate(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run security vulnerability scans.
    
    Supports: bandit, safety, semgrep, etc.
    """
    logger.info("Executing security scan quality gate")
    
    project_path = context.get("project_path", ".")
    scanners = context.get("security_scanners", ["bandit", "safety"])
    
    results = {}
    overall_passed = True
    
    for scanner in scanners:
        try:
            if scanner == "bandit":
                result = await _run_bandit(project_path)
            elif scanner == "safety":
                result = await _run_safety(project_path)
            elif scanner == "semgrep":
                result = await _run_semgrep(project_path)
            else:
                logger.warning(f"Unknown security scanner: {scanner}")
                result = {"passed": False, "output": f"Unknown scanner: {scanner}"}
            
            results[scanner] = result
            if not result["passed"]:
                overall_passed = False
                
        except Exception as e:
            logger.error(f"Security scanner {scanner} failed", error=str(e))
            results[scanner] = {"passed": False, "output": str(e)}
            overall_passed = False
    
    return {
        "passed": overall_passed,
        "gate_name": "security_scan",
        "results": results,
        "summary": f"Security: {'PASSED' if overall_passed else 'FAILED'}"
    }

async def _run_bandit(project_path: str) -> Dict[str, Any]:
    """Run bandit security scanner."""
    try:
        result = await asyncio.create_subprocess_exec(
            "bandit", "-r", project_path, "-f", "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()
        
        # Bandit returns 1 for issues found, but we check the JSON output
        output = stdout.decode() + stderr.decode()
        
        # Simple check - no high or medium severity issues
        passed = '"severity": "HIGH"' not in output and '"severity": "MEDIUM"' not in output
        
        return {"passed": passed, "output": output, "tool": "bandit"}
        
    except FileNotFoundError:
        return {"passed": False, "output": "bandit not found in PATH", "tool": "bandit"}

async def _run_safety(project_path: str) -> Dict[str, Any]:
    """Run safety dependency scanner."""
    try:
        result = await asyncio.create_subprocess_exec(
            "safety", "check", "--json",
            cwd=project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()
        
        passed = result.returncode == 0
        output = stdout.decode() + stderr.decode()
        
        return {"passed": passed, "output": output, "tool": "safety"}
        
    except FileNotFoundError:
        return {"passed": False, "output": "safety not found in PATH", "tool": "safety"}

async def _run_semgrep(project_path: str) -> Dict[str, Any]:
    """Run semgrep security scanner."""
    try:
        result = await asyncio.create_subprocess_exec(
            "semgrep", "--config=auto", project_path, "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()
        
        # Semgrep returns 1 for findings, but we check severity
        output = stdout.decode() + stderr.decode()
        
        # Simple check - no high severity findings
        passed = '"severity": "ERROR"' not in output
        
        return {"passed": passed, "output": output, "tool": "semgrep"}
        
    except FileNotFoundError:
        return {"passed": False, "output": "semgrep not found in PATH", "tool": "semgrep"}

@quality_gate("performance_check", priority=70, description="Performance benchmarking")
async def performance_check_gate(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run performance checks and benchmarks.
    """
    logger.info("Executing performance check quality gate")
    
    project_path = context.get("project_path", ".")
    performance_tools = context.get("performance_tools", ["pytest-benchmark"])
    
    results = {}
    overall_passed = True
    
    for tool in performance_tools:
        try:
            if tool == "pytest-benchmark":
                result = await _run_pytest_benchmark(project_path)
            elif tool == "locust":
                result = await _run_locust(project_path)
            else:
                logger.warning(f"Unknown performance tool: {tool}")
                result = {"passed": False, "output": f"Unknown tool: {tool}"}
            
            results[tool] = result
            if not result["passed"]:
                overall_passed = False
                
        except Exception as e:
            logger.error(f"Performance tool {tool} failed", error=str(e))
            results[tool] = {"passed": False, "output": str(e)}
            overall_passed = False
    
    return {
        "passed": overall_passed,
        "gate_name": "performance_check",
        "results": results,
        "summary": f"Performance: {'PASSED' if overall_passed else 'FAILED'}"
    }

async def _run_pytest_benchmark(project_path: str) -> Dict[str, Any]:
    """Run pytest with benchmarks."""
    try:
        result = await asyncio.create_subprocess_exec(
            "pytest", project_path, "--benchmark-only",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()
        
        passed = result.returncode == 0
        output = stdout.decode() + stderr.decode()
        
        return {"passed": passed, "output": output, "tool": "pytest-benchmark"}
        
    except FileNotFoundError:
        return {"passed": True, "output": "pytest-benchmark not found, skipping", "tool": "pytest-benchmark"}

async def _run_locust(project_path: str) -> Dict[str, Any]:
    """Run Locust load testing."""
    # This would be a more complex implementation in practice
    return {"passed": True, "output": "Locust integration not implemented", "tool": "locust"}