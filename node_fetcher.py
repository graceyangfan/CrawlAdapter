"""
Node Fetcher Module

Fetches free proxy nodes from various sources including the getNode project.
Supports both Clash and V2Ray node formats with automatic conversion.
"""

import asyncio
import base64
import json
import logging
import re
import time
from typing import Dict, List, Optional, Union
from urllib.parse import parse_qs, urlparse

import aiohttp
import yaml


class NodeFetcher:
    """
    Fetches and processes proxy nodes from multiple sources.
    
    Supports:
    - getNode project (Clash and V2Ray formats)
    - Custom subscription URLs
    - Direct node configurations
    """
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        """
        Initialize the node fetcher.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
        
        # getNode project URLs
        self.getnode_urls = {
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
    
    async def fetch_nodes(self, source_type: str = 'all') -> List[Dict]:
        """
        Fetch nodes from specified sources.
        
        Args:
            source_type: Type of source ('clash', 'v2ray', or 'all')
            
        Returns:
            List of proxy node configurations
        """
        all_nodes = []
        
        if source_type in ['clash', 'all']:
            clash_nodes = await self._fetch_clash_nodes()
            all_nodes.extend(clash_nodes)
            
        if source_type in ['v2ray', 'all']:
            v2ray_nodes = await self._fetch_v2ray_nodes()
            all_nodes.extend(v2ray_nodes)
            
        self.logger.info(f"Fetched {len(all_nodes)} nodes from {source_type} sources")
        return all_nodes
    
    async def _fetch_clash_nodes(self) -> List[Dict]:
        """Fetch nodes from Clash format sources."""
        for url in self.getnode_urls['clash']:
            try:
                content = await self._fetch_url_content(url)
                if content:
                    config = yaml.safe_load(content)
                    if 'proxies' in config:
                        self.logger.info(f"Successfully fetched {len(config['proxies'])} Clash nodes from {url}")
                        return config['proxies']
            except Exception as e:
                self.logger.warning(f"Failed to fetch Clash nodes from {url}: {e}")
                continue
        
        self.logger.error("Failed to fetch Clash nodes from all sources")
        return []
    
    async def _fetch_v2ray_nodes(self) -> List[Dict]:
        """Fetch and convert V2Ray nodes to Clash format."""
        for url in self.getnode_urls['v2ray']:
            try:
                content = await self._fetch_url_content(url)
                if content:
                    v2ray_links = [line.strip() for line in content.split('\n') if line.strip()]
                    clash_nodes = []
                    
                    for link in v2ray_links:
                        try:
                            node = self._convert_v2ray_to_clash(link)
                            if node:
                                clash_nodes.append(node)
                        except Exception as e:
                            self.logger.debug(f"Failed to convert V2Ray link: {e}")
                            continue
                    
                    if clash_nodes:
                        self.logger.info(f"Successfully converted {len(clash_nodes)} V2Ray nodes from {url}")
                        return clash_nodes
                        
            except Exception as e:
                self.logger.warning(f"Failed to fetch V2Ray nodes from {url}: {e}")
                continue
        
        self.logger.error("Failed to fetch V2Ray nodes from all sources")
        return []
    
    async def _fetch_url_content(self, url: str) -> Optional[str]:
        """Fetch content from URL with retry logic."""
        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            return await response.text()
                        else:
                            self.logger.warning(f"HTTP {response.status} from {url}")
                            
            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    
        return None
    
    def _convert_v2ray_to_clash(self, v2ray_link: str) -> Optional[Dict]:
        """
        Convert V2Ray link to Clash proxy configuration.
        
        Supports vmess:// links with base64 encoded JSON configuration.
        """
        if not v2ray_link.startswith('vmess://'):
            return None
            
        try:
            # Decode base64 content
            encoded_data = v2ray_link[8:]  # Remove 'vmess://' prefix
            decoded_data = base64.b64decode(encoded_data).decode('utf-8')
            vmess_config = json.loads(decoded_data)
            
            # Convert to Clash format
            clash_config = {
                'name': vmess_config.get('ps', f"vmess-{vmess_config.get('add')}"),
                'type': 'vmess',
                'server': vmess_config.get('add'),
                'port': int(vmess_config.get('port', 443)),
                'uuid': vmess_config.get('id'),
                'alterId': int(vmess_config.get('aid', 0)),
                'cipher': 'auto'
            }
            
            # Handle network type
            network = vmess_config.get('net', 'tcp')
            clash_config['network'] = network
            
            if network == 'ws':
                clash_config['ws-opts'] = {
                    'path': vmess_config.get('path', '/'),
                    'headers': {'Host': vmess_config.get('host', '')} if vmess_config.get('host') else {}
                }
            
            # Handle TLS
            if vmess_config.get('tls') == 'tls':
                clash_config['tls'] = True
                if vmess_config.get('sni'):
                    clash_config['servername'] = vmess_config.get('sni')
            
            return clash_config
            
        except Exception as e:
            self.logger.debug(f"Failed to parse vmess link: {e}")
            return None
    
    async def validate_nodes(self, nodes: List[Dict]) -> List[Dict]:
        """
        Validate and filter nodes based on basic criteria.
        
        Args:
            nodes: List of proxy node configurations
            
        Returns:
            List of validated nodes
        """
        valid_nodes = []
        
        for node in nodes:
            if self._is_valid_node(node):
                valid_nodes.append(node)
            else:
                self.logger.debug(f"Invalid node filtered out: {node.get('name', 'unknown')}")
        
        self.logger.info(f"Validated {len(valid_nodes)} out of {len(nodes)} nodes")
        return valid_nodes
    
    def _is_valid_node(self, node: Dict) -> bool:
        """Check if a node configuration is valid."""
        required_fields = ['name', 'type', 'server', 'port']
        
        # Check required fields
        for field in required_fields:
            if field not in node or not node[field]:
                return False
        
        # Check server is not localhost or invalid IP
        server = node['server']
        if server in ['localhost', '127.0.0.1', '0.0.0.0']:
            return False
        
        # Check port is valid
        try:
            port = int(node['port'])
            if not (1 <= port <= 65535):
                return False
        except (ValueError, TypeError):
            return False
        
        return True
