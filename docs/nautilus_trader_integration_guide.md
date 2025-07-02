# Nautilus Trader Integration Guide

## Development Guide for News Data Client and Strategy Adaptation

This guide provides comprehensive insights for developing custom data clients and strategies that integrate with Nautilus Trader, using the PANews crawler as a reference implementation.

## 1. Core Architecture Design

### Data Flow Architecture
```
PanewsLab API → PANewsDataClient → CustomData → SimpleNewsStrategy
                     ↑
              CrawlAdapter ProxyClient
```

### Component Separation
- **PANewsDataClient**: Focuses on data acquisition and proxy management
- **SimpleNewsStrategy**: Handles business logic processing
- **CrawlAdapter**: Independent proxy management module

## 2. Data Client Development Guidelines

### 2.1 Custom Data Type Definition

```python
@customdataclass
class PANewsData(Data):
    """PANews news data type"""
    title: str
    content: str
    url: str
    publish_time: str
    symbols: str = ""  # Comma-separated related trading symbols
    category: str = "news"
    source: str = "PANews"
    news_id: str = ""
    
    def get_symbols_list(self) -> List[str]:
        """Get trading symbols list"""
        if not self.symbols:
            return []
        return [s.strip() for s in self.symbols.split(',') if s.strip()]
    
    def is_crypto_related(self) -> bool:
        """Check if news is cryptocurrency related"""
        crypto_keywords = [
            'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'blockchain',
            'defi', 'nft'
        ]
        text = (self.title + ' ' + self.content).lower()
        return any(keyword in text for keyword in crypto_keywords)
```

**Key Points**:
- Use `@customdataclass` decorator
- Inherit from `Data` base class
- Provide business-related helper methods

### 2.2 Configuration Class Design

```python
class PANewsDataClientConfig(LiveDataClientConfig, frozen=True):
    """PANews data client configuration"""
    # Basic configuration
    base_url: str = "https://www.panewslab.com"
    scraping_interval: int = 300  # User configurable scraping interval
    max_news_per_request: int = 5
    
    # Proxy configuration - User customizable
    enable_proxy: bool = True
    clash_config_dir: str = "./clash_configs"
    clash_binary_path: Optional[str] = None
    proxy_port: int = 7890
    api_port: int = 9090
    enable_rules: bool = True
```

**Key Points**:
- Inherit from `LiveDataClientConfig`
- Use `frozen=True` to ensure immutability
- Provide user-configurable key parameters
- Set default values in `__post_init__`

### 2.3 Core Client Implementation

```python
class PANewsDataClient(LiveMarketDataClient):
    async def _connect(self):
        """Connect to data source"""
        # 1. Initialize proxy client
        await self._setup_proxy_client()
        
        # 2. Create HTTP session
        self._session = aiohttp.ClientSession(...)
        
        # 3. Start periodic scraping task
        self._scraping_task = self._loop.create_task(self._scraping_loop())
```

**Key Points**:
- Inherit from `LiveMarketDataClient`
- Initialize all components in `_connect()`
- Use async tasks for periodic data acquisition
- Integrate proxy client with fault tolerance

### 2.4 Data Publishing Mechanism

```python
# Publish news data as CustomData
for item in new_items:
    custom_data = CustomData(
        data_type=DataType(PANewsData, metadata={"source": "PANews"}),
        data=item
    )
    self._handle_data(custom_data)
```

**Key Points**:
- Wrap custom data with `CustomData`
- Publish to message bus via `self._handle_data()`
- Set appropriate `DataType` and metadata

## 3. Strategy Development Guidelines

### 3.1 Strategy Configuration

```python
class SimpleNewsStrategyConfig(StrategyConfig, frozen=True):
    """Simple news strategy configuration"""
    news_client_id: str = "PANEWS"

class SimpleNewsStrategy(Strategy):
    def __init__(self, config: SimpleNewsStrategyConfig):
        super().__init__(config)
        self.news_client_id = ClientId(config.news_client_id)
```

### 3.2 Data Subscription

