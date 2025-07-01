"""
CrawlAdapter Type Definitions

Contains all data types, enums, and data structures used throughout the library.
Separated from core.py to improve modularity and reduce file size.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union


# ============================================================================
# Enums
# ============================================================================

class ProxyType(Enum):
    """Supported proxy types."""
    VMESS = "vmess"
    VLESS = "vless"
    SHADOWSOCKS = "ss"
    TROJAN = "trojan"
    HTTP = "http"
    SOCKS5 = "socks5"


class LoadBalanceStrategy(Enum):
    """Load balancing strategies."""
    HEALTH_WEIGHTED = "health_weighted"
    ROUND_ROBIN = "round_robin"
    LEAST_USED = "least_used"
    RANDOM = "random"


class ConfigType(Enum):
    """Configuration types."""
    SCRAPING = "scraping"
    SPEED = "speed"
    GENERAL = "general"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ProxyNode:
    """Standardized proxy node information."""
    name: str
    server: str
    port: int
    type: ProxyType
    config: Dict
    
    # Health and usage tracking
    health_score: float = 0.0
    last_checked: Optional[datetime] = None
    usage_count: int = 0
    last_used: Optional[datetime] = None
    
    # Performance metrics
    avg_latency: float = 0.0
    success_rate: float = 0.0
    
    def __post_init__(self):
        """Post-initialization processing."""
        if isinstance(self.type, str):
            self.type = ProxyType(self.type)
    
    @property
    def is_healthy(self) -> bool:
        """Check if proxy is considered healthy."""
        # Lower health threshold to consider more proxies as healthy
        return self.health_score > 0.1
    
    def to_dict(self) -> Dict:
        """Convert to dictionary format."""
        return {
            'name': self.name,
            'server': self.server,
            'port': self.port,
            'type': self.type.value,
            **self.config
        }


@dataclass
class HealthCheckResult:
    """Health check result for a proxy."""
    proxy_name: str
    success: bool
    latency: float = 0.0
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Detailed metrics
    connectivity: float = 0.0
    success_rate: float = 0.0
    stability: float = 0.0
    overall_score: float = 0.0


@dataclass
class ProxyStats:
    """Proxy usage and performance statistics."""
    total_proxies: int
    healthy_proxies: int
    failed_proxies: int
    health_rate: float
    
    # Usage statistics
    total_usage: int
    average_usage: float
    most_used_proxy: str
    most_used_count: int
    least_used_proxy: str
    least_used_count: int
    
    # Timing
    last_update: float
    last_health_check: float


@dataclass
class ProxyConfig:
    """Configuration for proxy client."""
    config_dir: str = './clash_configs'
    clash_binary_path: Optional[str] = None
    proxy_port: int = 7890
    api_port: int = 9090
    auto_update_interval: int = 3600
    enable_default_rules: bool = True
    enable_adaptive_health_check: bool = False
    enable_metrics: bool = False
    
    @property
    def clash_api_base(self) -> str:
        """Get Clash API base URL."""
        return f"http://127.0.0.1:{self.api_port}"
    
    @property
    def proxy_url(self) -> str:
        """Get proxy URL for HTTP clients."""
        return f"http://127.0.0.1:{self.proxy_port}"

    def to_dict(self) -> Dict:
        """Convert to dictionary format for serialization."""
        return {
            'config_dir': self.config_dir,
            'clash_binary_path': self.clash_binary_path,
            'proxy_port': self.proxy_port,
            'api_port': self.api_port,
            'auto_update_interval': self.auto_update_interval,
            'enable_default_rules': self.enable_default_rules,
            'enable_adaptive_health_check': self.enable_adaptive_health_check,
            'enable_metrics': self.enable_metrics
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ProxyConfig':
        """Create ProxyConfig from dictionary."""
        return cls(**data)


@dataclass
class StartupOptions:
    """Options for starting the proxy client."""
    config_type: str = 'scraping'
    source_types: Optional[List[str]] = None
    enable_auto_update: bool = True
    rules: Optional[List[str]] = None
    custom_sources: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'config_type': self.config_type,
            'source_types': self.source_types,
            'enable_auto_update': self.enable_auto_update,
            'rules': self.rules,
            'custom_sources': self.custom_sources
        }


# ============================================================================
# Type Aliases
# ============================================================================

ProxyDict = Dict[str, Union[str, int, Dict]]
HealthResults = Dict[str, HealthCheckResult]
ProxyList = List[ProxyNode]
RuleList = List[str]
