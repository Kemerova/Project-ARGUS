"""
Hooks System: Plugin-based extensibility for ARGUS-V2

Replaces V1's rigid quality gates with a flexible hook system
that allows runtime plugin loading and custom validation logic.
"""

import asyncio
import inspect
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Callable, Awaitable, Any, Optional
from functools import wraps

import structlog

logger = structlog.get_logger(__name__)

class HookType(Enum):
    """Types of hooks supported by ARGUS-V2."""
    PRE_ORCHESTRATION = "pre_orchestration"
    POST_ORCHESTRATION = "post_orchestration"
    PRE_PHASE = "pre_phase"
    POST_PHASE = "post_phase"
    QUALITY_GATE = "quality_gate"
    AGENT_REQUEST = "agent_request"
    AGENT_RESPONSE = "agent_response"
    ERROR_HANDLER = "error_handler"

@dataclass
class HookInfo:
    """Information about a registered hook."""
    name: str
    hook_type: HookType
    func: Callable
    priority: int = 0
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

class HookManager:
    """
    Manages the hook system for ARGUS-V2.
    
    Provides a plugin-based architecture for extending framework
    functionality without modifying core code.
    """
    
    def __init__(self):
        self.hooks: Dict[HookType, List[HookInfo]] = {
            hook_type: [] for hook_type in HookType
        }
        self._hook_cache: Dict[str, List[HookInfo]] = {}
        
    def register_hook(
        self,
        hook_type: HookType,
        func: Callable,
        name: Optional[str] = None,
        priority: int = 0,
        description: str = ""
    ) -> str:
        """Register a hook function."""
        hook_name = name or f"{func.__module__}.{func.__name__}"
        
        # Validate function signature
        if asyncio.iscoroutinefunction(func):
            sig = inspect.signature(func)
            if len(sig.parameters) != 1:
                raise ValueError(
                    f"Async hook function must accept exactly one parameter, "
                    f"got {len(sig.parameters)}"
                )
        else:
            # Convert sync function to async
            original_func = func
            @wraps(original_func)
            async def async_wrapper(context: Dict[str, Any]) -> Dict[str, Any]:
                return original_func(context)
            func = async_wrapper
        
        hook_info = HookInfo(
            name=hook_name,
            hook_type=hook_type,
            func=func,
            priority=priority,
            description=description
        )
        
        self.hooks[hook_type].append(hook_info)
        
        # Sort by priority (higher priority first)
        self.hooks[hook_type].sort(key=lambda h: h.priority, reverse=True)
        
        # Clear cache
        self._hook_cache.clear()
        
        logger.info(
            "Registered hook",
            name=hook_name,
            type=hook_type.value,
            priority=priority
        )
        
        return hook_name
    
    def unregister_hook(self, hook_type: HookType, name: str) -> bool:
        """Unregister a hook by name."""
        hooks = self.hooks[hook_type]
        
        for i, hook_info in enumerate(hooks):
            if hook_info.name == name:
                del hooks[i]
                self._hook_cache.clear()
                logger.info(
                    "Unregistered hook",
                    name=name,
                    type=hook_type.value
                )
                return True
        
        return False
    
    async def execute_hooks(
        self,
        hook_type: HookType,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute all hooks of a given type."""
        hooks = self.hooks[hook_type]
        if not hooks:
            return context
        
        logger.debug(
            "Executing hooks",
            type=hook_type.value,
            count=len(hooks)
        )
        
        result_context = context.copy()
        
        for hook_info in hooks:
            try:
                hook_result = await hook_info.func(result_context)
                
                # Merge hook result back into context
                if isinstance(hook_result, dict):
                    result_context.update(hook_result)
                
                logger.debug(
                    "Hook executed successfully",
                    name=hook_info.name,
                    type=hook_type.value
                )
                
            except Exception as e:
                logger.error(
                    "Hook execution failed",
                    name=hook_info.name,
                    type=hook_type.value,
                    error=str(e)
                )
                
                # Execute error handler hooks
                if hook_type != HookType.ERROR_HANDLER:
                    await self.execute_hooks(
                        HookType.ERROR_HANDLER,
                        {
                            "original_context": context,
                            "failed_hook": hook_info.name,
                            "error": str(e),
                            "hook_type": hook_type.value
                        }
                    )
        
        return result_context
    
    def get_hooks(self, hook_type: HookType) -> List[HookInfo]:
        """Get all hooks of a given type."""
        return self.hooks[hook_type].copy()
    
    def get_hook_info(self, hook_type: HookType, name: str) -> Optional[HookInfo]:
        """Get information about a specific hook."""
        for hook_info in self.hooks[hook_type]:
            if hook_info.name == name:
                return hook_info
        return None
    
    def list_all_hooks(self) -> Dict[str, List[str]]:
        """List all registered hooks by type."""
        return {
            hook_type.value: [hook.name for hook in hooks]
            for hook_type, hooks in self.hooks.items()
        }

# Decorator functions for easy hook registration

def hook(
    hook_type: HookType,
    name: Optional[str] = None,
    priority: int = 0,
    description: str = ""
):
    """Decorator to register a function as a hook."""
    def decorator(func):
        # Store hook metadata on function for later registration
        func._hook_info = {
            "hook_type": hook_type,
            "name": name,
            "priority": priority,
            "description": description
        }
        return func
    return decorator

def quality_gate(name: str, priority: int = 0, description: str = ""):
    """Decorator to register a quality gate hook."""
    return hook(
        HookType.QUALITY_GATE,
        name=name,
        priority=priority,
        description=description
    )

def agent_middleware(priority: int = 0, description: str = ""):
    """Decorator to register agent middleware hooks."""
    return hook(
        HookType.AGENT_REQUEST,
        priority=priority,
        description=description
    )

def error_handler(priority: int = 0, description: str = ""):
    """Decorator to register error handler hooks."""
    return hook(
        HookType.ERROR_HANDLER,
        priority=priority,
        description=description
    )

# Auto-registration function for modules
def register_hooks_from_module(hook_manager: HookManager, module):
    """Register all hooks from a module."""
    registered_count = 0
    
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        
        if callable(attr) and hasattr(attr, '_hook_info'):
            hook_info = attr._hook_info
            hook_manager.register_hook(
                hook_type=hook_info["hook_type"],
                func=attr,
                name=hook_info["name"] or f"{module.__name__}.{attr_name}",
                priority=hook_info["priority"],
                description=hook_info["description"]
            )
            registered_count += 1
    
    logger.info(
        "Registered hooks from module",
        module=module.__name__,
        count=registered_count
    )
    
    return registered_count

__all__ = [
    "HookType",
    "HookInfo", 
    "HookManager",
    "hook",
    "quality_gate",
    "agent_middleware",
    "error_handler",
    "register_hooks_from_module"
]