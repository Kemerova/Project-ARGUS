"""
AsyncScheduler: High-performance task scheduling for ARGUS-V2

Manages async task execution, resource allocation, and concurrent
orchestration sessions with efficient resource utilization.
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Callable, Awaitable, Any
from uuid import uuid4

import structlog

logger = structlog.get_logger(__name__)

class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class ScheduledTask:
    """A task scheduled for execution."""
    id: str
    name: str
    coro: Callable[[], Awaitable[Any]]
    priority: TaskPriority = TaskPriority.NORMAL
    timeout: Optional[int] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ResourceLimits:
    """Resource limits for task execution."""
    max_concurrent_tasks: int = 10
    max_concurrent_orchestrations: int = 3
    max_memory_mb: int = 1024
    max_cpu_percent: int = 80

class AsyncScheduler:
    """
    High-performance async task scheduler for ARGUS-V2.
    
    Manages concurrent execution of orchestration sessions and tasks
    with resource limits, priority queuing, and performance monitoring.
    """
    
    def __init__(self, limits: ResourceLimits = None):
        self.limits = limits or ResourceLimits()
        self.tasks: Dict[str, ScheduledTask] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.semaphore = asyncio.Semaphore(self.limits.max_concurrent_tasks)
        self.orchestration_semaphore = asyncio.Semaphore(
            self.limits.max_concurrent_orchestrations
        )
        self.running = False
        self.worker_tasks: List[asyncio.Task] = []
        
    async def start(self):
        """Start the scheduler and worker tasks."""
        if self.running:
            return
            
        self.running = True
        
        # Start worker tasks
        for i in range(min(4, self.limits.max_concurrent_tasks)):
            worker_task = asyncio.create_task(self._worker(f"worker-{i}"))
            self.worker_tasks.append(worker_task)
            
        logger.info(
            "Scheduler started",
            workers=len(self.worker_tasks),
            max_concurrent=self.limits.max_concurrent_tasks
        )
    
    async def stop(self):
        """Stop the scheduler and cancel running tasks."""
        if not self.running:
            return
            
        self.running = False
        
        # Cancel all running tasks
        for task_id, task in self.running_tasks.items():
            task.cancel()
            logger.info("Cancelled running task", task_id=task_id)
        
        # Cancel worker tasks
        for worker_task in self.worker_tasks:
            worker_task.cancel()
            
        # Wait for all tasks to complete
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
            
        logger.info("Scheduler stopped")
    
    async def schedule_task(
        self,
        name: str,
        coro: Callable[[], Awaitable[Any]],
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: Optional[int] = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Schedule a task for execution."""
        task_id = str(uuid4())
        
        task = ScheduledTask(
            id=task_id,
            name=name,
            coro=coro,
            priority=priority,
            timeout=timeout,
            metadata=metadata or {}
        )
        
        self.tasks[task_id] = task
        
        # Add to priority queue (lower number = higher priority)
        priority_value = 5 - priority.value  # Invert so higher priority = lower number
        await self.task_queue.put((priority_value, time.time(), task_id))
        
        logger.info(
            "Task scheduled",
            task_id=task_id,
            name=name,
            priority=priority.value,
            queue_size=self.task_queue.qsize()
        )
        
        return task_id
    
    async def schedule_orchestration(
        self,
        name: str,
        coro: Callable[[], Awaitable[Any]],
        timeout: Optional[int] = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Schedule an orchestration with orchestration-specific resource limits."""
        # Wrap the coroutine to use orchestration semaphore
        async def orchestration_wrapper():
            async with self.orchestration_semaphore:
                return await coro()
        
        return await self.schedule_task(
            name=f"orchestration:{name}",
            coro=orchestration_wrapper,
            priority=TaskPriority.HIGH,
            timeout=timeout,
            metadata={**(metadata or {}), "type": "orchestration"}
        )
    
    async def _worker(self, worker_name: str):
        """Worker task that processes the task queue."""
        logger.info("Worker started", worker=worker_name)
        
        while self.running:
            try:
                # Get next task from queue with timeout
                try:
                    priority, scheduled_time, task_id = await asyncio.wait_for(
                        self.task_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                if task_id not in self.tasks:
                    logger.warning(
                        "Task not found in registry",
                        worker=worker_name,
                        task_id=task_id
                    )
                    continue
                
                task = self.tasks[task_id]
                
                # Execute task with semaphore
                async with self.semaphore:
                    await self._execute_task(task, worker_name)
                    
            except asyncio.CancelledError:
                logger.info("Worker cancelled", worker=worker_name)
                break
            except Exception as e:
                logger.error(
                    "Worker error",
                    worker=worker_name,
                    error=str(e)
                )
        
        logger.info("Worker stopped", worker=worker_name)
    
    async def _execute_task(self, task: ScheduledTask, worker_name: str):
        """Execute a single task."""
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()
        
        logger.info(
            "Executing task",
            worker=worker_name,
            task_id=task.id,
            name=task.name,
            priority=task.priority.value
        )
        
        try:
            # Create asyncio task for execution
            execution_task = asyncio.create_task(task.coro())
            self.running_tasks[task.id] = execution_task
            
            # Execute with timeout if specified
            if task.timeout:
                task.result = await asyncio.wait_for(execution_task, task.timeout)
            else:
                task.result = await execution_task
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            
            execution_time = task.completed_at - task.started_at
            
            logger.info(
                "Task completed",
                worker=worker_name,
                task_id=task.id,
                name=task.name,
                execution_time_ms=int(execution_time * 1000)
            )
            
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            task.completed_at = time.time()
            logger.info("Task cancelled", task_id=task.id, name=task.name)
            
        except asyncio.TimeoutError:
            task.status = TaskStatus.FAILED
            task.error = f"Task timed out after {task.timeout}s"
            task.completed_at = time.time()
            logger.error(
                "Task timed out",
                task_id=task.id,
                name=task.name,
                timeout=task.timeout
            )
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = time.time()
            logger.error(
                "Task failed",
                task_id=task.id,
                name=task.name,
                error=str(e)
            )
            
        finally:
            # Clean up
            if task.id in self.running_tasks:
                del self.running_tasks[task.id]
    
    async def get_task_status(self, task_id: str) -> Optional[ScheduledTask]:
        """Get status of a specific task."""
        return self.tasks.get(task_id)
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a specific task."""
        if task_id not in self.tasks:
            return False
            
        task = self.tasks[task_id]
        
        if task.status == TaskStatus.RUNNING and task_id in self.running_tasks:
            # Cancel the running asyncio task
            running_task = self.running_tasks[task_id]
            running_task.cancel()
            logger.info("Cancelled running task", task_id=task_id)
            
        elif task.status == TaskStatus.PENDING:
            # Mark as cancelled if still pending
            task.status = TaskStatus.CANCELLED
            task.completed_at = time.time()
            logger.info("Cancelled pending task", task_id=task_id)
            
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        total_tasks = len(self.tasks)
        running_count = len(self.running_tasks)
        pending_count = self.task_queue.qsize()
        
        status_counts = {}
        for status in TaskStatus:
            status_counts[status.value] = sum(
                1 for task in self.tasks.values() 
                if task.status == status
            )
        
        # Calculate average execution times
        completed_tasks = [
            task for task in self.tasks.values() 
            if task.status == TaskStatus.COMPLETED and task.started_at and task.completed_at
        ]
        
        avg_execution_time = 0.0
        if completed_tasks:
            total_time = sum(
                task.completed_at - task.started_at 
                for task in completed_tasks
            )
            avg_execution_time = total_time / len(completed_tasks)
        
        return {
            "running": self.running,
            "total_tasks": total_tasks,
            "running_tasks": running_count,
            "pending_tasks": pending_count,
            "worker_tasks": len(self.worker_tasks),
            "status_counts": status_counts,
            "limits": {
                "max_concurrent_tasks": self.limits.max_concurrent_tasks,
                "max_concurrent_orchestrations": self.limits.max_concurrent_orchestrations,
            },
            "performance": {
                "avg_execution_time_ms": int(avg_execution_time * 1000),
                "completed_tasks": len(completed_tasks),
            }
        }
    
    async def wait_for_task(self, task_id: str, timeout: Optional[int] = None) -> Optional[ScheduledTask]:
        """Wait for a specific task to complete."""
        if task_id not in self.tasks:
            return None
            
        task = self.tasks[task_id]
        start_time = time.time()
        
        while task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            if timeout and (time.time() - start_time) > timeout:
                return task
                
            await asyncio.sleep(0.1)
        
        return task
    
    async def wait_for_completion(self, timeout: Optional[int] = None) -> Dict[str, Any]:
        """Wait for all scheduled tasks to complete."""
        start_time = time.time()
        
        while self.running_tasks or not self.task_queue.empty():
            if timeout and (time.time() - start_time) > timeout:
                break
                
            await asyncio.sleep(0.1)
        
        return self.get_stats()