"""
Enhanced Gateway with Connection Pooling
"""

import asyncio
from typing import Dict
import aiohttp

class ConnectionPool:
    """Manages persistent connections to LLM providers."""
    
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.pools: Dict[str, aiohttp.ClientSession] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
    
    async def get_session(self, provider: str) -> aiohttp.ClientSession:
        """Get or create a session for the provider."""
        if provider not in self.pools:
            if provider not in self._locks:
                self._locks[provider] = asyncio.Lock()
            
            async with self._locks[provider]:
                if provider not in self.pools:
                    connector = aiohttp.TCPConnector(
                        limit=self.max_connections,
                        limit_per_host=5,
                        ttl_dns_cache=300,
                        use_dns_cache=True
                    )
                    self.pools[provider] = aiohttp.ClientSession(
                        connector=connector,
                        timeout=aiohttp.ClientTimeout(total=30)
                    )
        
        return self.pools[provider]
    
    async def close_all(self):
        """Close all connection pools."""
        for session in self.pools.values():
            await session.close()
        self.pools.clear()

# Global connection pool instance
connection_pool = ConnectionPool()
