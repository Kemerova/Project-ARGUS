"""
Real-time Monitoring System for ARGUS-V2

Provides live orchestration tracking, metrics collection, and health monitoring
with WebSocket-based real-time updates.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any
from collections import defaultdict, deque

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

logger = structlog.get_logger(__name__)

@dataclass
class MetricPoint:
    """Single metric data point."""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)

@dataclass
class OrchestrationMetrics:
    """Metrics for an orchestration session."""
    session_id: str
    project_name: str
    start_time: float
    end_time: Optional[float] = None
    status: str = "running"
    phases_completed: int = 0
    total_phases: int = 0
    agent_calls: int = 0
    consensus_scores: List[float] = field(default_factory=list)
    error_count: int = 0
    memory_usage_mb: float = 0.0

@dataclass
class AgentMetrics:
    """Metrics for individual agents."""
    agent_name: str
    provider: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    avg_response_time_ms: float = 0.0
    total_tokens_used: int = 0
    last_call_time: Optional[float] = None

class MetricsCollector:
    """Collects and aggregates system metrics."""
    
    def __init__(self):
        self.orchestrations: Dict[str, OrchestrationMetrics] = {}
        self.agent_metrics: Dict[str, AgentMetrics] = {}
        self.system_metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.connected_clients: Set[WebSocket] = set()
        
    def record_orchestration_start(self, session_id: str, project_name: str, total_phases: int):
        """Record the start of an orchestration."""
        self.orchestrations[session_id] = OrchestrationMetrics(
            session_id=session_id,
            project_name=project_name,
            start_time=time.time(),
            total_phases=total_phases
        )
        
        asyncio.create_task(self._broadcast_update("orchestration_started", {
            "session_id": session_id,
            "project_name": project_name,
            "timestamp": time.time()
        }))
    
    def record_orchestration_end(self, session_id: str, status: str):
        """Record the end of an orchestration."""
        if session_id in self.orchestrations:
            self.orchestrations[session_id].end_time = time.time()
            self.orchestrations[session_id].status = status
            
            asyncio.create_task(self._broadcast_update("orchestration_ended", {
                "session_id": session_id,
                "status": status,
                "timestamp": time.time()
            }))
    
    def record_phase_completion(self, session_id: str, phase_name: str, consensus_score: float):
        """Record completion of a phase."""
        if session_id in self.orchestrations:
            metrics = self.orchestrations[session_id]
            metrics.phases_completed += 1
            metrics.consensus_scores.append(consensus_score)
            
            asyncio.create_task(self._broadcast_update("phase_completed", {
                "session_id": session_id,
                "phase_name": phase_name,
                "consensus_score": consensus_score,
                "progress": metrics.phases_completed / metrics.total_phases
            }))
    
    def record_agent_call(self, agent_name: str, provider: str, response_time_ms: float, 
                         tokens_used: int, success: bool):
        """Record an agent call."""
        if agent_name not in self.agent_metrics:
            self.agent_metrics[agent_name] = AgentMetrics(
                agent_name=agent_name,
                provider=provider
            )
        
        metrics = self.agent_metrics[agent_name]
        metrics.total_calls += 1
        metrics.total_tokens_used += tokens_used
        metrics.last_call_time = time.time()
        
        if success:
            metrics.successful_calls += 1
        else:
            metrics.failed_calls += 1
        
        # Update average response time
        if metrics.total_calls == 1:
            metrics.avg_response_time_ms = response_time_ms
        else:
            metrics.avg_response_time_ms = (
                (metrics.avg_response_time_ms * (metrics.total_calls - 1) + response_time_ms) 
                / metrics.total_calls
            )
        
        asyncio.create_task(self._broadcast_update("agent_call", {
            "agent_name": agent_name,
            "provider": provider,
            "response_time_ms": response_time_ms,
            "success": success,
            "timestamp": time.time()
        }))
    
    def record_system_metric(self, metric_name: str, value: float, labels: Dict[str, str] = None):
        """Record a system metric."""
        point = MetricPoint(
            timestamp=time.time(),
            value=value,
            labels=labels or {}
        )
        self.system_metrics[metric_name].append(point)
        
        asyncio.create_task(self._broadcast_update("system_metric", {
            "metric_name": metric_name,
            "value": value,
            "labels": labels,
            "timestamp": time.time()
        }))
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data."""
        now = time.time()
        
        # Active orchestrations
        active_orchestrations = [
            {
                "session_id": orch.session_id,
                "project_name": orch.project_name,
                "progress": orch.phases_completed / max(orch.total_phases, 1),
                "duration": now - orch.start_time,
                "status": orch.status
            }
            for orch in self.orchestrations.values()
            if orch.end_time is None
        ]
        
        # Agent performance summary
        agent_summary = []
        for agent in self.agent_metrics.values():
            success_rate = agent.successful_calls / max(agent.total_calls, 1)
            agent_summary.append({
                "name": agent.agent_name,
                "provider": agent.provider,
                "total_calls": agent.total_calls,
                "success_rate": success_rate,
                "avg_response_time": agent.avg_response_time_ms,
                "tokens_used": agent.total_tokens_used
            })
        
        # Recent orchestration history
        recent_orchestrations = sorted(
            [orch for orch in self.orchestrations.values() if orch.end_time is not None],
            key=lambda x: x.end_time or 0,
            reverse=True
        )[:10]
        
        orchestration_history = []
        for orch in recent_orchestrations:
            duration = (orch.end_time or now) - orch.start_time
            avg_consensus = sum(orch.consensus_scores) / len(orch.consensus_scores) if orch.consensus_scores else 0
            
            orchestration_history.append({
                "session_id": orch.session_id,
                "project_name": orch.project_name,
                "status": orch.status,
                "duration": duration,
                "phases_completed": orch.phases_completed,
                "avg_consensus": avg_consensus,
                "agent_calls": orch.agent_calls
            })
        
        # System health metrics
        cpu_metrics = list(self.system_metrics.get("cpu_percent", []))[-50:]
        memory_metrics = list(self.system_metrics.get("memory_percent", []))[-50:]
        
        return {
            "timestamp": now,
            "active_orchestrations": active_orchestrations,
            "agent_summary": agent_summary,
            "orchestration_history": orchestration_history,
            "system_health": {
                "cpu_usage": [{"timestamp": p.timestamp, "value": p.value} for p in cpu_metrics],
                "memory_usage": [{"timestamp": p.timestamp, "value": p.value} for p in memory_metrics],
            },
            "statistics": {
                "total_orchestrations": len(self.orchestrations),
                "active_count": len(active_orchestrations),
                "total_agents": len(self.agent_metrics),
                "total_agent_calls": sum(a.total_calls for a in self.agent_metrics.values())
            }
        }
    
    async def add_client(self, websocket: WebSocket):
        """Add a WebSocket client for real-time updates."""
        await websocket.accept()
        self.connected_clients.add(websocket)
        
        # Send initial dashboard data
        try:
            await websocket.send_json({
                "type": "dashboard_data",
                "data": self.get_dashboard_data()
            })
        except:
            self.connected_clients.discard(websocket)
    
    async def remove_client(self, websocket: WebSocket):
        """Remove a WebSocket client."""
        self.connected_clients.discard(websocket)
    
    async def _broadcast_update(self, event_type: str, data: Dict[str, Any]):
        """Broadcast an update to all connected clients."""
        if not self.connected_clients:
            return
        
        message = {
            "type": event_type,
            "data": data
        }
        
        # Send to all connected clients
        disconnected = set()
        for client in self.connected_clients:
            try:
                await client.send_json(message)
            except:
                disconnected.add(client)
        
        # Remove disconnected clients
        self.connected_clients -= disconnected

