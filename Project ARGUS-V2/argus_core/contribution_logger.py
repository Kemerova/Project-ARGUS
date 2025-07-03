"""
ARGUS-V2 Team Contribution Logger

Tracks and summarizes each team member's contributions to prompts and orchestrations.
Provides detailed analytics on agent performance, expertise areas, and collaboration patterns.
"""

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from collections import defaultdict
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)

class ContributionType(Enum):
    """Types of contributions team members can make."""
    ANALYSIS = "analysis"
    DESIGN = "design"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"
    VALIDATION = "validation"
    OPTIMIZATION = "optimization"
    SECURITY_ASSESSMENT = "security_assessment"
    PERFORMANCE_EVALUATION = "performance_evaluation"

@dataclass
class PromptContribution:
    """Represents a single team member's contribution to a prompt."""
    agent_name: str
    agent_role: str
    contribution_type: ContributionType
    content_summary: str
    key_insights: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    quality_score: float = 0.0
    response_time_ms: int = 0
    tokens_used: int = 0
    consensus_contribution: float = 0.0
    expertise_areas_applied: List[str] = field(default_factory=list)
    collaboration_notes: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class PromptSummary:
    """Summary of all contributions to a specific prompt."""
    prompt_id: str
    prompt_text: str
    prompt_category: str
    session_id: str
    phase_name: str
    contributions: List[PromptContribution] = field(default_factory=list)
    consensus_achieved: bool = False
    final_consensus_score: float = 0.0
    total_response_time_ms: int = 0
    total_tokens_used: int = 0
    outcome_quality: float = 0.0
    collaboration_effectiveness: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class TeamMemberProfile:
    """Profile tracking a team member's overall contributions."""
    agent_name: str
    agent_role: str
    total_contributions: int = 0
    contribution_types: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    expertise_areas: Dict[str, float] = field(default_factory=dict)
    avg_quality_score: float = 0.0
    avg_response_time_ms: float = 0.0
    total_tokens_used: int = 0
    successful_contributions: int = 0
    collaboration_score: float = 0.0
    key_strengths: List[str] = field(default_factory=list)
    improvement_areas: List[str] = field(default_factory=list)
    notable_contributions: List[str] = field(default_factory=list)
    last_active: datetime = field(default_factory=datetime.now)

