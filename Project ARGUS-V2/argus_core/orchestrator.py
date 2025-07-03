"""
Orchestrator: Core coordination engine for ARGUS-V2

Simplified from V1's complex phase system to a streamlined
Plan → Execute → Validate workflow with async-first design.
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Awaitable
from uuid import uuid4

import structlog

from .gateway import AgentGateway, AgentRequest, AgentResponse, AgentRole
from .scheduler import AsyncScheduler
from .hooks import HookManager, HookType
from .monitoring import (
    track_orchestration_start, 
    track_orchestration_end, 
    track_phase_completion
)
from .contribution_logger import (
    generate_session_contribution_report,
    finalize_prompt_log
)

logger = structlog.get_logger(__name__)

class PhaseType(Enum):
    """Simplified phase types for V2."""
    PLAN = "plan"
    EXECUTE = "execute" 
    VALIDATE = "validate"

class OrchestrationStatus(Enum):
    """Status of orchestration execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class PhaseConfig:
    """Configuration for a single phase."""
    name: str
    type: PhaseType
    timeout: int = 300  # seconds
    parallel: bool = False
    consensus_threshold: float = 0.75
    required_agents: List[str] = field(default_factory=list)
    quality_gates: List[str] = field(default_factory=list)
    
@dataclass
class PhaseResult:
    """Result of phase execution."""
    phase: str
    status: OrchestrationStatus
    agent_responses: List[AgentResponse]
    consensus_score: float
    execution_time_ms: int
    quality_gate_results: Dict[str, bool]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class OrchestrationRequest:
    """Request for orchestration execution."""
    project_name: str
    prompt: str
    phases: List[PhaseConfig]
    context: Dict[str, Any] = field(default_factory=dict)
    max_total_time: int = 1800  # 30 minutes default

@dataclass
class OrchestrationResult:
    """Final result of orchestration."""
    session_id: str
    project_name: str
    status: OrchestrationStatus
    phase_results: List[PhaseResult]
    total_execution_time_ms: int
    consensus_achieved: bool
    final_output: str
    metadata: Dict[str, Any] = field(default_factory=dict)

