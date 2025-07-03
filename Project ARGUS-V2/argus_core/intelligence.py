"""
Enhanced Agent Intelligence for ARGUS-V2

Implements context-aware prompt optimization, response caching,
and learning from previous orchestrations.
"""

import asyncio
import hashlib
import json
import pickle
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import sqlite3

import structlog
from argus_core.gateway import AgentRequest, AgentResponse

logger = structlog.get_logger(__name__)

@dataclass
class PromptPattern:
    """Pattern for prompt optimization."""
    pattern_type: str
    keywords: List[str]
    template: str
    success_rate: float = 0.0
    usage_count: int = 0

@dataclass
class OrchestrationHistory:
    """Historical data from orchestration sessions."""
    session_id: str
    project_name: str
    project_type: str
    success: bool
    duration_seconds: float
    agent_responses: List[Dict[str, Any]]
    consensus_scores: List[float]
    final_output_quality: float
    timestamp: datetime

@dataclass
class AgentProfile:
    """Performance profile for an agent."""
    agent_name: str
    provider: str
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    avg_response_time: float = 0.0
    success_rate: float = 1.0
    preferred_prompt_styles: List[str] = field(default_factory=list)
    expertise_areas: Dict[str, float] = field(default_factory=dict)

class ResponseCache:
    """Intelligent caching system for agent responses."""
    
    def __init__(self, cache_dir: Path = Path("cache")):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_db = cache_dir / "response_cache.db"
        self.init_db()
    
    def init_db(self):
        """Initialize the cache database."""
        conn = sqlite3.connect(self.cache_db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_entries (
                key TEXT PRIMARY KEY,
                agent_name TEXT,
                provider TEXT,
                prompt_hash TEXT,
                response_data BLOB,
                created_at TIMESTAMP,
                accessed_at TIMESTAMP,
                access_count INTEGER DEFAULT 1,
                relevance_score REAL DEFAULT 1.0
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_prompt_hash ON cache_entries(prompt_hash)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_provider ON cache_entries(agent_name, provider)
        """)
        conn.commit()
        conn.close()
    
    def _hash_prompt(self, prompt: str, context: Dict[str, Any]) -> str:
        """Create a hash for prompt + context."""
        content = f"{prompt}:{json.dumps(context, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    async def get_cached_response(self, request: AgentRequest) -> Optional[AgentResponse]:
        """Get cached response if available and relevant."""
        prompt_hash = self._hash_prompt(request.prompt, request.context)
        
        conn = sqlite3.connect(self.cache_db)
        cursor = conn.execute("""
            SELECT response_data, relevance_score, created_at 
            FROM cache_entries 
            WHERE agent_name = ? AND prompt_hash = ?
            ORDER BY relevance_score DESC, created_at DESC
            LIMIT 1
        """, (request.agent_name, prompt_hash))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            response_data, relevance_score, created_at = row
            
            # Check if cache entry is still relevant (within 24 hours and high relevance)
            cache_age_hours = (datetime.now() - datetime.fromisoformat(created_at)).total_seconds() / 3600
            
            if cache_age_hours < 24 and relevance_score > 0.8:
                # Update access count
                self._update_access_count(prompt_hash, request.agent_name)
                
                # Deserialize and return cached response
                response = pickle.loads(response_data)
                logger.info(f"Cache hit for agent {request.agent_name}, relevance: {relevance_score:.2f}")
                return response
        
        return None
    
    async def cache_response(self, request: AgentRequest, response: AgentResponse, relevance_score: float = 1.0):
        """Cache an agent response."""
        prompt_hash = self._hash_prompt(request.prompt, request.context)
        response_data = pickle.dumps(response)
        
        conn = sqlite3.connect(self.cache_db)
        conn.execute("""
            INSERT OR REPLACE INTO cache_entries 
            (key, agent_name, provider, prompt_hash, response_data, created_at, accessed_at, relevance_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"{request.agent_name}:{prompt_hash}",
            request.agent_name,
            response.provider.value,
            prompt_hash,
            response_data,
            datetime.now().isoformat(),
            datetime.now().isoformat(),
            relevance_score
        ))
        conn.commit()
        conn.close()
        
        logger.debug(f"Cached response for agent {request.agent_name}")
    
    def _update_access_count(self, prompt_hash: str, agent_name: str):
        """Update access count and timestamp for cache entry."""
        conn = sqlite3.connect(self.cache_db)
        conn.execute("""
            UPDATE cache_entries 
            SET accessed_at = ?, access_count = access_count + 1
            WHERE prompt_hash = ? AND agent_name = ?
        """, (datetime.now().isoformat(), prompt_hash, agent_name))
        conn.commit()
        conn.close()
    
    async def cleanup_old_entries(self, max_age_days: int = 7):
        """Clean up old cache entries."""
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        
        conn = sqlite3.connect(self.cache_db)
        cursor = conn.execute("""
            DELETE FROM cache_entries 
            WHERE created_at < ? AND access_count < 2
        """, (cutoff_date.isoformat(),))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"Cleaned up {deleted_count} old cache entries")

