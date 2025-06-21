"""
Fetcher Classes for CrawlAdapter

Consolidates NodeFetcher, HealthChecker, and AdaptiveHealthChecker functionality.
"""

import asyncio
import logging
import statistics
import time
import base64
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

import aiohttp
import yaml

from .core import HealthCheckResult, ProxyNode


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
    """Health history for a single proxy."""
    proxy_name: str
    scores: List[float] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)
    last_check: float = 0.0
    next_check: float = 0.0
    current_state: ProxyHealthState = ProxyHealthState.UNKNOWN
    check_count: int = 0
    
    def add_score(self, score: float, timestamp: float = None):
        """Add a new health score."""
        if timestamp is None:
            timestamp = time.time()
        
        self.scores.append(score)
        self.timestamps.append(timestamp)
        self.last_check = timestamp
        self.check_count += 1
        
        # Keep only recent history (last 24 hours)
        cutoff_time = timestamp - 86400
        while self.timestamps and self.timestamps[0] < cutoff_time:
            self.timestamps.pop(0)
            self.scores.pop(0)
    
    def get_average_score(self, window_size: int = 10) -> float:
        """Get average score over recent checks."""
        if not self.scores:
            return 0.0
        recent_scores = self.scores[-window_size:]
        return statistics.mean(recent_scores)
    
    def get_stability(self) -> float:
        """Calculate stability score based on score variance."""
        if len(self.scores) < 3:
            return 0.5  # Default for insufficient data
        
        recent_scores = self.scores[-10:]  # Last 10 checks
        if not recent_scores:
            return 0.5
        
        try:
            mean_score = statistics.mean(recent_scores)
            if mean_score == 0:
                return 0.0
            
            std_dev = statistics.stdev(recent_scores) if len(recent_scores) > 1 else 0
            cv = std_dev / mean_score  # Coefficient of variation
            
            # Convert to stability score (0-1, higher is better)
            stability = max(0, 1 - cv)
            return min(1, stability)
        except statistics.StatisticsError:
            return 0.5


