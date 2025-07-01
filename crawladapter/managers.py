"""
Manager Classes for CrawlAdapter

Consolidates ConfigurationManager, ProxyManager, and related management functionality.
"""

import logging
import shutil
import time
import random
import statistics
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from .types import ProxyNode, ProxyStats, LoadBalanceStrategy, ConfigType, HealthCheckResult
from .rules import RuleTemplates, RuleCategory


class ConfigurationManager:
    """
    Manages Clash configuration generation and file operations.
    
    Consolidates configuration management functionality with rule template integration.
    """

    def __init__(self, config_dir: str = './clash_configs', rule_categories: Optional[List[RuleCategory]] = None):
        """
        Initialize configuration manager.

        Args:
            config_dir: Directory to store configurations
            rule_categories: List of rule categories to include in configurations
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        self.backup_dir = self.config_dir / 'backups'
        self.backup_dir.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)

        # Set default rule categories if none provided
        self.rule_categories = rule_categories or [
            RuleCategory.LOCAL_NETWORK,
            RuleCategory.IP_TESTING,
            RuleCategory.DEVELOPMENT,
            RuleCategory.CDN_RESOURCES
        ]

        # Health check test URLs - 可以由用户自定义
        self.health_check_urls: List[str] = []

    def generate_clash_config(self, proxies: List[Dict], config_type: str = 'scraping') -> Dict:
        """
        Generate Clash configuration with proxies and rules.

        Args:
            proxies: List of proxy configurations
            config_type: Type of configuration ('scraping', 'speed', 'general')

        Returns:
            Complete Clash configuration dictionary
        """
        if not proxies:
            raise ValueError("No proxies provided for configuration generation")

        proxy_names = [proxy['name'] for proxy in proxies]
        
        if config_type == 'scraping':
            return self._get_scraping_config(proxy_names, proxies)
        elif config_type == 'speed':
            return self._get_speed_config(proxy_names, proxies)
        else:
            return self._get_general_config(proxy_names, proxies)

    def _get_scraping_config(self, proxy_names: List[str], proxies: List[Dict]) -> Dict:
        """Generate configuration optimized for web scraping."""
        return {
            'mixed-port': 7890,
            'allow-lan': False,
            'mode': 'rule',
            'log-level': 'info',
            'external-controller': '127.0.0.1:9090',
            'secret': '',
            'proxies': proxies,
            'proxy-groups': [
                {
                    'name': 'PROXY',
                    'type': 'select',
                    'proxies': ['auto-fallback', 'load-balance'] + proxy_names
                },
                {
                    'name': 'auto-fallback',
                    'type': 'fallback',
                    'proxies': proxy_names,
                    'url': 'http://httpbin.org/get',
                    'interval': 300,
                    'tolerance': 150
                },
                {
                    'name': 'load-balance',
                    'type': 'load-balance',
                    'proxies': proxy_names,
                    'url': 'http://httpbin.org/get',
                    'interval': 300,
                    'strategy': 'round-robin'
                }
            ],
            'rules': self._build_rules_with_health_check(
                categories=self.rule_categories,
                default_action='PROXY'
            )
        }

    def _get_speed_config(self, proxy_names: List[str], proxies: List[Dict]) -> Dict:
        """Generate configuration optimized for speed."""
        return {
            'mixed-port': 7890,
            'allow-lan': False,
            'mode': 'rule',
            'log-level': 'warning',
            'external-controller': '127.0.0.1:9090',
            'secret': '',
            'proxies': proxies,
            'proxy-groups': [
                {
                    'name': 'PROXY',
                    'type': 'select',
                    'proxies': ['url-test'] + proxy_names
                },
                {
                    'name': 'url-test',
                    'type': 'url-test',
                    'proxies': proxy_names,
                    'url': 'http://www.gstatic.com/generate_204',
                    'interval': 180,
                    'tolerance': 100
                }
            ],
            'rules': RuleTemplates.get_minimal_rules()
        }

    def _get_general_config(self, proxy_names: List[str], proxies: List[Dict]) -> Dict:
        """Generate general-purpose configuration."""
        return {
            'mixed-port': 7890,
            'allow-lan': False,
            'mode': 'rule',
            'log-level': 'info',
            'external-controller': '127.0.0.1:9090',
            'secret': '',
            'proxies': proxies,
            'proxy-groups': [
                {
                    'name': 'PROXY',
                    'type': 'select',
                    'proxies': ['auto'] + proxy_names
                },
                {
                    'name': 'auto',
                    'type': 'url-test',
                    'proxies': proxy_names,
                    'url': 'http://httpbin.org/get',
                    'interval': 300
                }
            ],
            'rules': RuleTemplates.build_custom_rules(
                categories=[RuleCategory.LOCAL_NETWORK],
                default_action='DIRECT'
            )
        }

    def save_configuration(self, config: Dict, config_name: str = 'config.yaml') -> Path:
        """
        Save configuration to file with backup.

        Args:
            config: Configuration dictionary
            config_name: Name of configuration file

        Returns:
            Path to saved configuration file
        """
        config_path = self.config_dir / config_name
        
        # Create backup if file exists
        if config_path.exists():
            backup_name = f"{config_name}.backup.{int(time.time())}"
            backup_path = self.backup_dir / backup_name
            shutil.copy2(config_path, backup_path)
            self.logger.debug(f"Created backup: {backup_path}")

        # Save new configuration
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)

        self.logger.info(f"Configuration saved: {config_path}")
        return config_path

    def update_ports(self, config_path: Path, proxy_port: int, api_port: int) -> None:
        """Update ports in existing configuration file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            config['mixed-port'] = proxy_port
            config['external-controller'] = f'127.0.0.1:{api_port}'
            
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            self.logger.debug(f"Updated ports: proxy={proxy_port}, api={api_port}")
            
        except Exception as e:
            self.logger.error(f"Failed to update ports: {e}")

    def set_rule_categories(self, categories: List[RuleCategory]) -> None:
        """Set rule categories for configuration generation."""
        self.rule_categories = categories
        self.logger.info(f"Updated rule categories: {[cat.value for cat in categories]}")

    def set_health_check_urls(self, urls: List[str]) -> None:
        """
        Set health check URLs that should be routed through proxy.

        Args:
            urls: List of health check URLs
        """
        self.health_check_urls = urls.copy()
        self.logger.info(f"Updated health check URLs: {len(urls)} URLs")

    def _extract_domains_from_urls(self, urls: List[str]) -> List[str]:
        """
        Extract domains from URLs for rule generation.

        Args:
            urls: List of URLs

        Returns:
            List of domain rules
        """
        from urllib.parse import urlparse

        domains = set()
        for url in urls:
            try:
                parsed = urlparse(url)
                if parsed.hostname:
                    # Add both the domain and www variant
                    domain = parsed.hostname.lower()
                    domains.add(f'DOMAIN-SUFFIX,{domain},PROXY')

                    # If domain starts with www, also add without www
                    if domain.startswith('www.'):
                        base_domain = domain[4:]
                        domains.add(f'DOMAIN-SUFFIX,{base_domain},PROXY')

            except Exception as e:
                self.logger.warning(f"Failed to parse URL {url}: {e}")

        return list(domains)

    def _build_rules_with_health_check(self, categories: List[RuleCategory],
                                     default_action: str = 'DIRECT') -> List[str]:
        """
        Build rules including health check URL rules.

        Args:
            categories: Rule categories to include
            default_action: Default action for unmatched traffic

        Returns:
            Complete list of rules with health check URLs prioritized
        """
        rules = []

        # 1. 首先添加健康检查URL规则（最高优先级）
        if self.health_check_urls:
            health_check_rules = self._extract_domains_from_urls(self.health_check_urls)
            if health_check_rules:
                rules.append('# Health check URLs - 健康检查网址通过代理')
                rules.extend(health_check_rules)

        # 2. 添加分类规则
        category_rules = RuleTemplates.build_custom_rules(
            categories=categories,
            default_action=default_action
        )

        # 移除分类规则中的默认规则，我们稍后会添加
        if category_rules and category_rules[-1].startswith('MATCH,'):
            category_rules = category_rules[:-1]

        rules.extend(category_rules)

        # 3. 最后添加默认规则
        rules.append(f'MATCH,{default_action}')

        return rules

    def generate_minimal_config(self, proxies: List[Dict]) -> Dict:
        """Generate minimal configuration with basic rules only."""
        if not proxies:
            raise ValueError("No proxies provided for configuration generation")

        proxy_names = [proxy['name'] for proxy in proxies]
        
        return {
            'mixed-port': 7890,
            'allow-lan': False,
            'mode': 'rule',
            'log-level': 'info',
            'external-controller': '127.0.0.1:9090',
            'secret': '',
            'proxies': proxies,
            'proxy-groups': [
                {
                    'name': 'PROXY',
                    'type': 'select',
                    'proxies': ['auto'] + proxy_names
                },
                {
                    'name': 'auto',
                    'type': 'url-test',
                    'proxies': proxy_names,
                    'url': 'http://httpbin.org/get',
                    'interval': 300
                }
            ],
            'rules': RuleTemplates.get_minimal_rules()
        }


