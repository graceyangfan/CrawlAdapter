"""
CrawlAdapter Health Check Strategies

Unified health checking system with strategy pattern implementation.
Eliminates code duplication between HealthChecker and AdaptiveHealthChecker.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

import aiohttp

from .types import HealthCheckResult, ProxyNode
from .exceptions import HealthCheckError


# ============================================================================
# Health Check Strategy Interface
# ============================================================================

class IHealthCheckStrategy(ABC):
    """Abstract interface for health check strategies."""
    
    @abstractmethod
    async def check_proxy(self, proxy_name: str, clash_api_base: str) -> HealthCheckResult:
        """Check health of a single proxy."""
        pass
    
    @abstractmethod
    async def check_all_proxies(self, proxies: List[ProxyNode], clash_api_base: str) -> Dict[str, HealthCheckResult]:
        """Check health of all proxies."""
        pass


# ============================================================================
# Health Check Configuration
# ============================================================================

@dataclass
class HealthCheckConfig:
    """Configuration for health checking."""
    timeout: int = 15
    max_concurrent: int = 10
    test_urls: List[str] = field(default_factory=lambda: [
        'http://httpbin.org/ip',
        'http://www.gstatic.com/generate_204',
        'https://www.google.com/generate_204'
    ])
    min_success_rate: float = 0.1
    retry_count: int = 3

    @classmethod
    def from_config_dict(cls, config_dict: Dict) -> 'HealthCheckConfig':
        """Create HealthCheckConfig from configuration dictionary."""
        health_config = config_dict.get('health_check', {})

        return cls(
            timeout=health_config.get('timeout', 15),
            max_concurrent=health_config.get('max_concurrent', 10),
            test_urls=health_config.get('test_urls', [
                'http://httpbin.org/ip',
                'http://www.gstatic.com/generate_204',
                'https://www.google.com/generate_204'
            ]),
            min_success_rate=health_config.get('min_success_rate', 0.1),
            retry_count=health_config.get('retry_count', 3)
        )


# ============================================================================
# Base Health Check Implementation
# ============================================================================

class BaseHealthChecker:
    """Base health checker with common functionality."""
    
    def __init__(self, config: HealthCheckConfig = None):
        """Initialize base health checker."""
        self.config = config or HealthCheckConfig()
        self.logger = logging.getLogger(__name__)
        self.semaphore = asyncio.Semaphore(self.config.max_concurrent)
    
    async def _perform_connectivity_test(self, proxy_name: str, clash_api_base: str) -> HealthCheckResult:
        """
        Perform the actual connectivity test.
        This is the core logic shared by all strategies.
        """
        start_time = time.time()
        
        try:
            # Switch to the specific proxy
            switch_url = f"{clash_api_base}/proxies/PROXY"
            switch_data = {"name": proxy_name}
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as session:
                # Switch proxy
                async with session.put(switch_url, json=switch_data) as response:
                    if response.status != 204:
                        return HealthCheckResult(
                            proxy_name=proxy_name,
                            success=False,
                            error="Failed to switch proxy"
                        )
                
                # Test connectivity with multiple URLs
                success_count = 0
                total_tests = len(self.config.test_urls)
                
                for test_url in self.config.test_urls:
                    try:
                        async with session.get(test_url, timeout=aiohttp.ClientTimeout(total=10)) as test_response:
                            if test_response.status == 200:
                                success_count += 1
                    except Exception:
                        # Individual test failure is expected
                        pass
                
                end_time = time.time()
                latency = (end_time - start_time) * 1000  # Convert to ms
                success_rate = success_count / total_tests if total_tests > 0 else 0
                is_healthy = success_rate >= self.config.min_success_rate
                
                return HealthCheckResult(
                    proxy_name=proxy_name,
                    success=is_healthy,
                    latency=latency,
                    connectivity=success_rate,
                    success_rate=success_rate,
                    overall_score=success_rate if is_healthy else 0.0
                )
        
        except Exception as e:
            self.logger.debug(f"Proxy {proxy_name} health check failed: {e}")
            return HealthCheckResult(
                proxy_name=proxy_name,
                success=False,
                latency=9999,
                connectivity=0.0,
                success_rate=0.0,
                overall_score=0.0,
                error=str(e)
            )


# ============================================================================
# Basic Health Check Strategy
# ============================================================================

class BasicHealthCheckStrategy(BaseHealthChecker, IHealthCheckStrategy):
    """Basic health check strategy with simple connectivity testing."""
    
    async def check_proxy(self, proxy_name: str, clash_api_base: str) -> HealthCheckResult:
        """Check health of a single proxy."""
        async with self.semaphore:
            return await self._perform_connectivity_test(proxy_name, clash_api_base)
    
    async def check_all_proxies(self, proxies: List[ProxyNode], clash_api_base: str) -> Dict[str, HealthCheckResult]:
        """Check health of all proxies concurrently."""
        tasks = []
        for proxy in proxies:
            task = self.check_proxy(proxy.name, clash_api_base)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        health_results = {}
        for proxy, result in zip(proxies, results):
            if isinstance(result, HealthCheckResult):
                health_results[proxy.name] = result
            else:
                # Create failed result for exceptions
                health_results[proxy.name] = HealthCheckResult(
                    proxy_name=proxy.name,
                    success=False,
                    error=str(result) if result else "Unknown error"
                )
        
        return health_results


# ============================================================================
# Adaptive Health Check Strategy
# ============================================================================

class ProxyHealthState(Enum):
    """Proxy health states for adaptive checking."""
    EXCELLENT = "excellent"  # > 0.9 score, stable
    GOOD = "good"           # > 0.7 score, stable
    FAIR = "fair"           # > 0.5 score
    POOR = "poor"           # > 0.3 score
    CRITICAL = "critical"   # <= 0.3 score
    UNKNOWN = "unknown"     # New proxy, no history


@dataclass
class ProxyHealthHistory:
    """Track health history for a proxy."""
    proxy_name: str
    scores: List[float] = field(default_factory=list)
    current_state: ProxyHealthState = ProxyHealthState.UNKNOWN
    last_check: float = 0.0
    check_count: int = 0
    max_history: int = 10
    
    def add_score(self, score: float) -> None:
        """Add a new health score."""
        self.scores.append(score)
        if len(self.scores) > self.max_history:
            self.scores.pop(0)
        
        self.last_check = time.time()
        self.check_count += 1
    
    @property
    def average_score(self) -> float:
        """Get average health score."""
        return sum(self.scores) / len(self.scores) if self.scores else 0.0
    
    @property
    def stability(self) -> float:
        """Calculate stability (lower variance = higher stability)."""
        if len(self.scores) < 2:
            return 0.0
        
        avg = self.average_score
        variance = sum((score - avg) ** 2 for score in self.scores) / len(self.scores)
        return max(0.0, 1.0 - variance)


class AdaptiveHealthCheckStrategy(BaseHealthChecker, IHealthCheckStrategy):
    """Adaptive health check strategy with intelligent scheduling."""
    
    def __init__(self, config: HealthCheckConfig = None):
        """Initialize adaptive health checker."""
        super().__init__(config)
        
        # Health tracking
        self.proxy_histories: Dict[str, ProxyHealthHistory] = {}
        self.check_queue: List[Tuple[float, str]] = []  # (next_check_time, proxy_name)
        self.is_running = False
        self.check_task: Optional[asyncio.Task] = None
        
        # Adaptive configuration
        self.base_interval = 300  # 5 minutes
        self.min_interval = 60    # 1 minute
        self.max_interval = 1800  # 30 minutes
        
        # Interval multipliers based on health state
        self.interval_multipliers = {
            ProxyHealthState.EXCELLENT: 2.0,   # Check less frequently
            ProxyHealthState.GOOD: 1.5,
            ProxyHealthState.FAIR: 1.0,        # Base interval
            ProxyHealthState.POOR: 0.5,        # Check more frequently
            ProxyHealthState.CRITICAL: 0.25,   # Check very frequently
            ProxyHealthState.UNKNOWN: 0.5      # Check frequently until classified
        }
    
    async def check_proxy(self, proxy_name: str, clash_api_base: str) -> HealthCheckResult:
        """Check health of a single proxy and update history."""
        async with self.semaphore:
            result = await self._perform_connectivity_test(proxy_name, clash_api_base)
            
            # Update history
            self._update_health_history(proxy_name, result.overall_score)
            
            return result
    
    async def check_all_proxies(self, proxies: List[ProxyNode], clash_api_base: str) -> Dict[str, HealthCheckResult]:
        """Check health of all proxies and update histories."""
        tasks = []
        for proxy in proxies:
            task = self.check_proxy(proxy.name, clash_api_base)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        health_results = {}
        for proxy, result in zip(proxies, results):
            if isinstance(result, HealthCheckResult):
                health_results[proxy.name] = result
            else:
                # Create failed result and update history
                failed_result = HealthCheckResult(
                    proxy_name=proxy.name,
                    success=False,
                    error=str(result) if result else "Unknown error"
                )
                self._update_health_history(proxy.name, 0.0)
                health_results[proxy.name] = failed_result
        
        return health_results
    
    def _update_health_history(self, proxy_name: str, score: float) -> None:
        """Update health history for a proxy."""
        if proxy_name not in self.proxy_histories:
            self.proxy_histories[proxy_name] = ProxyHealthHistory(proxy_name)
        
        self.proxy_histories[proxy_name].add_score(score)
        
        # Update state classification
        new_state = self._classify_health_state(proxy_name)
        self.proxy_histories[proxy_name].current_state = new_state
    
    def _classify_health_state(self, proxy_name: str) -> ProxyHealthState:
        """Classify proxy health state based on history."""
        if proxy_name not in self.proxy_histories:
            return ProxyHealthState.UNKNOWN
        
        history = self.proxy_histories[proxy_name]
        if not history.scores:
            return ProxyHealthState.UNKNOWN
        
        avg_score = history.average_score
        stability = history.stability
        
        # Classify based on average score and stability
        if avg_score > 0.9 and stability > 0.8:
            return ProxyHealthState.EXCELLENT
        elif avg_score > 0.7 and stability > 0.6:
            return ProxyHealthState.GOOD
        elif avg_score > 0.5:
            return ProxyHealthState.FAIR
        elif avg_score > 0.3:
            return ProxyHealthState.POOR
        else:
            return ProxyHealthState.CRITICAL
    
    def calculate_next_check_interval(self, proxy_name: str) -> int:
        """Calculate adaptive check interval for a proxy."""
        state = self._classify_health_state(proxy_name)
        multiplier = self.interval_multipliers.get(state, 1.0)
        
        interval = int(self.base_interval * multiplier)
        
        # Apply bounds
        interval = max(self.min_interval, interval)
        interval = min(self.max_interval, interval)
        
        return interval
    
    def get_proxy_health_info(self, proxy_name: str) -> Dict:
        """Get detailed health information for a proxy."""
        if proxy_name not in self.proxy_histories:
            return {
                'state': ProxyHealthState.UNKNOWN.value,
                'average_score': 0.0,
                'stability': 0.0,
                'check_count': 0,
                'last_check': 0.0
            }
        
        history = self.proxy_histories[proxy_name]
        return {
            'state': history.current_state.value,
            'average_score': history.average_score,
            'stability': history.stability,
            'check_count': history.check_count,
            'last_check': history.last_check,
            'recent_scores': history.scores[-5:] if history.scores else []
        }