# Global metrics collector instance
metrics_collector = MetricsCollector()

# Monitoring dashboard FastAPI app
monitor_app = FastAPI(title="ARGUS-V2 Monitoring Dashboard")

@monitor_app.get("/")
async def dashboard():
    """Serve the monitoring dashboard."""
    return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
    <title>ARGUS-V2 Monitoring Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                  color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .metric { font-size: 24px; font-weight: bold; color: #333; }
        .status-running { color: #28a745; }
        .status-completed { color: #17a2b8; }
        .status-failed { color: #dc3545; }
        .progress-bar { background: #e9ecef; height: 20px; border-radius: 10px; overflow: hidden; }
        .progress-fill { background: linear-gradient(90deg, #28a745, #20c997); height: 100%; transition: width 0.3s; }
        #charts { margin-top: 20px; }
        .chart-container { width: 100%; height: 300px; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 ARGUS-V2 Monitoring Dashboard</h1>
        <p>Real-time orchestration monitoring and system health</p>
    </div>
    
    <div class="grid">
        <div class="card">
            <h3>🎭 Active Orchestrations</h3>
            <div class="metric" id="activeCount">0</div>
            <div id="activeList"></div>
        </div>
        
        <div class="card">
            <h3>🤖 Agent Performance</h3>
            <div id="agentStats"></div>
        </div>
        
        <div class="card">
            <h3>📊 System Health</h3>
            <div>CPU: <span class="metric" id="cpuUsage">0%</span></div>
            <div>Memory: <span class="metric" id="memUsage">0%</span></div>
        </div>
        
        <div class="card">
            <h3>📈 Statistics</h3>
            <div>Total Orchestrations: <span class="metric" id="totalOrch">0</span></div>
            <div>Total Agent Calls: <span class="metric" id="totalCalls">0</span></div>
        </div>
    </div>
    
    <div id="charts">
        <div class="card">
            <h3>📈 System Performance</h3>
            <div class="chart-container">
                <canvas id="performanceChart"></canvas>
            </div>
        </div>
    </div>

    <script>
        const ws = new WebSocket('ws://localhost:8001/ws');
        
        let performanceChart;
        
        // Initialize charts
        const ctx = document.getElementById('performanceChart').getContext('2d');
        performanceChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'CPU Usage %',
                    data: [],
                    borderColor: '#667eea',
                    fill: false
                }, {
                    label: 'Memory Usage %',
                    data: [],
                    borderColor: '#764ba2',
                    fill: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, max: 100 }
                }
            }
        });
        
        ws.onmessage = function(event) {
            const message = JSON.parse(event.data);
            
            if (message.type === 'dashboard_data') {
                updateDashboard(message.data);
            } else if (message.type === 'orchestration_started') {
                // Handle real-time updates
                console.log('Orchestration started:', message.data);
            }
        };
        
        function updateDashboard(data) {
            // Update active orchestrations
            document.getElementById('activeCount').textContent = data.active_orchestrations.length;
            
            const activeList = document.getElementById('activeList');
            activeList.innerHTML = data.active_orchestrations.map(orch => `
                <div style="margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 4px;">
                    <strong>${orch.project_name}</strong> (${(orch.progress * 100).toFixed(1)}%)
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${orch.progress * 100}%"></div>
                    </div>
                </div>
            `).join('');
            
            // Update agent stats
            const agentStats = document.getElementById('agentStats');
            agentStats.innerHTML = data.agent_summary.map(agent => `
                <div style="margin: 5px 0;">
                    <strong>${agent.name}</strong>: ${agent.total_calls} calls, 
                    ${(agent.success_rate * 100).toFixed(1)}% success, 
                    ${agent.avg_response_time.toFixed(0)}ms avg
                </div>
            `).join('');
            
            // Update system health
            const cpuUsage = data.system_health.cpu_usage;
            const memUsage = data.system_health.memory_usage;
            
            if (cpuUsage.length > 0) {
                document.getElementById('cpuUsage').textContent = 
                    cpuUsage[cpuUsage.length - 1].value.toFixed(1) + '%';
            }
            
            if (memUsage.length > 0) {
                document.getElementById('memUsage').textContent = 
                    memUsage[memUsage.length - 1].value.toFixed(1) + '%';
            }
            
            // Update statistics
            document.getElementById('totalOrch').textContent = data.statistics.total_orchestrations;
            document.getElementById('totalCalls').textContent = data.statistics.total_agent_calls;
            
            // Update performance chart
            if (performanceChart && cpuUsage.length > 0) {
                const labels = cpuUsage.map(p => new Date(p.timestamp * 1000).toLocaleTimeString());
                const cpuData = cpuUsage.map(p => p.value);
                const memData = memUsage.map(p => p.value);
                
                performanceChart.data.labels = labels.slice(-20); // Last 20 points
                performanceChart.data.datasets[0].data = cpuData.slice(-20);
                performanceChart.data.datasets[1].data = memData.slice(-20);
                performanceChart.update();
            }
        }
        
        // Update dashboard every 5 seconds
        setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({type: 'get_dashboard_data'}));
            }
        }, 5000);
    </script>
