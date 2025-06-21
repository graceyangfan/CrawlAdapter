"""
CrawlAdapter Core Module

Contains the main ProxyClient class, type definitions, and exceptions.
This is the central module that users interact with.
"""

import asyncio
import logging
import os
import platform
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import aiohttp


# ============================================================================
# Type Definitions and Enums
# ============================================================================

class ProxyType(Enum):
    """Supported proxy types."""
    VMESS = "vmess"
    VLESS = "vless"
    SHADOWSOCKS = "ss"
    TROJAN = "trojan"
    HTTP = "http"
    SOCKS5 = "socks5"


class LoadBalanceStrategy(Enum):
    """Load balancing strategies."""
    HEALTH_WEIGHTED = "health_weighted"
    ROUND_ROBIN = "round_robin"
    LEAST_USED = "least_used"
    RANDOM = "random"


class ConfigType(Enum):
    """Configuration types."""
    SCRAPING = "scraping"
    SPEED = "speed"
    GENERAL = "general"


@dataclass
class ProxyNode:
    """Standardized proxy node information."""
    name: str
    server: str
    port: int
    type: ProxyType
    config: Dict
    
    # Health and usage tracking
    health_score: float = 0.0
    last_checked: Optional[datetime] = None
    usage_count: int = 0
    last_used: Optional[datetime] = None
    
    # Performance metrics
    avg_latency: float = 0.0
    success_rate: float = 0.0
    
    def __post_init__(self):
        """Post-initialization processing."""
        if isinstance(self.type, str):
            self.type = ProxyType(self.type)
    
    @property
    def is_healthy(self) -> bool:
        """Check if proxy is considered healthy."""
        # Lower health threshold to consider more proxies as healthy
        return self.health_score > 0.1
    
    @property
    def proxy_url(self) -> str:
        """Get proxy URL for HTTP clients."""
        return f"http://127.0.0.1:7890"  # Standard Clash proxy port
    
    def to_dict(self) -> Dict:
        """Convert to dictionary format."""
        return {
            'name': self.name,
            'server': self.server,
            'port': self.port,
            'type': self.type.value,
            **self.config
        }


@dataclass
class HealthCheckResult:
    """Health check result for a proxy."""
    proxy_name: str
    success: bool
    latency: float = 0.0
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Detailed metrics
    connectivity: float = 0.0
    success_rate: float = 0.0
    stability: float = 0.0
    overall_score: float = 0.0


@dataclass
class ProxyStats:
    """Proxy usage and performance statistics."""
    total_proxies: int
    healthy_proxies: int
    failed_proxies: int
    health_rate: float
    
    # Usage statistics
    total_usage: int
    average_usage: float
    most_used_proxy: str
    most_used_count: int
    least_used_proxy: str
    least_used_count: int
    
    # Timing
    last_update: float
    last_health_check: float


# ============================================================================
# Exception Classes
# ============================================================================

class CrawlAdapterError(Exception):
    """Base exception for CrawlAdapter."""
    pass


class ProxyNotAvailableError(CrawlAdapterError):
    """Raised when no healthy proxies are available."""
    pass


class ConfigurationError(CrawlAdapterError):
    """Raised when there's a configuration error."""
    pass


class HealthCheckError(CrawlAdapterError):
    """Raised when health check fails."""
    pass


class NodeFetchError(CrawlAdapterError):
    """Raised when node fetching fails."""
    pass


class RuleError(CrawlAdapterError):
    """Raised when there's a rule-related error."""
    pass


# ============================================================================
# Type Aliases
# ============================================================================

ProxyDict = Dict[str, Union[str, int, Dict]]
HealthResults = Dict[str, HealthCheckResult]
ProxyList = List[ProxyNode]
RuleList = List[str]


# ============================================================================
# Main ProxyClient Class
# ============================================================================

