"""
Enhanced Health Checker Module

Provides comprehensive health checking for proxy nodes with multiple metrics,
historical tracking, and intelligent scoring algorithms.
"""

import asyncio
import logging
import statistics
import time
from typing import Dict, List, Optional, Tuple

import aiohttp


class EnhancedHealthChecker:
    """
    Enhanced health checking with multiple test endpoints and retry logic.

    Features:
    - Multiple endpoint testing
    - Latency measurement
    - Success rate tracking
    - Historical stability analysis
    - Intelligent scoring algorithms
    """

    def __init__(self, timeout: int = 10, max_concurrent: int = 10):
        """
        Initialize health checker.

        Args:
            timeout: Request timeout in seconds
            max_concurrent: Maximum concurrent health checks
        """
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.logger = logging.getLogger(__name__)

        self.test_endpoints = [
            'http://www.gstatic.com/generate_204',
            'http://httpbin.org/get',
            'http://www.google.com/generate_204',
            'http://detectportal.firefox.com/success.txt'
        ]

        # Historical health data
        self.health_scores = {}
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def check_all_proxies(self, proxies: List[Dict], clash_api_base: str) -> Dict[str, Dict]:
        """
        Check health of all proxies concurrently.

        Args:
            proxies: List of proxy configurations
            clash_api_base: Base URL for Clash API

        Returns:
            Dictionary mapping proxy names to health scores
        """
        tasks = []
        proxy_names = [proxy['name'] for proxy in proxies]

        for proxy_name in proxy_names:
            task = self._check_proxy_with_semaphore(proxy_name, clash_api_base)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        health_results = {}
        for proxy_name, result in zip(proxy_names, results):
            if isinstance(result, Exception):
                self.logger.error(f"Health check failed for {proxy_name}: {result}")
                health_results[proxy_name] = self._get_failed_scores()
            else:
                health_results[proxy_name] = result

        self.logger.info(f"Completed health checks for {len(proxy_names)} proxies")
        return health_results

    async def _check_proxy_with_semaphore(self, proxy_name: str, clash_api_base: str) -> Dict:
        """Check proxy health with semaphore for concurrency control."""
        async with self.semaphore:
            return await self.comprehensive_health_check(proxy_name, clash_api_base)

    async def comprehensive_health_check(self, proxy_name: str, clash_api_base: str) -> Dict:
        """
        Perform comprehensive health check with multiple metrics.

        Args:
            proxy_name: Name of the proxy to test
            clash_api_base: Base URL for Clash API

        Returns:
            Dictionary with health scores and metrics
        """
        scores = {
            'connectivity': 0.0,
            'latency': float('inf'),
            'success_rate': 0.0,
            'stability': 0.0,
            'overall_score': 0.0,
            'last_check': time.time()
        }

        # Test connectivity with multiple endpoints
        successful_tests = 0
        latencies = []

        for endpoint in self.test_endpoints:
            try:
                start_time = time.time()
                success = await self._test_endpoint_through_clash(
                    proxy_name, endpoint, clash_api_base
                )
                end_time = time.time()

                if success:
                    successful_tests += 1
                    latency_ms = (end_time - start_time) * 1000
                    latencies.append(latency_ms)

            except Exception as e:
                self.logger.debug(f"Health check failed for {proxy_name} on {endpoint}: {e}")

        # Calculate metrics
        if successful_tests > 0:
            scores['connectivity'] = successful_tests / len(self.test_endpoints)
            scores['success_rate'] = successful_tests / len(self.test_endpoints)
            scores['latency'] = statistics.mean(latencies)

        # Calculate stability from historical data
        scores['stability'] = self._calculate_stability(proxy_name, scores)

        # Calculate overall score
        scores['overall_score'] = self._calculate_overall_score(scores)

        # Update historical data
        self._update_health_history(proxy_name, scores)

        return scores

    async def _test_endpoint_through_clash(self, proxy_name: str, endpoint: str, clash_api_base: str) -> bool:
        """
        Test endpoint connectivity through Clash proxy.

        Args:
            proxy_name: Name of the proxy to use
            endpoint: URL to test
            clash_api_base: Base URL for Clash API

        Returns:
            True if test successful, False otherwise
        """
        try:
            # Switch to the specific proxy
            switch_url = f"{clash_api_base}/proxies/PROXY"
            switch_data = {"name": proxy_name}

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                # Switch proxy
                async with session.put(switch_url, json=switch_data) as response:
                    if response.status != 204:
                        self.logger.debug(f"Failed to switch to proxy {proxy_name}")
                        return False

                # Wait a moment for proxy switch to take effect
                await asyncio.sleep(0.5)

                # Test endpoint through proxy
                proxy_url = "http://127.0.0.1:7890"
                connector = aiohttp.TCPConnector()

                async with aiohttp.ClientSession(
                    connector=connector,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as proxy_session:
                    async with proxy_session.get(
                        endpoint,
                        proxy=proxy_url,
                        allow_redirects=False
                    ) as test_response:
                        return test_response.status in [200, 204]

        except Exception as e:
            self.logger.debug(f"Endpoint test failed for {proxy_name}: {e}")
            return False

    def _calculate_stability(self, proxy_name: str, current_scores: Dict) -> float:
        """
        Calculate stability score based on historical data.

        Args:
            proxy_name: Name of the proxy
            current_scores: Current health scores

        Returns:
            Stability score between 0 and 1
        """
        if proxy_name not in self.health_scores or len(self.health_scores[proxy_name]) < 3:
            return 0.5  # Default stability for new proxies

        history = self.health_scores[proxy_name]
        recent_scores = [record['scores']['success_rate'] for record in history[-10:]]

        if not recent_scores:
            return 0.5

        # Calculate coefficient of variation (lower is more stable)
        mean_score = statistics.mean(recent_scores)
        if mean_score == 0:
            return 0.0

        try:
            std_dev = statistics.stdev(recent_scores) if len(recent_scores) > 1 else 0
            cv = std_dev / mean_score

            # Convert to stability score (0-1, higher is better)
            stability = max(0, 1 - cv)
            return min(1, stability)

        except statistics.StatisticsError:
            return 0.5

    def _calculate_overall_score(self, scores: Dict) -> float:
        """
        Calculate overall health score from individual metrics.

        Args:
            scores: Dictionary with individual health scores

        Returns:
            Overall score between 0 and 1
        """
        connectivity = scores.get('connectivity', 0)
        success_rate = scores.get('success_rate', 0)
        stability = scores.get('stability', 0)
        latency = scores.get('latency', float('inf'))

        # Normalize latency score (lower latency is better)
        if latency == float('inf'):
            latency_score = 0
        else:
            # Score decreases as latency increases (good latency < 500ms)
            latency_score = max(0, 1 - (latency / 1000))

        # Weighted average of all metrics
        weights = {
            'connectivity': 0.3,
            'success_rate': 0.3,
            'latency': 0.2,
            'stability': 0.2
        }

        overall = (
            connectivity * weights['connectivity'] +
            success_rate * weights['success_rate'] +
            latency_score * weights['latency'] +
            stability * weights['stability']
        )

        return round(overall, 3)

    def _update_health_history(self, proxy_name: str, current_scores: Dict):
        """
        Update historical health data for stability analysis.

        Args:
            proxy_name: Name of the proxy
            current_scores: Current health scores
        """
        if proxy_name not in self.health_scores:
            self.health_scores[proxy_name] = []

        self.health_scores[proxy_name].append({
            'timestamp': time.time(),
            'scores': current_scores.copy()
        })

        # Keep only recent history (last 24 hours)
        cutoff_time = time.time() - 86400
        self.health_scores[proxy_name] = [
            record for record in self.health_scores[proxy_name]
            if record['timestamp'] > cutoff_time
        ]

    def _get_failed_scores(self) -> Dict:
        """Get default scores for failed health checks."""
        return {
            'connectivity': 0.0,
            'latency': float('inf'),
            'success_rate': 0.0,
            'stability': 0.0,
            'overall_score': 0.0,
            'last_check': time.time()
        }

    def get_best_proxies(self, health_results: Dict[str, Dict], count: int = 5) -> List[Tuple[str, float]]:
        """
        Get the best performing proxies based on health scores.

        Args:
            health_results: Health check results
            count: Number of best proxies to return

        Returns:
            List of tuples (proxy_name, overall_score) sorted by score
        """
        proxy_scores = [
            (name, scores.get('overall_score', 0))
            for name, scores in health_results.items()
            if scores.get('overall_score', 0) > 0
        ]

        # Sort by overall score (descending)
        proxy_scores.sort(key=lambda x: x[1], reverse=True)

        return proxy_scores[:count]

    def get_proxy_statistics(self) -> Dict:
        """
        Get overall statistics about proxy health.

        Returns:
            Dictionary with health statistics
        """
        if not self.health_scores:
            return {'total_proxies': 0, 'healthy_proxies': 0, 'average_score': 0}

        total_proxies = len(self.health_scores)
        healthy_proxies = 0
        total_score = 0

        for proxy_name, history in self.health_scores.items():
            if history:
                latest_score = history[-1]['scores'].get('overall_score', 0)
                total_score += latest_score
                if latest_score > 0.5:  # Consider healthy if score > 0.5
                    healthy_proxies += 1

        average_score = total_score / total_proxies if total_proxies > 0 else 0

        return {
            'total_proxies': total_proxies,
            'healthy_proxies': healthy_proxies,
            'average_score': round(average_score, 3),
            'health_rate': round(healthy_proxies / total_proxies, 3) if total_proxies > 0 else 0
        }
