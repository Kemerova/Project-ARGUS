"""
Agent Providers: Custom agent provider plugins for ARGUS-V2

Allows easy integration of custom LLM providers and local models.
"""

import asyncio
import json
from typing import Dict, Any, Optional

from argus_core.gateway import LLMProviderBase, AgentRequest, AgentResponse, AgentConfig, LLMProvider
from argus_core.hooks import hook, HookType
import structlog

logger = structlog.get_logger(__name__)

class CustomAgentProvider(LLMProviderBase):
    """
    Template for custom agent providers.
    
    Extend this class to integrate custom LLM services or local models.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.endpoint = config.get("endpoint", "http://localhost:8080")
        self.api_key = config.get("api_key")
        self.model = config.get("model", "custom-model")
        
    async def call(self, request: AgentRequest, config: AgentConfig) -> AgentResponse:
        """Make a request to the custom LLM provider."""
        start_time = asyncio.get_event_loop().time()
        
        # Example implementation for a custom REST API
        payload = {
            "model": self.model,
            "prompt": request.prompt,
            "max_tokens": request.max_tokens or config.max_tokens,
            "temperature": request.temperature or config.temperature,
            "context": request.context
        }
        
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.endpoint}/v1/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=config.timeout)
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    end_time = asyncio.get_event_loop().time()
                    response_time_ms = int((end_time - start_time) * 1000)
                    
                    return AgentResponse(
                        content=data.get("text", ""),
                        agent_name=request.agent_name,
                        provider=LLMProvider.LOCAL,
                        tokens_used=data.get("tokens_used", 0),
                        response_time_ms=response_time_ms,
                        metadata={
                            "model": self.model,
                            "endpoint": self.endpoint,
                            "custom_data": data.get("metadata", {})
                        }
                    )
                    
        except Exception as e:
            logger.error(f"Custom provider call failed: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Check if the custom provider is healthy."""
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.endpoint}/health",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
                    
        except Exception as e:
            logger.warning(f"Custom provider health check failed: {e}")
            return False