class ProxyClient:
    """
    Universal proxy client for web scraping and HTTP requests.

    Features:
    - Custom routing rules for selective proxy usage
    - Automatic proxy node fetching and validation
    - Health monitoring and intelligent selection
    - Multiple load balancing strategies
    - Automatic failover and recovery
    - Framework-agnostic integration
    """

    def __init__(
        self,
        config_dir: str = './clash_configs',
        clash_binary_path: Optional[str] = None,
        auto_update_interval: int = 3600,
        enable_default_rules: bool = True,
        enable_adaptive_health_check: bool = False,  # Simplified: disable adaptive health check by default
        enable_metrics: bool = False  # Simplified: disable monitoring by default
    ):
        """
        Initialize the proxy client.

        Args:
            config_dir: Directory for storing configurations
            clash_binary_path: Path to Clash binary (auto-detected if None)
            auto_update_interval: Interval for automatic proxy updates (seconds)
            enable_default_rules: Whether to load default routing rules
            enable_adaptive_health_check: Use adaptive health checking (simplified)
            enable_metrics: Enable performance metrics collection (simplified)
        """
        self.config_dir = Path(config_dir).resolve()  # 使用绝对路径
        self.clash_binary_path = clash_binary_path
        self.auto_update_interval = auto_update_interval
        self.enable_default_rules = enable_default_rules
        self.enable_adaptive_health_check = enable_adaptive_health_check
        self.enable_metrics = enable_metrics

        # Initialize logger
        self.logger = logging.getLogger(__name__)

        # State management
        self.is_running = False
        self.clash_process = None
        self.proxy_port = 7890
        self.api_port = 9090
        self.clash_api_base = f"http://127.0.0.1:{self.api_port}"

        # Background tasks
        self.health_check_task = None
        self.auto_update_task = None
        self.last_health_check = 0

        # Simplified: directly initialize core components, reduce dependency injection complexity
        self.config_manager = None
        self.proxy_manager = None
        self.rule_manager = None
        self.health_checker = None
        self.metrics_collector = None

        # Simplified: directly manage proxy nodes
        self.active_proxies: List[ProxyNode] = []
        self.current_rules: List[str] = []

        # Create config directory
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Auto-detect binary and config paths if not provided
        if not self.clash_binary_path:
            self.clash_binary_path = self._find_clash_binary()

        # Health check URLs
        self.health_check_urls: List[str] = [
            'http://httpbin.org/ip',
            'http://www.gstatic.com/generate_204',
            'https://www.google.com/generate_204'
        ]

    def set_health_check_urls(self, urls: List[str]) -> None:
        """Set custom health check URLs."""
        self.health_check_urls = urls
        self.logger.info(f"Updated health check URLs: {len(urls)} URLs")

    async def _kill_existing_clash(self) -> None:
        """kill clash """
        try:
            if platform.system() == 'Windows':
                subprocess.run(['taskkill', '/f', '/im', 'clash.exe'],
                             capture_output=True, check=False)
                subprocess.run(['taskkill', '/f', '/im', 'mihomo.exe'],
                             capture_output=True, check=False)
            else:
                subprocess.run(['pkill', '-f', 'clash'],
                             capture_output=True, check=False)
                subprocess.run(['pkill', '-f', 'mihomo'],
                             capture_output=True, check=False)

            self.logger.info("Killed existing Clash processes")
            await asyncio.sleep(2) 

        except Exception as e:
            self.logger.debug(f"Error killing existing Clash: {e}")

    def _find_clash_binary(self) -> Optional[str]:
        """find  clash binary """
        if self.clash_binary_path:
            path = Path(self.clash_binary_path)
            if path.exists():
                abs_path = str(path.resolve())
                self.logger.info(f"Using specified binary: {abs_path}")
                return abs_path
        is_windows = platform.system() == 'Windows'
        possible_paths = []

        local_dirs = ['./mihomo_proxy', '../mihomo_proxy', './clash', '../clash']

        for local_dir in local_dirs:
            base_path = Path(local_dir)
            if is_windows:
                possible_paths.extend([
                    base_path / 'mihomo.exe',
                    base_path / 'clash.exe'
                ])
            else:
                possible_paths.extend([
                    base_path / 'mihomo',
                    base_path / 'clash'
                ])


        if not is_windows:
            system_paths = [
                Path('/usr/local/bin/mihomo'),
                Path('/usr/bin/mihomo'),
                Path('/usr/local/bin/clash'),
                Path('/usr/bin/clash'),
                Path.home() / 'mihomo',
                Path.home() / 'clash'
            ]
            possible_paths.extend(system_paths)
        for path in possible_paths:
            abs_path = path.resolve()
            if abs_path.exists():
                self.logger.info(f"Found local binary: {abs_path}")
                return str(abs_path)


        import shutil
        for binary_name in ['mihomo', 'clash']:
            binary_path = shutil.which(binary_name)
            if binary_path:
                abs_path = str(Path(binary_path).resolve())
                self.logger.info(f"Found binary in PATH: {abs_path}")
                return abs_path

        self.logger.warning(f"No Clash/Mihomo binary found for {platform.system()}")
        self.logger.info("Searched locations:")
        for path in possible_paths[:5]: 
            self.logger.info(f"  - {path.resolve()}")
        return None

    def _find_clash_config(self) -> Optional[str]:
        """
        Find clash config file using absolute paths.

        Returns:
            Absolute path to config file or None if not found
        """
        # Get the package installation directory
        package_dir = Path(__file__).parent.parent.resolve()

        # Check possible config file locations with absolute paths
        config_dirs = [
            self.config_dir,  # User specified config directory
            package_dir / 'clash_configs',  # Package config directory
            Path.cwd() / 'clash_configs',  # Current working directory
            Path.cwd().parent / 'clash_configs',  # Parent directory
        ]

        config_files = ['config.yaml', 'config.yml', 'clash.yaml', 'clash.yml']

        for config_dir in config_dirs:
            if config_dir.exists() and config_dir.is_dir():
                for config_file in config_files:
                    config_path = config_dir / config_file
                    if config_path.exists() and config_path.is_file():
                        abs_path = str(config_path.resolve())
                        self.logger.info(f"Found clash config: {abs_path}")
                        return abs_path

        self.logger.warning("No clash config file found")
        self.logger.info("Searched locations:")
        for config_dir in config_dirs:
            for config_file in config_files:
                self.logger.info(f"  - {(config_dir / config_file).resolve()}")
        return None

    async def _fetch_proxy_nodes(self, source_types: List[str] = None) -> bool:
        """Simplified proxy node fetching method."""
        try:
            self.logger.info("🔍 Fetching proxy nodes...")

            # Use NodeFetcher to get nodes
            nodes = await self.node_fetcher.fetch_nodes('all')

            if not nodes:
                self.logger.error("No nodes fetched")
                return False

            # Convert to ProxyNode objects
            self.active_proxies = []
            for i, node in enumerate(nodes):
                try:
                    proxy_node = ProxyNode(
                        name=node.get('name', f'proxy_{i}'),
                        server=node.get('server', ''),
                        port=node.get('port', 443),
                        type=node.get('type', 'vmess'),
                        config=node
                    )
                    self.active_proxies.append(proxy_node)
                except Exception as e:
                    self.logger.warning(f"Failed to create proxy node {i}: {e}")

            self.logger.info(f"✅ Fetched {len(self.active_proxies)} proxy nodes")
            return len(self.active_proxies) > 0

        except Exception as e:
            self.logger.error(f"❌ Failed to fetch nodes: {e}")
            return False

    async def _health_check_nodes(self) -> List[ProxyNode]:
        """health check """
        try:
            self.logger.info("🏥 Performing health check...")

            healthy_nodes = []
            for node in self.active_proxies:
                try:
                    import socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    result = sock.connect_ex((node.server, node.port))
                    sock.close()

                    if result == 0:
                        healthy_nodes.append(node)
                        self.logger.debug(f"✅ {node.name}: TCP connection OK")
                    else:
                        self.logger.debug(f"❌ {node.name}: TCP connection failed")

                except Exception as e:
                    self.logger.debug(f"❌ {node.name}: Health check error - {e}")

            self.logger.info(f"✅ Health check completed: {len(healthy_nodes)}/{len(self.active_proxies)} nodes healthy")
            return healthy_nodes

        except Exception as e:
            self.logger.error(f"❌ Health check failed: {e}")
            return []

    def _generate_clash_config(self, nodes: List[ProxyNode], rules: List[str], config_type: str = 'scraping') -> Dict:
        """generate clash config """
        unique_nodes = []
        used_names = set()

        for i, node in enumerate(nodes):
            original_name = node.name
            name = original_name
            counter = 1

            while name in used_names:
                name = f"{original_name}_{counter}"
                counter += 1

            node.name = name
            node.config['name'] = name
            used_names.add(name)
            unique_nodes.append(node.config)

        # Generate configuration
        config = {
            'mixed-port': self.proxy_port,
            'allow-lan': False,
            'mode': 'rule',
            'log-level': 'info',
            'external-controller': f'127.0.0.1:{self.api_port}',
            'ipv6': True,
            'dns': {
                'enable': True,
                'nameserver': ['8.8.8.8', '1.1.1.1', '114.114.114.114'],
                'fallback': ['8.8.4.4', '1.0.0.1'],
                'enhanced-mode': 'fake-ip',
                'fake-ip-range': '198.18.0.1/16'
            },
            'proxies': unique_nodes,
            'proxy-groups': [
                {
                    'name': 'PROXY',
                    'type': 'select',
                    'proxies': [node['name'] for node in unique_nodes] + ['DIRECT']
                },
                {
                    'name': 'AUTO',
                    'type': 'url-test',
                    'proxies': [node['name'] for node in unique_nodes] if unique_nodes else ['DIRECT'],
                    'url': 'http://www.gstatic.com/generate_204',
                    'interval': 300,
                    'tolerance': 50
                }
            ],
            'rules': self._generate_rules(rules)
        }

        return config

    def _generate_rules(self, custom_rules: List[str]) -> List[str]:
        """rule generation """
        rules = []

        # 1. direct connection
        rules.extend([
            'IP-CIDR,127.0.0.0/8,DIRECT',
            'IP-CIDR,172.16.0.0/12,DIRECT',
            'IP-CIDR,192.168.0.0/16,DIRECT',
            'IP-CIDR,10.0.0.0/8,DIRECT',
            'DOMAIN-SUFFIX,local,DIRECT'
        ])

        # 2. user defined rules
        for rule in custom_rules:
            if rule.startswith('*.'):
                domain = rule[2:]
                rules.append(f'DOMAIN-SUFFIX,{domain},PROXY')
            elif '/' in rule:
                rules.append(f'IP-CIDR,{rule},PROXY')
            else:
                rules.append(f'DOMAIN-SUFFIX,{rule},PROXY')

        # 3. health check
        health_domains = [
            'httpbin.org',
            'www.gstatic.com',
            'gstatic.com',
            'google.com',
            'www.google.com'
        ]
        for domain in health_domains:
            rules.append(f'DOMAIN-SUFFIX,{domain},PROXY')

        # 4. chinese domains
        direct_domains = [
            'baidu.com', 'qq.com', 'taobao.com', 'jd.com',
            '163.com', 'sina.com.cn', 'weibo.com', 'zhihu.com'
        ]
        for domain in direct_domains:
            rules.append(f'DOMAIN-SUFFIX,{domain},DIRECT')

        # 5. chinese ip
        rules.append('GEOIP,CN,DIRECT')

        # 6. default
        rules.append('MATCH,DIRECT')

        return rules

    def _save_configuration(self, config: Dict) -> Path:
        """save config """
        config_path = self.config_dir / 'config.yaml'

        if config_path.exists():
            import shutil
            backup_path = self.config_dir / f'config.yaml.backup.{int(time.time())}'
            shutil.copy2(config_path, backup_path)

        import yaml
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)

        self.logger.info(f"Configuration saved: {config_path}")
        return config_path
    
    def _initialize_managers(self):
        """Initialize manager instances if not already set."""
        if self.config_manager is None:
            from .managers import ConfigurationManager
            self.config_manager = ConfigurationManager(str(self.config_dir))
        if not hasattr(self, 'node_fetcher') or self.node_fetcher is None:
            from .fetchers import NodeFetcher
            self.node_fetcher = NodeFetcher()
        if self.enable_default_rules and self.rule_manager is None:
            from .rules import RuleManager
            self.rule_manager = RuleManager()

        if self.health_checker is None:
            from .fetchers import HealthChecker
            self.health_checker = HealthChecker()

        if self.enable_metrics and self.metrics_collector is None:
            try:
                from .monitoring import get_metrics_collector
                self.metrics_collector = get_metrics_collector()
            except ImportError:
                self.logger.warning("Monitoring module not available, disabling metrics")
                self.enable_metrics = False
    
    async def start(
        self,
        config_type: str = 'scraping',
        source_types: List[str] = None,
        enable_auto_update: bool = True,
        rules: Optional[List[str]] = None
    ) -> bool:
        """
        Start the proxy client with optional custom routing rules.

        Args:
            config_type: Type of configuration ('scraping', 'speed', 'general')
            source_types: List of proxy source types to use
            enable_auto_update: Enable automatic proxy updates
            rules: Custom routing rules (domains, IPs, patterns)

        Returns:
            True if started successfully
        """
        try:
            self.logger.info("🚀 Starting CrawlAdapter proxy client...")

            # Step 1: Kill existing Clash processes
            await self._kill_existing_clash()

            # Step 2: Initialize managers
            self._initialize_managers()

            # Step 3: Apply health check URLs
            if hasattr(self, '_pending_health_check_urls') and self._pending_health_check_urls:
                self.health_check_urls = self._pending_health_check_urls.copy()
                self.logger.info(f"Applied {len(self._pending_health_check_urls)} pending health check URLs")
                self._pending_health_check_urls = None

            # Step 4: Save custom rules
            if rules:
                self.current_rules = rules
                self.logger.info(f"Added {len(rules)} custom routing rules")
            else:
                self.current_rules = []

            # Step 5: Fetch proxy nodes
            if not await self._fetch_proxy_nodes(source_types or ['all']):
                self.logger.error("Failed to fetch proxy nodes")
                return False

            # Step 6: Health check
            healthy_nodes = await self._health_check_nodes()
            if not healthy_nodes:
                self.logger.warning("No healthy nodes found, using all nodes")
                healthy_nodes = self.active_proxies

            # Step 7: Generate configuration
            config = self._generate_clash_config(healthy_nodes, self.current_rules, config_type)
            config_path = self._save_configuration(config)

            # Step 8: Start Clash process
            if not await self._start_clash_process(config_path):
                self.logger.error("Failed to start Clash process")
                return False

            # Step 9: Verify startup
            if not await self._verify_clash_running():
                self.logger.error("Clash verification failed")
                return False

            # step 10: Start auto-update task
            if enable_auto_update:
                self.auto_update_task = asyncio.create_task(self._auto_update_loop())

            if self.enable_adaptive_health_check:
                self.health_check_task = asyncio.create_task(self._health_check_loop())

            self.is_running = True
            self.logger.info("✅ CrawlAdapter started successfully")
            self.logger.info(f"   Proxy port: {self.proxy_port}")
            self.logger.info(f"   API port: {self.api_port}")
            self.logger.info(f"   Active proxies: {len(healthy_nodes)}")

            # Record metrics
            if self.metrics_collector:
                self.metrics_collector.increment('client_starts')
                self.metrics_collector.set_gauge('active_proxies', len(healthy_nodes))

            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to start CrawlAdapter: {e}")
            return False

    async def stop(self) -> None:
        """Stop the proxy client and cleanup resources."""
        try:
            self.logger.info("🛑 Stopping CrawlAdapter proxy client...")

            self.is_running = False

            # Cancel background tasks
            if self.health_check_task:
                self.health_check_task.cancel()
                try:
                    await self.health_check_task
                except asyncio.CancelledError:
                    pass

            if self.auto_update_task:
                self.auto_update_task.cancel()
                try:
                    await self.auto_update_task
                except asyncio.CancelledError:
                    pass

            # Stop Clash process
            await self._stop_clash_process()

            # Additional cleanup: kill all Clash processes
            await self._kill_existing_clash()

            self.logger.info("✅ CrawlAdapter stopped successfully")

        except Exception as e:
            self.logger.error(f"❌ Error stopping proxy client: {e}")

    async def get_proxy(self, url: Optional[str] = None, strategy: str = 'health_weighted') -> Optional[str]:
        """
        Get proxy URL with intelligent routing based on rules.

        Args:
            url: Target URL to check against routing rules
            strategy: Load balancing strategy if proxy should be used

        Returns:
            Proxy URL if should use proxy, None for direct connection
        """
        if not self.is_running:
            return None

        # If URL provided, check routing rules
        if url and not self.should_use_proxy(url):
            return None

        # Get proxy URL using strategy
        return await self.get_proxy_url(strategy)

    async def get_proxy_url(self, strategy: str = 'round_robin') -> Optional[str]:
        """
        Get proxy URL using simplified strategy.

        Args:
            strategy: Load balancing strategy (simplified)

        Returns:
            Proxy URL or None if no proxy available
        """
        if not self.is_running:
            return None

        try:
            # Simplified: if there are active proxies, directly return proxy URL
            if self.active_proxies:
                # Record metrics
                if self.metrics_collector:
                    self.metrics_collector.increment('proxy_requests')

                return f"http://127.0.0.1:{self.proxy_port}"
            return None

        except Exception as e:
            self.logger.error(f"Error getting proxy URL: {e}")
            return None

    def should_use_proxy(self, url: str) -> bool:
        """
        Check if URL should use proxy based on routing rules.

        Args:
            url: URL to check

        Returns:
            True if should use proxy
        """
        if not self.rule_manager:
            return False

        return self.rule_manager.should_use_proxy(url)

    def set_health_check_urls(self, urls: List[str]) -> None:
        """
        Set custom health check URLs.

        Args:
            urls: List of URLs to use for health checking
        """
        # Store URLs for later use
        self._pending_health_check_urls = urls.copy()

        if self.health_checker and hasattr(self.health_checker, 'test_endpoints'):
            self.health_checker.test_endpoints = urls.copy()
            self.logger.info(f"Updated health check URLs: {len(urls)} URLs")

            # Update config manager if available
            if self.config_manager:
                self.config_manager.set_health_check_urls(urls)
        else:
            self.logger.info(f"Stored {len(urls)} health check URLs for later use")

    def get_proxy_stats(self) -> Optional[ProxyStats]:
        """Get current proxy statistics."""
        if not self.proxy_manager:
            return None

        return self.proxy_manager.get_statistics()

    async def get_proxy_info(self) -> Dict:
        """
        Get simplified proxy information and statistics.

        Returns:
            Dictionary containing proxy status, statistics, and health info
        """
        try:
            info = {
                'is_running': self.is_running,
                'proxy_port': self.proxy_port,
                'api_port': self.api_port,
                'config_dir': str(self.config_dir),
                'enable_default_rules': self.enable_default_rules
            }

            # Add simplified proxy statistics
            info['proxy_stats'] = {
                'total_proxies': len(self.active_proxies),
                'healthy_proxies': len(self.active_proxies),  # 简化版本
                'current_rules': len(self.current_rules) if hasattr(self, 'current_rules') else 0
            }

            # Add Clash API availability check
            if self.is_running:
                try:
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{self.clash_api_base}/proxies") as response:
                            if response.status == 200:
                                data = await response.json()
                                info['clash_api_available'] = True
                                info['current_proxy'] = data.get('proxies', {}).get('PROXY', {}).get('now', 'DIRECT')
                            else:
                                info['clash_api_available'] = False
                except:
                    info['clash_api_available'] = False
            else:
                info['clash_api_available'] = False

            return info

        except Exception as e:
            self.logger.error(f"Error getting proxy info: {e}")
            return {
                'is_running': self.is_running,
                'error': str(e),
                'proxy_stats': None,
                'clash_api_available': False
            }

    async def switch_proxy(self, proxy_name: Optional[str] = None, strategy: str = 'round_robin') -> bool:
        """
        Switch to a different proxy using Clash API.

        Args:
            proxy_name: Specific proxy name to switch to (optional)
            strategy: Load balancing strategy if proxy_name not specified

        Returns:
            True if switch was successful
        """
        if not self.is_running:
            self.logger.warning("Cannot switch proxy: client not running")
            return False

        try:
            import aiohttp

            # Get available proxy list
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.clash_api_base}/proxies/PROXY") as response:
                    if response.status == 200:
                        data = await response.json()
                        current_proxy = data.get('now', '')
                        all_proxies = data.get('all', [])

                        # Select different proxy
                        available_proxies = [p for p in all_proxies if p != current_proxy and p != 'DIRECT']

                        if available_proxies:
                            if proxy_name and proxy_name in available_proxies:
                                new_proxy = proxy_name
                            elif strategy == 'round_robin':
                                new_proxy = available_proxies[0]
                            elif strategy == 'random':
                                import random
                                new_proxy = random.choice(available_proxies)
                            else:
                                new_proxy = available_proxies[0]

                            # Switch proxy
                            switch_data = {"name": new_proxy}
                            async with session.put(f"{self.clash_api_base}/proxies/PROXY", json=switch_data) as switch_response:
                                if switch_response.status == 204:
                                    self.logger.info(f"🔄 Proxy switched: {current_proxy} → {new_proxy}")
                                    return True
                                else:
                                    self.logger.warning(f"Proxy switch failed: HTTP {switch_response.status}")
                        else:
                            self.logger.warning("No other proxies available")
                    else:
                        self.logger.warning(f"Failed to get proxy list: HTTP {response.status}")

            return False

        except Exception as e:
            self.logger.error(f"Error switching proxy: {e}")
            return False

    async def _start_clash_process(self, config_path: Path) -> bool:
        """Start Clash process with configuration."""
        try:
            # Find available ports
            self.proxy_port = self._find_available_port(7890, 7999)
            self.api_port = self._find_available_port(9090, 9099)
            self.clash_api_base = f"http://127.0.0.1:{self.api_port}"

            # Update config with actual ports
            await self._update_config_ports(config_path)

            # Start Clash
            clash_binary = self.clash_binary_path or self._find_clash_binary()
            if not clash_binary:
                raise CrawlAdapterError("Clash binary not found")

            cmd = [clash_binary, '-f', str(config_path)]
            self.logger.info(f"Starting Clash: {' '.join(cmd)}")

            self.clash_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0
            )

            # Wait for Clash to start
            await asyncio.sleep(3)

            # Check if process is still running
            if self.clash_process.poll() is not None:
                stdout, stderr = self.clash_process.communicate()
                error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "Unknown error"
                raise RuntimeError(f"Clash process exited: {error_msg}")

            # Verify Clash is running
            if not await self._verify_clash_running():
                raise RuntimeError("Clash failed to start properly")

            self.logger.info(f"✅ Clash started successfully")
            self.logger.info(f"   Proxy port: {self.proxy_port}")
            self.logger.info(f"   API port: {self.api_port}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to start Clash: {e}")
            return False

    async def _update_config_ports(self, config_path: Path) -> None:
        """read config and update ports """
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            config['mixed-port'] = self.proxy_port
            config['external-controller'] = f'127.0.0.1:{self.api_port}'

            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)

            self.logger.debug(f"Updated config ports: proxy={self.proxy_port}, api={self.api_port}")

        except Exception as e:
            self.logger.error(f"Failed to update config ports: {e}")
            raise

    async def _stop_clash_process(self) -> None:
        """Stop Clash process."""
        if self.clash_process:
            try:
                if platform.system() == 'Windows':
                    self.clash_process.terminate()
                else:
                    self.clash_process.send_signal(signal.SIGTERM)

                # Wait for process to terminate
                try:
                    self.clash_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.clash_process.kill()

                self.clash_process = None
                self.logger.info("Clash process stopped")

            except Exception as e:
                self.logger.error(f"Error stopping Clash process: {e}")

    def _find_available_port(self, start_port: int, end_port: int) -> int:
        """Find an available port in the given range."""
        import socket

        for port in range(start_port, end_port + 1):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('127.0.0.1', port))
                    return port
            except OSError:
                continue

        raise RuntimeError(f"No available ports in range {start_port}-{end_port}")



    async def _verify_clash_running(self) -> bool:
        """Verify that Clash is running and responding."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.clash_api_base}/version", timeout=5) as response:
                    return response.status == 200
        except:
            return False

    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while self.is_running:
            try:
                if self.health_checker and self.proxy_manager:
                    if self.enable_adaptive_health_check:
                        # Adaptive health checker manages its own scheduling
                        if not hasattr(self.health_checker, '_adaptive_started'):
                            await self.health_checker.start_adaptive_checking(
                                [p.name for p in self.proxy_manager.active_proxies],
                                self.clash_api_base
                            )
                            self.health_checker._adaptive_started = True
                    else:
                        # Traditional health check
                        results = await self.health_checker.check_all_proxies(
                            self.proxy_manager.active_proxies, self.clash_api_base
                        )
                        self.proxy_manager.update_proxy_health(results)
                        self.last_health_check = time.time()

                # Record metrics
                if self.metrics_collector:
                    self.metrics_collector.increment('health_checks')

                # Sleep interval depends on health checker type
                if self.enable_adaptive_health_check:
                    await asyncio.sleep(60)  # Adaptive checker manages its own intervals
                else:
                    await asyncio.sleep(300)  # 5 minutes for traditional checker

            except Exception as e:
                self.logger.error(f"Health check error: {e}")
                await asyncio.sleep(60)

    async def _auto_update_loop(self) -> None:
        """Background auto-update loop."""
        while self.is_running:
            try:
                await asyncio.sleep(self.auto_update_interval)

                if self.proxy_manager:
                    # Fetch new nodes
                    updated = await self.proxy_manager.update_proxies()
                    if updated:
                        # Regenerate configuration
                        # Convert ProxyNode objects to dictionaries for configuration generation
                        proxy_configs = [proxy.config for proxy in self.proxy_manager.active_proxies]
                        config = self.config_manager.generate_clash_config(
                            proxy_configs, 'scraping'
                        )
                        config_path = self.config_manager.save_configuration(config)

                        # Reload Clash configuration
                        await self._reload_clash_config()

                        self.logger.info("Proxy configuration updated")

                        # Record metrics
                        if self.metrics_collector:
                            self.metrics_collector.increment('config_updates')

            except Exception as e:
                self.logger.error(f"Auto-update error: {e}")

    async def _reload_clash_config(self) -> bool:
        """Reload Clash configuration without restarting."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(f"{self.clash_api_base}/configs", json={
                    "path": str(self.config_dir / "config.yaml")
                }) as response:
                    return response.status == 204
        except Exception as e:
            self.logger.error(f"Failed to reload Clash config: {e}")
            return False
