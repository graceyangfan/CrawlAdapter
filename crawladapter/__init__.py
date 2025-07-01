"""
CrawlAdapter - Professional Proxy Management Tool

Focused on core functionality:
- Node fetching and health checking
- Clash configuration generation and management
- Proxy switching and IP monitoring
- Web scraper support

Usage example:
    from crawladapter import ProxyClient

    client = ProxyClient()
    await client.start(rules=["*.panewslab.com"])

    proxy_url = await client.get_proxy("https://www.panewslab.com")
    # Use proxy_url for HTTP requests
"""

# Import core functionality from new modular structure
from .client import ProxyClient
from .simple_client import SimpleProxyClient, create_simple_client, get_proxy_for_url
from .config_loader import load_config, create_proxy_config, get_config_loader
from .types import (
    ProxyNode,
    HealthCheckResult,
    ProxyStats,
    ProxyConfig,
    StartupOptions,
    ProxyType,
    LoadBalanceStrategy,
    ConfigType,
    ProxyDict,
    HealthResults,
    ProxyList,
    RuleList
)
from .exceptions import (
    CrawlAdapterError,
    ProxyNotAvailableError,
    ConfigurationError,
    HealthCheckError,
    NodeFetchError,
    RuleError,
    ClashProcessError,
    ProxyConnectionError
)

# Import node fetcher and health monitor
from .fetchers import NodeFetcher
from .health_checker import HealthChecker

# Import managers (backward compatibility)
try:
    from .managers import ConfigurationManager, ProxyManager
except ImportError:
    ConfigurationManager = None
    ProxyManager = None

# Import rule management (backward compatibility)
try:
    from .rules import RuleManager, RuleTemplates, RuleCategory
except ImportError:
    RuleManager = None
    RuleTemplates = None
    RuleCategory = None

# Version information
__version__ = "2.0.0"
__author__ = "CrawlAdapter Team"
__license__ = "MIT"

__all__ = [
    # Core classes
    'ProxyClient',
    'SimpleProxyClient',
    'NodeFetcher',
    'HealthChecker',

    # Data types
    'ProxyNode',
    'HealthCheckResult',
    'ProxyStats',
    'ProxyConfig',
    'StartupOptions',

    # Enums
    'ProxyType',
    'LoadBalanceStrategy',
    'ConfigType',

    # Exceptions
    'CrawlAdapterError',
    'ProxyNotAvailableError',
    'ConfigurationError',
    'HealthCheckError',
    'NodeFetchError',
    'RuleError',
    'ClashProcessError',
    'ProxyConnectionError',

    # Type aliases
    'ProxyDict',
    'HealthResults',
    'ProxyList',
    'RuleList',

    # Convenience functions
    'create_simple_client',
    'get_proxy_for_url',
    'load_config',
    'create_proxy_config',
    'get_config_loader',

    # Managers (backward compatibility)
    'ConfigurationManager',
    'ProxyManager',
    'RuleManager',
    'RuleTemplates',
    'RuleCategory',
]