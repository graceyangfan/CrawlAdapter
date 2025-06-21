# CrawlAdapter

A professional proxy management tool for web scraping and HTTP requests, featuring automatic proxy rotation, health monitoring, and Clash integration.

## Overview

CrawlAdapter provides a complete proxy management solution that handles the entire workflow from node fetching to intelligent proxy switching. It separates web scraping logic from proxy management, allowing developers to focus on their core scraping tasks while ensuring reliable proxy functionality.

## Key Features

- **Complete Proxy Workflow**: Automated node fetching → health checking → config generation → Clash management → proxy switching
- **Intelligent Health Monitoring**: Multi-URL testing with adaptive scoring and automatic failover
- **Rule-Based Routing**: Flexible domain-based routing with DIRECT fallback for non-proxy traffic
- **Automatic Process Management**: Clash binary detection, process lifecycle management, and cleanup
- **Framework Agnostic**: Works with any HTTP client (aiohttp, requests, httpx, etc.)
- **Production Ready**: PEP8 compliant, comprehensive error handling, and detailed logging

## Architecture

### Core Workflow

```
1. Binary Detection → 2. Node Fetching → 3. Health Validation → 4. Config Generation
                                                                          ↓
8. Proxy Switching ← 7. Rule Application ← 6. Clash Restart ← 5. Process Management
```

### Component Separation

- **CrawlAdapter**: Handles all proxy-related operations (nodes, health checks, Clash management, switching)
- **Web Scrapers**: Focus solely on data extraction and parsing (e.g., PanewsLabCrawler)
- **Clean Interface**: Simple API for proxy URL retrieval and manual switching

## Quick Start

### Installation

#### Development Installation (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/CrawlAdapter.git
cd CrawlAdapter

# Install in development mode
pip install -e .

# Verify installation
python -c "from crawladapter import ProxyClient; print('✅ Installation successful')"
```

#### Production Installation

```bash
# Install from local directory
pip install .

# Or with optional features
pip install .[monitoring,examples]
```

For detailed installation instructions, see [INSTALLATION.md](INSTALLATION.md).

### Basic Usage

```python
import asyncio
from crawladapter import ProxyClient

async def main():
    # Initialize with automatic binary and config detection
    client = ProxyClient()

    # Start with custom routing rules
    await client.start(rules=[
        '*.panewslab.com',      # Use proxy for news sites
        '*.httpbin.org',        # Use proxy for testing
        # Other domains use DIRECT connection
    ])

    # Get proxy URL for requests
    proxy_url = await client.get_proxy('https://www.panewslab.com')

    # Use with any HTTP client
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(url, proxy=proxy_url) as response:
            content = await response.text()

    # Clean shutdown
    await client.stop()

# Run the example
asyncio.run(main())
```

### News Crawler Integration

```python
from examples.panewslab_crawler import PanewsLabCrawler

# Crawler focuses only on web scraping
crawler = PanewsLabCrawler(
    proxy_enabled=True,
    proxy_rules=['*.panewslab.com', '*.httpbin.org']
)

await crawler.start()
news_items = await crawler.fetch_newsflash(limit=10)
await crawler.stop()
```

## Configuration

### Custom Proxy Sources

```python
# Configure custom node sources
custom_sources = {
    'clash': [
        'https://example.com/clash-config.yaml',
        'https://another.com/nodes.yaml'
    ],
    'v2ray': [
        'https://example.com/v2ray-subscription'
    ]
}

from crawladapter import NodeFetcher
client = ProxyClient()
client.node_fetcher = NodeFetcher(custom_sources=custom_sources)
```

### Health Check Configuration

```python
# Set custom health check URLs
health_urls = [
    'http://httpbin.org/ip',                    # HTTP test
    'https://www.google.com/generate_204',      # HTTPS connectivity
    'https://detectportal.firefox.com/success.txt'  # Network detection
]

client.set_health_check_urls(health_urls)
```

### Routing Rules

```python
# Define domain-based routing rules
rules = [
    '*.panewslab.com',      # News sites through proxy
    '*.coindesk.com',       # Crypto news through proxy
    '*.httpbin.org',        # Testing endpoints through proxy
    # All other domains use DIRECT connection automatically
]

await client.start(rules=rules)
```

## API Reference

### ProxyClient

Main proxy management client.

```python
ProxyClient(
    config_dir: str = './clash_configs',
    clash_binary_path: Optional[str] = None,
    auto_update_interval: int = 3600,
    enable_default_rules: bool = True
)
```

#### Core Methods

- `start(rules=None, config_type='scraping')`: Start the proxy client
- `stop()`: Stop the proxy client and cleanup
- `get_proxy(url)`: Get proxy URL for a specific target
- `switch_proxy(strategy='round_robin')`: Manually switch proxy
- `get_proxy_info()`: Get current proxy information
- `set_health_check_urls(urls)`: Set custom health check URLs

### NodeFetcher

Fetches proxy nodes from various sources.

#### Methods

- `fetch_nodes(source_type='all')`: Fetch nodes from sources
- `add_custom_nodes(nodes)`: Add custom proxy nodes
- `set_custom_sources(sources)`: Set custom source URLs

### HealthChecker

Monitors proxy health and performance.

#### Methods

- `check_proxy_health(proxy_name, clash_api_base)`: Check single proxy
- `check_all_proxies(proxies, clash_api_base)`: Check all proxies
- `get_health_stats()`: Get health statistics

## Project Structure

```
CrawlAdapter/
├── crawladapter/           # Core proxy management package
│   ├── core.py            # Main ProxyClient implementation
│   ├── fetchers.py        # Node fetching and health checking
│   └── __init__.py        # Package exports
├── examples/              # Usage examples
│   └── panewslab_crawler.py  # News crawler example
├── clash_configs/         # Clash configuration directory
├── mihomo_proxy/          # Clash binary directory
├── requirements.txt       # Python dependencies
└── setup.py              # Package installation
```

## Examples

See the `examples/` directory for complete usage examples:

- `panewslab_crawler.py`: News crawler with proxy support
- `complete_news_crawler_test.py`: Comprehensive testing example

## Requirements

- Python 3.8+
- aiohttp
- PyYAML
- BeautifulSoup4
- Clash/Mihomo binary

## License

MIT License - see LICENSE file for details.