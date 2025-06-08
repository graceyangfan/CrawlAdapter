"""
Clash Proxy Adapter for Web Scraping

This module provides a comprehensive Clash proxy client for avoiding IP bans
during web scraping operations. It supports automatic node fetching, health
checking, load balancing, and proxy rotation.

Features:
- Automatic free node fetching from getNode project
- Support for Clash and V2Ray node formats
- Health checking and latency monitoring
- Load balancing and automatic failover
- Easy integration with web scraping frameworks
"""

from .client import ClashProxyClient
from .config_manager import ConfigurationManager
from .health_checker import EnhancedHealthChecker
from .node_fetcher import NodeFetcher
from .proxy_manager import UnifiedProxyConfigManager

__all__ = [
    "ClashProxyClient",
    "ConfigurationManager", 
    "EnhancedHealthChecker",
    "NodeFetcher",
    "UnifiedProxyConfigManager",
]