class NodeFetcher:
    """
    Fetches proxy nodes from multiple sources with customizable sources.
    
    Consolidates node fetching functionality with enhanced flexibility.
    """

    def __init__(self, timeout: int = 30, max_retries: int = 3, custom_sources: Optional[Dict[str, List[str]]] = None):
        """
        Initialize the node fetcher.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            custom_sources: Custom node source URLs to override defaults
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
        
        # Default getNode project URLs
        self._default_sources = {
            'clash': [
                'https://raw.githubusercontent.com/Flikify/getNode/main/clash.yaml',
                'https://ghproxy.com/https://raw.githubusercontent.com/Flikify/getNode/main/clash.yaml',
                'https://cdn.jsdelivr.net/gh/Flikify/getNode@main/clash.yaml'
            ],
            'v2ray': [
                'https://raw.githubusercontent.com/Flikify/getNode/main/v2ray.txt',
                'https://ghproxy.com/https://raw.githubusercontent.com/Flikify/getNode/main/v2ray.txt',
                'https://cdn.jsdelivr.net/gh/Flikify/getNode@main/v2ray.txt'
            ]
        }
        
        # Use custom sources if provided, otherwise use defaults
        self.getnode_urls = custom_sources if custom_sources else self._default_sources.copy()
    
    def add_source(self, source_type: str, url: str, priority: int = 0) -> None:
        """Add a custom node source URL."""
        if source_type not in self.getnode_urls:
            self.getnode_urls[source_type] = []
        
        if priority == 0:
            # Insert at beginning for highest priority
            self.getnode_urls[source_type].insert(0, url)
        else:
            # Insert at appropriate position based on priority
            insert_pos = min(priority, len(self.getnode_urls[source_type]))
            self.getnode_urls[source_type].insert(insert_pos, url)
        
        self.logger.info(f"Added {source_type} source: {url} (priority: {priority})")
    
    def remove_source(self, source_type: str, url: str) -> bool:
        """Remove a node source URL."""
        if source_type in self.getnode_urls and url in self.getnode_urls[source_type]:
            self.getnode_urls[source_type].remove(url)
            self.logger.info(f"Removed {source_type} source: {url}")
            return True
        return False
    
    def get_sources(self) -> Dict[str, List[str]]:
        """Get current node sources."""
        return self.getnode_urls.copy()

    async def fetch_nodes(self, source_type: str = 'all') -> List[Dict]:
        """
        Fetch proxy nodes from configured sources.

        Args:
            source_type: Type of source to fetch ('clash', 'v2ray', or 'all')

        Returns:
            List of proxy node dictionaries
        """
        all_nodes = []
        
        if source_type == 'all':
            # Fetch from all source types
            for stype in self.getnode_urls.keys():
                nodes = await self._fetch_from_source_type(stype)
                all_nodes.extend(nodes)
        else:
            # Fetch from specific source type
            nodes = await self._fetch_from_source_type(source_type)
            all_nodes.extend(nodes)
        
        # Remove duplicates based on server+port
        unique_nodes = []
        seen = set()
        for node in all_nodes:
            key = f"{node.get('server', '')}:{node.get('port', 0)}"
            if key not in seen:
                seen.add(key)
                unique_nodes.append(node)
        
        self.logger.info(f"Fetched {len(unique_nodes)} unique nodes from {source_type} sources")
        return unique_nodes

    async def _fetch_from_source_type(self, source_type: str) -> List[Dict]:
        """Fetch nodes from a specific source type."""
        if source_type not in self.getnode_urls:
            self.logger.warning(f"Unknown source type: {source_type}")
            return []
        
        urls = self.getnode_urls[source_type]
        
        for url in urls:
            try:
                nodes = await self._fetch_from_url(url, source_type)
                if nodes:
                    self.logger.info(f"Successfully fetched {len(nodes)} nodes from {url}")
                    return nodes
            except Exception as e:
                self.logger.debug(f"Failed to fetch from {url}: {e}")
                continue
        
        self.logger.warning(f"Failed to fetch nodes from all {source_type} sources")
        return []

    async def _fetch_from_url(self, url: str, source_type: str) -> List[Dict]:
        """Fetch and parse nodes from a single URL."""
        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            content = await response.text()
                            
                            if source_type == 'clash':
                                return self._parse_clash_config(content)
                            elif source_type == 'v2ray':
                                return self._parse_v2ray_config(content)
                            
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise e
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        return []

    def _parse_clash_config(self, content: str) -> List[Dict]:
        """Parse Clash YAML configuration."""
        try:
            if self._is_html_content(content):
                self.logger.warning("Received HTML content instead of YAML config")
                return []
            if not content or len(content.strip()) < 50:
                self.logger.warning("Content is empty or too short to be a valid config")
                return []

            config = yaml.safe_load(content)

            if config is None:
                self.logger.warning("YAML parsing returned None - invalid YAML format")
                return []
            
            if not isinstance(config, dict):
                self.logger.warning(f"Config is not a dictionary, got {type(config)}")
                return []

            proxies = config.get('proxies', [])

            if not proxies:
                self.logger.warning("No proxies found in config")
                return []

            # Validate and clean proxy configurations
            valid_proxies = []
            for proxy in proxies:
                if isinstance(proxy, dict) and self._validate_proxy_config(proxy):
                    valid_proxies.append(proxy)

            self.logger.info(f"Successfully parsed {len(valid_proxies)} valid proxies from {len(proxies)} total")
            return valid_proxies

        except yaml.YAMLError as e:
            self.logger.error(f"YAML parsing error: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Failed to parse Clash config: {e}")
            return []

    def _is_html_content(self, content: str) -> bool:
        """Check if content is HTML instead of YAML."""
        content_lower = content.lower().strip()
        html_indicators = [
            '<html>', '<!doctype html>', '<head>', '<body>',
            '<!-- twitter cards -->', '<meta', '<title>'
        ]
        return any(indicator in content_lower for indicator in html_indicators)

    def _parse_v2ray_config(self, content: str) -> List[Dict]:
        """Parse V2Ray configuration and convert to Clash format."""
        try:
            # V2Ray configs are typically base64 encoded vmess:// URLs
            lines = content.strip().split('\n')
            proxies = []
            
            for line in lines:
                line = line.strip()
                if line.startswith('vmess://'):
                    try:
                        # Decode vmess URL
                        encoded = line[8:]  # Remove 'vmess://' prefix
                        decoded = base64.b64decode(encoded).decode('utf-8')
                        vmess_config = json.loads(decoded)
                        
                        # Convert to Clash format
                        clash_proxy = {
                            'name': vmess_config.get('ps', f"vmess_{len(proxies)}"),
                            'type': 'vmess',
                            'server': vmess_config.get('add', ''),
                            'port': int(vmess_config.get('port', 443)),
                            'uuid': vmess_config.get('id', ''),
                            'alterId': int(vmess_config.get('aid', 0)),
                            'cipher': 'auto',
                            'network': vmess_config.get('net', 'tcp'),
                            'tls': vmess_config.get('tls') == 'tls'
                        }
                        
                        if self._validate_proxy_config(clash_proxy):
                            proxies.append(clash_proxy)
                            
                    except Exception as e:
                        self.logger.debug(f"Failed to parse vmess URL: {e}")
                        continue
            
            return proxies
            
        except Exception as e:
            self.logger.error(f"Failed to parse V2Ray config: {e}")
            return []

    def _validate_proxy_config(self, proxy: Dict) -> bool:
        """Validate proxy configuration."""
        required_fields = ['name', 'type', 'server', 'port']
        
        for field in required_fields:
            if field not in proxy or not proxy[field]:
                return False
        
        # Validate port
        try:
            port = int(proxy['port'])
            if not (1 <= port <= 65535):
                return False
        except (ValueError, TypeError):
            return False
        
        # Validate server (basic check)
        server = proxy['server']
        if not server or server in ['localhost', '127.0.0.1', '0.0.0.0']:
            return False
        
        return True


class HealthChecker:
    """
    Simplified health checker with basic connectivity testing.

    Provides essential health checking functionality with improved reliability.
    """

    def __init__(self, timeout: int = 15, max_concurrent: int = 10):
        """Initialize health checker."""
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.logger = logging.getLogger(__name__)
        self.semaphore = asyncio.Semaphore(max_concurrent)

        self.test_endpoints = [
            'http://httpbin.org/ip',
            'http://www.gstatic.com/generate_204',
            'https://www.google.com/generate_204'
        ]

        self.test_urls = self.test_endpoints.copy()

    def set_test_urls(self, urls: List[str]) -> None:
        """Set custom test URLs for health checking."""
        self.test_urls = urls
        self.test_endpoints = urls.copy()  
        self.logger.info(f"Updated test URLs: {len(urls)} URLs")

    async def check_all_proxies(self, proxies: List[ProxyNode], clash_api_base: str) -> Dict[str, HealthCheckResult]:
        """Check health of all proxies."""
        tasks = []
        for proxy in proxies:
            task = self.check_proxy_health(proxy.name, clash_api_base)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        health_results = {}
        for proxy, result in zip(proxies, results):
            if isinstance(result, HealthCheckResult):
                health_results[proxy.name] = result
            else:
                # Create failed result
                health_results[proxy.name] = HealthCheckResult(
                    proxy_name=proxy.name,
                    success=False,
                    error=str(result) if result else "Unknown error"
                )
        
        return health_results

    async def check_proxy_health(self, proxy_name: str, clash_api_base: str) -> HealthCheckResult:
        """Check health of a single proxy with simplified logic."""
        async with self.semaphore:
            start_time = time.time()

            try:
                # Switch to the specific proxy
                switch_url = f"{clash_api_base}/proxies/PROXY"
                switch_data = {"name": proxy_name}

                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                    # Switch proxy
                    async with session.put(switch_url, json=switch_data) as response:
                        if response.status != 204:
                            return HealthCheckResult(
                                proxy_name=proxy_name,
                                success=False,
                                error="Failed to switch proxy"
                            )

                    # Wait for proxy switch
                    await asyncio.sleep(1)


                    success_count = 0
                    total_tests =  len(self.test_endpoints) 

                    for endpoint in self.test_endpoints[:total_tests]:
                        try:
                            proxy_url = "http://127.0.0.1:7890"
                            async with aiohttp.ClientSession(
                                timeout=aiohttp.ClientTimeout(total=8) 
                            ) as proxy_session:
                                async with proxy_session.get(endpoint, proxy=proxy_url) as test_response:
                                    if test_response.status in [200, 204]:
                                        success_count += 1
                                        break 
                        except:
                            continue

                    end_time = time.time()
                    latency = (end_time - start_time) * 1000
                    success_rate = success_count / total_tests if total_tests > 0 else 0
                    is_healthy = success_count > 0

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


class AdaptiveHealthChecker:
    """
    Advanced health checker with adaptive intervals based on proxy performance.
    
    Consolidates adaptive health checking functionality with intelligent scheduling.
    """

    def __init__(self, timeout: int = 15):
        """Initialize adaptive health checker."""
        self.timeout = timeout 
        self.logger = logging.getLogger(__name__)
        
        # Health tracking
        self.proxy_histories: Dict[str, ProxyHealthHistory] = {}
        self.check_queue: List[Tuple[float, str]] = []  # (next_check_time, proxy_name)
        self.is_running = False
        self.check_task: Optional[asyncio.Task] = None
        
        # Configuration
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
            ProxyHealthState.UNKNOWN: 0.5      # Check new proxies frequently
        }
        
        # Test endpoints - 
        self.test_endpoints = [
            'http://httpbin.org/ip',          
            'http://www.gstatic.com/generate_204',  
            'https://www.google.com/generate_204',  
            'http://detectportal.firefox.com/success.txt', 
            'http://www.msftconnecttest.com/connecttest.txt', 
        ]
        
        # Concurrency control
        self.semaphore = asyncio.Semaphore(10)

    def classify_health_state(self, proxy_name: str) -> ProxyHealthState:
        """Classify proxy health state based on recent performance."""
        if proxy_name not in self.proxy_histories:
            return ProxyHealthState.UNKNOWN
        
        history = self.proxy_histories[proxy_name]
        avg_score = history.get_average_score()
        is_stable = history.get_stability() >= 0.8
        
        # Classify based on score and stability
        if avg_score >= 0.9 and is_stable:
            return ProxyHealthState.EXCELLENT
        elif avg_score >= 0.7 and is_stable:
            return ProxyHealthState.GOOD
        elif avg_score >= 0.5:
            return ProxyHealthState.FAIR
        elif avg_score >= 0.3:
            return ProxyHealthState.POOR
        else:
            return ProxyHealthState.CRITICAL

    def calculate_next_check_interval(self, proxy_name: str) -> int:
        """Calculate adaptive check interval for a proxy."""
        state = self.classify_health_state(proxy_name)
        multiplier = self.interval_multipliers.get(state, 1.0)
        
        interval = int(self.base_interval * multiplier)
        
        # Apply bounds
        interval = max(self.min_interval, interval)
        interval = min(self.max_interval, interval)
        
        return interval

    async def start_adaptive_checking(self, proxies: List[str], clash_api_base: str) -> None:
        """Start adaptive health checking for a list of proxies."""
        self.is_running = True
        
        # Initialize check schedule for all proxies
        for proxy_name in proxies:
            self.schedule_next_check(proxy_name)
        
        # Start background checking task
        self.check_task = asyncio.create_task(self._adaptive_check_loop(clash_api_base))
        self.logger.info(f"Started adaptive health checking for {len(proxies)} proxies")

    def schedule_next_check(self, proxy_name: str) -> None:
        """Schedule the next health check for a proxy."""
        interval = self.calculate_next_check_interval(proxy_name)
        next_check_time = time.time() + interval
        
        # Update history
        if proxy_name in self.proxy_histories:
            self.proxy_histories[proxy_name].next_check = next_check_time
        
        # Add to check queue
        self.check_queue.append((next_check_time, proxy_name))
        self.check_queue.sort(key=lambda x: x[0])  # Sort by check time

    async def _adaptive_check_loop(self, clash_api_base: str) -> None:
        """Background loop for adaptive health checking."""
        while self.is_running:
            try:
                current_time = time.time()
                
                # Process due checks
                due_checks = []
                remaining_checks = []
                
                for check_time, proxy_name in self.check_queue:
                    if check_time <= current_time:
                        due_checks.append(proxy_name)
                    else:
                        remaining_checks.append((check_time, proxy_name))
                
                self.check_queue = remaining_checks
                
                # Perform due health checks
                if due_checks:
                    tasks = [
                        self.check_proxy_health(proxy_name, clash_api_base)
                        for proxy_name in due_checks
                    ]
                    
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Schedule next checks
                    for proxy_name in due_checks:
                        self.schedule_next_check(proxy_name)
                
                # Sleep until next check or 30 seconds, whichever is shorter
                if self.check_queue:
                    next_check_time = self.check_queue[0][0]
                    sleep_time = min(30, max(1, next_check_time - current_time))
                else:
                    sleep_time = 30
                
                await asyncio.sleep(sleep_time)
            
            except Exception as e:
                self.logger.error(f"Error in adaptive check loop: {e}")
                await asyncio.sleep(30)

    async def check_proxy_health(self, proxy_name: str, clash_api_base: str) -> HealthCheckResult:
        """Perform health check on a single proxy."""
        async with self.semaphore:
            # Use the same logic as HealthChecker but update history
            result = await self._perform_health_check(proxy_name, clash_api_base)
            
            # Update history
            self._update_health_history(proxy_name, result.overall_score)
            
            return result

    async def _perform_health_check(self, proxy_name: str, clash_api_base: str) -> HealthCheckResult:
        """Perform the actual health check."""
        start_time = time.time()
        
        try:
            # Switch to the specific proxy
            switch_url = f"{clash_api_base}/proxies/PROXY"
            switch_data = {"name": proxy_name}
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                # Switch proxy
                async with session.put(switch_url, json=switch_data) as response:
                    if response.status != 204:
                        return HealthCheckResult(
                            proxy_name=proxy_name,
                            success=False,
                            error="Failed to switch proxy"
                        )
                
                # Wait for proxy switch
                await asyncio.sleep(0.5)
                
                # Test connectivity 
                success_count = 0
                total_tests = len(self.test_endpoints)

                proxy_url = "http://127.0.0.1:7890"

                for endpoint in self.test_endpoints:
                    try:
                        async with aiohttp.ClientSession(
                            timeout=aiohttp.ClientTimeout(total=self.timeout)
                        ) as proxy_session:
                            async with proxy_session.get(endpoint, proxy=proxy_url) as test_response:
                                if test_response.status in [200, 204]:
                                    success_count += 1
                                    if 'httpbin.org/ip' in endpoint:
                                        try:
                                            data = await test_response.json()
                                            if 'origin' not in data:
                                                success_count -= 1 
                                        except:
                                            success_count -= 1  
                    except Exception:
                        continue
                
                end_time = time.time()
                latency = (end_time - start_time) * 1000  # Convert to ms
                success_rate = success_count / total_tests
                
                return HealthCheckResult(
                    proxy_name=proxy_name,
                    success=success_count > 0,
                    latency=latency,
                    connectivity=success_rate,
                    success_rate=success_rate,
                    overall_score=success_rate
                )
        
        except Exception as e:
            self.logger.warning(f"Adaptive health check failed for {proxy_name}: {e}")
            return HealthCheckResult(
                proxy_name=proxy_name,
                success=False, 
                latency=9999, 
                connectivity=0.0, 
                success_rate=0.0,
                overall_score=0.0, 
                error=str(e)
            )

    def _update_health_history(self, proxy_name: str, score: float) -> None:
        """Update health history for a proxy."""
        if proxy_name not in self.proxy_histories:
            self.proxy_histories[proxy_name] = ProxyHealthHistory(proxy_name)
        
        self.proxy_histories[proxy_name].add_score(score)
        
        # Update state
        new_state = self.classify_health_state(proxy_name)
        self.proxy_histories[proxy_name].current_state = new_state

    async def stop_adaptive_checking(self) -> None:
        """Stop adaptive health checking."""
        self.is_running = False
        if self.check_task:
            self.check_task.cancel()
            try:
                await self.check_task
            except asyncio.CancelledError:
                pass
