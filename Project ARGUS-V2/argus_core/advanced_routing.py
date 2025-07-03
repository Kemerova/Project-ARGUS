"""
Advanced Agent Routing System for ARGUS-V2
"""

from typing import List, Dict, Tuple
from dataclasses import dataclass
from .intelligence import learning_engine

@dataclass
class RoutingDecision:
    """Represents an agent routing decision."""
    agent_name: str
    confidence_score: float
    reasoning: str

class AdvancedRouter:
    """Routes tasks to optimal agents based on expertise and context."""
    
    def __init__(self):
        self.learning_engine = learning_engine
    
    async def route_task(self, task_description: str, project_type: str, 
                        available_agents: List[str]) -> List[RoutingDecision]:
        """Route a task to the best available agents."""
        
        # Get agent recommendations from learning engine
        recommendations = self.learning_engine.recommend_agents_for_task(
            project_type, task_description
        )
        
        # Filter by available agents and create routing decisions
        routing_decisions = []
        
        for agent_name, score in recommendations:
            if agent_name in available_agents:
                profile = self.learning_engine.get_agent_profile(agent_name)
                
                # Calculate reasoning
                reasoning = self._generate_routing_reasoning(
                    profile, task_description, score
                )
                
                routing_decisions.append(RoutingDecision(
                    agent_name=agent_name,
                    confidence_score=score,
                    reasoning=reasoning
                ))
        
        # Sort by confidence score
        routing_decisions.sort(key=lambda x: x.confidence_score, reverse=True)
        
        return routing_decisions[:3]  # Return top 3 candidates
    
    def _generate_routing_reasoning(self, profile, task_description: str, 
                                  score: float) -> str:
        """Generate human-readable reasoning for routing decision."""
        reasons = []
        
        # Check expertise areas
        if hasattr(profile, 'expertise_areas'):
            high_expertise = [area for area, level in profile.expertise_areas.items() 
                            if level > 0.8]
            if high_expertise:
                reasons.append(f"High expertise in: {', '.join(high_expertise)}")
        
        # Check success rate
        if hasattr(profile, 'success_rate') and profile.success_rate > 0.9:
            reasons.append(f"Excellent success rate ({profile.success_rate:.1%})")
        
        # Check response time
        if hasattr(profile, 'avg_response_time') and profile.avg_response_time < 1000:
            reasons.append("Fast response time")
        
        # Task-specific matching
        task_lower = task_description.lower()
        if "security" in task_lower and "security" in profile.strengths:
            reasons.append("Security specialization match")
        elif "architecture" in task_lower and "architecture" in profile.strengths:
            reasons.append("Architecture specialization match")
        elif "performance" in task_lower and "performance" in profile.strengths:
            reasons.append("Performance specialization match")
        
        return "; ".join(reasons) if reasons else f"Overall suitability score: {score:.2f}"

# Global router instance
advanced_router = AdvancedRouter()
