"""
CrawlAdapter Core Module

Legacy compatibility module that re-exports the new modular components.
The main functionality has been moved to separate modules for better organization.

For new code, prefer importing directly from the specific modules:
- from crawladapter.client import ProxyClient
- from crawladapter.types import ProxyNode, ProxyConfig
- from crawladapter.exceptions import CrawlAdapterError
"""

# Import from new modular structure
from .types import (
    ProxyType,
    LoadBalanceStrategy, 
    ConfigType,
    ProxyNode,
    HealthCheckResult,
    ProxyStats,
    ProxyConfig,
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

from .client import ProxyClient

# Legacy compatibility - all functionality moved to modular structure
# This module now serves as a compatibility layer for existing code

# For backward compatibility, also expose the main classes directly
__all__ = [
    # Core classes
    'ProxyClient',
    
    # Data types
    'ProxyNode',
    'HealthCheckResult', 
    'ProxyStats',
    'ProxyConfig',
    
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
    'RuleList'
]