class ContributionLogger:
    """Logs and analyzes team member contributions across all orchestrations."""
    
    def __init__(self, log_dir: Path = Path("contribution_logs")):
        self.log_dir = log_dir
        self.log_dir.mkdir(exist_ok=True)
        
        # Storage
        self.prompt_summaries: Dict[str, PromptSummary] = {}
        self.team_profiles: Dict[str, TeamMemberProfile] = {}
        self.session_logs: Dict[str, List[str]] = defaultdict(list)
        
        # Analytics
        self.collaboration_patterns: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.expertise_evolution: Dict[str, List[Dict]] = defaultdict(list)
        
        # Load existing data
        self.load_contribution_history()
    
    def log_prompt_contribution(
        self, 
        prompt_id: str,
        prompt_text: str,
        prompt_category: str,
        session_id: str,
        phase_name: str,
        agent_name: str,
        agent_role: str,
        contribution_type: ContributionType,
        response_content: str,
        quality_score: float = 0.0,
        response_time_ms: int = 0,
        tokens_used: int = 0,
        consensus_contribution: float = 0.0
    ) -> PromptContribution:
        """Log a team member's contribution to a specific prompt."""
        
        # Analyze the contribution content
        analysis = self._analyze_contribution_content(response_content, contribution_type)
        
        contribution = PromptContribution(
            agent_name=agent_name,
            agent_role=agent_role,
            contribution_type=contribution_type,
            content_summary=analysis['summary'],
            key_insights=analysis['insights'],
            recommendations=analysis['recommendations'],
            quality_score=quality_score,
            response_time_ms=response_time_ms,
            tokens_used=tokens_used,
            consensus_contribution=consensus_contribution,
            expertise_areas_applied=analysis['expertise_areas'],
            collaboration_notes=analysis['collaboration_notes']
        )
        
        # Add to prompt summary
        if prompt_id not in self.prompt_summaries:
            self.prompt_summaries[prompt_id] = PromptSummary(
                prompt_id=prompt_id,
                prompt_text=prompt_text[:200] + "..." if len(prompt_text) > 200 else prompt_text,
                prompt_category=prompt_category,
                session_id=session_id,
                phase_name=phase_name
            )
        
        self.prompt_summaries[prompt_id].contributions.append(contribution)
        self.session_logs[session_id].append(prompt_id)
        
        # Update team member profile
        self._update_team_profile(contribution)
        
        # Update collaboration patterns
        self._update_collaboration_patterns(prompt_id, agent_name)
        
        logger.info(
            "Contribution logged",
            prompt_id=prompt_id,
            agent=agent_name,
            type=contribution_type.value,
            quality=quality_score
        )
        
        return contribution
    
    def finalize_prompt_summary(
        self,
        prompt_id: str,
        consensus_achieved: bool,
        final_consensus_score: float,
        outcome_quality: float
    ):
        """Finalize the summary for a completed prompt."""
        if prompt_id not in self.prompt_summaries:
            logger.warning(f"Prompt {prompt_id} not found for finalization")
            return
        
        summary = self.prompt_summaries[prompt_id]
        summary.consensus_achieved = consensus_achieved
        summary.final_consensus_score = final_consensus_score
        summary.outcome_quality = outcome_quality
        
        # Calculate aggregate metrics
        summary.total_response_time_ms = sum(c.response_time_ms for c in summary.contributions)
        summary.total_tokens_used = sum(c.tokens_used for c in summary.contributions)
        
        # Calculate collaboration effectiveness
        summary.collaboration_effectiveness = self._calculate_collaboration_effectiveness(summary)
        
        # Save to disk
        self._save_prompt_summary(prompt_id)
        
        logger.info(
            "Prompt summary finalized",
            prompt_id=prompt_id,
            consensus=consensus_achieved,
            quality=outcome_quality,
            collaboration=summary.collaboration_effectiveness
        )
    
    def generate_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Generate a comprehensive summary for an orchestration session."""
        session_prompts = self.session_logs.get(session_id, [])
        
        if not session_prompts:
            return {"error": "No prompts found for session"}
        
        # Collect all contributions for this session
        all_contributions = []
        session_summaries = []
        
        for prompt_id in session_prompts:
            if prompt_id in self.prompt_summaries:
                summary = self.prompt_summaries[prompt_id]
                session_summaries.append(summary)
                all_contributions.extend(summary.contributions)
        
        # Analyze team performance
        team_performance = self._analyze_team_performance(all_contributions)
        
        # Collaboration analysis
        collaboration_analysis = self._analyze_collaboration_patterns(session_id, all_contributions)
        
        # Quality metrics
        quality_metrics = self._calculate_session_quality_metrics(session_summaries)
        
        # Generate insights
        session_insights = self._generate_session_insights(
            team_performance, collaboration_analysis, quality_metrics
        )
        
        summary = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "total_prompts": len(session_prompts),
            "total_contributions": len(all_contributions),
            "team_performance": team_performance,
            "collaboration_analysis": collaboration_analysis,
            "quality_metrics": quality_metrics,
            "session_insights": session_insights,
            "prompt_summaries": [asdict(s) for s in session_summaries]
        }
        
        # Save session summary
        session_file = self.log_dir / f"session_{session_id}_summary.json"
        with open(session_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        return summary
    
    def generate_team_member_report(self, agent_name: str) -> Dict[str, Any]:
        """Generate a detailed report for a specific team member."""
        if agent_name not in self.team_profiles:
            return {"error": f"No profile found for {agent_name}"}
        
        profile = self.team_profiles[agent_name]
        
        # Get recent contributions
        recent_contributions = self._get_recent_contributions(agent_name, days=30)
        
        # Performance trends
        performance_trends = self._analyze_performance_trends(agent_name)
        
        # Collaboration network
        collaboration_network = self._analyze_collaboration_network(agent_name)
        
        # Expertise evolution
        expertise_evolution = self.expertise_evolution.get(agent_name, [])
        
        report = {
            "agent_name": agent_name,
            "profile": asdict(profile),
            "recent_contributions": recent_contributions,
            "performance_trends": performance_trends,
            "collaboration_network": collaboration_network,
            "expertise_evolution": expertise_evolution,
            "recommendations": self._generate_member_recommendations(profile)
        }
        
        return report
    
    def _analyze_contribution_content(self, content: str, contribution_type: ContributionType) -> Dict[str, Any]:
        """Analyze contribution content to extract insights and metadata."""
        content_lower = content.lower()
        
        # Extract key insights based on content patterns
        insights = []
        recommendations = []
        expertise_areas = []
        collaboration_notes = ""
        
        # Pattern matching for insights
        if "architecture" in content_lower:
            insights.append("Architectural considerations identified")
            expertise_areas.append("architecture")
        
        if "security" in content_lower or "vulnerability" in content_lower:
            insights.append("Security implications analyzed")
            expertise_areas.append("security")
        
        if "performance" in content_lower or "optimization" in content_lower:
            insights.append("Performance optimization opportunities identified")
            expertise_areas.append("performance")
        
        if "scalability" in content_lower:
            insights.append("Scalability factors considered")
            expertise_areas.append("scalability")
        
        # Extract recommendations (look for action words)
        action_words = ["recommend", "suggest", "should", "must", "implement", "consider"]
        sentences = content.split('.')
        for sentence in sentences:
            if any(word in sentence.lower() for word in action_words):
                recommendations.append(sentence.strip())
        
        # Generate summary
        summary = self._generate_content_summary(content, contribution_type)
        
        # Detect collaboration indicators
        collaboration_indicators = ["building on", "agreeing with", "expanding", "complementing"]
        if any(indicator in content_lower for indicator in collaboration_indicators):
            collaboration_notes = "Shows collaborative build-up on team ideas"
        
        return {
            "summary": summary,
            "insights": insights[:3],  # Top 3 insights
            "recommendations": recommendations[:3],  # Top 3 recommendations
            "expertise_areas": expertise_areas,
            "collaboration_notes": collaboration_notes
        }
    
    def _generate_content_summary(self, content: str, contribution_type: ContributionType) -> str:
        """Generate a concise summary of the contribution content."""
        # Simple extractive summarization
        sentences = content.split('.')
        if len(sentences) <= 2:
            return content[:150] + "..." if len(content) > 150 else content
        
        # Take first and last sentences for summary
        summary_parts = [sentences[0].strip()]
        if len(sentences) > 1:
            summary_parts.append(sentences[-1].strip())
        
        summary = ". ".join(summary_parts)
        return summary[:200] + "..." if len(summary) > 200 else summary
    
    def _update_team_profile(self, contribution: PromptContribution):
        """Update team member profile with new contribution data."""
        agent_name = contribution.agent_name
        
        if agent_name not in self.team_profiles:
            self.team_profiles[agent_name] = TeamMemberProfile(
                agent_name=agent_name,
                agent_role=contribution.agent_role
            )
        
        profile = self.team_profiles[agent_name]
        profile.total_contributions += 1
        profile.contribution_types[contribution.contribution_type.value] += 1
        profile.total_tokens_used += contribution.tokens_used
        profile.last_active = contribution.timestamp
        
        # Update averages
        profile.avg_quality_score = self._update_running_average(
            profile.avg_quality_score, contribution.quality_score, profile.total_contributions
        )
        
        profile.avg_response_time_ms = self._update_running_average(
            profile.avg_response_time_ms, contribution.response_time_ms, profile.total_contributions
        )
        
        # Update expertise areas
        for area in contribution.expertise_areas_applied:
            if area not in profile.expertise_areas:
                profile.expertise_areas[area] = 0.1
            profile.expertise_areas[area] = min(1.0, profile.expertise_areas[area] + 0.1)
        
        # Track successful contributions
        if contribution.quality_score >= 0.8:
            profile.successful_contributions += 1
        
        # Update collaboration score based on consensus contribution
        if contribution.consensus_contribution > 0:
            profile.collaboration_score = self._update_running_average(
                profile.collaboration_score, contribution.consensus_contribution, profile.total_contributions
            )
    
    def _update_running_average(self, current_avg: float, new_value: float, count: int) -> float:
        """Update a running average with a new value."""
        if count <= 1:
            return new_value
        return ((current_avg * (count - 1)) + new_value) / count
    
    def _update_collaboration_patterns(self, prompt_id: str, agent_name: str):
        """Update collaboration patterns between team members."""
        if prompt_id not in self.prompt_summaries:
            return
        
        summary = self.prompt_summaries[prompt_id]
        other_agents = [c.agent_name for c in summary.contributions if c.agent_name != agent_name]
        
        for other_agent in other_agents:
            self.collaboration_patterns[agent_name][other_agent] += 1
    
    def _calculate_collaboration_effectiveness(self, summary: PromptSummary) -> float:
        """Calculate how effectively the team collaborated on a prompt."""
        if len(summary.contributions) <= 1:
            return 1.0  # Single contributor, perfect by default
        
        # Factors for collaboration effectiveness
        factors = []
        
        # Diversity of contribution types
        contrib_types = set(c.contribution_type for c in summary.contributions)
        type_diversity = len(contrib_types) / len(ContributionType)
        factors.append(type_diversity)
        
        # Quality consistency
        quality_scores = [c.quality_score for c in summary.contributions if c.quality_score > 0]
        if quality_scores:
            quality_std = sum(abs(q - sum(quality_scores)/len(quality_scores)) for q in quality_scores) / len(quality_scores)
            quality_consistency = 1.0 - min(quality_std, 1.0)
            factors.append(quality_consistency)
        
        # Response time balance
        response_times = [c.response_time_ms for c in summary.contributions if c.response_time_ms > 0]
        if response_times:
            time_balance = 1.0 - (max(response_times) - min(response_times)) / max(response_times, 1)
            factors.append(max(0.0, time_balance))
        
        # Consensus contribution balance
        consensus_contribs = [c.consensus_contribution for c in summary.contributions if c.consensus_contribution > 0]
        if consensus_contribs:
            consensus_balance = 1.0 - (max(consensus_contribs) - min(consensus_contribs)) / max(consensus_contribs, 1)
            factors.append(max(0.0, consensus_balance))
        
        return sum(factors) / len(factors) if factors else 0.5
    
    def _analyze_team_performance(self, contributions: List[PromptContribution]) -> Dict[str, Any]:
        """Analyze overall team performance for a session."""
        if not contributions:
            return {}
        
        # Group by agent
        agent_contributions = defaultdict(list)
        for contrib in contributions:
            agent_contributions[contrib.agent_name].append(contrib)
        
        team_stats = {}
        for agent_name, agent_contribs in agent_contributions.items():
            avg_quality = sum(c.quality_score for c in agent_contribs) / len(agent_contribs)
            total_tokens = sum(c.tokens_used for c in agent_contribs)
            avg_response_time = sum(c.response_time_ms for c in agent_contribs) / len(agent_contribs)
            
            contribution_types = defaultdict(int)
            for contrib in agent_contribs:
                contribution_types[contrib.contribution_type.value] += 1
            
            team_stats[agent_name] = {
                "total_contributions": len(agent_contribs),
                "avg_quality_score": round(avg_quality, 3),
                "total_tokens_used": total_tokens,
                "avg_response_time_ms": round(avg_response_time, 1),
                "contribution_types": dict(contribution_types),
                "primary_expertise": self._identify_primary_expertise(agent_contribs)
            }
        
        return team_stats
    
    def _identify_primary_expertise(self, contributions: List[PromptContribution]) -> List[str]:
        """Identify the primary expertise areas for an agent based on contributions."""
        expertise_count = defaultdict(int)
        for contrib in contributions:
            for area in contrib.expertise_areas_applied:
                expertise_count[area] += 1
        
        # Return top 3 expertise areas
        sorted_expertise = sorted(expertise_count.items(), key=lambda x: x[1], reverse=True)
        return [area for area, count in sorted_expertise[:3]]
    
    def _analyze_collaboration_patterns(self, session_id: str, contributions: List[PromptContribution]) -> Dict[str, Any]:
        """Analyze collaboration patterns for a session."""
        # Build collaboration matrix
        agents = set(c.agent_name for c in contributions)
        collaboration_matrix = {agent: {other: 0 for other in agents} for agent in agents}
        
        # Count collaborations (prompts worked on together)
        prompt_agents = defaultdict(set)
        for contrib in contributions:
            prompt_id = f"{session_id}_{contrib.timestamp.strftime('%H%M%S')}"
            prompt_agents[prompt_id].add(contrib.agent_name)
        
        for prompt_id, prompt_agent_set in prompt_agents.items():
            agent_list = list(prompt_agent_set)
            for i, agent1 in enumerate(agent_list):
                for agent2 in agent_list[i+1:]:
                    collaboration_matrix[agent1][agent2] += 1
                    collaboration_matrix[agent2][agent1] += 1
        
        # Calculate collaboration metrics
        total_collaborations = sum(sum(row.values()) for row in collaboration_matrix.values()) / 2
        most_collaborative_pair = None
        max_collaborations = 0
        
        for agent1 in agents:
            for agent2 in agents:
                if agent1 != agent2 and collaboration_matrix[agent1][agent2] > max_collaborations:
                    max_collaborations = collaboration_matrix[agent1][agent2]
                    most_collaborative_pair = (agent1, agent2)
        
        return {
            "total_collaborations": total_collaborations,
            "collaboration_matrix": collaboration_matrix,
            "most_collaborative_pair": most_collaborative_pair,
            "avg_collaborations_per_agent": total_collaborations / len(agents) if agents else 0
        }
    
    def _calculate_session_quality_metrics(self, summaries: List[PromptSummary]) -> Dict[str, Any]:
        """Calculate quality metrics for a session."""
        if not summaries:
            return {}
        
        # Consensus metrics
        consensus_scores = [s.final_consensus_score for s in summaries if s.final_consensus_score > 0]
        consensus_achieved_count = sum(1 for s in summaries if s.consensus_achieved)
        
        # Quality metrics
        outcome_qualities = [s.outcome_quality for s in summaries if s.outcome_quality > 0]
        collaboration_scores = [s.collaboration_effectiveness for s in summaries]
        
        # Response time metrics
        total_response_times = [s.total_response_time_ms for s in summaries if s.total_response_time_ms > 0]
        
        return {
            "avg_consensus_score": round(sum(consensus_scores) / len(consensus_scores), 3) if consensus_scores else 0,
            "consensus_achievement_rate": round(consensus_achieved_count / len(summaries), 3),
            "avg_outcome_quality": round(sum(outcome_qualities) / len(outcome_qualities), 3) if outcome_qualities else 0,
            "avg_collaboration_effectiveness": round(sum(collaboration_scores) / len(collaboration_scores), 3),
            "avg_response_time_ms": round(sum(total_response_times) / len(total_response_times), 1) if total_response_times else 0,
            "total_prompts_processed": len(summaries)
        }
    
    def _generate_session_insights(self, team_performance, collaboration_analysis, quality_metrics) -> List[str]:
        """Generate insights about the session."""
        insights = []
        
        # Performance insights
        if team_performance:
            best_performer = max(team_performance.items(), key=lambda x: x[1]['avg_quality_score'])
            insights.append(f"Best performing agent: {best_performer[0]} (avg quality: {best_performer[1]['avg_quality_score']:.2f})")
            
            fastest_responder = min(team_performance.items(), key=lambda x: x[1]['avg_response_time_ms'])
            insights.append(f"Fastest responder: {fastest_responder[0]} ({fastest_responder[1]['avg_response_time_ms']:.1f}ms avg)")
        
        # Collaboration insights
        if collaboration_analysis.get('most_collaborative_pair'):
            pair = collaboration_analysis['most_collaborative_pair']
            insights.append(f"Most collaborative pair: {pair[0]} and {pair[1]}")
        
        # Quality insights
        if quality_metrics.get('consensus_achievement_rate', 0) >= 0.8:
            insights.append("High consensus achievement rate indicates strong team alignment")
        elif quality_metrics.get('consensus_achievement_rate', 0) < 0.5:
            insights.append("Low consensus rate suggests need for better coordination")
        
        if quality_metrics.get('avg_collaboration_effectiveness', 0) >= 0.8:
            insights.append("Excellent collaboration effectiveness across the team")
        
        return insights
    
    def _get_recent_contributions(self, agent_name: str, days: int = 30) -> List[Dict]:
        """Get recent contributions for an agent."""
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_contribs = []
        
        for summary in self.prompt_summaries.values():
            for contrib in summary.contributions:
                if contrib.agent_name == agent_name and contrib.timestamp >= cutoff_date:
                    recent_contribs.append({
                        "prompt_id": summary.prompt_id,
                        "contribution_type": contrib.contribution_type.value,
                        "quality_score": contrib.quality_score,
                        "timestamp": contrib.timestamp.isoformat()
                    })
        
        return sorted(recent_contribs, key=lambda x: x['timestamp'], reverse=True)
    
    def _analyze_performance_trends(self, agent_name: str) -> Dict[str, Any]:
        """Analyze performance trends for an agent."""
        agent_contribs = []
        for summary in self.prompt_summaries.values():
            for contrib in summary.contributions:
                if contrib.agent_name == agent_name:
                    agent_contribs.append(contrib)
        
        if len(agent_contribs) < 2:
            return {"trend": "insufficient_data"}
        
        # Sort by timestamp
        agent_contribs.sort(key=lambda x: x.timestamp)
        
        # Calculate trends
        recent_half = agent_contribs[len(agent_contribs)//2:]
        early_half = agent_contribs[:len(agent_contribs)//2]
        
        recent_avg_quality = sum(c.quality_score for c in recent_half) / len(recent_half)
        early_avg_quality = sum(c.quality_score for c in early_half) / len(early_half)
        
        quality_trend = "improving" if recent_avg_quality > early_avg_quality else "declining"
        
        return {
            "quality_trend": quality_trend,
            "quality_improvement": round(recent_avg_quality - early_avg_quality, 3),
            "total_contributions_analyzed": len(agent_contribs)
        }
    
    def _analyze_collaboration_network(self, agent_name: str) -> Dict[str, Any]:
        """Analyze collaboration network for an agent."""
        collaborators = defaultdict(int)
        
        for prompt_summary in self.prompt_summaries.values():
            agent_in_prompt = any(c.agent_name == agent_name for c in prompt_summary.contributions)
            if agent_in_prompt:
                for contrib in prompt_summary.contributions:
                    if contrib.agent_name != agent_name:
                        collaborators[contrib.agent_name] += 1
        
        return {
            "total_collaborators": len(collaborators),
            "collaboration_frequency": dict(collaborators),
            "most_frequent_collaborator": max(collaborators.items(), key=lambda x: x[1])[0] if collaborators else None
        }
    
    def _generate_member_recommendations(self, profile: TeamMemberProfile) -> List[str]:
        """Generate recommendations for team member improvement."""
        recommendations = []
        
        # Quality recommendations
        if profile.avg_quality_score < 0.7:
            recommendations.append("Focus on improving response quality through more thorough analysis")
        
        # Response time recommendations
        if profile.avg_response_time_ms > 2000:
            recommendations.append("Work on reducing response time while maintaining quality")
        
        # Collaboration recommendations
        if profile.collaboration_score < 0.6:
            recommendations.append("Increase collaboration by building on other team members' ideas")
        
        # Expertise recommendations
        expertise_count = len(profile.expertise_areas)
        if expertise_count < 2:
            recommendations.append("Develop expertise in additional areas for more versatility")
        elif expertise_count > 5:
            recommendations.append("Focus on deepening expertise in core areas")
        
        return recommendations
    
    def load_contribution_history(self):
        """Load existing contribution logs from disk."""
        try:
            # Load team profiles
            profiles_file = self.log_dir / "team_profiles.json"
            if profiles_file.exists():
                with open(profiles_file) as f:
                    profiles_data = json.load(f)
                    for name, data in profiles_data.items():
                        self.team_profiles[name] = TeamMemberProfile(**data)
            
            logger.info(f"Loaded {len(self.team_profiles)} team profiles")
            
        except Exception as e:
            logger.warning(f"Could not load contribution history: {e}")
    
    def save_contribution_data(self):
        """Save contribution data to disk."""
        try:
            # Save team profiles
            profiles_file = self.log_dir / "team_profiles.json"
            profiles_data = {name: asdict(profile) for name, profile in self.team_profiles.items()}
            with open(profiles_file, 'w') as f:
                json.dump(profiles_data, f, indent=2, default=str)
            
            logger.info("Contribution data saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save contribution data: {e}")
    
    def _save_prompt_summary(self, prompt_id: str):
        """Save individual prompt summary to disk."""
        if prompt_id not in self.prompt_summaries:
            return
        
        summary_file = self.log_dir / f"prompt_{prompt_id}_summary.json"
        summary_data = asdict(self.prompt_summaries[prompt_id])
        
        with open(summary_file, 'w') as f:
            json.dump(summary_data, f, indent=2, default=str)

# Global contribution logger instance
contribution_logger = ContributionLogger()

# Integration functions for easy use in orchestrator
def log_agent_contribution(
    prompt_id: str,
    prompt_text: str,
    session_id: str,
    phase_name: str,
    agent_name: str,
    agent_role: str,
    contribution_type: str,
    response_content: str,
    quality_score: float = 0.0,
    response_time_ms: int = 0,
    tokens_used: int = 0,
    consensus_contribution: float = 0.0
):
    """Easy integration function for logging agent contributions."""
    contrib_type = ContributionType(contribution_type)
    prompt_category = _determine_prompt_category(prompt_text, phase_name)
    
    return contribution_logger.log_prompt_contribution(
        prompt_id=prompt_id,
        prompt_text=prompt_text,
        prompt_category=prompt_category,
        session_id=session_id,
        phase_name=phase_name,
        agent_name=agent_name,
        agent_role=agent_role,
        contribution_type=contrib_type,
        response_content=response_content,
        quality_score=quality_score,
        response_time_ms=response_time_ms,
        tokens_used=tokens_used,
        consensus_contribution=consensus_contribution
    )

def finalize_prompt_log(prompt_id: str, consensus_achieved: bool, consensus_score: float, outcome_quality: float):
    """Finalize a prompt's contribution log."""
    contribution_logger.finalize_prompt_summary(
        prompt_id=prompt_id,
        consensus_achieved=consensus_achieved,
        final_consensus_score=consensus_score,
        outcome_quality=outcome_quality
    )

def generate_session_contribution_report(session_id: str) -> Dict[str, Any]:
    """Generate a comprehensive contribution report for a session."""
    return contribution_logger.generate_session_summary(session_id)

def generate_team_member_contribution_report(agent_name: str) -> Dict[str, Any]:
    """Generate a detailed contribution report for a team member."""
    return contribution_logger.generate_team_member_report(agent_name)

def _determine_prompt_category(prompt_text: str, phase_name: str) -> str:
    """Determine the category of a prompt based on content and phase."""
    prompt_lower = prompt_text.lower()
    
    if "architecture" in prompt_lower or "design" in prompt_lower:
        return "architectural_design"
    elif "security" in prompt_lower or "vulnerability" in prompt_lower:
        return "security_analysis"
    elif "performance" in prompt_lower or "optimization" in prompt_lower:
        return "performance_optimization"
    elif "test" in prompt_lower or "quality" in prompt_lower:
        return "quality_assurance"
    elif "implement" in prompt_lower or "code" in prompt_lower:
        return "implementation"
    elif phase_name:
        return f"phase_{phase_name}"
    else:
        return "general"