"""
PANews Data Client - Integrated with CrawlAdapter's SimpleProxyClient
Focused on news crawling with seamless Nautilus Trader integration
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin
import aiohttp
import json

from nautilus_trader.live.data_client import LiveMarketDataClient
from nautilus_trader.model.identifiers import ClientId, Venue
from nautilus_trader.core.data import Data
from nautilus_trader.model.custom import customdataclass
from nautilus_trader.model.data import CustomData, DataType
from nautilus_trader.config import NautilusConfig
from nautilus_trader.live.config import LiveDataClientConfig
from nautilus_trader.common.providers import InstrumentProvider
from nautilus_trader.data.messages import SubscribeData, UnsubscribeData
from dataclasses import dataclass, field

# Import CrawlAdapter's SimpleProxyClient
try:
    from crawladapter import SimpleProxyClient
    CRAWLADAPTER_AVAILABLE = True
except ImportError:
    CRAWLADAPTER_AVAILABLE = False
    SimpleProxyClient = None


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
            'defi', 'nft', 'cryptocurrency', 'digital currency'
        ]
        text = (self.title + ' ' + self.content).lower()
        return any(keyword in text for keyword in crypto_keywords)


class PANewsDataClientConfig(LiveDataClientConfig, frozen=True):
    """PANews data client configuration"""
    # Basic configuration
    base_url: str = "https://www.panewslab.com"  # Restored to use HTTPS
    api_endpoint: str = "/webapi/flashnews"
    scraping_interval: int = 300  # 5 minutes, user configurable
    request_timeout: int = 30
    max_news_per_request: int = 5  # Get only latest 5 news items

    # Proxy configuration
    enable_proxy: bool = True
    proxy_rules: Optional[List[str]] = None
    custom_sources: Optional[Dict] = None
    clash_config_dir: str = "./clash_configs"
    clash_binary_path: Optional[str] = None  # User can set Clash binary path
    proxy_port: int = 7890  # User can set proxy port
    api_port: int = 9090  # User can set API port
    enable_rules: bool = True  # User can set whether to enable rules

    # Request configuration
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    def __post_init__(self):
        if self.proxy_rules is None:
            # Use msgspec.structs.force_setattr to modify frozen object
            import msgspec.structs
            msgspec.structs.force_setattr(self, 'proxy_rules', [
                # Target websites
                "*.panewslab.com",
                "panewslab.com",
                # Health check and IP detection websites
                "*.httpbin.org",
                "*.ipinfo.io",
                "*.gstatic.com",  # Google health check
                "*.google.com",   # Google services
                "*.cloudflare.com",  # Cloudflare test
                "*.github.com",   # GitHub connectivity test
                # Common connectivity test websites
                "connectivitycheck.gstatic.com",
                "www.gstatic.com",
                "clients3.google.com"
            ])


class PANewsDataClient(LiveMarketDataClient):
    """
    PANews Data Client - Integrated with SimpleProxyClient

    Focused on news crawling functionality, handling proxy management through SimpleProxyClient
    """
    
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        client_id: ClientId,
        venue: Venue,
        msgbus,
        cache,
        clock,
        config: PANewsDataClientConfig,
        instrument_provider: Optional[InstrumentProvider] = None,
        name: Optional[str] = None,
    ):
        # Create a fake instrument_provider since news data doesn't need trading instrument info
        if instrument_provider is None:
            instrument_provider = InstrumentProvider()

        super().__init__(
            loop=loop,
            client_id=client_id,
            venue=venue,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            instrument_provider=instrument_provider,
            config=config,
        )

        self._config = config
        self._name = name or "PANewsDataClient"

        # Component initialization
        self._proxy_client: Optional[SimpleProxyClient] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._scraping_task: Optional[asyncio.Task] = None

        # State management
        self._processed_news_ids: set = set()
        self._last_scrape_time: Optional[datetime] = None

        # Request headers
        self._headers = {
            'User-Agent': self._config.user_agent,
            'Accept': 'application/json, text/html, */*',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }

        self._log.info(f"Initialized {self._name}")
    
    async def _connect(self):
        """Connect to data source"""
        self._log.info("Connecting to PANews data source...")

        # Initialize proxy client (don't throw exceptions, continue even if failed)
        if self._config.enable_proxy and CRAWLADAPTER_AVAILABLE:
            try:
                await self._setup_proxy_client()
            except Exception as e:
                self._log.warning(f"Proxy setup failed, will use direct connection: {e}")
                self._proxy_client = None
        else:
            if not CRAWLADAPTER_AVAILABLE:
                self._log.warning("CrawlAdapter not available, using direct connection")
            else:
                self._log.info("Proxy disabled, using direct connection")

        # Create HTTP session (configure SSL to match successful requests example)
        timeout = aiohttp.ClientTimeout(total=self._config.request_timeout)
        # Create SSL context, disable certificate verification (similar to requests verify=False)
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self._session = aiohttp.ClientSession(
            timeout=timeout,
            headers=self._headers,
            connector=connector
        )

        # Start periodic scraping task
        self._scraping_task = self._loop.create_task(self._scraping_loop())

        self._log.info("✅ PANews data source connected successfully")
    
    async def _disconnect(self):
        """Disconnect"""
        self._log.info("Disconnecting PANews data source...")

        try:
            # Stop scraping task
            if self._scraping_task and not self._scraping_task.done():
                self._scraping_task.cancel()
                try:
                    await self._scraping_task
                except asyncio.CancelledError:
                    pass

            # Close HTTP session
            if self._session:
                await self._session.close()
                self._session = None

            # Stop proxy client
            if self._proxy_client:
                await self._proxy_client.stop()
                self._proxy_client = None

            self._log.info("✅ PANews data source disconnected")

        except Exception as e:
            self._log.error(f"Error disconnecting PANews data source: {e}")

    async def _setup_proxy_client(self):
        """Setup proxy client"""
        try:
            self._log.info("Initializing SimpleProxyClient...")

            # Prepare SimpleProxyClient parameters - using user configuration
            proxy_params = {
                'config_dir': self._config.clash_config_dir,
                'proxy_port': self._config.proxy_port,
                'api_port': self._config.api_port,
                'enable_rules': self._config.enable_rules,
            }

            # Add Clash binary path (if user set it)
            if self._config.clash_binary_path:
                proxy_params['clash_binary_path'] = self._config.clash_binary_path
                self._log.info(f"Using custom Clash binary path: {self._config.clash_binary_path}")

            # Add custom sources (if any)
            if self._config.custom_sources:
                proxy_params['custom_sources'] = self._config.custom_sources
                self._log.info(f"Using custom proxy sources: {list(self._config.custom_sources.keys())}")
            else:
                self._log.info("Using default proxy sources")

            self._log.info(f"Proxy configuration: port={self._config.proxy_port}, API port={self._config.api_port}, enable rules={self._config.enable_rules}")

            # Create SimpleProxyClient
            self._proxy_client = SimpleProxyClient(**proxy_params)

            # Start proxy client with extended rules and health check configuration
            startup_rules = self._config.proxy_rules.copy()

            # Ensure PANews domains are in rules (important!)
            panews_domains = [
                "*.panewslab.com",
                "panewslab.com",
                "www.panewslab.com"
            ]

            for domain in panews_domains:
                if domain not in startup_rules:
                    startup_rules.append(domain)
                    self._log.info(f"Adding PANews domain to proxy rules: {domain}")

            # Ensure health check URLs are in rules
            health_check_domains = [
                "*.gstatic.com",
                "www.gstatic.com",
                "connectivitycheck.gstatic.com",
                "*.google.com",
                "*.httpbin.org"
            ]

            for domain in health_check_domains:
                if domain not in startup_rules:
                    startup_rules.append(domain)

            self._log.info(f"Starting proxy client, rule count: {len(startup_rules)}")
            self._log.info(f"Proxy rules: {startup_rules}")  # Changed to info level for visibility

            success = await self._proxy_client.start(rules=startup_rules)

            if success:
                self._log.info("✅ SimpleProxyClient started successfully")

                # Get proxy status
                try:
                    status = await self._proxy_client.get_status()
                    healthy_proxies = status.get('healthy_proxies', 0)
                    total_proxies = status.get('total_proxies', 0)

                    self._log.info(f"Proxy status: total {total_proxies} nodes, {healthy_proxies} healthy")

                    if healthy_proxies > 0:
                        self._log.info("✅ Found available proxy nodes")
                        # Test proxy connectivity
                        await self._test_proxy_connectivity()
                    else:
                        self._log.warning("⚠️ No healthy proxy nodes, will use direct connection")

                except Exception as e:
                    self._log.warning(f"Failed to get proxy status: {e}")

            else:
                self._log.warning("SimpleProxyClient startup failed, using direct connection")
                self._proxy_client = None

        except Exception as e:
            self._log.error(f"Failed to setup proxy client: {e}")
            self._proxy_client = None

    async def _test_proxy_connectivity(self):
        """Test proxy connectivity"""
        if not self._proxy_client:
            return

        try:
            # Test multiple connectivity check URLs
            test_urls = [
                "http://www.gstatic.com/generate_204",
                "https://httpbin.org/ip",
                "https://www.panewslab.com"
            ]

            for test_url in test_urls:
                try:
                    proxy_url = await self._proxy_client.get_proxy(test_url)
                    if proxy_url:
                        self._log.info(f"✅ Proxy connectivity test successful: {test_url}")

                        # Test actual HTTP request (create temporary session to avoid dependency issues)
                        import ssl
                        ssl_context = ssl.create_default_context()
                        ssl_context.check_hostname = False
                        ssl_context.verify_mode = ssl.CERT_NONE
                        connector = aiohttp.TCPConnector(ssl=ssl_context)
                        async with aiohttp.ClientSession(connector=connector) as test_session:
                            async with test_session.get(test_url, proxy=proxy_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                                if response.status == 200:
                                    self._log.info(f"✅ Proxy HTTP request successful: {test_url} -> {response.status}")
                                else:
                                    self._log.warning(f"⚠️ Proxy HTTP request abnormal: {test_url} -> {response.status}")
                        break  # One success is enough
                    else:
                        self._log.warning(f"⚠️ Unable to get proxy URL: {test_url}")

                except Exception as e:
                    self._log.warning(f"⚠️ Proxy connectivity test failed: {test_url} -> {e}")
                    continue

        except Exception as e:
            self._log.warning(f"Proxy connectivity test exception: {e}")

    async def _scraping_loop(self):
        """Main loop for periodic news scraping"""
        self._log.info("Starting news scraping loop")

        while True:
            try:
                await self._scrape_and_publish_news()
                await asyncio.sleep(self._config.scraping_interval)

            except asyncio.CancelledError:
                self._log.info("News scraping loop cancelled")
                break
            except Exception as e:
                self._log.error(f"News scraping loop exception: {e}")
                # Wait shorter time before retry after error
                await asyncio.sleep(60)

    async def _scrape_and_publish_news(self):
        """Scrape and publish news"""
        try:
            self._log.info("Starting PANews scraping...")

            # Build API URL
            api_url = urljoin(
                self._config.base_url,
                f"{self._config.api_endpoint}?LId=1&Rn={self._config.max_news_per_request}&tw=0"
            )

            # Get proxy URL
            proxy_url = await self._get_proxy_url(api_url)

            if proxy_url:
                self._log.info(f"Using proxy: {proxy_url}")
                # Additional test: confirm proxy client correctly handles PANews domain
                test_panews_url = "https://www.panewslab.com"
                test_proxy = await self._get_proxy_url(test_panews_url)
                if test_proxy:
                    self._log.info(f"✅ PANews domain proxy confirmed: {test_proxy}")
                else:
                    self._log.warning("⚠️ PANews domain not handled by proxy, may cause connection failure")
            else:
                self._log.info("Using direct connection")

            # Make request (with retry logic)
            news_items = []
            max_retries = 3

            for attempt in range(max_retries):
                try:
                    async with self._session.get(api_url, proxy=proxy_url) as response:
                        if response.status == 200:
                            # Parse JSON response
                            json_data = await response.json()
                            news_items = self._parse_news_json(json_data)
                            break
                        elif response.status == 502 and attempt < max_retries - 1:
                            self._log.warning(f"Proxy request failed (HTTP {response.status}), trying direct connection (attempt {attempt + 1}/{max_retries})")
                            # If proxy fails, try direct connection
                            if attempt == 1:
                                proxy_url = None
                            continue
                        else:
                            self._log.error(f"Request failed: HTTP {response.status}")
                            return
                except Exception as e:
                    if attempt < max_retries - 1:
                        self._log.warning(f"Request exception, retrying (attempt {attempt + 1}/{max_retries}): {e}")
                        # Second attempt uses direct connection
                        if attempt == 1:
                            proxy_url = None
                        await asyncio.sleep(5)  # Wait 5 seconds before retry
                        continue
                    else:
                        self._log.error(f"Request finally failed: {e}")
                        return
            else:
                self._log.error("All retries failed")
                return

            # Filter new news and publish
            new_items = []
            for item in news_items:
                if item.news_id not in self._processed_news_ids:
                    new_items.append(item)
                    self._processed_news_ids.add(item.news_id)

            # Publish news data as CustomData
            for item in new_items:
                # Create CustomData wrapping news data
                custom_data = CustomData(
                    data_type=DataType(PANewsData, metadata={"source": "PANews"}),
                    data=item
                )
                self._handle_data(custom_data)

            self._log.info(f"Scraping completed: total {len(news_items)} items, {len(new_items)} new")
            self._last_scrape_time = datetime.now()

        except Exception as e:
            self._log.error(f"Failed to scrape news: {e}")

    async def _get_proxy_url(self, target_url: str) -> Optional[str]:
        """Get proxy URL"""
        if not self._proxy_client:
            return None

        try:
            return await self._proxy_client.get_proxy(target_url)
        except Exception as e:
            self._log.warning(f"Failed to get proxy URL: {e}")
            return None

    def _parse_news_json(self, json_data: dict) -> List[PANewsData]:
        """Parse JSON data to news objects"""
        news_items = []

        try:
            # Parse PANews API JSON structure
            if not json_data or 'data' not in json_data:
                self._log.warning("Invalid JSON structure: missing 'data' field")
                return []

            data = json_data['data']
            if not isinstance(data, dict) or 'flashNews' not in data:
                self._log.warning("Invalid JSON structure: missing 'flashNews' field")
                return []

            flash_news = data['flashNews']
            if not isinstance(flash_news, list) or len(flash_news) == 0:
                self._log.warning("Invalid JSON structure: 'flashNews' is not a valid list")
                return []

            # Get news list
            first_flash_news = flash_news[0]
            if not isinstance(first_flash_news, dict) or 'list' not in first_flash_news:
                self._log.warning("Invalid JSON structure: missing 'list' field")
                return []

            news_list = first_flash_news['list']
            if not isinstance(news_list, list):
                self._log.warning("Invalid JSON structure: 'list' is not a valid list")
                return []

            # Parse each news item
            for item in news_list:
                try:
                    news_item = self._parse_single_news_item(item)
                    if news_item:
                        news_items.append(news_item)
                except Exception as e:
                    self._log.warning(f"Failed to parse single news item: {e}")
                    continue

        except Exception as e:
            self._log.error(f"Failed to parse JSON data: {e}")

        return news_items

    def _parse_single_news_item(self, item: dict) -> Optional[PANewsData]:
        """Parse single news item"""
        try:
            # Extract basic information
            title = item.get('title', '').strip()
            if not title or len(title) < 3:
                return None

            content = item.get('desc', '').replace('\\r\\nOriginal link', '').replace('\\\\r\\\\n', '\n')
            news_id = str(item.get('id', ''))

            # Handle publish time
            publish_time_timestamp = item.get('publishTime', 0)
            if publish_time_timestamp:
                dt = datetime.fromtimestamp(publish_time_timestamp)
                publish_time = dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                publish_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Build URL
            item_type = item.get('type', 0)
            if news_id:
                if item_type == 2:  # Flash news type
                    url = urljoin(self._config.base_url, f"/zh/newsflash/{news_id}")
                else:
                    url = urljoin(self._config.base_url, f"/zh/articledetails/{news_id}.html")
            else:
                url = ""

            # Extract category information
            tags = item.get('tags')
            if isinstance(tags, list) and tags:
                category = ', '.join(str(tag) for tag in tags)
            elif tags:
                category = str(tags)
            else:
                category = 'flashnews'

            # Extract author information
            author_info = item.get('author', {})
            if isinstance(author_info, dict):
                author_name = author_info.get('name', '')
                if author_name:
                    category = f"{category} | {author_name}"

            # Extract trading symbol symbols
            symbols = self._extract_crypto_symbols(f"{title} {content}")
            symbols_str = ','.join(symbols) if symbols else ""

            # Create news data object
            return PANewsData(
                title=title,
                content=content,
                url=url,
                publish_time=publish_time,
                symbols=symbols_str,
                category=category,
                source="PANews",
                news_id=news_id,
                ts_event=self._clock.timestamp_ns(),
                ts_init=self._clock.timestamp_ns()
            )

        except Exception as e:
            self._log.warning(f"Failed to parse news item: {e}")
            return None

    def _extract_crypto_symbols(self, text: str) -> List[str]:
        """Extract cryptocurrency symbols from text"""
        if not text:
            return []

        # Common cryptocurrency symbols
        crypto_symbols = [
            'BTC', 'ETH', 'BNB', 'ADA', 'SOL', 'XRP', 'DOT', 'DOGE',
            'AVAX', 'SHIB', 'MATIC', 'LTC', 'UNI', 'LINK', 'ATOM',
            'USDT', 'USDC', 'BUSD', 'DAI', 'WBTC', 'AAVE', 'MKR',
            'COMP', 'YFI', 'SUSHI', 'CRV', 'SNX', 'BAL', 'REN'
        ]

        text_upper = text.upper()
        found_symbols = []

        for symbol in crypto_symbols:
            # Use word boundary matching to avoid false matches
            import re
            pattern = r'\b' + re.escape(symbol) + r'\b'
            if re.search(pattern, text_upper):
                found_symbols.append(symbol)

        return list(set(found_symbols))  # Remove duplicates

    async def get_proxy_status(self) -> Dict[str, Any]:
        """Get proxy status information"""
        if not self._proxy_client:
            return {
                'proxy_enabled': False,
                'status': 'disabled'
            }

        try:
            status = await self._proxy_client.get_status()
            return {
                'proxy_enabled': True,
                'proxy_client_status': status,
                'last_scrape_time': self._last_scrape_time.isoformat() if self._last_scrape_time else None,
                'processed_news_count': len(self._processed_news_ids)
            }
        except Exception as e:
            return {
                'proxy_enabled': True,
                'status': 'error',
                'error': str(e)
            }

    async def switch_proxy(self) -> bool:
        """Switch proxy"""
        if not self._proxy_client:
            self._log.warning("Proxy client not available")
            return False

        try:
            return await self._proxy_client.switch_proxy()
        except Exception as e:
            self._log.error(f"Failed to switch proxy: {e}")
            return False

    async def manual_scrape(self) -> List[PANewsData]:
        """Manually trigger a news scraping"""
        try:
            self._log.info("Manually triggering news scraping")

            # Build API URL
            api_url = urljoin(
                self._config.base_url,
                f"{self._config.api_endpoint}?LId=1&Rn={self._config.max_news_per_request}&tw=0"
            )

            # Get proxy URL
            proxy_url = await self._get_proxy_url(api_url)

            # Make request
            async with self._session.get(api_url, proxy=proxy_url) as response:
                if response.status != 200:
                    self._log.error(f"Manual scraping failed: HTTP {response.status}")
                    return []

                # Parse JSON response
                json_data = await response.json()
                news_items = self._parse_news_json(json_data)

                self._log.info(f"Manual scraping completed: retrieved {len(news_items)} news items")
                return news_items

        except Exception as e:
            self._log.error(f"Manual scraping failed: {e}")
            return []

    # -- SUBSCRIPTIONS ----------------------------------------------------------------------------

    async def _subscribe(self, command: SubscribeData) -> None:
        """Handle data subscription"""
        self._log.info(f"Subscribing to data type: {command.data_type}")

        # For news data, we don't need special subscription logic
        # because news data is automatically obtained through periodic scraping tasks
        # Here we just need to record the subscription
        if command.data_type.type == PANewsData:
            self._log.info("✅ Subscribed to PANews news data")
        else:
            self._log.warning(f"Unsupported data type: {command.data_type}")

    async def _unsubscribe(self, command: UnsubscribeData) -> None:
        """Handle data unsubscription"""
        self._log.info(f"Unsubscribing from data type: {command.data_type}")

        if command.data_type.type == PANewsData:
            self._log.info("✅ Unsubscribed from PANews news data")
        else:
            self._log.warning(f"Unsupported data type: {command.data_type}")

    async def _request(self, request) -> None:
        """Handle data request"""
        self._log.warning(f"PANewsDataClient does not support data requests, only subscription mode: {request}")


# Factory class
from nautilus_trader.live.factories import LiveDataClientFactory


class PANewsDataClientFactory(LiveDataClientFactory):
    """PANews data client factory"""

    @staticmethod
    def create(
        loop: asyncio.AbstractEventLoop,
        name: str,
        config: PANewsDataClientConfig,
        msgbus,
        cache,
        clock,
    ) -> PANewsDataClient:
        """Create PANews data client"""

        client_id = ClientId(name)
        venue = Venue("PANEWS")

        # Create fake instrument_provider, news data doesn't need trading instrument info
        instrument_provider = InstrumentProvider()

        return PANewsDataClient(
            loop=loop,
            client_id=client_id,
            venue=venue,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            config=config,
            instrument_provider=instrument_provider,
            name=name
        )
