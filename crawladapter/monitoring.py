"""
Monitoring and Metrics Collection for CrawlAdapter

Consolidates MetricsCollector and dependency injection functionality.
"""

import time
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
import json
import logging


class MetricType(Enum):
    """Types of metrics that can be collected."""
    COUNTER = "counter"      # Incrementing values
    GAUGE = "gauge"         # Current values
    HISTOGRAM = "histogram"  # Distribution of values
    TIMER = "timer"         # Duration measurements


@dataclass
class MetricValue:
    """A single metric value with timestamp."""
    value: float
    timestamp: float = field(default_factory=time.time)
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSeries:
    """A series of metric values."""
    name: str
    metric_type: MetricType
    description: str
    values: deque = field(default_factory=lambda: deque(maxlen=1000))
    total_count: int = 0
    
    def add_value(self, value: float, labels: Optional[Dict[str, str]] = None):
        """Add a new metric value."""
        metric_value = MetricValue(value, labels=labels or {})
        self.values.append(metric_value)
        self.total_count += 1
    
    def get_latest(self) -> Optional[MetricValue]:
        """Get the latest metric value."""
        return self.values[-1] if self.values else None
    
    def get_average(self, window_size: int = 100) -> float:
        """Get average value over recent samples."""
        if not self.values:
            return 0.0
        
        recent_values = list(self.values)[-window_size:]
        return sum(v.value for v in recent_values) / len(recent_values)
    
    def get_sum(self) -> float:
        """Get sum of all values (useful for counters)."""
        return sum(v.value for v in self.values)


