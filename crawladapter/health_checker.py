"""
CrawlAdapter Health Checker

Modern health checking system with strategy-based implementation.
Replaces the old separate HealthChecker and AdaptiveHealthChecker classes.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Union

from .types import HealthCheckResult, ProxyNode
from .health_strategies import (
    IHealthCheckStrategy,
    BasicHealthCheckStrategy,
    AdaptiveHealthCheckStrategy,
    HealthCheckConfig
)
from .exceptions import HealthCheckError


class HealthChecker:
    """
    Professional proxy health monitoring system with strategy-based implementation.

    Provides comprehensive health monitoring for proxy nodes with support for
    multiple monitoring strategies and real-time health assessment.
    """
    
    def __init__(
        self,
        strategy: Union[str, IHealthCheckStrategy] = 'basic',
        config: Optional[HealthCheckConfig] = None
    ):
        """
        Initialize health checker.
        
        Args:
            strategy: Health check strategy ('basic', 'adaptive', or custom strategy instance)
            config: Health check configuration
        """
        self.config = config or HealthCheckConfig()
        self.logger = logging.getLogger(__name__)
        
        # Initialize strategy
        if isinstance(strategy, str):
            self.strategy = self._create_strategy(strategy)
        elif isinstance(strategy, IHealthCheckStrategy):
            self.strategy = strategy
        else:
            raise ValueError(f"Invalid strategy type: {type(strategy)}")
        
        # Background checking for adaptive strategy
        self.background_task: Optional[asyncio.Task] = None
        self.is_background_running = False
    
    def _create_strategy(self, strategy_name: str) -> IHealthCheckStrategy:
        """Create strategy instance from name."""
        strategies = {
            'basic': BasicHealthCheckStrategy,
            'adaptive': AdaptiveHealthCheckStrategy
        }
        
        if strategy_name not in strategies:
            raise ValueError(f"Unknown strategy: {strategy_name}. Available: {list(strategies.keys())}")
        
        return strategies[strategy_name](self.config)
    
    async def check_proxy(self, proxy_name: str, clash_api_base: str) -> HealthCheckResult:
        """
        Check health of a single proxy.
        
        Args:
            proxy_name: Name of the proxy to check
            clash_api_base: Base URL for Clash API
            
        Returns:
            Health check result
        """
        try:
            return await self.strategy.check_proxy(proxy_name, clash_api_base)
        except Exception as e:
            self.logger.error(f"Health check failed for proxy {proxy_name}: {e}")
            raise HealthCheckError(
                f"Health check failed for proxy {proxy_name}",
                proxy_name=proxy_name,
                error_details=str(e)
            )
    
    async def check_all_proxies(
        self,
        proxies: List[ProxyNode],
        clash_api_base: str
    ) -> Dict[str, HealthCheckResult]:
        """
        Check health of all proxies.
        
        Args:
            proxies: List of proxy nodes to check
            clash_api_base: Base URL for Clash API
            
        Returns:
            Dictionary mapping proxy names to health check results
        """
        try:
            if not proxies:
                self.logger.warning("No proxies provided for health check")
                return {}
            
            self.logger.info(f"Starting health check for {len(proxies)} proxies")
            start_time = time.time()
            
            results = await self.strategy.check_all_proxies(proxies, clash_api_base)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Log summary
            healthy_count = sum(1 for result in results.values() if result.success)
            self.logger.info(
                f"Health check completed in {duration:.2f}s: "
                f"{healthy_count}/{len(proxies)} proxies healthy"
            )
            
            return results
            
        except Exception as e:
            self.logger.error(f"Health check failed for all proxies: {e}")
            raise HealthCheckError(
                "Health check failed for all proxies",
                error_details=str(e)
            )
    
    def get_healthy_proxies(
        self,
        proxies: List[ProxyNode],
        health_results: Dict[str, HealthCheckResult]
    ) -> List[ProxyNode]:
        """
        Filter proxies to return only healthy ones.
        
        Args:
            proxies: List of all proxy nodes
            health_results: Health check results
            
        Returns:
            List of healthy proxy nodes
        """
        healthy_proxies = []
        
        for proxy in proxies:
            result = health_results.get(proxy.name)
            if result and result.success:
                # Update proxy health information
                proxy.health_score = result.overall_score
                proxy.avg_latency = result.latency
                proxy.success_rate = result.success_rate
                proxy.last_checked = result.timestamp
                
                healthy_proxies.append(proxy)
        
        return healthy_proxies
    
    def get_health_summary(self, health_results: Dict[str, HealthCheckResult]) -> Dict:
        """
        Get summary statistics from health check results.
        
        Args:
            health_results: Health check results
            
        Returns:
            Summary statistics dictionary
        """
        if not health_results:
            return {
                'total_proxies': 0,
                'healthy_proxies': 0,
                'failed_proxies': 0,
                'health_rate': 0.0,
                'average_latency': 0.0,
                'average_success_rate': 0.0
            }
        
        total_proxies = len(health_results)
        healthy_proxies = sum(1 for result in health_results.values() if result.success)
        failed_proxies = total_proxies - healthy_proxies
        health_rate = healthy_proxies / total_proxies if total_proxies > 0 else 0.0
        
        # Calculate averages for healthy proxies only
        healthy_results = [result for result in health_results.values() if result.success]
        
        if healthy_results:
            average_latency = sum(result.latency for result in healthy_results) / len(healthy_results)
            average_success_rate = sum(result.success_rate for result in healthy_results) / len(healthy_results)
        else:
            average_latency = 0.0
            average_success_rate = 0.0
        
        return {
            'total_proxies': total_proxies,
            'healthy_proxies': healthy_proxies,
            'failed_proxies': failed_proxies,
            'health_rate': health_rate,
            'average_latency': average_latency,
            'average_success_rate': average_success_rate
        }
    
    # Adaptive strategy specific methods
    def get_proxy_health_info(self, proxy_name: str) -> Optional[Dict]:
        """
        Get detailed health information for a proxy (adaptive strategy only).
        
        Args:
            proxy_name: Name of the proxy
            
        Returns:
            Detailed health information or None if not available
        """
        if isinstance(self.strategy, AdaptiveHealthCheckStrategy):
            return self.strategy.get_proxy_health_info(proxy_name)
        return None
    
    def get_all_proxy_health_info(self) -> Dict[str, Dict]:
        """
        Get detailed health information for all tracked proxies (adaptive strategy only).
        
        Returns:
            Dictionary mapping proxy names to health information
        """
        if isinstance(self.strategy, AdaptiveHealthCheckStrategy):
            return {
                proxy_name: self.strategy.get_proxy_health_info(proxy_name)
                for proxy_name in self.strategy.proxy_histories.keys()
            }
        return {}
    
    async def start_background_checking(
        self,
        proxies: List[str],
        clash_api_base: str
    ) -> None:
        """
        Start background health checking (adaptive strategy only).
        
        Args:
            proxies: List of proxy names to monitor
            clash_api_base: Base URL for Clash API
        """
        if not isinstance(self.strategy, AdaptiveHealthCheckStrategy):
            self.logger.warning("Background checking only available with adaptive strategy")
            return
        
        if self.is_background_running:
            self.logger.warning("Background checking already running")
            return
        
        self.is_background_running = True
        self.background_task = asyncio.create_task(
            self._background_check_loop(proxies, clash_api_base)
        )
        self.logger.info(f"Started background health checking for {len(proxies)} proxies")
    
    async def stop_background_checking(self) -> None:
        """Stop background health checking."""
        if self.background_task:
            self.is_background_running = False
            self.background_task.cancel()
            try:
                await self.background_task
            except asyncio.CancelledError:
                pass
            self.background_task = None
            self.logger.info("Stopped background health checking")
    
    async def _background_check_loop(self, proxies: List[str], clash_api_base: str) -> None:
        """Background loop for adaptive health checking."""
        if not isinstance(self.strategy, AdaptiveHealthCheckStrategy):
            return
        
        # Initialize check schedule
        for proxy_name in proxies:
            next_check = time.time() + self.strategy.calculate_next_check_interval(proxy_name)
            self.strategy.check_queue.append((next_check, proxy_name))
        
        while self.is_background_running:
            try:
                current_time = time.time()
                
                # Process due checks
                due_checks = []
                remaining_checks = []
                
                for check_time, proxy_name in self.strategy.check_queue:
                    if check_time <= current_time:
                        due_checks.append(proxy_name)
                    else:
                        remaining_checks.append((check_time, proxy_name))
                
                self.strategy.check_queue = remaining_checks
                
                # Perform due health checks
                if due_checks:
                    tasks = [
                        self.strategy.check_proxy(proxy_name, clash_api_base)
                        for proxy_name in due_checks
                    ]
                    
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Schedule next checks
                    for proxy_name in due_checks:
                        next_check = current_time + self.strategy.calculate_next_check_interval(proxy_name)
                        self.strategy.check_queue.append((next_check, proxy_name))
                
                # Sleep until next check or 30 seconds, whichever is shorter
                if self.strategy.check_queue:
                    next_check_time = min(check_time for check_time, _ in self.strategy.check_queue)
                    sleep_time = min(30, max(1, next_check_time - current_time))
                else:
                    sleep_time = 30
                
                await asyncio.sleep(sleep_time)
            
            except Exception as e:
                self.logger.error(f"Error in background check loop: {e}")
                await asyncio.sleep(30)
    
    def __str__(self) -> str:
        """String representation."""
        strategy_name = self.strategy.__class__.__name__
        return f"HealthChecker(strategy={strategy_name})"



