# Clash Proxy Adapter for Web Scraping

A comprehensive Clash proxy client designed for web scraping applications that need to avoid IP bans through automatic proxy rotation and load balancing.

## Features

- **Automatic Node Fetching**: Fetches free proxy nodes from getNode project and other sources
- **Multiple Proxy Formats**: Supports Clash and V2Ray node formats with automatic conversion
- **Health Monitoring**: Comprehensive health checking with latency measurement and success rate tracking
- **Load Balancing**: Multiple strategies including health-weighted, round-robin, least-used, and random selection
- **Automatic Failover**: Intelligent proxy switching when nodes fail
- **Easy Integration**: Simple API for integration with existing scraping frameworks
- **Background Updates**: Automatic proxy list updates and health monitoring
- **Configuration Management**: Template-based configuration generation with backup support

## Installation

### Prerequisites

1. **Clash Binary**: Install Clash or Mihomo (clash-verge-rev core)
   - Download from [Clash releases](https://github.com/Dreamacro/clash/releases)
   - Or [Mihomo releases](https://github.com/MetaCubeX/mihomo/releases)
   - Or install via package manager

2. **Python Dependencies**:
   ```bash
   pip install aiohttp pyyaml psutil
   ```

### Quick Start

```python
import asyncio
from nautilus_trader.adapters.clash import ClashProxyClient

async def main():
    # Initialize client
    client = ClashProxyClient(config_dir='./clash_configs')
    
    try:
        # Start with scraping-optimized configuration
        await client.start(config_type='scraping')
        
        # Get proxy URL for HTTP requests
        proxy_url = await client.get_proxy_url()
        print(f"Proxy URL: {proxy_url}")
        
        # Use with aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'http://httpbin.org/ip',
                proxy=proxy_url
            ) as response:
                data = await response.json()
                print(f"Current IP: {data['origin']}")
    
    finally:
        await client.stop()

asyncio.run(main())
```

## API Reference

### ClashProxyClient

Main client class for managing Clash proxy operations.

#### Constructor

```python
ClashProxyClient(
    config_dir: str = './clash_configs',
    clash_binary_path: Optional[str] = None,
    auto_update_interval: int = 3600
)
```

**Parameters:**
- `config_dir`: Directory for storing configurations
- `clash_binary_path`: Path to Clash binary (auto-detected if None)
- `auto_update_interval`: Interval for automatic proxy updates in seconds

#### Methods

##### `async start(config_type='scraping', source_types=None, enable_auto_update=True)`

Start the Clash proxy client.

**Parameters:**
- `config_type`: Configuration type ('scraping', 'speed', 'general')
- `source_types`: List of proxy source types (['clash', 'v2ray'] or ['all'])
- `enable_auto_update`: Enable automatic proxy list updates

**Returns:** `bool` - True if started successfully

##### `async stop()`

Stop the client and cleanup resources.

##### `async get_proxy_url(strategy='health_weighted')`

Get proxy URL for HTTP clients.

**Parameters:**
- `strategy`: Selection strategy ('health_weighted', 'round_robin', 'least_used', 'random')

**Returns:** `Optional[str]` - Proxy URL or None

##### `async get_proxy_info()`

Get current proxy information and statistics.

**Returns:** `Dict` - Comprehensive proxy information

##### `async switch_proxy(proxy_name=None, strategy='health_weighted')`

Switch to specific proxy or select using strategy.

**Parameters:**
- `proxy_name`: Specific proxy name to switch to
- `strategy`: Selection strategy if proxy_name is None

**Returns:** `bool` - True if switch successful

##### `async test_proxy(proxy_name, test_url='http://httpbin.org/ip')`

Test a specific proxy.

**Parameters:**
- `proxy_name`: Name of proxy to test
- `test_url`: URL to test with

**Returns:** `Dict` - Test results with latency and IP information

## Configuration Types

### Scraping Configuration (Default)

Optimized for web scraping with fallback and load balancing:

```yaml
proxy-groups:
  - name: PROXY
    type: select
    proxies: ['auto-fallback', 'load-balance', ...]
  - name: auto-fallback
    type: fallback
    proxies: [...]
    url: 'http://www.gstatic.com/generate_204'
    interval: 300
    tolerance: 150
  - name: load-balance
    type: load-balance
    proxies: [...]
    strategy: round-robin
```

### Speed Configuration

Optimized for fastest connection:

```yaml
proxy-groups:
  - name: PROXY
    type: select
    proxies: ['auto-speed', ...]
  - name: auto-speed
    type: url-test
    proxies: [...]
    interval: 180
    tolerance: 50
```

### General Configuration

Balanced configuration for general use:

```yaml
proxy-groups:
  - name: PROXY
    type: select
    proxies: ['auto', ...]
  - name: auto
    type: url-test
    proxies: [...]
    interval: 300
```

## Load Balancing Strategies

### Health Weighted

Selects proxies based on health scores with higher probability for healthier proxies.

```python
proxy_url = await client.get_proxy_url(strategy='health_weighted')
```

### Round Robin

Cycles through healthy proxies in order.

```python
proxy_url = await client.get_proxy_url(strategy='round_robin')
```

### Least Used

Selects the proxy with the lowest usage count.

```python
proxy_url = await client.get_proxy_url(strategy='least_used')
```

### Random

Randomly selects from healthy proxies.

```python
proxy_url = await client.get_proxy_url(strategy='random')
```

## Health Monitoring

The client continuously monitors proxy health using multiple metrics:

- **Connectivity**: Success rate across multiple test endpoints
- **Latency**: Average response time in milliseconds
- **Stability**: Consistency of performance over time
- **Overall Score**: Weighted combination of all metrics

Health checks run automatically every 5 minutes, and proxies are scored from 0-1.

## Integration Examples

### With aiohttp

```python
async with ClashProxyClient() as client:
    proxy_url = await client.get_proxy_url()
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, proxy=proxy_url) as response:
            data = await response.text()
```

### With requests (synchronous)

```python
# Setup
client = ClashProxyClient()
await client.start()
proxy_url = await client.get_proxy_url()

# Use with requests
proxies = {'http': proxy_url, 'https': proxy_url}
response = requests.get(url, proxies=proxies)

# Cleanup
await client.stop()
```

### With Scrapy

```python
class ProxyMiddleware:
    def __init__(self):
        self.client = ClashProxyClient()
        
    async def process_request(self, request, spider):
        proxy_url = await self.client.get_proxy_url()
        if proxy_url:
            request.meta['proxy'] = proxy_url
```

## Error Handling

The client provides robust error handling:

```python
try:
    proxy_url = await client.get_proxy_url()
    if not proxy_url:
        # No healthy proxies available
        await asyncio.sleep(60)  # Wait and retry
        return
    
    # Make request with timeout
    async with session.get(url, proxy=proxy_url, timeout=10) as response:
        data = await response.text()
        
except asyncio.TimeoutError:
    # Switch to different proxy on timeout
    await client.switch_proxy(strategy='health_weighted')
    
except Exception as e:
    # Log error and continue with next proxy
    logger.error(f"Request failed: {e}")
```

## Monitoring and Statistics

Get comprehensive statistics about proxy performance:

```python
info = await client.get_proxy_info()

print(f"Total proxies: {info['proxy_stats']['total_proxies']}")
print(f"Healthy proxies: {info['proxy_stats']['healthy_proxies']}")
print(f"Health rate: {info['health_stats']['health_rate']:.2%}")
print(f"Average score: {info['health_stats']['average_score']}")
```

## Troubleshooting

### Common Issues

1. **Clash binary not found**
   - Install Clash or Mihomo
   - Set `clash_binary_path` parameter
   - Add binary to system PATH

2. **No healthy proxies**
   - Check internet connection
   - Verify getNode sources are accessible
   - Wait for automatic proxy updates

3. **High latency**
   - Use 'speed' configuration type
   - Adjust health check intervals
   - Filter proxies by region

### Logging

Enable debug logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

Contributions are welcome! Please ensure:

- PEP8 style compliance
- English comments and documentation
- Comprehensive test coverage
- Example usage for new features

## License

This project is part of the Nautilus Trader framework and follows the same licensing terms.
