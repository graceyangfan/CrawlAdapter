"""
Unified Proxy Configuration Manager

Manages proxy configurations from multiple sources with intelligent
load balancing, health-based selection, and automatic failover.
"""

import asyncio
import logging
import random
import time
from typing import Dict, List, Optional, Set

from .node_fetcher import NodeFetcher


class UnifiedProxyConfigManager:
    """
    Unified manager for different proxy source types.

    Features:
    - Multiple proxy source integration
    - Health-based proxy selection
    - Load balancing strategies
    - Automatic failover
    - Proxy rotation management
    """

    def __init__(self, node_fetcher: Optional[NodeFetcher] = None):
        """
        Initialize proxy configuration manager.

        Args:
            node_fetcher: NodeFetcher instance for fetching nodes
        """
        self.node_fetcher = node_fetcher or NodeFetcher()
        self.logger = logging.getLogger(__name__)

        # Proxy management state
        self.active_proxies = []
        self.healthy_proxies = set()
        self.failed_proxies = set()
        self.proxy_health_scores = {}
        self.last_update = 0
        self.update_interval = 3600  # 1 hour

        # Load balancing state
        self.current_proxy_index = 0
        self.proxy_usage_count = {}
        self.proxy_last_used = {}

    async def initialize(self, source_types: List[str] = None) -> bool:
        """
        Initialize proxy manager by fetching nodes from sources.

        Args:
            source_types: List of source types to fetch ('clash', 'v2ray', 'all')

        Returns:
            True if initialization successful
        """
        if source_types is None:
            source_types = ['all']

        try:
            all_proxies = []

            for source_type in source_types:
                proxies = await self.node_fetcher.fetch_nodes(source_type)
                validated_proxies = await self.node_fetcher.validate_nodes(proxies)
                all_proxies.extend(validated_proxies)

            # Remove duplicates based on server and port
            unique_proxies = self._remove_duplicate_proxies(all_proxies)

            self.active_proxies = unique_proxies
            self.last_update = time.time()

            # Initialize proxy tracking
            for proxy in self.active_proxies:
                proxy_name = proxy['name']
                self.proxy_usage_count[proxy_name] = 0
                self.proxy_last_used[proxy_name] = 0

            self.logger.info(f"Initialized with {len(self.active_proxies)} unique proxies")
            return len(self.active_proxies) > 0

        except Exception as e:
            self.logger.error(f"Failed to initialize proxy manager: {e}")
            return False

    def _remove_duplicate_proxies(self, proxies: List[Dict]) -> List[Dict]:
        """
        Remove duplicate proxies based on server and port.

        Args:
            proxies: List of proxy configurations

        Returns:
            List of unique proxies
        """
        seen = set()
        unique_proxies = []

        for proxy in proxies:
            key = (proxy.get('server'), proxy.get('port'), proxy.get('type'))
            if key not in seen:
                seen.add(key)
                unique_proxies.append(proxy)

        self.logger.info(f"Removed {len(proxies) - len(unique_proxies)} duplicate proxies")
        return unique_proxies

    async def update_proxies(self, force: bool = False) -> bool:
        """
        Update proxy list if needed.

        Args:
            force: Force update regardless of interval

        Returns:
            True if update was performed
        """
        current_time = time.time()

        if not force and (current_time - self.last_update) < self.update_interval:
            return False

        self.logger.info("Updating proxy list...")
        return await self.initialize()

    def update_proxy_health(self, health_results: Dict[str, Dict]):
        """
        Update proxy health information.

        Args:
            health_results: Health check results from EnhancedHealthChecker
        """
        self.proxy_health_scores = health_results

        # Update healthy and failed proxy sets
        self.healthy_proxies.clear()
        self.failed_proxies.clear()

        for proxy_name, health_data in health_results.items():
            overall_score = health_data.get('overall_score', 0)

            if overall_score > 0.3:  # Threshold for healthy proxy
                self.healthy_proxies.add(proxy_name)
            else:
                self.failed_proxies.add(proxy_name)

        self.logger.info(f"Updated health: {len(self.healthy_proxies)} healthy, {len(self.failed_proxies)} failed")

    def get_best_proxy(self, strategy: str = 'health_weighted') -> Optional[Dict]:
        """
        Get the best proxy based on specified strategy.

        Args:
            strategy: Selection strategy ('health_weighted', 'round_robin', 'least_used', 'random')

        Returns:
            Best proxy configuration or None
        """
        if not self.active_proxies:
            return None

        if strategy == 'health_weighted':
            return self._get_health_weighted_proxy()
        elif strategy == 'round_robin':
            return self._get_round_robin_proxy()
        elif strategy == 'least_used':
            return self._get_least_used_proxy()
        elif strategy == 'random':
            return self._get_random_proxy()
        else:
            self.logger.warning(f"Unknown strategy {strategy}, using health_weighted")
            return self._get_health_weighted_proxy()

    def _get_health_weighted_proxy(self) -> Optional[Dict]:
        """Get proxy using health-weighted selection."""
        if not self.healthy_proxies:
            # Fallback to any available proxy if no healthy ones
            return self._get_random_proxy()

        # Create weighted list based on health scores
        weighted_proxies = []

        for proxy in self.active_proxies:
            proxy_name = proxy['name']
            if proxy_name in self.healthy_proxies:
                health_score = self.proxy_health_scores.get(proxy_name, {}).get('overall_score', 0.1)
                # Add proxy multiple times based on health score
                weight = max(1, int(health_score * 10))
                weighted_proxies.extend([proxy] * weight)

        if weighted_proxies:
            selected = random.choice(weighted_proxies)
            self._update_proxy_usage(selected['name'])
            return selected

        return None

    def _get_round_robin_proxy(self) -> Optional[Dict]:
        """Get proxy using round-robin selection."""
        if not self.active_proxies:
            return None

        # Filter to healthy proxies if available
        available_proxies = [
            proxy for proxy in self.active_proxies
            if proxy['name'] in self.healthy_proxies
        ] if self.healthy_proxies else self.active_proxies

        if not available_proxies:
            return None

        proxy = available_proxies[self.current_proxy_index % len(available_proxies)]
        self.current_proxy_index += 1
        self._update_proxy_usage(proxy['name'])

        return proxy

    def _get_least_used_proxy(self) -> Optional[Dict]:
        """Get the least used proxy."""
        if not self.active_proxies:
            return None

        # Filter to healthy proxies if available
        available_proxies = [
            proxy for proxy in self.active_proxies
            if proxy['name'] in self.healthy_proxies
        ] if self.healthy_proxies else self.active_proxies

        if not available_proxies:
            return None

        # Find proxy with minimum usage count
        min_usage = min(
            self.proxy_usage_count.get(proxy['name'], 0)
            for proxy in available_proxies
        )

        least_used_proxies = [
            proxy for proxy in available_proxies
            if self.proxy_usage_count.get(proxy['name'], 0) == min_usage
        ]

        selected = random.choice(least_used_proxies)
        self._update_proxy_usage(selected['name'])

        return selected

    def _get_random_proxy(self) -> Optional[Dict]:
        """Get a random proxy."""
        if not self.active_proxies:
            return None

        # Prefer healthy proxies if available
        available_proxies = [
            proxy for proxy in self.active_proxies
            if proxy['name'] in self.healthy_proxies
        ] if self.healthy_proxies else self.active_proxies

        if not available_proxies:
            return None

        selected = random.choice(available_proxies)
        self._update_proxy_usage(selected['name'])

        return selected

    def _update_proxy_usage(self, proxy_name: str):
        """Update proxy usage statistics."""
        self.proxy_usage_count[proxy_name] = self.proxy_usage_count.get(proxy_name, 0) + 1
        self.proxy_last_used[proxy_name] = time.time()

    def get_proxy_by_name(self, proxy_name: str) -> Optional[Dict]:
        """
        Get specific proxy by name.

        Args:
            proxy_name: Name of the proxy

        Returns:
            Proxy configuration or None
        """
        for proxy in self.active_proxies:
            if proxy['name'] == proxy_name:
                self._update_proxy_usage(proxy_name)
                return proxy

        return None

    def get_proxy_statistics(self) -> Dict:
        """
        Get proxy usage and health statistics.

        Returns:
            Dictionary with proxy statistics
        """
        total_proxies = len(self.active_proxies)
        healthy_count = len(self.healthy_proxies)
        failed_count = len(self.failed_proxies)

        # Calculate usage statistics
        total_usage = sum(self.proxy_usage_count.values())
        avg_usage = total_usage / total_proxies if total_proxies > 0 else 0

        # Find most and least used proxies
        most_used = max(self.proxy_usage_count.items(), key=lambda x: x[1]) if self.proxy_usage_count else ("", 0)
        least_used = min(self.proxy_usage_count.items(), key=lambda x: x[1]) if self.proxy_usage_count else ("", 0)

        return {
            'total_proxies': total_proxies,
            'healthy_proxies': healthy_count,
            'failed_proxies': failed_count,
            'health_rate': healthy_count / total_proxies if total_proxies > 0 else 0,
            'total_usage': total_usage,
            'average_usage': avg_usage,
            'most_used_proxy': most_used[0],
            'most_used_count': most_used[1],
            'least_used_proxy': least_used[0],
            'least_used_count': least_used[1],
            'last_update': self.last_update
        }

    def generate_clash_config(self, config_type: str = 'scraping') -> Dict:
        """
        Generate Clash configuration with current proxies.

        Args:
            config_type: Type of configuration to generate

        Returns:
            Complete Clash configuration
        """
        if not self.active_proxies:
            raise ValueError("No active proxies available for configuration generation")

        from .config_manager import ConfigurationManager

        config_manager = ConfigurationManager()
        return config_manager.generate_clash_config(self.active_proxies, config_type)

    def get_healthy_proxy_names(self) -> List[str]:
        """
        Get list of healthy proxy names.

        Returns:
            List of healthy proxy names
        """
        return list(self.healthy_proxies)

    def mark_proxy_failed(self, proxy_name: str):
        """
        Mark a proxy as failed.

        Args:
            proxy_name: Name of the proxy to mark as failed
        """
        self.healthy_proxies.discard(proxy_name)
        self.failed_proxies.add(proxy_name)
        self.logger.warning(f"Marked proxy {proxy_name} as failed")

    def reset_proxy_status(self, proxy_name: str):
        """
        Reset proxy status (remove from failed list).

        Args:
            proxy_name: Name of the proxy to reset
        """
        self.failed_proxies.discard(proxy_name)
        self.logger.info(f"Reset status for proxy {proxy_name}")