```python
def on_start(self):
    """Subscribe to news data when strategy starts"""
    self.subscribe_data(
        data_type=DataType(PANewsData, metadata={"source": "PANews"}),
        client_id=self.news_client_id
    )
```

### 3.3 Data Processing

```python
def on_data(self, data: Data):
    """Process received data"""
    # Check if it's PANewsData type
    if isinstance(data, PANewsData):
        self._process_news(data)
    # Also check CustomData format
    elif isinstance(data, CustomData):
        news_data = data.data
        if isinstance(news_data, PANewsData):
            self._process_news(news_data)
```

## 4. System Integration Configuration

### 4.1 Trading Node Configuration

```python
# Create trading node configuration
config = TradingNodeConfig(
    trader_id="NewsTrader-001",
    data_clients={
        "PANEWS": news_config  # Data client configuration
    },
    strategies=[strategy_config],  # Strategy configuration list
    timeout_connection=180.0,  # Accommodate proxy initialization time
)

# Create trading node
node = TradingNode(config=config)

# Register data client factory
node.add_data_client_factory("PANEWS", PANewsDataClientFactory)
```

### 4.2 Factory Class Implementation

```python
class PANewsDataClientFactory(LiveDataClientFactory):
    @staticmethod
    def create(loop, name, config, msgbus, cache, clock) -> PANewsDataClient:
        client_id = ClientId(name)
        venue = Venue("PANEWS")
        instrument_provider = InstrumentProvider()  # News data doesn't need instruments
        
        return PANewsDataClient(...)
```

## 5. Proxy Integration Guidelines

### 5.1 Proxy Client Integration

```python
async def _setup_proxy_client(self):
    """Setup proxy client"""
    proxy_params = {
        'config_dir': self._config.clash_config_dir,
        'proxy_port': self._config.proxy_port,
        'api_port': self._config.api_port,
        'enable_rules': self._config.enable_rules,
    }
    
    self._proxy_client = SimpleProxyClient(**proxy_params)
    success = await self._proxy_client.start(rules=startup_rules)
```

### 5.2 Proxy Rules Configuration

```python
# Ensure target domains are in proxy rules
target_domains = [
    "*.panewslab.com",
    "panewslab.com", 
    "www.panewslab.com"
]

# Health check domains
health_check_domains = [
    "*.gstatic.com",
    "*.httpbin.org",
    "*.google.com"
]
```

## 6. Extension Development Guide

### 6.1 New Data Source Adaptation Steps

1. **Define Data Type**: Create custom data class inheriting from `Data`
2. **Implement Configuration**: Inherit from `LiveDataClientConfig`
3. **Develop Client**: Inherit from `LiveMarketDataClient`
4. **Create Factory**: Inherit from `LiveDataClientFactory`
5. **Develop Strategy**: Inherit from `Strategy`
6. **System Integration**: Configure `TradingNode`

### 6.2 Key Considerations

- **Error Handling**: Automatic fallback to direct connection when proxy fails
- **Retry Mechanism**: Retry logic for network request failures
- **Data Deduplication**: Avoid processing duplicate news
- **Timeout Configuration**: Accommodate proxy initialization time
- **Logging**: Detailed status and error logging

### 6.3 User Customizable Configuration

Users can customize through configuration:
- Scraping interval (`scraping_interval`)
- Proxy settings (`clash_config_dir`, `proxy_port`)
- Request parameters (`max_news_per_request`, `timeout`)
- Proxy rules (`proxy_rules`)
- Custom proxy sources (`custom_sources`)

## 7. Best Practices

### 7.1 Performance Optimization
- Use connection pooling for HTTP sessions
- Implement efficient data parsing
- Cache frequently accessed data
- Use async/await properly

### 7.2 Error Resilience
- Implement graceful degradation
- Use circuit breaker patterns
- Provide meaningful error messages
- Log errors with context

### 7.3 Monitoring and Observability
- Track data acquisition metrics
- Monitor proxy health status
- Log performance statistics
- Implement health checks

This architecture design achieves clear separation of concerns, making it easy to extend and maintain, providing a complete reference template for other users developing similar news data adapters.
