# CrawlAdapter

**Universal Proxy Management for Web Scraping**

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-beta-orange.svg)](https://github.com/graceyangfan/CrawlAdapter)

CrawlAdapter is a comprehensive and extensible proxy management library built on Clash, designed for web scraping applications that require intelligent proxy rotation, custom routing rules, and seamless integration with various scraping frameworks.

## 🚀 Key Features

- **Intelligent Proxy Management**: Automatic proxy node fetching, health checking, and rotation
- **Clash Integration**: Built on the powerful Clash proxy engine with full configuration control
- **Smart Routing**: Rule-based traffic routing with support for domain patterns and custom rules
- **Health Monitoring**: Adaptive health checking with multiple strategies and automatic failover
- **Easy Integration**: Simple API for integration with existing web scraping projects
- **Extensible Architecture**: Modular design supporting custom sources, health strategies, and configurations
- **Production Ready**: Comprehensive error handling, logging, and monitoring capabilities

## 📋 Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Components](#core-components)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [API Reference](#api-reference)
- [Advanced Features](#advanced-features)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## 🔧 Installation

### Prerequisites

- Python 3.8 or higher
- Clash binary (mihomo) - automatically downloaded during setup

### Install from Source

```bash
git clone https://github.com/graceyangfan/CrawlAdapter.git
cd CrawlAdapter
pip install -e .
```

### Setup Clash Binary

CrawlAdapter requires the Clash (mihomo) binary. Run the setup script to automatically download it:

```bash
python setup_clash_binary.py
```

Or use the utility module:

```python
from utils import download_clash_binary
download_clash_binary()
```

## 🚀 Quick Start

### Basic Usage

```python
import asyncio
from crawladapter import ProxyClient

async def main():
    # Initialize the proxy client
    client = ProxyClient()
    
    # Start with custom rules for specific domains
    await client.start(rules=["*.example.com", "*.target-site.com"])
    
    # Get proxy URL for a request
    proxy_url = await client.get_proxy("https://example.com")
    
    # Use the proxy with your HTTP client
    if proxy_url:
        # Make request through proxy
        async with aiohttp.ClientSession() as session:
            async with session.get("https://example.com", proxy=proxy_url) as response:
                content = await response.text()
    
    # Clean shutdown
    await client.stop()

asyncio.run(main())
```

### Simple Client for Quick Setup

```python
from crawladapter import create_simple_client

async def quick_example():
    # Create and start client in one step
    client = await create_simple_client(
        rules=["*.panewslab.com"],
        custom_sources={
            'clash': ['https://example.com/config.yml']
        }
    )
    
    # Use the client
    proxy_url = await client.get_proxy("https://panewslab.com")
    
    await client.stop()
```

## 🏗️ Core Components

### Architecture Overview

CrawlAdapter follows a modular architecture with clear separation of concerns:

```
crawladapter/
├── client.py              # Main ProxyClient interface
├── simple_client.py       # Simplified client for quick setup
├── core.py                # Legacy compatibility layer
├── fetchers.py            # Node fetching from various sources
├── health_checker.py      # Health monitoring and validation
├── health_strategies.py   # Different health checking strategies
├── process_manager.py     # Clash process lifecycle management
├── config_generator.py    # Dynamic configuration generation
├── config_loader.py       # Configuration loading and validation
├── managers.py            # Configuration, proxy, and rule managers
├── rules.py               # Traffic routing rule management
├── types.py               # Type definitions and data models
└── exceptions.py          # Custom exception classes
```

### Key Classes

#### ProxyClient
The main interface for proxy management:
- Handles complete proxy lifecycle
- Integrates all components seamlessly
- Provides intelligent proxy selection
- Manages health monitoring

#### SimpleProxyClient
Simplified interface for quick integration:
- Minimal configuration required
- Automatic setup and teardown
- Perfect for simple use cases

#### NodeFetcher
Responsible for obtaining proxy nodes:
- Supports Clash and V2Ray configurations
- Custom source integration
- Automatic parsing and validation

#### HealthChecker
Monitors proxy health and performance:
- Multiple health checking strategies
- Adaptive check intervals
- Automatic failover handling

## ⚙️ Configuration

### Configuration Sources

CrawlAdapter supports multiple configuration methods:

1. **Default Configuration**: Built-in templates for common use cases
2. **Custom Sources**: Fetch nodes from external URLs
3. **Manual Configuration**: Direct proxy node specification
4. **Environment Variables**: Runtime configuration overrides

### Configuration Templates

The library includes optimized templates for different scenarios:

```yaml
# Scraping-optimized configuration
clash_templates:
  scraping:
    mode: rule
    log_level: warning
    dns:
      enable: true
      enhanced_mode: fake-ip
    proxy_groups:
      - name: "PROXY"
        type: select
      - name: "AUTO"
        type: url-test
        interval: 300
```

### Custom Rules

Define routing rules for specific domains or patterns:

```python
rules = [
    "*.example.com",           # All subdomains of example.com
    "target-site.com",         # Specific domain
    "DOMAIN-SUFFIX,api.com",   # Clash rule format
    "IP-CIDR,192.168.1.0/24"  # IP range
]
```

## 📚 Usage Examples

### Web Scraping Integration

```python
import aiohttp
from crawladapter import ProxyClient

class WebScraper:
    def __init__(self):
        self.proxy_client = ProxyClient()

    async def start(self):
        await self.proxy_client.start(rules=["*.target-site.com"])

    async def scrape_url(self, url):
        proxy_url = await self.proxy_client.get_proxy(url)

        async with aiohttp.ClientSession() as session:
            kwargs = {"proxy": proxy_url} if proxy_url else {}
            async with session.get(url, **kwargs) as response:
                return await response.text()

    async def stop(self):
        await self.proxy_client.stop()
```

### Real-World Example: News Crawler

Based on the included `examples/panewslab_crawler.py`:

```python
import aiohttp
from crawladapter import ProxyClient

class PanewsLabCrawler:
    """Professional news crawler with proxy support."""

    def __init__(self, custom_sources=None):
        self.proxy_client = ProxyClient()
        self.custom_sources = custom_sources
        self.api_endpoint = "https://www.panewslab.com/webapi/flashnews"

    async def start(self):
        """Initialize the crawler with proxy support."""
        await self.proxy_client.start(
            rules=["*.panewslab.com"],
            custom_sources=self.custom_sources
        )

    async def fetch_news(self, limit=10):
        """Fetch latest news with automatic proxy rotation."""
        proxy_url = await self.proxy_client.get_proxy(self.api_endpoint)

        params = {"LId": 1, "Rn": limit, "tw": 0}

        async with aiohttp.ClientSession() as session:
            kwargs = {"proxy": proxy_url} if proxy_url else {}
            async with session.get(
                self.api_endpoint,
                params=params,
                **kwargs
            ) as response:
                data = await response.json()
                return self._parse_news_data(data)

    def _parse_news_data(self, data):
        """Parse news data from API response."""
        news_items = []
        for item in data.get('data', []):
            news_items.append({
                'title': item.get('title', ''),
                'content': item.get('content', ''),
                'publish_time': item.get('publish_time', ''),
                'symbols': item.get('symbols', [])
            })
        return news_items

    async def stop(self):
        """Clean shutdown."""
        await self.proxy_client.stop()

# Usage
async def main():
    crawler = PanewsLabCrawler(
        custom_sources={
            'clash': ['https://example.com/clash-config.yml']
        }
    )

    await crawler.start()
    news = await crawler.fetch_news(limit=5)

    for item in news:
        print(f"📰 {item['title']}")

    await crawler.stop()

asyncio.run(main())
```

### Custom Node Sources

```python
custom_sources = {
    'clash': [
        'https://example.com/clash-config.yml',
        'https://another-source.com/config.yaml'
    ],
    'v2ray': [
        'https://v2ray-source.com/subscription'
    ]
}

client = ProxyClient()
await client.start(
    rules=["*.target.com"],
    custom_sources=custom_sources
)
```

### Health Monitoring

```python
from crawladapter import ProxyClient
from crawladapter.health_strategies import AdaptiveHealthStrategy

# Use adaptive health checking
client = ProxyClient()
await client.start(
    rules=["*.example.com"],
    health_strategy=AdaptiveHealthStrategy(
        base_interval=60,  # Base check interval
        max_concurrent=10  # Max concurrent checks
    )
)

# Monitor health status
stats = await client.get_proxy_stats()
for proxy_name, stats in stats.items():
    print(f"{proxy_name}: {stats.health_score:.2f}")
```

## 📖 API Reference

### ProxyClient

#### Constructor
```python
ProxyClient(
    config_dir: Optional[str] = None,
    clash_binary_path: Optional[str] = None,
    proxy_port: int = 7890,
    api_port: int = 9090
)
```

#### Methods

##### start()
```python
async def start(
    rules: Optional[List[str]] = None,
    custom_sources: Optional[Dict] = None,
    config_path: Optional[str] = None
) -> bool
```
Initialize and start the proxy client with specified rules and sources.

##### get_proxy()
```python
async def get_proxy(
    url: Optional[str] = None,
    strategy: str = 'health_weighted'
) -> Optional[str]
```
Get proxy URL for a specific target URL based on routing rules.

##### stop()
```python
async def stop() -> None
```
Clean shutdown of all proxy services and processes.

##### get_proxy_stats()
```python
async def get_proxy_stats() -> Dict[str, ProxyStats]
```
Retrieve current health and performance statistics for all proxies.

### SimpleProxyClient

#### create_simple_client()
```python
async def create_simple_client(
    config_dir: Optional[str] = None,
    clash_binary_path: Optional[str] = None,
    proxy_port: int = 7890,
    api_port: int = 9090,
    rules: Optional[List[str]] = None,
    custom_sources: Optional[Dict] = None
) -> SimpleProxyClient
```
Create and initialize a simple proxy client in one step.

### Configuration Types

#### ProxyNode
```python
@dataclass
class ProxyNode:
    name: str
    type: ProxyType
    server: str
    port: int
    cipher: Optional[str] = None
    password: Optional[str] = None
    # ... additional fields
```

#### HealthCheckResult
```python
@dataclass
class HealthCheckResult:
    proxy_name: str
    success: bool
    response_time: float
    overall_score: float
    error_message: Optional[str] = None
```

## 🔧 Advanced Features

### Custom Health Strategies

Implement custom health checking logic:

```python
from crawladapter.health_strategies import BaseHealthStrategy

class CustomHealthStrategy(BaseHealthStrategy):
    async def check_proxy(self, proxy_name: str, clash_api_base: str):
        # Custom health check implementation
        result = await self._perform_custom_test(proxy_name)
        return HealthCheckResult(
            proxy_name=proxy_name,
            success=result.success,
            response_time=result.latency,
            overall_score=self._calculate_score(result)
        )

# Use custom strategy
client = ProxyClient()
client.health_checker.strategy = CustomHealthStrategy()
```

### Rule-Based Routing

Advanced routing configuration:

```python
from crawladapter.rules import RuleManager, RuleCategory

rule_manager = RuleManager()

# Add rules by category
rule_manager.add_rule("*.social-media.com", RuleCategory.SOCIAL)
rule_manager.add_rule("*.news-site.com", RuleCategory.NEWS)
rule_manager.add_rule("DIRECT", RuleCategory.BYPASS)

# Custom rule logic
def custom_rule_logic(url: str) -> bool:
    # Implement custom routing logic
    return "api" in url or "cdn" in url

rule_manager.add_custom_rule(custom_rule_logic)
```

### Performance Monitoring

Monitor and optimize proxy performance:

```python
import time
from crawladapter import ProxyClient

class PerformanceMonitor:
    def __init__(self, client: ProxyClient):
        self.client = client
        self.metrics = {}

    async def monitor_request(self, url: str):
        start_time = time.time()
        proxy_url = await self.client.get_proxy(url)

        # Make request and measure performance
        # ... request logic ...

        end_time = time.time()
        self.metrics[url] = {
            'proxy_used': proxy_url is not None,
            'response_time': end_time - start_time,
            'timestamp': start_time
        }

    def get_performance_report(self):
        return self.metrics
```

### Integration with Popular Frameworks

#### Scrapy Integration

```python
from scrapy import Spider
from crawladapter import ProxyClient

class ProxySpider(Spider):
    name = 'proxy_spider'

    def __init__(self):
        super().__init__()
        self.proxy_client = ProxyClient()

    async def start_requests(self):
        await self.proxy_client.start(rules=["*.target-site.com"])

        for url in self.start_urls:
            proxy_url = await self.proxy_client.get_proxy(url)
            meta = {'proxy': proxy_url} if proxy_url else {}
            yield scrapy.Request(url, meta=meta)

    def closed(self, reason):
        asyncio.run(self.proxy_client.stop())
```

#### Requests Integration

```python
import requests
from crawladapter import get_proxy_for_url

def make_request(url: str):
    proxy_url = asyncio.run(get_proxy_for_url(url, rules=["*.example.com"]))

    proxies = {'http': proxy_url, 'https': proxy_url} if proxy_url else None
    response = requests.get(url, proxies=proxies)
    return response
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. Clash Binary Not Found

**Problem**: `ClashProcessError: Clash binary not found`

**Solution**:
```bash
# Run the setup script
python setup_clash_binary.py

# Or manually specify the path
client = ProxyClient(clash_binary_path="/path/to/mihomo")
```

#### 2. No Healthy Proxies

**Problem**: All proxies fail health checks

**Solutions**:
- Check network connectivity
- Verify proxy sources are accessible
- Adjust health check timeout settings
- Use different health check URLs

```python
from crawladapter.health_strategies import BasicHealthStrategy

# Use more lenient health checking
strategy = BasicHealthStrategy(
    timeout=30,  # Increase timeout
    test_urls=[
        "http://www.gstatic.com/generate_204",
        "http://httpbin.org/ip"
    ]
)
```

#### 3. Configuration Errors

**Problem**: Invalid configuration or parsing errors

**Solution**:
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Validate configuration
from crawladapter.config_loader import load_config
config = load_config("path/to/config.yaml")
```

#### 4. Port Conflicts

**Problem**: Ports already in use

**Solution**:
```python
# Use different ports
client = ProxyClient(
    proxy_port=7891,  # Default: 7890
    api_port=9091     # Default: 9090
)
```

### Performance Optimization

#### 1. Health Check Optimization

```python
from crawladapter.health_strategies import AdaptiveHealthStrategy

# Optimize health checking
strategy = AdaptiveHealthStrategy(
    base_interval=120,      # Check every 2 minutes
    max_concurrent=5,       # Limit concurrent checks
    timeout=15,             # Faster timeout
    retry_count=2           # Fewer retries
)
```

#### 2. Memory Usage

```python
# Limit node count for memory efficiency
client = ProxyClient()
await client.start(
    rules=["*.target.com"],
    max_nodes=50  # Limit to 50 best nodes
)
```

#### 3. Network Optimization

```python
# Configure for high-throughput scenarios
config = {
    'clash_config': {
        'mixed_port': 7890,
        'allow_lan': False,
        'mode': 'rule',
        'log_level': 'warning',  # Reduce logging overhead
        'external_controller': '127.0.0.1:9090'
    }
}
```

### Debugging

#### Enable Detailed Logging

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable specific module logging
logging.getLogger('crawladapter.health_checker').setLevel(logging.DEBUG)
logging.getLogger('crawladapter.process_manager').setLevel(logging.DEBUG)
```

#### Health Check Debugging

```python
# Manual health check
from crawladapter.health_checker import HealthChecker
from crawladapter.health_strategies import BasicHealthStrategy

checker = HealthChecker(BasicHealthStrategy())
results = await checker.check_proxies(proxies, "http://127.0.0.1:9090")

for name, result in results.items():
    print(f"{name}: {'✅' if result.success else '❌'} ({result.response_time:.2f}ms)")
```

## 🏗️ Development and Contributing

### Development Setup

```bash
# Clone the repository
git clone https://github.com/graceyangfan/CrawlAdapter.git
cd CrawlAdapter

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=crawladapter --cov-report=html
```

### Project Structure

```
CrawlAdapter/
├── crawladapter/           # Main package
│   ├── __init__.py        # Package exports
│   ├── client.py          # Main client interface
│   ├── simple_client.py   # Simplified client
│   ├── core.py            # Legacy compatibility
│   ├── fetchers.py        # Node fetching
│   ├── health_checker.py  # Health monitoring
│   ├── process_manager.py # Process management
│   ├── config_generator.py # Config generation
│   ├── managers.py        # Various managers
│   ├── rules.py           # Routing rules
│   ├── types.py           # Type definitions
│   └── exceptions.py      # Custom exceptions
├── examples/              # Usage examples
├── utils/                 # Utility tools
├── tests/                 # Test suite
├── requirements.txt       # Dependencies
├── setup.py              # Package setup
└── README.md             # This file
```

### Contributing Guidelines

1. **Fork the repository** and create a feature branch
2. **Write tests** for new functionality
3. **Follow PEP 8** style guidelines
4. **Add documentation** for new features
5. **Submit a pull request** with clear description

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_client.py

# Run with coverage
pytest --cov=crawladapter

# Run integration tests (requires clash binary)
pytest tests/integration/ -v
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Clash/Mihomo**: The powerful proxy engine that powers CrawlAdapter
- **Community Contributors**: Thanks to all contributors who help improve this project
- **Open Source Libraries**: Built on top of excellent open source Python libraries

## 📞 Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/graceyangfan/CrawlAdapter/issues)
- **Documentation**: [Full documentation](https://github.com/graceyangfan/CrawlAdapter/blob/main/README.md)
- **Examples**: Check the `examples/` directory for more usage patterns

---

**CrawlAdapter** - Making web scraping proxy management simple and reliable.