</body>
</html>
    """)

@monitor_app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await metrics_collector.add_client(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "get_dashboard_data":
                await websocket.send_json({
                    "type": "dashboard_data",
                    "data": metrics_collector.get_dashboard_data()
                })
    except WebSocketDisconnect:
        await metrics_collector.remove_client(websocket)

async def start_monitoring_server(port: int = 8001):
    """Start the monitoring dashboard server."""
    import uvicorn
    
    logger.info(f"Starting ARGUS-V2 monitoring dashboard on port {port}")
    
    # Start system metrics collection
    asyncio.create_task(collect_system_metrics())
    
    config = uvicorn.Config(monitor_app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def collect_system_metrics():
    """Collect system performance metrics."""
    import psutil
    
    while True:
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
            
            metrics_collector.record_system_metric("cpu_percent", cpu_percent)
            metrics_collector.record_system_metric("memory_percent", memory_percent)
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
        
        await asyncio.sleep(5)

# Integration hooks for orchestrator
def track_orchestration_start(session_id: str, project_name: str, total_phases: int):
    """Hook to track orchestration start."""
    metrics_collector.record_orchestration_start(session_id, project_name, total_phases)

def track_orchestration_end(session_id: str, status: str):
    """Hook to track orchestration end."""
    metrics_collector.record_orchestration_end(session_id, status)

def track_phase_completion(session_id: str, phase_name: str, consensus_score: float):
    """Hook to track phase completion."""
    metrics_collector.record_phase_completion(session_id, phase_name, consensus_score)

def track_agent_call(agent_name: str, provider: str, response_time_ms: float, 
                    tokens_used: int, success: bool):
    """Hook to track agent calls."""
    metrics_collector.record_agent_call(agent_name, provider, response_time_ms, tokens_used, success)