class Orchestrator:
    """
    Core orchestration engine for ARGUS-V2.
    
    Manages the simplified Plan → Execute → Validate workflow
    with async execution, consensus tracking, and quality gates.
    """
    
    def __init__(self, gateway: AgentGateway, scheduler: AsyncScheduler):
        self.gateway = gateway
        self.scheduler = scheduler
        self.hook_manager = HookManager()
        self.active_sessions: Dict[str, OrchestrationResult] = {}
        
    async def orchestrate(self, request: OrchestrationRequest) -> OrchestrationResult:
        """
        Execute full orchestration workflow.
        
        Coordinates agents through Plan → Execute → Validate phases
        with consensus tracking and quality gates.
        """
        session_id = str(uuid4())
        start_time = time.time()
        
        logger.info(
            "Starting orchestration",
            session_id=session_id,
            project=request.project_name,
            phases=[p.name for p in request.phases]
        )
        
        # Track orchestration start
        track_orchestration_start(session_id, request.project_name, len(request.phases))
        
        # Initialize result
        result = OrchestrationResult(
            session_id=session_id,
            project_name=request.project_name,
            status=OrchestrationStatus.RUNNING,
            phase_results=[],
            total_execution_time_ms=0,
            consensus_achieved=False,
            final_output="",
            metadata={"start_time": start_time}
        )
        
        self.active_sessions[session_id] = result
        
        try:
            # Execute pre-orchestration hooks
            await self.hook_manager.execute_hooks(
                HookType.PRE_ORCHESTRATION,
                {"request": request, "session_id": session_id}
            )
            
            # Execute each phase
            for phase_config in request.phases:
                phase_result = await self._execute_phase(phase_config, request, session_id)
                result.phase_results.append(phase_result)
                
                # Check if phase failed and should stop
                if phase_result.status == OrchestrationStatus.FAILED:
                    logger.error(
                        "Phase failed, stopping orchestration",
                        session_id=session_id,
                        phase=phase_config.name
                    )
                    result.status = OrchestrationStatus.FAILED
                    break
            
            # Calculate final results
            if result.status == OrchestrationStatus.RUNNING:
                result = await self._finalize_orchestration(result, request)
                
        except Exception as e:
            logger.error(
                "Orchestration failed with exception",
                session_id=session_id,
                error=str(e)
            )
            result.status = OrchestrationStatus.FAILED
            result.metadata["error"] = str(e)
            
        finally:
            # Calculate total execution time
            end_time = time.time()
            result.total_execution_time_ms = int((end_time - start_time) * 1000)
            
            # Execute post-orchestration hooks
            await self.hook_manager.execute_hooks(
                HookType.POST_ORCHESTRATION,
                {"result": result, "session_id": session_id}
            )
            
            # Track orchestration end
            track_orchestration_end(session_id, result.status.value)
            
            # Generate contribution report for the session
            try:
                contribution_report = generate_session_contribution_report(session_id)
                result.metadata["contribution_report"] = contribution_report
                logger.info(
                    "Contribution report generated",
                    session_id=session_id,
                    total_contributions=contribution_report.get("total_contributions", 0)
                )
            except Exception as e:
                logger.warning(f"Failed to generate contribution report: {e}")
            
            logger.info(
                "Orchestration completed",
                session_id=session_id,
                status=result.status.value,
                execution_time_ms=result.total_execution_time_ms,
                consensus=result.consensus_achieved
            )
            
        return result
    
    async def _execute_phase(
        self,
        phase_config: PhaseConfig,
        request: OrchestrationRequest,
        session_id: str
    ) -> PhaseResult:
        """Execute a single orchestration phase."""
        start_time = time.time()
        
        logger.info(
            "Executing phase",
            session_id=session_id,
            phase=phase_config.name,
            type=phase_config.type.value
        )
        
        # Execute pre-phase hooks
        await self.hook_manager.execute_hooks(
            HookType.PRE_PHASE,
            {
                "phase_config": phase_config,
                "request": request,
                "session_id": session_id
            }
        )
        
        try:
            # Create agent requests
            agent_requests = await self._create_agent_requests(
                phase_config, request, session_id
            )
            
            # Execute agent calls
            if phase_config.parallel:
                agent_responses = await self.gateway.call_parallel(agent_requests)
            else:
                agent_responses = []
                for agent_request in agent_requests:
                    response = await self.gateway.call_agent(agent_request)
                    agent_responses.append(response)
            
            # Calculate consensus
            consensus_score = self._calculate_consensus(agent_responses)
            
            # Execute quality gates
            quality_gate_results = await self._execute_quality_gates(
                phase_config, agent_responses, request
            )
            
            # Determine phase status
            status = OrchestrationStatus.COMPLETED
            if consensus_score < phase_config.consensus_threshold:
                status = OrchestrationStatus.FAILED
                logger.warning(
                    "Phase failed consensus threshold",
                    phase=phase_config.name,
                    consensus=consensus_score,
                    threshold=phase_config.consensus_threshold
                )
            
            if not all(quality_gate_results.values()):
                status = OrchestrationStatus.FAILED
                logger.warning(
                    "Phase failed quality gates",
                    phase=phase_config.name,
                    gates=quality_gate_results
                )
            
        except Exception as e:
            logger.error(
                "Phase execution failed",
                session_id=session_id,
                phase=phase_config.name,
                error=str(e)
            )
            status = OrchestrationStatus.FAILED
            agent_responses = []
            consensus_score = 0.0
            quality_gate_results = {}
        
        # Calculate execution time
        end_time = time.time()
        execution_time_ms = int((end_time - start_time) * 1000)
        
        # Track phase completion
        track_phase_completion(session_id, phase_config.name, consensus_score)
        
        result = PhaseResult(
            phase=phase_config.name,
            status=status,
            agent_responses=agent_responses,
            consensus_score=consensus_score,
            execution_time_ms=execution_time_ms,
            quality_gate_results=quality_gate_results,
            metadata={
                "type": phase_config.type.value,
                "parallel": phase_config.parallel,
                "agent_count": len(agent_requests)
            }
        )
        
        # Execute post-phase hooks
        await self.hook_manager.execute_hooks(
            HookType.POST_PHASE,
            {
                "phase_result": result,
                "phase_config": phase_config,
                "session_id": session_id
            }
        )
        
        return result
    
    async def _create_agent_requests(
        self,
        phase_config: PhaseConfig,
        request: OrchestrationRequest,
        session_id: str
    ) -> List[AgentRequest]:
        """Create agent requests for the phase."""
        agent_configs = self.gateway.get_agent_configs()
        agent_requests = []
        
        # Use required agents if specified, otherwise use all available
        target_agents = phase_config.required_agents or list(agent_configs.keys())
        
        for agent_name in target_agents:
            if agent_name not in agent_configs:
                logger.warning(
                    "Required agent not available",
                    agent=agent_name,
                    phase=phase_config.name
                )
                continue
                
            # Create phase-specific prompt
            phase_prompt = self._create_phase_prompt(
                phase_config, request, agent_name, session_id
            )
            
            agent_request = AgentRequest(
                prompt=phase_prompt,
                context=request.context,
                agent_name=agent_name,
                phase=phase_config.name
            )
            
            agent_requests.append(agent_request)
        
        return agent_requests
    
    def _create_phase_prompt(
        self,
        phase_config: PhaseConfig,
        request: OrchestrationRequest,
        agent_name: str,
        session_id: str
    ) -> str:
        """Create a phase-specific prompt for the agent."""
        agent_configs = self.gateway.get_agent_configs()
        agent_config = agent_configs[agent_name]
        
        # Get previous phase results for context
        previous_context = self._get_previous_phase_context(session_id)
        
        base_prompt = f"""
ARGUS-V2 Orchestration Session: {session_id}
Project: {request.project_name}
Phase: {phase_config.name} ({phase_config.type.value})
Your Role: {agent_config.role.value}

TASK:
{request.prompt}

CONTEXT:
{request.context}

PREVIOUS PHASES:
{previous_context}

INSTRUCTIONS:
Please provide your analysis and recommendations for this {phase_config.type.value} phase.
Focus on your expertise as {agent_config.role.value}.
Be specific, actionable, and collaborative.

EXPECTED OUTPUT:
- Clear analysis based on your role
- Specific recommendations
- Any concerns or risks identified
- Collaboration points with other agents
"""
        
        return base_prompt.strip()
    
    def _get_previous_phase_context(self, session_id: str) -> str:
        """Get context from previous phases."""
        if session_id not in self.active_sessions:
            return "No previous phases."
            
        result = self.active_sessions[session_id]
        if not result.phase_results:
            return "No previous phases."
            
        context_parts = []
        for phase_result in result.phase_results:
            context_parts.append(f"Phase {phase_result.phase}: {phase_result.status.value}")
            if phase_result.agent_responses:
                context_parts.append(f"  Consensus: {phase_result.consensus_score:.2f}")
                context_parts.append(f"  Agents: {len(phase_result.agent_responses)}")
        
        return "\n".join(context_parts)
    
    def _calculate_consensus(self, responses: List[AgentResponse]) -> float:
        """Calculate consensus score from agent responses."""
        if not responses:
            return 0.0
            
        # Simple consensus based on response length similarity
        # In production, this would use more sophisticated NLP analysis
        lengths = [len(response.content) for response in responses]
        if not lengths:
            return 0.0
            
        avg_length = sum(lengths) / len(lengths)
        variance = sum((length - avg_length) ** 2 for length in lengths) / len(lengths)
        
        # Convert variance to consensus score (lower variance = higher consensus)
        max_variance = avg_length * 0.5  # Arbitrary threshold
        consensus = max(0.0, 1.0 - (variance / max_variance))
        
        return min(1.0, consensus)
    
    async def _execute_quality_gates(
        self,
        phase_config: PhaseConfig,
        responses: List[AgentResponse],
        request: OrchestrationRequest
    ) -> Dict[str, bool]:
        """Execute quality gates for the phase."""
        results = {}
        
        for gate_name in phase_config.quality_gates:
            try:
                # Execute quality gate hook
                gate_result = await self.hook_manager.execute_hooks(
                    HookType.QUALITY_GATE,
                    {
                        "gate_name": gate_name,
                        "phase_config": phase_config,
                        "responses": responses,
                        "request": request
                    }
                )
                
                # Assume quality gate passes if no hooks or all hooks pass
                results[gate_name] = gate_result.get("passed", True)
                
            except Exception as e:
                logger.error(
                    "Quality gate failed with exception",
                    gate=gate_name,
                    error=str(e)
                )
                results[gate_name] = False
        
        return results
    
    async def _finalize_orchestration(
        self,
        result: OrchestrationResult,
        request: OrchestrationRequest
    ) -> OrchestrationResult:
        """Finalize orchestration results."""
        # Calculate overall consensus
        if result.phase_results:
            consensus_scores = [pr.consensus_score for pr in result.phase_results]
            result.consensus_achieved = sum(consensus_scores) / len(consensus_scores) >= 0.75
        
        # Generate final output from last phase
        if result.phase_results and result.phase_results[-1].agent_responses:
            last_responses = result.phase_results[-1].agent_responses
            # Simple combination - in production would be more sophisticated
            result.final_output = "\n\n".join(r.content for r in last_responses)
        
        # Set final status
        if all(pr.status == OrchestrationStatus.COMPLETED for pr in result.phase_results):
            result.status = OrchestrationStatus.COMPLETED
        else:
            result.status = OrchestrationStatus.FAILED
            
        return result
    
    def get_session_status(self, session_id: str) -> Optional[OrchestrationResult]:
        """Get current status of an orchestration session."""
        return self.active_sessions.get(session_id)
    
    async def cancel_session(self, session_id: str) -> bool:
        """Cancel an active orchestration session."""
        if session_id not in self.active_sessions:
            return False
            
        result = self.active_sessions[session_id]
        result.status = OrchestrationStatus.CANCELLED
        
        logger.info("Cancelled orchestration session", session_id=session_id)
        return True