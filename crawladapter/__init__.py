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

# Import core functionality
from .core import (
    ProxyClient,
    ProxyNode,
    HealthCheckResult,
    ProxyStats,
    ProxyType,
    LoadBalanceStrategy,
    ConfigType,
    CrawlAdapterError,
    ProxyNotAvailableError,
    ConfigurationError,
    HealthCheckError,
    NodeFetchError,
    RuleError
)

# Import node fetcher and health checker
from .fetchers import NodeFetcher, HealthChecker

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
    'NodeFetcher',
    'HealthChecker',

    # Data types
    'ProxyNode',
    'HealthCheckResult',
    'ProxyStats',

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

    # Managers (backward compatibility)
    'ConfigurationManager',
    'ProxyManager',
    'RuleManager',
    'RuleTemplates',
    'RuleCategory',
]