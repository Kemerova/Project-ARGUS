"""
AgentGateway: Unified interface for all LLM providers

Replaces the complex agent hierarchy from V1 with a single,
efficient gateway that handles routing to different LLM providers.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, List, AsyncIterator
from contextlib import asynccontextmanager

import aiohttp
import structlog

# Import intelligence system for optimization and caching
from .intelligence import get_optimized_response, cache_agent_response

# Import contribution logging
from .contribution_logger import log_agent_contribution

logger = structlog.get_logger(__name__)

class AgentRole(Enum):
    """Standard agent roles in ARGUS orchestration."""
    LEAD_ARCHITECT = "lead_architect"
    SECURITY_ANALYST = "security_analyst" 
    CODE_REVIEWER = "code_reviewer"
    PERFORMANCE_ENGINEER = "performance_engineer"

class LLMProvider(Enum):
    """Supported LLM providers."""
    CLAUDE = "claude"
    GEMINI = "gemini"
    OPENAI = "openai"
    LOCAL = "local"

@dataclass
class AgentConfig:
    """Configuration for a single agent."""
    name: str
    role: AgentRole
    provider: LLMProvider
    model: str
    max_tokens: int = 4000
    temperature: float = 0.7
    timeout: int = 30
    rate_limit: int = 60  # requests per minute

@dataclass
class AgentRequest:
    """Request to an agent."""
    prompt: str
    context: Dict[str, Any]
    agent_name: str
    phase: str
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    session_id: Optional[str] = None
    contribution_type: str = "analysis"

@dataclass 
class AgentResponse:
    """Response from an agent."""
    content: str
    agent_name: str
    provider: LLMProvider
    tokens_used: int
    response_time_ms: int
    metadata: Dict[str, Any]

class LLMProviderBase(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def call(self, request: AgentRequest, config: AgentConfig) -> AgentResponse:
        """Make a request to the LLM provider."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is healthy."""
        pass

class ClaudeProvider(LLMProviderBase):
    """Claude/Anthropic provider implementation."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1"
        
    async def call(self, request: AgentRequest, config: AgentConfig) -> AgentResponse:
        """Call Claude API."""
        start_time = asyncio.get_event_loop().time()
        
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        payload = {
            "model": config.model,
            "max_tokens": request.max_tokens or config.max_tokens,
            "temperature": request.temperature or config.temperature,
            "messages": [{"role": "user", "content": request.prompt}]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=config.timeout)
            ) as response:
                response.raise_for_status()
                data = await response.json()
                
                end_time = asyncio.get_event_loop().time()
                response_time_ms = int((end_time - start_time) * 1000)
                
                return AgentResponse(
                    content=data["content"][0]["text"],
                    agent_name=request.agent_name,
                    provider=LLMProvider.CLAUDE,
                    tokens_used=data["usage"]["output_tokens"],
                    response_time_ms=response_time_ms,
                    metadata={"model": config.model, "usage": data["usage"]}
                )
    
    async def health_check(self) -> bool:
        """Check Claude API health."""
        try:
            headers = {"x-api-key": self.api_key}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/models",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.warning("Claude health check failed", error=str(e))
            return False

class GeminiProvider(LLMProviderBase):
    """Google Gemini provider implementation."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        
    async def call(self, request: AgentRequest, config: AgentConfig) -> AgentResponse:
        """Call Gemini API."""
        start_time = asyncio.get_event_loop().time()
        
        url = f"{self.base_url}/models/{config.model}:generateContent"
        params = {"key": self.api_key}
        
        payload = {
            "contents": [{"parts": [{"text": request.prompt}]}],
            "generationConfig": {
                "maxOutputTokens": request.max_tokens or config.max_tokens,
                "temperature": request.temperature or config.temperature,
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                params=params,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=config.timeout)
            ) as response:
                response.raise_for_status()
                data = await response.json()
                
                end_time = asyncio.get_event_loop().time()
                response_time_ms = int((end_time - start_time) * 1000)
                
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                
                return AgentResponse(
                    content=content,
                    agent_name=request.agent_name,
                    provider=LLMProvider.GEMINI,
                    tokens_used=data.get("usageMetadata", {}).get("totalTokenCount", 0),
                    response_time_ms=response_time_ms,
                    metadata={"model": config.model, "usage": data.get("usageMetadata", {})}
                )
    
    async def health_check(self) -> bool:
        """Check Gemini API health."""
        try:
            url = f"{self.base_url}/models"
            params = {"key": self.api_key}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.warning("Gemini health check failed", error=str(e))
            return False