class PromptOptimizer:
    """Optimizes prompts based on historical performance."""
    
    def __init__(self):
        self.patterns: List[PromptPattern] = []
        self.load_patterns()
    
    def load_patterns(self):
        """Load optimization patterns."""
        # Predefined patterns based on successful prompt structures
        self.patterns = [
            PromptPattern(
                pattern_type="architectural_analysis",
                keywords=["architecture", "design", "structure", "system"],
                template="""SYSTEM ARCHITECTURE ANALYSIS

PROJECT: {project_name}
CONTEXT: {context}

As the Lead Architect, analyze the following requirements and provide:

1. ARCHITECTURAL OVERVIEW
   - High-level system design
   - Key components and their relationships
   - Technology stack recommendations

2. DESIGN DECISIONS
   - Critical architectural choices
   - Trade-offs and rationale
   - Scalability considerations

3. IMPLEMENTATION ROADMAP
   - Development phases
   - Dependencies and prerequisites
   - Risk mitigation strategies

REQUIREMENTS:
{prompt}

Provide a comprehensive, actionable architectural analysis.""",
                success_rate=0.92
            ),
            PromptPattern(
                pattern_type="security_assessment",
                keywords=["security", "vulnerability", "threat", "risk"],
                template="""SECURITY ASSESSMENT

PROJECT: {project_name}
SCOPE: {context}

As the Security Analyst, conduct a thorough security review:

1. THREAT ANALYSIS
   - Potential attack vectors
   - Vulnerability assessment
   - Risk prioritization

2. SECURITY REQUIREMENTS
   - Authentication mechanisms
   - Authorization controls
   - Data protection measures

3. MITIGATION STRATEGIES
   - Security controls implementation
   - Monitoring and detection
   - Incident response planning

FOCUS AREA:
{prompt}

Deliver actionable security recommendations with implementation priorities.""",
                success_rate=0.89
            ),
            PromptPattern(
                pattern_type="code_review",
                keywords=["code", "review", "quality", "refactor"],
                template="""CODE QUALITY REVIEW

PROJECT: {project_name}
COMPONENT: {context}

As the Code Reviewer, evaluate the following:

1. CODE QUALITY ASSESSMENT
   - Adherence to best practices
   - Code maintainability
   - Performance implications

2. IMPROVEMENT RECOMMENDATIONS
   - Refactoring opportunities
   - Optimization suggestions
   - Technical debt reduction

3. QUALITY GATES
   - Testing strategy
   - Documentation requirements
   - Deployment considerations

REVIEW TARGET:
{prompt}

Provide specific, actionable feedback for code improvement.""",
                success_rate=0.85
            )
        ]
    
    def optimize_prompt(self, request: AgentRequest, agent_profile: AgentProfile) -> str:
        """Optimize prompt based on agent profile and patterns."""
        original_prompt = request.prompt
        
        # Find best matching pattern
        best_pattern = self._find_best_pattern(original_prompt, agent_profile)
        
        if best_pattern:
            # Apply pattern template
            optimized_prompt = best_pattern.template.format(
                project_name=request.context.get("project_name", "Unknown Project"),
                context=self._format_context(request.context),
                prompt=original_prompt
            )
            
            logger.info(f"Applied {best_pattern.pattern_type} pattern for agent {request.agent_name}")
            return optimized_prompt
        
        # If no pattern matches, enhance with agent-specific formatting
        return self._enhance_with_agent_context(original_prompt, request, agent_profile)
    
    def _find_best_pattern(self, prompt: str, agent_profile: AgentProfile) -> Optional[PromptPattern]:
        """Find the best matching pattern for the prompt and agent."""
        prompt_lower = prompt.lower()
        
        for pattern in self.patterns:
            keyword_matches = sum(1 for keyword in pattern.keywords if keyword in prompt_lower)
            match_score = keyword_matches / len(pattern.keywords)
            
            # Consider agent expertise
            agent_expertise = agent_profile.expertise_areas.get(pattern.pattern_type, 0.5)
            combined_score = match_score * 0.7 + agent_expertise * 0.3
            
            if combined_score > 0.6:  # Threshold for pattern application
                return pattern
        
        return None
    
    def _enhance_with_agent_context(self, prompt: str, request: AgentRequest, 
                                  agent_profile: AgentProfile) -> str:
        """Enhance prompt with agent-specific context."""
        role_context = {
            "lead_architect": "As the Lead Architect, focus on system design and architectural decisions.",
            "security_analyst": "As the Security Analyst, prioritize security implications and risk assessment.",
            "code_reviewer": "As the Code Reviewer, emphasize code quality and best practices."
        }
        
        agent_role = agent_profile.agent_name.replace("_", " ").lower()
        context_prefix = role_context.get(agent_role, f"As {agent_profile.agent_name}, apply your expertise to")
        
        enhanced_prompt = f"""{context_prefix}

PROJECT CONTEXT:
{self._format_context(request.context)}

TASK:
{prompt}

Please provide a comprehensive response that leverages your specific expertise and addresses the task systematically."""
        
        return enhanced_prompt
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context information for prompt inclusion."""
        formatted_lines = []
        for key, value in context.items():
            if isinstance(value, (str, int, float)):
                formatted_lines.append(f"- {key.replace('_', ' ').title()}: {value}")
        return "\n".join(formatted_lines)

class LearningEngine:
    """Learns from orchestration outcomes to improve future performance."""
    
    def __init__(self, data_dir: Path = Path("learning_data")):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
        self.history_db = data_dir / "orchestration_history.db"
        self.agent_profiles: Dict[str, AgentProfile] = {}
        self.init_db()
        self.load_agent_profiles()
    
    def init_db(self):
        """Initialize the learning database."""
        conn = sqlite3.connect(self.history_db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orchestration_history (
                session_id TEXT PRIMARY KEY,
                project_name TEXT,
                project_type TEXT,
                success BOOLEAN,
                duration_seconds REAL,
                consensus_scores TEXT,
                final_quality REAL,
                timestamp TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_performance (
                session_id TEXT,
                agent_name TEXT,
                response_quality REAL,
                response_time REAL,
                consensus_contribution REAL,
                timestamp TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def record_orchestration(self, history: OrchestrationHistory):
        """Record orchestration outcome for learning."""
        conn = sqlite3.connect(self.history_db)
        
        # Store orchestration data
        conn.execute("""
            INSERT OR REPLACE INTO orchestration_history 
            (session_id, project_name, project_type, success, duration_seconds, 
             consensus_scores, final_quality, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            history.session_id,
            history.project_name,
            history.project_type,
            history.success,
            history.duration_seconds,
            json.dumps(history.consensus_scores),
            history.final_output_quality,
            history.timestamp.isoformat()
        ))
        
        # Store agent performance data
        for response_data in history.agent_responses:
            conn.execute("""
                INSERT INTO agent_performance 
                (session_id, agent_name, response_quality, response_time, 
                 consensus_contribution, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                history.session_id,
                response_data["agent_name"],
                response_data["quality_score"],
                response_data["response_time"],
                response_data["consensus_contribution"],
                history.timestamp.isoformat()
            ))
        
        conn.commit()
        conn.close()
        
        # Update agent profiles
        self.update_agent_profiles(history)
    
    def update_agent_profiles(self, history: OrchestrationHistory):
        """Update agent profiles based on performance."""
        for response_data in history.agent_responses:
            agent_name = response_data["agent_name"]
            
            if agent_name not in self.agent_profiles:
                self.agent_profiles[agent_name] = AgentProfile(
                    agent_name=agent_name,
                    provider=response_data.get("provider", "unknown")
                )
            
            profile = self.agent_profiles[agent_name]
            
            # Update success rate
            if history.success:
                profile.success_rate = (profile.success_rate * 0.9) + (1.0 * 0.1)
            else:
                profile.success_rate = (profile.success_rate * 0.9) + (0.0 * 0.1)
            
            # Update average response time
            response_time = response_data["response_time"]
            profile.avg_response_time = (profile.avg_response_time * 0.8) + (response_time * 0.2)
            
            # Update expertise areas based on project type
            project_type = history.project_type
            quality_score = response_data["quality_score"]
            
            if project_type not in profile.expertise_areas:
                profile.expertise_areas[project_type] = quality_score
            else:
                # Weighted update based on performance
                current_expertise = profile.expertise_areas[project_type]
                profile.expertise_areas[project_type] = (current_expertise * 0.7) + (quality_score * 0.3)
        
        self.save_agent_profiles()
    
    def load_agent_profiles(self):
        """Load agent profiles from storage."""
        profiles_file = self.data_dir / "agent_profiles.json"
        if profiles_file.exists():
            try:
                with open(profiles_file) as f:
                    data = json.load(f)
                    for name, profile_data in data.items():
                        self.agent_profiles[name] = AgentProfile(**profile_data)
            except Exception as e:
                logger.warning(f"Failed to load agent profiles: {e}")
    
    def save_agent_profiles(self):
        """Save agent profiles to storage."""
        profiles_file = self.data_dir / "agent_profiles.json"
        data = {}
        for name, profile in self.agent_profiles.items():
            data[name] = {
                "agent_name": profile.agent_name,
                "provider": profile.provider,
                "strengths": profile.strengths,
                "weaknesses": profile.weaknesses,
                "avg_response_time": profile.avg_response_time,
                "success_rate": profile.success_rate,
                "preferred_prompt_styles": profile.preferred_prompt_styles,
                "expertise_areas": profile.expertise_areas
            }
        
        with open(profiles_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_agent_profile(self, agent_name: str) -> AgentProfile:
        """Get agent profile, creating default if not exists."""
        if agent_name not in self.agent_profiles:
            self.agent_profiles[agent_name] = AgentProfile(
                agent_name=agent_name,
                provider="unknown"
            )
        return self.agent_profiles[agent_name]
    
    def recommend_agents_for_task(self, project_type: str, task_description: str) -> List[Tuple[str, float]]:
        """Recommend best agents for a specific task."""
        recommendations = []
        
        for agent_name, profile in self.agent_profiles.items():
            # Calculate suitability score
            expertise_score = profile.expertise_areas.get(project_type, 0.5)
            success_rate_score = profile.success_rate
            
            # Consider task keywords
            task_lower = task_description.lower()
            keyword_bonus = 0.0
            
            if "security" in task_lower and "security" in profile.strengths:
                keyword_bonus += 0.2
            if "architecture" in task_lower and "architecture" in profile.strengths:
                keyword_bonus += 0.2
            if "performance" in task_lower and "performance" in profile.strengths:
                keyword_bonus += 0.2
            
            total_score = (expertise_score * 0.4) + (success_rate_score * 0.4) + (keyword_bonus * 0.2)
            recommendations.append((agent_name, total_score))
        
        # Sort by score and return top recommendations
        recommendations.sort(key=lambda x: x[1], reverse=True)
        return recommendations[:3]

# Global instances
response_cache = ResponseCache()
prompt_optimizer = PromptOptimizer()
learning_engine = LearningEngine()

# Integration functions for gateway
async def get_optimized_response(request: AgentRequest) -> Optional[AgentResponse]:
    """Get cached or optimized response for agent request."""
    # Check cache first
    cached_response = await response_cache.get_cached_response(request)
    if cached_response:
        return cached_response
    
    # Optimize prompt
    agent_profile = learning_engine.get_agent_profile(request.agent_name)
    optimized_prompt = prompt_optimizer.optimize_prompt(request, agent_profile)
    
    # Create optimized request
    optimized_request = AgentRequest(
        prompt=optimized_prompt,
        context=request.context,
        agent_name=request.agent_name,
        phase=request.phase,
        max_tokens=request.max_tokens,
        temperature=request.temperature
    )
    
    return optimized_request

async def cache_agent_response(request: AgentRequest, response: AgentResponse, quality_score: float = 1.0):
    """Cache agent response with quality score."""
    await response_cache.cache_response(request, response, quality_score)