class MetricsCollector:
    """
    Lightweight metrics collector for performance monitoring.
    
    Features:
    - Low overhead metric collection
    - Multiple metric types (counter, gauge, histogram, timer)
    - Automatic aggregation and statistics
    - Thread-safe operations
    - Optional persistence
    """
    
    def __init__(self, max_series_length: int = 1000, enable_persistence: bool = False):
        """
        Initialize metrics collector.
        
        Args:
            max_series_length: Maximum number of values to keep per metric
            enable_persistence: Whether to persist metrics to disk
        """
        self.max_series_length = max_series_length
        self.enable_persistence = enable_persistence
        self.logger = logging.getLogger(__name__)
        
        # Thread-safe storage
        self._metrics: Dict[str, MetricSeries] = {}
        self._lock = threading.RLock()
        
        # Built-in metrics
        self._init_builtin_metrics()
    
    def _init_builtin_metrics(self):
        """Initialize built-in metrics for CrawlAdapter."""
        builtin_metrics = [
            ("proxy_switches", MetricType.COUNTER, "Number of proxy switches"),
            ("health_checks", MetricType.COUNTER, "Number of health checks performed"),
            ("failed_requests", MetricType.COUNTER, "Number of failed requests"),
            ("active_proxies", MetricType.GAUGE, "Number of active proxies"),
            ("healthy_proxies", MetricType.GAUGE, "Number of healthy proxies"),
            ("request_latency", MetricType.HISTOGRAM, "Request latency in milliseconds"),
            ("proxy_success_rate", MetricType.GAUGE, "Overall proxy success rate"),
            ("config_generations", MetricType.COUNTER, "Number of config generations"),
            ("node_fetches", MetricType.COUNTER, "Number of node fetch operations"),
            ("client_starts", MetricType.COUNTER, "Number of client starts"),
            ("config_updates", MetricType.COUNTER, "Number of configuration updates"),
            ("proxy_requests", MetricType.COUNTER, "Number of proxy requests"),
        ]
        
        for name, metric_type, description in builtin_metrics:
            self.register_metric(name, metric_type, description)
    
    def register_metric(self, name: str, metric_type: MetricType, description: str = "") -> None:
        """Register a new metric."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = MetricSeries(
                    name=name,
                    metric_type=metric_type,
                    description=description
                )
                self.logger.debug(f"Registered metric: {name} ({metric_type.value})")
    
    def increment(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric."""
        with self._lock:
            if name not in self._metrics:
                self.register_metric(name, MetricType.COUNTER)
            
            metric = self._metrics[name]
            if metric.metric_type != MetricType.COUNTER:
                self.logger.warning(f"Metric {name} is not a counter")
                return
            
            # For counters, we add to the previous value
            latest = metric.get_latest()
            current_value = latest.value if latest else 0.0
            metric.add_value(current_value + value, labels)
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric value."""
        with self._lock:
            if name not in self._metrics:
                self.register_metric(name, MetricType.GAUGE)
            
            metric = self._metrics[name]
            if metric.metric_type != MetricType.GAUGE:
                self.logger.warning(f"Metric {name} is not a gauge")
                return
            
            metric.add_value(value, labels)
    
    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a value in a histogram metric."""
        with self._lock:
            if name not in self._metrics:
                self.register_metric(name, MetricType.HISTOGRAM)
            
            metric = self._metrics[name]
            if metric.metric_type != MetricType.HISTOGRAM:
                self.logger.warning(f"Metric {name} is not a histogram")
                return
            
            metric.add_value(value, labels)
    
    def time_function(self, metric_name: str, labels: Optional[Dict[str, str]] = None):
        """Decorator to time function execution."""
        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration_ms = (time.time() - start_time) * 1000
                    self.record_histogram(metric_name, duration_ms, labels)
            return wrapper
        return decorator
    
    def timer_context(self, metric_name: str, labels: Optional[Dict[str, str]] = None):
        """Context manager for timing operations."""
        return TimerContext(self, metric_name, labels)
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a metric series by name."""
        with self._lock:
            return self._metrics.get(name)
    
    def get_all_metrics(self) -> Dict[str, MetricSeries]:
        """Get all registered metrics."""
        with self._lock:
            return self._metrics.copy()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        with self._lock:
            summary = {}
            
            for name, metric in self._metrics.items():
                latest = metric.get_latest()
                
                metric_summary = {
                    'type': metric.metric_type.value,
                    'description': metric.description,
                    'total_count': metric.total_count,
                    'latest_value': latest.value if latest else None,
                    'latest_timestamp': latest.timestamp if latest else None,
                }
                
                # Add type-specific statistics
                if metric.metric_type == MetricType.HISTOGRAM:
                    metric_summary['average'] = metric.get_average()
                    if metric.values:
                        values = [v.value for v in metric.values]
                        metric_summary['min'] = min(values)
                        metric_summary['max'] = max(values)
                
                elif metric.metric_type == MetricType.COUNTER:
                    metric_summary['total'] = metric.get_sum()
                
                summary[name] = metric_summary
            
            return summary
    
    def reset_metric(self, name: str) -> None:
        """Reset a specific metric."""
        with self._lock:
            if name in self._metrics:
                self._metrics[name].values.clear()
                self._metrics[name].total_count = 0
                self.logger.debug(f"Reset metric: {name}")
    
    def reset_all_metrics(self) -> None:
        """Reset all metrics."""
        with self._lock:
            for metric in self._metrics.values():
                metric.values.clear()
                metric.total_count = 0
            self.logger.info("Reset all metrics")
    
    def export_metrics(self, format: str = 'json') -> str:
        """Export metrics in specified format."""
        summary = self.get_summary()
        
        if format.lower() == 'json':
            return json.dumps(summary, indent=2)
        elif format.lower() == 'prometheus':
            return self._export_prometheus_format(summary)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _export_prometheus_format(self, summary: Dict[str, Any]) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        for name, data in summary.items():
            # Add help text
            if data['description']:
                lines.append(f"# HELP {name} {data['description']}")
            
            # Add type
            lines.append(f"# TYPE {name} {data['type']}")
            
            # Add value
            if data['latest_value'] is not None:
                lines.append(f"{name} {data['latest_value']}")
        
        return '\n'.join(lines)


class TimerContext:
    """Context manager for timing operations."""
    
    def __init__(self, collector: MetricsCollector, metric_name: str, labels: Optional[Dict[str, str]] = None):
        self.collector = collector
        self.metric_name = metric_name
        self.labels = labels
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = (time.time() - self.start_time) * 1000
            self.collector.record_histogram(self.metric_name, duration_ms, self.labels)


# Global metrics collector instance
_global_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _global_collector
    if _global_collector is None:
        _global_collector = MetricsCollector()
    return _global_collector


def set_metrics_collector(collector: MetricsCollector) -> None:
    """Set the global metrics collector instance."""
    global _global_collector
    _global_collector = collector


# Convenience functions for common operations
def increment_counter(name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
    """Increment a counter metric."""
    get_metrics_collector().increment(name, value, labels)


def set_gauge(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    """Set a gauge metric."""
    get_metrics_collector().set_gauge(name, value, labels)


def record_latency(name: str, latency_ms: float, labels: Optional[Dict[str, str]] = None) -> None:
    """Record a latency measurement."""
    get_metrics_collector().record_histogram(name, latency_ms, labels)


def time_operation(metric_name: str, labels: Optional[Dict[str, str]] = None):
    """Decorator to time operations."""
    return get_metrics_collector().time_function(metric_name, labels)


def timer(metric_name: str, labels: Optional[Dict[str, str]] = None):
    """Context manager for timing operations."""
    return get_metrics_collector().timer_context(metric_name, labels)


# Simple dependency injection container for backward compatibility
class DIContainer:
    """Simple dependency injection container."""
    
    def __init__(self):
        self._services: Dict[type, Any] = {}
        self._singletons: Dict[type, Any] = {}
    
    def register_singleton(self, interface: type, implementation: Any) -> None:
        """Register a singleton instance."""
        self._singletons[interface] = implementation
    
    def get(self, interface: type) -> Any:
        """Get an instance of the requested type."""
        if interface in self._singletons:
            return self._singletons[interface]
        
        if interface in self._services:
            return self._services[interface]()
        
        # Try to create directly
        try:
            return interface()
        except:
            raise ValueError(f"No registration found for {interface.__name__}")


def setup_default_container() -> DIContainer:
    """Setup container with default implementations."""
    container = DIContainer()
    
    # Register default implementations
    from .managers import ConfigurationManager, ProxyManager
    from .fetchers import HealthChecker, NodeFetcher
    from .rules import RuleManager
    
    container.register_singleton(ConfigurationManager, ConfigurationManager())
    container.register_singleton(ProxyManager, ProxyManager())
    container.register_singleton(HealthChecker, HealthChecker())
    container.register_singleton(NodeFetcher, NodeFetcher())
    container.register_singleton(RuleManager, RuleManager())
    container.register_singleton(MetricsCollector, get_metrics_collector())
    
    return container
