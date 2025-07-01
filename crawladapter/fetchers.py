"""
CrawlAdapter Node Fetchers

Focused module for fetching proxy nodes from various sources.
Health checking functionality has been moved to health_checker.py.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
import aiohttp
import yaml

from .exceptions import NodeFetchError


class NodeFetcher:
    """
    Fetches proxy nodes from various sources.
    
    Supports:
    - Clash configuration URLs
    - V2Ray subscription URLs  
    - Custom node sources
    """
    
    def __init__(self, custom_sources: Optional[Dict] = None, timeout: int = 30):
        """
        Initialize node fetcher.
        
        Args:
            custom_sources: Custom source URLs {'clash': [...], 'v2ray': [...]}
            timeout: Request timeout in seconds
        """
        self.logger = logging.getLogger(__name__)
        self.timeout = timeout
        self.custom_sources = custom_sources or {}
        
        # Default sources (can be overridden)
        self.default_sources = {
            'clash': [
                'https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.yml',
            ],
            'v2ray': []
        }
    
    def set_custom_sources(self, sources: Dict[str, List[str]]) -> None:
        """Set custom node sources."""
        self.custom_sources = sources
        self.logger.info(f"Updated custom sources: {len(sources)} source types")
    
    def add_custom_nodes(self, nodes: List[Dict]) -> None:
        """Add custom proxy nodes directly."""
        if not hasattr(self, 'custom_nodes'):
            self.custom_nodes = []
        
        self.custom_nodes.extend(nodes)
        self.logger.info(f"Added {len(nodes)} custom nodes")
    
    async def fetch_nodes(self, source_type: str = 'all') -> List[Dict]:
        """
        Fetch proxy nodes from configured sources.
        
        Args:
            source_type: Type of sources to fetch ('clash', 'v2ray', 'all')
            
        Returns:
            List of proxy node dictionaries
            
        Raises:
            NodeFetchError: If fetching fails
        """
        try:
            all_nodes = []
            
            # Use custom sources if available, otherwise use defaults
            sources = self.custom_sources if self.custom_sources else self.default_sources
            
            if source_type == 'all':
                source_types = list(sources.keys())
            else:
                source_types = [source_type] if source_type in sources else []
            
            if not source_types:
                self.logger.warning(f"No sources available for type: {source_type}")
                return []
            
            # Fetch from each source type
            for stype in source_types:
                urls = sources.get(stype, [])
                if not urls:
                    continue
                
                self.logger.info(f"Fetching {stype} nodes from {len(urls)} sources")
                
                for url in urls:
                    try:
                        nodes = await self._fetch_from_url(url, stype)
                        if nodes:
                            all_nodes.extend(nodes)
                            self.logger.info(f"Fetched {len(nodes)} nodes from {url}")
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch from {url}: {e}")
                        continue
            
            # Add custom nodes if available
            if hasattr(self, 'custom_nodes'):
                all_nodes.extend(self.custom_nodes)
                self.logger.info(f"Added {len(self.custom_nodes)} custom nodes")
            
            # Remove duplicates based on server+port
            unique_nodes = self._remove_duplicates(all_nodes)
            
            self.logger.info(f"Total unique nodes fetched: {len(unique_nodes)}")
            return unique_nodes
            
        except Exception as e:
            self.logger.error(f"Failed to fetch nodes: {e}")
            raise NodeFetchError(f"Node fetching failed: {str(e)}")
    
    async def _fetch_from_url(self, url: str, source_type: str) -> List[Dict]:
        """Fetch nodes from a specific URL."""
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise NodeFetchError(f"HTTP {response.status} from {url}")
                    
                    content = await response.text()
                    
                    if source_type == 'clash':
                        return self._parse_clash_config(content)
                    elif source_type == 'v2ray':
                        return self._parse_v2ray_subscription(content)
                    else:
                        self.logger.warning(f"Unknown source type: {source_type}")
                        return []
        
        except Exception as e:
            self.logger.error(f"Error fetching from {url}: {e}")
            raise NodeFetchError(f"Failed to fetch from {url}: {str(e)}")
    
    def _parse_clash_config(self, content: str) -> List[Dict]:
        """Parse Clash configuration YAML."""
        try:
            config = yaml.safe_load(content)
            if not isinstance(config, dict):
                return []
            
            proxies = config.get('proxies', [])
            if not isinstance(proxies, list):
                return []
            
            # Filter and validate proxies
            valid_proxies = []
            for proxy in proxies:
                if self._is_valid_proxy(proxy):
                    valid_proxies.append(proxy)
            
            return valid_proxies
            
        except Exception as e:
            self.logger.error(f"Failed to parse Clash config: {e}")
            return []
    
    def _parse_v2ray_subscription(self, content: str) -> List[Dict]:
        """Parse V2Ray subscription content."""
        try:
            # V2Ray subscriptions are typically base64 encoded
            import base64
            
            try:
                decoded = base64.b64decode(content).decode('utf-8')
            except:
                decoded = content
            
            # Parse V2Ray URLs (vmess://, vless://, etc.)
            lines = decoded.strip().split('\n')
            proxies = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    proxy = self._parse_v2ray_url(line)
                    if proxy and self._is_valid_proxy(proxy):
                        proxies.append(proxy)
                except Exception as e:
                    self.logger.debug(f"Failed to parse V2Ray URL: {line[:50]}... - {e}")
                    continue
            
            return proxies
            
        except Exception as e:
            self.logger.error(f"Failed to parse V2Ray subscription: {e}")
            return []
    
    def _parse_v2ray_url(self, url: str) -> Optional[Dict]:
        """Parse a single V2Ray URL into proxy dict."""
        try:
            import base64
            import json
            from urllib.parse import urlparse, parse_qs
            
            if url.startswith('vmess://'):
                # VMess format
                encoded = url[8:]  # Remove vmess://
                decoded = base64.b64decode(encoded).decode('utf-8')
                config = json.loads(decoded)
                
                return {
                    'name': config.get('ps', 'VMess'),
                    'type': 'vmess',
                    'server': config.get('add'),
                    'port': int(config.get('port', 443)),
                    'uuid': config.get('id'),
                    'alterId': int(config.get('aid', 0)),
                    'cipher': 'auto',
                    'network': config.get('net', 'tcp'),
                    'tls': config.get('tls') == 'tls'
                }
            
            # Add support for other protocols as needed
            return None
            
        except Exception as e:
            self.logger.debug(f"Failed to parse V2Ray URL: {e}")
            return None
    
    def _is_valid_proxy(self, proxy: Dict) -> bool:
        """Validate proxy configuration."""
        if not isinstance(proxy, dict):
            return False
        
        # Check required fields
        required_fields = ['name', 'type', 'server', 'port']
        for field in required_fields:
            if field not in proxy:
                return False
        
        # Validate proxy type
        valid_types = ['vmess', 'vless', 'trojan', 'ss', 'ssr', 'http', 'socks5']
        if proxy.get('type') not in valid_types:
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
    
    def _remove_duplicates(self, proxies: List[Dict]) -> List[Dict]:
        """Remove duplicate proxies based on server+port."""
        seen = set()
        unique_proxies = []
        
        for proxy in proxies:
            # Create identifier from server and port
            identifier = f"{proxy.get('server', '')}:{proxy.get('port', '')}"
            
            if identifier not in seen:
                seen.add(identifier)
                unique_proxies.append(proxy)
        
        return unique_proxies


# Legacy health checker classes have been moved to health_checker.py
# This module now focuses only on node fetching functionality