class OpenAIProvider(LLMProviderBase):
    """OpenAI provider implementation."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1"
        
    async def call(self, request: AgentRequest, config: AgentConfig) -> AgentResponse:
        """Call OpenAI API."""
        start_time = asyncio.get_event_loop().time()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": config.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens or config.max_tokens,
            "temperature": request.temperature or config.temperature,
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=config.timeout)
            ) as response:
                response.raise_for_status()
                data = await response.json()
                
                end_time = asyncio.get_event_loop().time()
                response_time_ms = int((end_time - start_time) * 1000)
                
                return AgentResponse(
                    content=data["choices"][0]["message"]["content"],
                    agent_name=request.agent_name,
                    provider=LLMProvider.OPENAI,
                    tokens_used=data["usage"]["total_tokens"],
                    response_time_ms=response_time_ms,
                    metadata={"model": config.model, "usage": data["usage"]}
                )
    
    async def health_check(self) -> bool:
        """Check OpenAI API health."""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/models",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.warning("OpenAI health check failed", error=str(e))
            return False

class AgentGateway:
    """
    Unified gateway for all LLM agent interactions.
    
    Replaces the complex V1 agent hierarchy with a single, efficient
    interface that handles routing, rate limiting, and response management.
    """
    
    def __init__(self):
        self.agents: Dict[str, AgentConfig] = {}
        self.providers: Dict[LLMProvider, LLMProviderBase] = {}
        self.rate_limiters: Dict[str, asyncio.Semaphore] = {}
        
    def register_provider(self, provider_type: LLMProvider, provider: LLMProviderBase):
        """Register an LLM provider."""
        self.providers[provider_type] = provider
        logger.info("Registered LLM provider", provider=provider_type.value)
        
    def register_agent(self, config: AgentConfig):
        """Register an agent configuration."""
        self.agents[config.name] = config
        
        # Create rate limiter for this agent
        self.rate_limiters[config.name] = asyncio.Semaphore(config.rate_limit)
        
        logger.info(
            "Registered agent",
            name=config.name,
            role=config.role.value,
            provider=config.provider.value
        )
    
    async def call_agent(self, request: AgentRequest) -> AgentResponse:
        """
        Call a specific agent with the given request.
        
        Handles routing, rate limiting, caching, and optimization.
        """
        if request.agent_name not in self.agents:
            raise ValueError(f"Agent '{request.agent_name}' not registered")
            
        config = self.agents[request.agent_name]
        provider = self.providers.get(config.provider)
        
        if not provider:
            raise ValueError(f"Provider '{config.provider.value}' not available")
        
        # Try to get cached/optimized response first
        optimized_request = await get_optimized_response(request)
        if optimized_request and hasattr(optimized_request, 'content'):
            # Return cached response
            logger.info(
                "Agent call served from cache",
                agent=request.agent_name,
                phase=request.phase
            )
            return optimized_request
        elif optimized_request:
            # Use optimized request
            request = optimized_request
        
        # Rate limiting
        rate_limiter = self.rate_limiters[request.agent_name]
        async with rate_limiter:
            try:
                start_time = time.time()
                response = await provider.call(request, config)
                
                # Track performance metrics
                from .monitoring import track_agent_call
                track_agent_call(
                    request.agent_name,
                    config.provider.value,
                    response.response_time_ms,
                    response.tokens_used,
                    True
                )
                
                # Cache the response
                quality_score = 1.0  # Default high quality, could be enhanced with analysis
                await cache_agent_response(request, response, quality_score)
                
                # Log agent contribution
                if hasattr(request, 'session_id'):
                    log_agent_contribution(
                        prompt_id=f"{request.session_id}_{request.agent_name}_{int(time.time())}",
                        prompt_text=request.prompt,
                        session_id=request.session_id,
                        phase_name=request.phase,
                        agent_name=request.agent_name,
                        agent_role=config.role.value,
                        contribution_type="analysis",  # Default type, could be enhanced
                        response_content=response.content,
                        quality_score=quality_score,
                        response_time_ms=response.response_time_ms,
                        tokens_used=response.tokens_used,
                        consensus_contribution=0.5  # Default value
                    )
                
                logger.info(
                    "Agent call successful",
                    agent=request.agent_name,
                    phase=request.phase,
                    response_time_ms=response.response_time_ms,
                    tokens=response.tokens_used
                )
                
                return response
                
            except Exception as e:
                # Track failed call
                from .monitoring import track_agent_call
                track_agent_call(
                    request.agent_name,
                    config.provider.value,
                    0,
                    0,
                    False
                )
                
                logger.error(
                    "Agent call failed",
                    agent=request.agent_name,
                    provider=config.provider.value,
                    error=str(e)
                )
                raise
    
    async def call_parallel(self, requests: List[AgentRequest]) -> List[AgentResponse]:
        """Call multiple agents in parallel."""
        tasks = [self.call_agent(request) for request in requests]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to failed responses
        results = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                logger.error(
                    "Parallel agent call failed",
                    agent=requests[i].agent_name,
                    error=str(response)
                )
                # Create error response
                results.append(AgentResponse(
                    content=f"Error: {response}",
                    agent_name=requests[i].agent_name,
                    provider=self.agents[requests[i].agent_name].provider,
                    tokens_used=0,
                    response_time_ms=0,
                    metadata={"error": str(response)}
                ))
            else:
                results.append(response)
                
        return results
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all registered providers."""
        health_status = {}
        
        for provider_type, provider in self.providers.items():
            try:
                health_status[provider_type.value] = await provider.health_check()
            except Exception as e:
                logger.error(
                    "Health check failed",
                    provider=provider_type.value,
                    error=str(e)
                )
                health_status[provider_type.value] = False
                
        return health_status
    
    def get_agent_configs(self) -> Dict[str, AgentConfig]:
        """Get all registered agent configurations."""
        return self.agents.copy()
    
    @asynccontextmanager
    async def session(self):
        """Context manager for gateway sessions."""
        logger.info("Starting agent gateway session")
        try:
            yield self
        finally:
            logger.info("Ending agent gateway session")