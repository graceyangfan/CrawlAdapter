"""
CrawlAdapter Client

Simplified ProxyClient implementation with clear separation of concerns.
This is the main user-facing interface for the library.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .types import ProxyConfig, ProxyNode, ProxyStats, HealthCheckResult, StartupOptions
from .exceptions import ProxyNotAvailableError, ConfigurationError
from .config_loader import create_proxy_config, get_config_loader
from .process_manager import ClashProcessManager
from .fetchers import NodeFetcher
from .health_checker import HealthChecker
from .managers import ConfigurationManager, ProxyManager
from .rules import RuleManager


class ProxyClient:
    """
    Simplified proxy client for web scraping and HTTP requests.
    
    Features:
    - Automatic proxy node fetching and validation
    - Custom routing rules for selective proxy usage
    - Health monitoring and intelligent selection
    - Clean separation of concerns
    """
    
    def __init__(
        self,
        config: Optional[ProxyConfig] = None,
        config_file: Optional[str] = None,
        config_dir: Optional[str] = None,
        clash_binary_path: Optional[str] = None,
        proxy_port: Optional[int] = None,
        api_port: Optional[int] = None,
        **kwargs
    ):
        """
        Initialize the proxy client.

        Args:
            config: ProxyConfig instance or None for auto-loading
            config_file: Path to configuration file (optional)
            config_dir: Directory for storing configurations (optional)
            clash_binary_path: Absolute path to Clash binary (optional, auto-detected if None)
            proxy_port: Port for proxy server (optional)
            api_port: Port for Clash API (optional)
            **kwargs: Additional configuration parameters
        """
        # Load configuration using the configuration loader
        if config is None:
            # Merge explicit parameters with kwargs
            config_params = {}
            if config_dir is not None:
                config_params['config_dir'] = config_dir
            if clash_binary_path is not None:
                config_params['clash_binary_path'] = clash_binary_path
            if proxy_port is not None:
                config_params['proxy_port'] = proxy_port
            if api_port is not None:
                config_params['api_port'] = api_port

            # Merge with kwargs
            config_params.update(kwargs)

            config = create_proxy_config(config_file=config_file, **config_params)
        
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # State management
        self.is_running = False
        self.active_proxies: List[ProxyNode] = []
        self.current_rules: List[str] = []
        
        # Component initialization
        self.process_manager = ClashProcessManager(self.config)
        self.node_fetcher = NodeFetcher()

        # Use health checker with strategy based on config
        strategy = 'adaptive' if self.config.enable_adaptive_health_check else 'basic'
        self.health_monitor = HealthChecker(strategy=strategy)

        self.config_manager = ConfigurationManager(str(self.config.config_dir))
        self.proxy_manager = ProxyManager()
        self.rule_manager = RuleManager()
        
        # Create config directory
        Path(self.config.config_dir).mkdir(parents=True, exist_ok=True)
        
        # Background tasks
        self.health_check_task: Optional[asyncio.Task] = None
        self.auto_update_task: Optional[asyncio.Task] = None
    
    async def start(
        self,
        options: Optional[StartupOptions] = None,
        **kwargs
    ) -> bool:
        """
        Start the proxy client.

        Args:
            options: StartupOptions object with all configuration
            **kwargs: Individual parameters (for backward compatibility)
                     config_type, source_types, enable_auto_update, rules, custom_sources

        Returns:
            True if started successfully
        """
        # Handle backward compatibility and create options
        if options is None:
            options = StartupOptions(
                config_type=kwargs.get('config_type', 'scraping'),
                source_types=kwargs.get('source_types'),
                enable_auto_update=kwargs.get('enable_auto_update', True),
                rules=kwargs.get('rules'),
                custom_sources=kwargs.get('custom_sources')
            )
        try:
            self.logger.info("🚀 Starting CrawlAdapter proxy client...")
            
            # Step 1: Setup custom sources if provided
            if options.custom_sources:
                self.node_fetcher = NodeFetcher(custom_sources=options.custom_sources)

            # Step 2: Apply routing rules
            if options.rules:
                self.current_rules = options.rules
                self.rule_manager.add_rules(options.rules)
                self.logger.info(f"Added {len(options.rules)} custom routing rules")
            elif self.config.enable_default_rules:
                self.rule_manager.load_default_rules()
                self.logger.info("Loaded default routing rules")

            # Step 3: Fetch proxy nodes
            if not await self._fetch_proxy_nodes(options.source_types or ['all']):
                self.logger.error("Failed to fetch proxy nodes")
                return False

            # Step 4: Generate initial configuration with all nodes
            self.logger.info("Generating initial configuration with all nodes...")
            initial_config_dict = self.config_manager.generate_clash_config(
                [node.to_dict() for node in self.active_proxies],
                options.config_type,
                include_health_check_rules=True  # 确保健康检查URL在代理规则中
            )
            initial_config_path = self.config_manager.save_configuration(initial_config_dict)

            # Step 5: Start Clash process for health checking
            self.logger.info("Starting Clash for health checking...")
            if not await self.process_manager.start_clash_process(str(initial_config_path)):
                self.logger.error("Failed to start Clash process for health checking")
                return False

            # Wait for Clash to be ready
            await asyncio.sleep(3)

            # Step 6: Perform health check (now Clash is running)
            self.logger.info("Performing health check on all nodes...")
            healthy_nodes = await self._health_check_nodes()
            if not healthy_nodes:
                self.logger.warning("No healthy nodes found, using all nodes")
                healthy_nodes = self.active_proxies
            else:
                self.logger.info(f"Health check completed: {len(healthy_nodes)}/{len(self.active_proxies)} nodes healthy")

            # Step 7: Generate final configuration with healthy nodes only
            self.logger.info("Generating final configuration with healthy nodes...")
            final_config_dict = self.config_manager.generate_clash_config(
                [node.to_dict() for node in healthy_nodes],
                options.config_type
            )
            final_config_path = self.config_manager.save_configuration(final_config_dict)

            # Step 8: Restart Clash with healthy nodes configuration
            self.logger.info("Restarting Clash with healthy nodes...")
            await self.process_manager.stop_clash_process()
            await asyncio.sleep(2)
            if not await self.process_manager.start_clash_process(str(final_config_path)):
                self.logger.error("Failed to restart Clash process with healthy nodes")
                return False

            # Step 9: Initialize proxy manager
            self.proxy_manager.update_proxies(proxy_nodes=healthy_nodes)
            
            # Step 8: Start background tasks
            if options.enable_auto_update:
                await self._start_background_tasks()
            
            self.is_running = True
            self.logger.info("✅ CrawlAdapter started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start CrawlAdapter: {e}")
            await self.stop()
            return False
    
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
        
        # Check routing rules if URL provided
        if url and not self.rule_manager.should_use_proxy(url):
            return None
        
        # Get proxy using strategy
        proxy_node = self.proxy_manager.select_proxy(strategy)
        if proxy_node:
            return self.config.proxy_url
        
        return None
    
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
            
            # Select proxy to switch to
            if proxy_name:
                target_proxy = proxy_name
            else:
                proxy_node = self.proxy_manager.select_proxy(strategy)
                if not proxy_node:
                    raise ProxyNotAvailableError("No healthy proxies available for switching")
                target_proxy = proxy_node.name
            
            # Switch via Clash API
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    f"{self.config.clash_api_base}/proxies/PROXY",
                    json={"name": target_proxy}
                ) as response:
                    if response.status == 204:
                        self.logger.info(f"✅ Switched to proxy: {target_proxy}")
                        return True
                    else:
                        self.logger.error(f"Failed to switch proxy: HTTP {response.status}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Error switching proxy: {e}")
            return False
    
    async def get_proxy_info(self) -> Dict:
        """Get current proxy information and statistics."""
        try:
            info = {
                'is_running': self.is_running,
                'proxy_port': self.config.proxy_port,
                'api_port': self.config.api_port,
                'config_dir': self.config.config_dir,
                'proxy_stats': {
                    'total_proxies': len(self.active_proxies),
                    'healthy_proxies': len([p for p in self.active_proxies if p.is_healthy]),
                    'current_rules': len(self.current_rules)
                }
            }
            
            # Add current proxy info if running
            if self.is_running:
                try:
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{self.config.clash_api_base}/proxies") as response:
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
    
    async def stop(self) -> None:
        """Stop the proxy client and clean up resources."""
        try:
            self.logger.info("Stopping CrawlAdapter...")
            
            # Stop background tasks
            if self.health_check_task:
                self.health_check_task.cancel()
            if self.auto_update_task:
                self.auto_update_task.cancel()

            # Stop background health monitoring
            await self.health_monitor.stop_background_checking()
            
            # Stop Clash process
            await self.process_manager.stop_clash_process()
            
            # Reset state
            self.is_running = False
            self.active_proxies.clear()
            
            self.logger.info("✅ CrawlAdapter stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping CrawlAdapter: {e}")

    # Convenience methods for simplified usage
    async def quick_start(
        self,
        rules: Optional[List[str]] = None,
        custom_sources: Optional[Dict] = None
    ) -> bool:
        """
        Quick start with minimal configuration.

        Args:
            rules: Optional routing rules
            custom_sources: Optional custom proxy sources

        Returns:
            True if started successfully
        """
        options = StartupOptions(
            config_type='scraping',
            rules=rules,
            custom_sources=custom_sources,
            enable_auto_update=False  # Keep it simple
        )
        return await self.start(options)

    async def is_proxy_needed(self, url: str) -> bool:
        """
        Check if proxy is needed for a URL based on rules.

        Args:
            url: Target URL to check

        Returns:
            True if proxy should be used
        """
        if not self.is_running:
            return False

        return self.rule_manager.should_use_proxy(url)

    async def get_current_proxy(self) -> Optional[str]:
        """
        Get the name of the currently active proxy.

        Returns:
            Current proxy name or None
        """
        try:
            if not self.is_running:
                return None

            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.config.clash_api_base}/proxies") as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('proxies', {}).get('PROXY', {}).get('now', 'DIRECT')
            return None
        except Exception:
            return None

    # Helper methods
    async def _fetch_proxy_nodes(self, source_types: List[str]) -> bool:
        """Fetch proxy nodes from configured sources."""
        try:
            nodes_data = await self.node_fetcher.fetch_nodes(source_types[0] if len(source_types) == 1 else 'all')
            
            if not nodes_data:
                self.logger.error("No proxy nodes fetched")
                return False
            
            # Convert to ProxyNode objects
            from .types import ProxyType
            self.active_proxies = []
            for node_data in nodes_data:
                try:
                    proxy_node = ProxyNode(
                        name=node_data.get('name', ''),
                        server=node_data.get('server', ''),
                        port=node_data.get('port', 0),
                        type=ProxyType(node_data.get('type', 'vmess')),
                        config=node_data
                    )
                    self.active_proxies.append(proxy_node)
                except Exception as e:
                    self.logger.warning(f"Failed to parse node {node_data.get('name', 'unknown')}: {e}")
            
            self.logger.info(f"Fetched {len(self.active_proxies)} proxy nodes")
            return len(self.active_proxies) > 0
            
        except Exception as e:
            self.logger.error(f"Error fetching proxy nodes: {e}")
            return False
    
    async def _health_check_nodes(self) -> List[ProxyNode]:
        """Perform health check on all nodes."""
        if not self.active_proxies:
            return []

        try:
            # Perform actual health checking using proxy health monitor
            health_results = await self.health_monitor.check_all_proxies(
                self.active_proxies,
                self.config.clash_api_base
            )

            # Get healthy proxies
            healthy_proxies = self.health_monitor.get_healthy_proxies(
                self.active_proxies,
                health_results
            )

            # Log health summary
            summary = self.health_monitor.get_health_summary(health_results)
            self.logger.info(
                f"Health check completed: {summary['healthy_proxies']}/{summary['total_proxies']} "
                f"proxies healthy ({summary['health_rate']:.1%})"
            )

            return healthy_proxies if healthy_proxies else self.active_proxies

        except Exception as e:
            self.logger.error(f"Error during health check: {e}")
            return self.active_proxies
    
    async def _start_background_tasks(self) -> None:
        """Start background tasks for health checking and auto-update."""
        try:
            # Start background health monitoring if using adaptive strategy
            if self.config.enable_adaptive_health_check:
                proxy_names = [proxy.name for proxy in self.active_proxies]
                await self.health_monitor.start_background_checking(
                    proxy_names,
                    self.config.clash_api_base
                )
                self.logger.info("Started background adaptive health monitoring")

            # TODO: Implement auto-update task

        except Exception as e:
            self.logger.error(f"Error starting background tasks: {e}")
