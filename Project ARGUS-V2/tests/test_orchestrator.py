"""
Tests for ARGUS-V2 Orchestrator

Comprehensive test suite ensuring orchestration functionality works correctly.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock

from argus_core.orchestrator import (
    Orchestrator, 
    OrchestrationRequest, 
    PhaseConfig, 
    PhaseType,
    OrchestrationStatus
)
from argus_core.gateway import AgentGateway, AgentResponse, LLMProvider
from argus_core.scheduler import AsyncScheduler

@pytest.fixture
async def mock_gateway():
    """Mock agent gateway."""
    gateway = Mock(spec=AgentGateway)
    gateway.call_agent = AsyncMock()
    gateway.call_parallel = AsyncMock()
    gateway.get_agent_configs = Mock(return_value={
        "claude": Mock(role=Mock(value="lead_architect")),
        "gemini": Mock(role=Mock(value="security_analyst"))
    })
    return gateway

@pytest.fixture
async def mock_scheduler():
    """Mock scheduler."""
    scheduler = Mock(spec=AsyncScheduler)
    scheduler.start = AsyncMock()
    scheduler.stop = AsyncMock()
    return scheduler

@pytest.fixture
async def orchestrator(mock_gateway, mock_scheduler):
    """Create orchestrator instance."""
    return Orchestrator(mock_gateway, mock_scheduler)

@pytest.fixture
def sample_request():
    """Sample orchestration request."""
    return OrchestrationRequest(
        project_name="test-project",
        prompt="Test orchestration prompt",
        phases=[
            PhaseConfig(
                name="plan",
                type=PhaseType.PLAN,
                timeout=300,
                consensus_threshold=0.75
            ),
            PhaseConfig(
                name="execute", 
                type=PhaseType.EXECUTE,
                timeout=600,
                parallel=True,
                quality_gates=["lint", "test"]
            )
        ]
    )

@pytest.fixture
def mock_agent_response():
    """Mock agent response."""
    return AgentResponse(
        content="Mock agent response content",
        agent_name="claude",
        provider=LLMProvider.CLAUDE,
        tokens_used=100,
        response_time_ms=500,
        metadata={}
    )

class TestOrchestrator:
    """Test orchestrator functionality."""
    
    async def test_orchestrate_success(self, orchestrator, sample_request, mock_agent_response, mock_gateway):
        """Test successful orchestration."""
        # Setup mock responses
        mock_gateway.call_agent.return_value = mock_agent_response
        mock_gateway.call_parallel.return_value = [mock_agent_response, mock_agent_response]
        
        # Execute orchestration
        result = await orchestrator.orchestrate(sample_request)
        
        # Verify results
        assert result.status == OrchestrationStatus.COMPLETED
        assert result.project_name == "test-project"
        assert len(result.phase_results) == 2
        assert result.total_execution_time_ms > 0
        assert result.session_id is not None
    
    async def test_orchestrate_with_failed_phase(self, orchestrator, sample_request, mock_gateway):
        """Test orchestration with a failed phase."""
        # Setup mock to fail on first call
        mock_gateway.call_agent.side_effect = Exception("Mock agent failure")
        
        # Execute orchestration
        result = await orchestrator.orchestrate(sample_request)
        
        # Verify failure is handled
        assert result.status == OrchestrationStatus.FAILED
        assert len(result.phase_results) >= 1
        assert result.phase_results[0].status == OrchestrationStatus.FAILED
    
    async def test_consensus_calculation(self, orchestrator):
        """Test consensus score calculation."""
        # Test with similar responses (high consensus)
        similar_responses = [
            AgentResponse("Similar response A", "agent1", LLMProvider.CLAUDE, 100, 500, {}),
            AgentResponse("Similar response B", "agent2", LLMProvider.GEMINI, 110, 600, {}),
            AgentResponse("Similar response C", "agent3", LLMProvider.OPENAI, 90, 400, {})
        ]
        
        consensus = orchestrator._calculate_consensus(similar_responses)
        assert consensus > 0.5  # Should have reasonable consensus
        
        # Test with very different responses (low consensus)
        different_responses = [
            AgentResponse("Short", "agent1", LLMProvider.CLAUDE, 10, 100, {}),
            AgentResponse("This is a much longer response with many more words and details", "agent2", LLMProvider.GEMINI, 200, 800, {}),
            AgentResponse("Medium length response here", "agent3", LLMProvider.OPENAI, 100, 400, {})
        ]
        
        consensus = orchestrator._calculate_consensus(different_responses)
        assert consensus >= 0.0  # Should handle different responses
    
    async def test_phase_execution_parallel(self, orchestrator, mock_gateway, mock_agent_response):
        """Test parallel phase execution."""
        # Setup parallel phase
        phase_config = PhaseConfig(
            name="parallel_test",
            type=PhaseType.EXECUTE,
            parallel=True,
            required_agents=["claude", "gemini"]
        )
        
        request = OrchestrationRequest(
            project_name="test",
            prompt="test",
            phases=[phase_config]
        )
        
        # Mock parallel execution
        mock_gateway.call_parallel.return_value = [mock_agent_response, mock_agent_response]
        
        # Execute phase
        result = await orchestrator._execute_phase(phase_config, request, "test-session")
        
        # Verify parallel execution was called
        mock_gateway.call_parallel.assert_called_once()
        assert result.status == OrchestrationStatus.COMPLETED
        assert len(result.agent_responses) == 2
    
    async def test_phase_execution_sequential(self, orchestrator, mock_gateway, mock_agent_response):
        """Test sequential phase execution."""
        # Setup sequential phase
        phase_config = PhaseConfig(
            name="sequential_test",
            type=PhaseType.PLAN,
            parallel=False,
            required_agents=["claude", "gemini"]
        )
        
        request = OrchestrationRequest(
            project_name="test",
            prompt="test",
            phases=[phase_config]
        )
        
        # Mock sequential execution
        mock_gateway.call_agent.return_value = mock_agent_response
        
        # Execute phase
        result = await orchestrator._execute_phase(phase_config, request, "test-session")
        
        # Verify sequential execution
        assert mock_gateway.call_agent.call_count == 2  # Called for each agent
        assert result.status == OrchestrationStatus.COMPLETED
        assert len(result.agent_responses) == 2
    
    async def test_quality_gates_execution(self, orchestrator, mock_gateway, mock_agent_response):
        """Test quality gates execution."""
        # Setup phase with quality gates
        phase_config = PhaseConfig(
            name="quality_test",
            type=PhaseType.VALIDATE,
            quality_gates=["lint", "test", "security_scan"]
        )
        
        request = OrchestrationRequest(
            project_name="test",
            prompt="test",
            phases=[phase_config]
        )
        
        mock_gateway.call_agent.return_value = mock_agent_response
        
        # Execute phase
        result = await orchestrator._execute_phase(phase_config, request, "test-session")
        
        # Verify quality gates were attempted
        assert "lint" in result.quality_gate_results
        assert "test" in result.quality_gate_results
        assert "security_scan" in result.quality_gate_results
    
    async def test_session_management(self, orchestrator, sample_request, mock_gateway, mock_agent_response):
        """Test session management."""
        mock_gateway.call_agent.return_value = mock_agent_response
        
        # Start orchestration
        result = await orchestrator.orchestrate(sample_request)
        
        # Verify session was created and stored
        assert result.session_id in orchestrator.active_sessions
        
        # Test getting session status
        status = orchestrator.get_session_status(result.session_id)
        assert status is not None
        assert status.session_id == result.session_id
    
    async def test_session_cancellation(self, orchestrator, sample_request):
        """Test session cancellation."""
        # Create a mock session
        session_id = "test-session-123"
        mock_result = Mock()
        mock_result.status = OrchestrationStatus.RUNNING
        orchestrator.active_sessions[session_id] = mock_result
        
        # Cancel session
        cancelled = await orchestrator.cancel_session(session_id)
        
        # Verify cancellation
        assert cancelled is True
        assert orchestrator.active_sessions[session_id].status == OrchestrationStatus.CANCELLED
    
    async def test_prompt_generation(self, orchestrator, sample_request):
        """Test phase prompt generation."""
        phase_config = sample_request.phases[0]
        
        # Generate prompt
        prompt = orchestrator._create_phase_prompt(
            phase_config, sample_request, "claude", "test-session"
        )
        
        # Verify prompt contains expected elements
        assert "test-session" in prompt
        assert "test-project" in prompt
        assert "plan" in prompt
        assert "lead_architect" in prompt
        assert "Test orchestration prompt" in prompt
    
    async def test_finalization(self, orchestrator, sample_request, mock_agent_response):
        """Test orchestration finalization."""
        # Create mock result with phase results
        from argus_core.orchestrator import OrchestrationResult, PhaseResult
        
        result = OrchestrationResult(
            session_id="test",
            project_name="test",
            status=OrchestrationStatus.RUNNING,
            phase_results=[
                PhaseResult(
                    phase="plan",
                    status=OrchestrationStatus.COMPLETED,
                    agent_responses=[mock_agent_response],
                    consensus_score=0.8,
                    execution_time_ms=1000,
                    quality_gate_results={}
                )
            ],
            total_execution_time_ms=0,
            consensus_achieved=False,
            final_output=""
        )
        
        # Finalize
        finalized = await orchestrator._finalize_orchestration(result, sample_request)
        
        # Verify finalization
        assert finalized.status == OrchestrationStatus.COMPLETED
        assert finalized.consensus_achieved is True  # 0.8 > 0.75 threshold
        assert finalized.final_output == mock_agent_response.content

@pytest.mark.asyncio
class TestIntegration:
    """Integration tests for orchestrator components."""
    
    async def test_full_orchestration_flow(self):
        """Test complete orchestration flow with real components."""
        # This would be an integration test with real gateway and scheduler
        # For now, we'll skip to avoid external dependencies
        pytest.skip("Integration test requires real LLM providers")
    
    async def test_performance_benchmarks(self):
        """Test performance requirements."""
        # Performance test to ensure orchestration completes within time limits
        pytest.skip("Performance test requires benchmarking setup")

# Utility functions for testing

def create_mock_response(content: str, agent: str = "test-agent") -> AgentResponse:
    """Create a mock agent response."""
    return AgentResponse(
        content=content,
        agent_name=agent,
        provider=LLMProvider.CLAUDE,
        tokens_used=len(content.split()),
        response_time_ms=100,
        metadata={}
    )