class OllamaProvider(LLMProviderBase):
    """
    Ollama local LLM provider.
    
    Integrates with Ollama for running local models.
    """
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        
    async def call(self, request: AgentRequest, config: AgentConfig) -> AgentResponse:
        """Call Ollama API."""
        start_time = asyncio.get_event_loop().time()
        
        payload = {
            "model": config.model,
            "prompt": request.prompt,
            "options": {
                "temperature": request.temperature or config.temperature,
                "num_predict": request.max_tokens or config.max_tokens,
            }
        }
        
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=config.timeout)
                ) as response:
                    response.raise_for_status()
                    
                    # Ollama streams responses, collect all chunks
                    full_response = ""
                    async for line in response.content:
                        if line:
                            data = json.loads(line.decode())
                            if "response" in data:
                                full_response += data["response"]
                            if data.get("done", False):
                                break
                    
                    end_time = asyncio.get_event_loop().time()
                    response_time_ms = int((end_time - start_time) * 1000)
                    
                    return AgentResponse(
                        content=full_response,
                        agent_name=request.agent_name,
                        provider=LLMProvider.LOCAL,
                        tokens_used=0,  # Ollama doesn't provide token counts
                        response_time_ms=response_time_ms,
                        metadata={"model": config.model, "provider": "ollama"}
                    )
                    
        except Exception as e:
            logger.error(f"Ollama provider call failed: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Check Ollama health."""
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
                    
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

class HuggingFaceProvider(LLMProviderBase):
    """
    Hugging Face Inference API provider.
    
    Integrates with Hugging Face's inference endpoints.
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api-inference.huggingface.co/models"
        
    async def call(self, request: AgentRequest, config: AgentConfig) -> AgentResponse:
        """Call Hugging Face API."""
        start_time = asyncio.get_event_loop().time()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "inputs": request.prompt,
            "parameters": {
                "max_new_tokens": request.max_tokens or config.max_tokens,
                "temperature": request.temperature or config.temperature,
                "return_full_text": False
            }
        }
        
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/{config.model}",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=config.timeout)
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    end_time = asyncio.get_event_loop().time()
                    response_time_ms = int((end_time - start_time) * 1000)
                    
                    # Extract generated text
                    if isinstance(data, list) and len(data) > 0:
                        content = data[0].get("generated_text", "")
                    else:
                        content = str(data)
                    
                    return AgentResponse(
                        content=content,
                        agent_name=request.agent_name,
                        provider=LLMProvider.LOCAL,
                        tokens_used=0,  # HF doesn't provide token counts in inference API
                        response_time_ms=response_time_ms,
                        metadata={"model": config.model, "provider": "huggingface"}
                    )
                    
        except Exception as e:
            logger.error(f"Hugging Face provider call failed: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Check Hugging Face API health."""
        try:
            import aiohttp
            
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://huggingface.co/api/models",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
                    
        except Exception as e:
            logger.warning(f"Hugging Face health check failed: {e}")
            return False

# Agent middleware hooks for request/response processing

@hook(HookType.AGENT_REQUEST, priority=50, description="Log agent requests")
async def log_agent_request(context: Dict[str, Any]) -> Dict[str, Any]:
    """Log all agent requests for debugging and monitoring."""
    request = context.get("request")
    if request:
        logger.info(
            "Agent request",
            agent=request.agent_name,
            phase=request.phase,
            prompt_length=len(request.prompt),
            context_keys=list(request.context.keys()) if request.context else []
        )
    
    return context

@hook(HookType.AGENT_RESPONSE, priority=50, description="Log agent responses")
async def log_agent_response(context: Dict[str, Any]) -> Dict[str, Any]:
    """Log all agent responses for debugging and monitoring."""
    response = context.get("response")
    if response:
        logger.info(
            "Agent response",
            agent=response.agent_name,
            provider=response.provider.value,
            response_time_ms=response.response_time_ms,
            tokens_used=response.tokens_used,
            content_length=len(response.content)
        )
    
    return context

@hook(HookType.AGENT_REQUEST, priority=30, description="Rate limiting middleware")
async def rate_limiting_middleware(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Implement rate limiting for agent requests.
    
    This is a simple example - production implementations would use
    more sophisticated rate limiting algorithms.
    """
    request = context.get("request")
    if not request:
        return context
    
    # Simple rate limiting based on agent
    # In practice, this would use Redis or similar for distributed rate limiting
    rate_limits = context.get("rate_limits", {})
    current_time = asyncio.get_event_loop().time()
    
    agent_name = request.agent_name
    if agent_name in rate_limits:
        last_request_time = rate_limits[agent_name]
        time_since_last = current_time - last_request_time
        
        # Minimum 1 second between requests (configurable)
        min_interval = context.get("min_request_interval", 1.0)
        if time_since_last < min_interval:
            wait_time = min_interval - time_since_last
            logger.warning(
                "Rate limiting agent request",
                agent=agent_name,
                wait_time=wait_time
            )
            await asyncio.sleep(wait_time)
    
    rate_limits[agent_name] = current_time
    context["rate_limits"] = rate_limits
    
    return context

@hook(HookType.AGENT_RESPONSE, priority=90, description="Response validation")
async def validate_agent_response(context: Dict[str, Any]) -> Dict[str, Any]:
    """Validate agent responses for quality and safety."""
    response = context.get("response")
    if not response:
        return context
    
    # Basic validation checks
    validation_errors = []
    
    # Check content length
    if len(response.content) < 10:
        validation_errors.append("Response too short")
    
    if len(response.content) > 50000:
        validation_errors.append("Response too long")
    
    # Check for common issues
    if "I cannot" in response.content and "help" in response.content:
        validation_errors.append("Agent declined to help")
    
    # Log validation results
    if validation_errors:
        logger.warning(
            "Response validation issues",
            agent=response.agent_name,
            errors=validation_errors
        )
        context["validation_errors"] = validation_errors
    else:
        logger.debug("Response validation passed", agent=response.agent_name)
    
    return context