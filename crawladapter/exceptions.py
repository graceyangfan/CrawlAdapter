"""
CrawlAdapter Exception Classes

Contains all custom exceptions used throughout the library.
Separated from core.py to improve modularity and error handling organization.
"""


# ============================================================================
# Base Exception
# ============================================================================

class CrawlAdapterError(Exception):
    """Base exception for CrawlAdapter."""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self):
        if self.details:
            return f"{self.message} (Details: {self.details})"
        return self.message


# ============================================================================
# Specific Exceptions
# ============================================================================

class ProxyNotAvailableError(CrawlAdapterError):
    """Raised when no healthy proxies are available."""
    
    def __init__(self, message: str = "No healthy proxies available", 
                 total_proxies: int = 0, healthy_proxies: int = 0):
        super().__init__(message, {
            'total_proxies': total_proxies,
            'healthy_proxies': healthy_proxies
        })


class ConfigurationError(CrawlAdapterError):
    """Raised when there's a configuration error."""
    
    def __init__(self, message: str, config_type: str = None, config_path: str = None):
        super().__init__(message, {
            'config_type': config_type,
            'config_path': config_path
        })


class HealthCheckError(CrawlAdapterError):
    """Raised when health check fails."""
    
    def __init__(self, message: str, proxy_name: str = None, error_details: str = None):
        super().__init__(message, {
            'proxy_name': proxy_name,
            'error_details': error_details
        })


class NodeFetchError(CrawlAdapterError):
    """Raised when node fetching fails."""
    
    def __init__(self, message: str, source_url: str = None, source_type: str = None):
        super().__init__(message, {
            'source_url': source_url,
            'source_type': source_type
        })


class RuleError(CrawlAdapterError):
    """Raised when there's a rule-related error."""
    
    def __init__(self, message: str, rule: str = None, rule_type: str = None):
        super().__init__(message, {
            'rule': rule,
            'rule_type': rule_type
        })


class ClashProcessError(CrawlAdapterError):
    """Raised when there's a Clash process management error."""
    
    def __init__(self, message: str, binary_path: str = None, config_path: str = None):
        super().__init__(message, {
            'binary_path': binary_path,
            'config_path': config_path
        })


class ProxyConnectionError(CrawlAdapterError):
    """Raised when proxy connection fails."""
    
    def __init__(self, message: str, proxy_name: str = None, target_url: str = None):
        super().__init__(message, {
            'proxy_name': proxy_name,
            'target_url': target_url
        })


# ============================================================================
# Exception Utilities
# ============================================================================

def handle_exception(func):
    """Decorator to handle and log exceptions consistently."""
    import functools
    import logging
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except CrawlAdapterError:
            raise  # Re-raise our custom exceptions
        except Exception as e:
            logger = logging.getLogger(func.__module__)
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            raise CrawlAdapterError(f"Unexpected error in {func.__name__}: {str(e)}")
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except CrawlAdapterError:
            raise  # Re-raise our custom exceptions
        except Exception as e:
            logger = logging.getLogger(func.__module__)
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            raise CrawlAdapterError(f"Unexpected error in {func.__name__}: {str(e)}")
    
    # Return appropriate wrapper based on whether function is async
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper
