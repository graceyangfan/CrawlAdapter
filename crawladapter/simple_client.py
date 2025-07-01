"""
CrawlAdapter Simple Client

Ultra-simplified proxy client interface for easy integration.
Provides only the essential methods needed for most use cases.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Union

from .types import ProxyConfig
from .client import ProxyClient as FullProxyClient
from .exceptions import CrawlAdapterError
from .config_loader import create_proxy_config, get_config_loader


class SimpleProxyClient:
    """
    Ultra-simplified proxy client with minimal interface.
    
    This is a facade over the full ProxyClient that provides only
    the essential methods needed for most use cases.
    
    Example:
        client = SimpleProxyClient()
        await client.start()
        
        proxy_url = await client.get_proxy("https://example.com")
        # Use proxy_url with your HTTP client
        
        await client.stop()
    """
    
    def __init__(
        self,
        config_dir: str = './clash_configs',
        clash_binary_path: Optional[str] = None,
        proxy_port: int = 7890,
        api_port: int = 9090,
        enable_rules: bool = True,
        custom_sources: Optional[Dict] = None,
        config_file: Optional[str] = None
    ):
        """
        Initialize simple proxy client.

        Args:
            config_dir: Directory for storing configurations
            clash_binary_path: Absolute path to Clash binary (optional, auto-detected if None)
            proxy_port: Port for proxy server
            api_port: Port for Clash API
            enable_rules: Enable intelligent routing rules
            custom_sources: Custom proxy node sources
            config_file: Path to configuration file (optional)
        """
        self.logger = logging.getLogger(__name__)

        # Create configuration using config loader
        self.config = create_proxy_config(
            config_file=config_file,
            config_dir=config_dir,
            clash_binary_path=clash_binary_path,
            proxy_port=proxy_port,
            api_port=api_port,
            enable_default_rules=enable_rules,
            enable_adaptive_health_check=False,  # Keep it simple
            enable_metrics=False  # Keep it simple
        )
        
        # Store custom sources for later use
        self.custom_sources = custom_sources
        
        # Internal full client
        self._client = FullProxyClient(self.config)
        
        # State
        self.is_running = False
    
    async def start(self, rules: Optional[List[str]] = None) -> bool:
        """
        Start the proxy client.
        
        Args:
            rules: Optional list of routing rules (domains, IPs, patterns)
                  Example: ["*.example.com", "192.168.1.0/24"]
        
        Returns:
            True if started successfully
        
        Raises:
            CrawlAdapterError: If startup fails
        """
        try:
            self.logger.info("🚀 Starting simple proxy client...")
            
            # Use default rules if none provided and rules are enabled
            if rules is None and self.config.enable_default_rules:
                rules = [
                    # Common sites that benefit from proxy
                    "*.panewslab.com",
                    "*.httpbin.org",
                    "*.ipinfo.io",
                    "*.ifconfig.co"
                ]
            
            success = await self._client.start(
                config_type='scraping',
                rules=rules,
                custom_sources=self.custom_sources,
                enable_auto_update=False  # Keep it simple
            )
            
            if success:
                self.is_running = True
                self.logger.info("✅ Simple proxy client started successfully")
                return True
            else:
                self.logger.error("❌ Failed to start simple proxy client")
                return False
                
        except Exception as e:
            self.logger.error(f"Error starting simple proxy client: {e}")
            raise CrawlAdapterError(f"Failed to start proxy client: {str(e)}")
    
    async def get_proxy(self, url: Optional[str] = None) -> Optional[str]:
        """
        Get proxy URL for making HTTP requests.
        
        Args:
            url: Target URL to check against routing rules (optional)
        
        Returns:
            Proxy URL string if proxy should be used, None for direct connection
        
        Example:
            proxy_url = await client.get_proxy("https://example.com")
            if proxy_url:
                # Use proxy
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, proxy=proxy_url) as response:
                        content = await response.text()
            else:
                # Use direct connection
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        content = await response.text()
        """
        if not self.is_running:
            self.logger.warning("Proxy client not running, returning None")
            return None
        
        try:
            return await self._client.get_proxy(url)
        except Exception as e:
            self.logger.error(f"Error getting proxy: {e}")
            return None
    
    async def switch_proxy(self) -> bool:
        """
        Switch to a different proxy.
        
        Returns:
            True if switch was successful
        """
        if not self.is_running:
            self.logger.warning("Proxy client not running")
            return False
        
        try:
            return await self._client.switch_proxy()
        except Exception as e:
            self.logger.error(f"Error switching proxy: {e}")
            return False
    
    async def get_status(self) -> Dict:
        """
        Get simple status information.
        
        Returns:
            Dictionary with basic status information
        """
        try:
            if not self.is_running:
                return {
                    'running': False,
                    'proxy_port': self.config.proxy_port,
                    'config_dir': self.config.config_dir
                }
            
            full_info = await self._client.get_proxy_info()
            
            # Simplify the information
            return {
                'running': full_info.get('is_running', False),
                'proxy_port': full_info.get('proxy_port', self.config.proxy_port),
                'config_dir': full_info.get('config_dir', self.config.config_dir),
                'total_proxies': full_info.get('proxy_stats', {}).get('total_proxies', 0),
                'healthy_proxies': full_info.get('proxy_stats', {}).get('healthy_proxies', 0),
                'current_proxy': full_info.get('current_proxy', 'DIRECT'),
                'api_available': full_info.get('clash_api_available', False)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting status: {e}")
            return {
                'running': self.is_running,
                'error': str(e)
            }
    
    async def stop(self) -> None:
        """
        Stop the proxy client and clean up resources.
        """
        try:
            if self.is_running:
                self.logger.info("Stopping simple proxy client...")
                await self._client.stop()
                self.is_running = False
                self.logger.info("✅ Simple proxy client stopped")
        except Exception as e:
            self.logger.error(f"Error stopping simple proxy client: {e}")
    
    # Context manager support
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
    
    def __str__(self) -> str:
        """String representation."""
        status = "running" if self.is_running else "stopped"
        return f"SimpleProxyClient(status={status}, port={self.config.proxy_port})"


# ============================================================================
# Convenience Functions
# ============================================================================

async def create_simple_client(
    config_dir: str = './clash_configs',
    clash_binary_path: Optional[str] = None,
    proxy_port: int = 7890,
    api_port: int = 9090,
    rules: Optional[List[str]] = None,
    custom_sources: Optional[Dict] = None
) -> SimpleProxyClient:
    """
    Create and start a simple proxy client in one call.

    Args:
        config_dir: Directory for storing configurations
        clash_binary_path: Absolute path to Clash binary (optional)
        proxy_port: Port for proxy server
        api_port: Port for Clash API
        rules: Optional routing rules
        custom_sources: Custom proxy node sources

    Returns:
        Started SimpleProxyClient instance

    Example:
        client = await create_simple_client(
            clash_binary_path="/usr/local/bin/mihomo",
            config_dir="/home/user/clash_configs",
            rules=["*.example.com"],
            custom_sources={'clash': ['https://example.com/config.yml']}
        )

        proxy_url = await client.get_proxy("https://example.com")
        # Use proxy_url...

        await client.stop()
    """
    client = SimpleProxyClient(
        config_dir=config_dir,
        clash_binary_path=clash_binary_path,
        proxy_port=proxy_port,
        api_port=api_port,
        custom_sources=custom_sources
    )
    
    await client.start(rules=rules)
    return client


async def get_proxy_for_url(
    url: str,
    config_dir: str = './clash_configs',
    rules: Optional[List[str]] = None
) -> Optional[str]:
    """
    One-shot function to get proxy URL for a specific target.
    
    This creates a temporary client, gets the proxy URL, and cleans up.
    Useful for simple scripts that only need occasional proxy access.
    
    Args:
        url: Target URL
        config_dir: Directory for storing configurations
        rules: Optional routing rules
    
    Returns:
        Proxy URL if proxy should be used, None for direct connection
    
    Example:
        proxy_url = await get_proxy_for_url(
            "https://example.com",
            rules=["*.example.com"]
        )
        
        if proxy_url:
            # Use proxy for this request
            pass
    """
    client = SimpleProxyClient(config_dir=config_dir)
    
    try:
        await client.start(rules=rules)
        return await client.get_proxy(url)
    finally:
        await client.stop()