class ProxyManager:
    """
    Manages proxy selection, health tracking, and load balancing.
    
    Consolidates proxy management functionality with intelligent selection strategies.
    """

    def __init__(self):
        """Initialize proxy manager."""
        self.active_proxies: List[ProxyNode] = []
        self.proxy_health: Dict[str, HealthCheckResult] = {}
        self.usage_stats: Dict[str, int] = {}
        self.last_used_index = 0
        self.logger = logging.getLogger(__name__)

    async def initialize(self, source_types: Optional[List[str]] = None) -> bool:
        """
        Initialize proxy manager with node fetching.

        Args:
            source_types: List of source types to fetch from

        Returns:
            True if initialization successful
        """
        try:
            from .fetchers import NodeFetcher

            # Use existing node_fetcher if available, otherwise create new one
            if not hasattr(self, 'node_fetcher') or self.node_fetcher is None:
                self.node_fetcher = NodeFetcher()
                self.logger.info("Created default NodeFetcher")
            else:
                self.logger.info("Using existing custom NodeFetcher")

            # Fetch nodes using the node_fetcher
            nodes = await self.node_fetcher.fetch_nodes(source_types[0] if source_types else 'all')
            
            if not nodes:
                self.logger.warning("No nodes fetched during initialization")
                return False
            
            # Convert to ProxyNode objects
            self.active_proxies = []
            for node_dict in nodes:
                try:
                    proxy_node = ProxyNode(
                        name=node_dict.get('name', f"proxy_{len(self.active_proxies)}"),
                        server=node_dict.get('server', ''),
                        port=node_dict.get('port', 443),
                        type=node_dict.get('type', 'vmess'),
                        config=node_dict
                    )
                    self.active_proxies.append(proxy_node)
                except Exception as e:
                    self.logger.debug(f"Failed to create proxy node: {e}")
            
            self.logger.info(f"Initialized with {len(self.active_proxies)} proxies")
            return len(self.active_proxies) > 0
            
        except Exception as e:
            self.logger.error(f"Failed to initialize proxy manager: {e}")
            return False

    def select_proxy(self, strategy: str = 'health_weighted') -> Optional[ProxyNode]:
        """
        Select a proxy using the specified strategy.

        Args:
            strategy: Selection strategy

        Returns:
            Selected proxy node or None
        """
        if not self.active_proxies:
            return None

        try:
            if strategy == LoadBalanceStrategy.HEALTH_WEIGHTED.value:
                return self._select_health_weighted()
            elif strategy == LoadBalanceStrategy.ROUND_ROBIN.value:
                return self._select_round_robin()
            elif strategy == LoadBalanceStrategy.LEAST_USED.value:
                return self._select_least_used()
            elif strategy == LoadBalanceStrategy.RANDOM.value:
                return self._select_random()
            else:
                return self._select_health_weighted()  # Default
                
        except Exception as e:
            self.logger.error(f"Error selecting proxy: {e}")
            return self.active_proxies[0] if self.active_proxies else None

    def _select_health_weighted(self) -> Optional[ProxyNode]:
        """Select proxy based on health scores."""
        healthy_proxies = [p for p in self.active_proxies if p.is_healthy]
        if not healthy_proxies:
            healthy_proxies = self.active_proxies  # Fallback to all proxies
        
        # Weight by health score
        weights = [max(0.1, p.health_score) for p in healthy_proxies]
        total_weight = sum(weights)
        
        if total_weight == 0:
            return healthy_proxies[0]
        
        # Weighted random selection
        r = random.uniform(0, total_weight)
        cumulative = 0
        for proxy, weight in zip(healthy_proxies, weights):
            cumulative += weight
            if r <= cumulative:
                self._update_usage(proxy.name)
                return proxy
        
        return healthy_proxies[-1]

    def _select_round_robin(self) -> ProxyNode:
        """Select proxy using round-robin strategy."""
        proxy = self.active_proxies[self.last_used_index]
        self.last_used_index = (self.last_used_index + 1) % len(self.active_proxies)
        self._update_usage(proxy.name)
        return proxy

    def _select_least_used(self) -> ProxyNode:
        """Select least used proxy."""
        min_usage = min(self.usage_stats.get(p.name, 0) for p in self.active_proxies)
        least_used = [p for p in self.active_proxies if self.usage_stats.get(p.name, 0) == min_usage]
        proxy = random.choice(least_used)
        self._update_usage(proxy.name)
        return proxy

    def _select_random(self) -> ProxyNode:
        """Select random proxy."""
        proxy = random.choice(self.active_proxies)
        self._update_usage(proxy.name)
        return proxy

    def _update_usage(self, proxy_name: str) -> None:
        """Update usage statistics for a proxy."""
        self.usage_stats[proxy_name] = self.usage_stats.get(proxy_name, 0) + 1

    def update_proxy_health(self, health_results: Dict[str, HealthCheckResult]) -> None:
        """Update proxy health information."""
        self.proxy_health.update(health_results)
        
        # Update proxy node health scores
        for proxy in self.active_proxies:
            if proxy.name in health_results:
                result = health_results[proxy.name]
                proxy.health_score = result.overall_score
                proxy.avg_latency = result.latency
                proxy.last_checked = result.timestamp

    def get_statistics(self) -> ProxyStats:
        """Get current proxy statistics."""
        total_proxies = len(self.active_proxies)
        healthy_proxies = len([p for p in self.active_proxies if p.is_healthy])
        failed_proxies = total_proxies - healthy_proxies
        health_rate = healthy_proxies / total_proxies if total_proxies > 0 else 0.0
        
        # Usage statistics
        total_usage = sum(self.usage_stats.values())
        average_usage = total_usage / total_proxies if total_proxies > 0 else 0.0
        
        most_used_proxy = max(self.usage_stats.items(), key=lambda x: x[1]) if self.usage_stats else ("", 0)
        least_used_proxy = min(self.usage_stats.items(), key=lambda x: x[1]) if self.usage_stats else ("", 0)
        
        return ProxyStats(
            total_proxies=total_proxies,
            healthy_proxies=healthy_proxies,
            failed_proxies=failed_proxies,
            health_rate=health_rate,
            total_usage=total_usage,
            average_usage=average_usage,
            most_used_proxy=most_used_proxy[0],
            most_used_count=most_used_proxy[1],
            least_used_proxy=least_used_proxy[0],
            least_used_count=least_used_proxy[1],
            last_update=time.time(),
            last_health_check=max([p.last_checked.timestamp() for p in self.active_proxies 
                                 if p.last_checked], default=0)
        )

    async def update_proxies(self) -> bool:
        """Update proxy list by fetching new nodes."""
        try:
            from .fetchers import NodeFetcher
            
            node_fetcher = NodeFetcher()
            new_nodes = await node_fetcher.fetch_nodes('all')
            
            if new_nodes:
                # Update active proxies
                old_count = len(self.active_proxies)
                self.active_proxies = []
                
                for node_dict in new_nodes:
                    try:
                        proxy_node = ProxyNode(
                            name=node_dict.get('name', f"proxy_{len(self.active_proxies)}"),
                            server=node_dict.get('server', ''),
                            port=node_dict.get('port', 443),
                            type=node_dict.get('type', 'vmess'),
                            config=node_dict
                        )
                        self.active_proxies.append(proxy_node)
                    except Exception as e:
                        self.logger.debug(f"Failed to create proxy node: {e}")
                
                new_count = len(self.active_proxies)
                self.logger.info(f"Updated proxies: {old_count} -> {new_count}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to update proxies: {e}")
            return False
