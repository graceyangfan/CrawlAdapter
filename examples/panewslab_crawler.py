"""
PanewsLab News Crawler

A professional news crawler for fetching data from PanewsLab.
Focuses solely on web scraping and data extraction, with proxy management
handled by CrawlAdapter's ProxyClient.

Features:
- Clean separation between scraping and proxy logic
- Automatic proxy integration through CrawlAdapter
- Comprehensive news data parsing and extraction
- Error handling and retry mechanisms
"""

import asyncio
import json
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin


import aiohttp
from bs4 import BeautifulSoup

# Import ProxyClient from CrawlAdapter (now properly installed)
from crawladapter import ProxyClient, NodeFetcher


class NewsItem:
    """Represents a single news item from PanewsLab."""
    
    def __init__(
        self,
        title: str,
        content: str,
        publish_time: str,
        url: str = "",
        symbols: List[str] = None,
        category: str = "",
        source: str = "PanewsLab"
    ):
        self.title = title
        self.content = content
        self.publish_time = publish_time
        self.url = url
        self.symbols = symbols or []
        self.category = category
        self.source = source
        self.timestamp = self._parse_timestamp()
    
    def _parse_timestamp(self) -> int:
        """Parse publish_time to Unix timestamp."""
        try:
            if isinstance(self.publish_time, str):
                # Handle relative times like "5分钟前", "1小时前"
                if "分钟前" in self.publish_time:
                    minutes = int(re.search(r'(\d+)', self.publish_time).group(1))
                    dt = datetime.now() - timedelta(minutes=minutes)
                elif "小时前" in self.publish_time:
                    hours = int(re.search(r'(\d+)', self.publish_time).group(1))
                    dt = datetime.now() - timedelta(hours=hours)
                elif "天前" in self.publish_time:
                    days = int(re.search(r'(\d+)', self.publish_time).group(1))
                    dt = datetime.now() - timedelta(days=days)
                else:
                    dt = datetime.now()
                return int(dt.timestamp())
            return int(datetime.now().timestamp())
        except:
            return int(datetime.now().timestamp())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'title': self.title,
            'content': self.content,
            'publish_time': self.publish_time,
            'url': self.url,
            'symbols': self.symbols,
            'category': self.category,
            'source': self.source,
            'timestamp': self.timestamp
        }
    
    def __str__(self) -> str:
        return f"NewsItem(title='{self.title[:50]}...', symbols={self.symbols})"


class PanewsLabCrawler:
    """
    Professional news crawler for PanewsLab with clean proxy integration.

    This crawler focuses solely on web scraping and data extraction.
    All proxy management is handled by CrawlAdapter's ProxyClient.

    Features:
    - Clean separation of concerns (scraping vs proxy management)
    - Automatic proxy integration through CrawlAdapter
    - Comprehensive news data parsing and extraction
    - Cryptocurrency symbol detection and categorization
    - Robust error handling and retry mechanisms
    - PEP8 compliant code with comprehensive documentation
    """
    
    def __init__(
        self,
        proxy_enabled: bool = True,
        proxy_rules: List[str] = None,
        base_url: str = "https://www.panewslab.com",
        timeout: int = 10,
        custom_nodes: Optional[List[Dict]] = None,
        custom_sources: Optional[Dict[str, List[str]]] = None,
        clash_config_path: Optional[str] = None,
        log_file: str = "test.log"
    ):
        """
        Initialize the crawler.

        Args:
            proxy_enabled: Whether to use proxy
            proxy_rules: Custom proxy rules for domains
            base_url: Base URL for PanewsLab
            timeout: Request timeout in seconds
            custom_nodes: Custom proxy nodes (already parsed clash/v2ray format)
            custom_sources: Custom source URLs {'clash': [...], 'v2ray': [...]}
            clash_config_path: Path to clash config file
            log_file: Log file path
        """
        self.proxy_enabled = proxy_enabled
        self.proxy_rules = proxy_rules or [
            '*.panewslab.com', 'panewslab.com',
            '*.httpbin.org', 'httpbin.org',  # General HTTP testing
            '*.ipinfo.io', 'ipinfo.io',      # IP detection service
            '*.gstatic.com', 'gstatic.com',  # Google connectivity test
            '*.detectportal.firefox.com', 'detectportal.firefox.com',  # Firefox connectivity test
            '*.connectivitycheck.platform.hicloud.com', 'connectivitycheck.platform.hicloud.com'  # Huawei connectivity test
        ]
        self.base_url = base_url
        self.timeout = timeout
        self.custom_nodes = custom_nodes
        self.custom_sources = custom_sources
        self.clash_config_path = clash_config_path
        self.log_file = log_file

        # Setup logging
        self._setup_logging()

        # Components
        self.proxy_client: Optional[ProxyClient] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logging.getLogger(__name__)

        # Pending health check URLs (applied when proxy client is created)
        self._pending_health_check_urls: Optional[List[str]] = None
        
        # Common crypto symbols for extraction
        self.crypto_symbols = [
            'BTC', 'ETH', 'BNB', 'ADA', 'SOL', 'XRP', 'DOT', 'DOGE',
            'AVAX', 'SHIB', 'MATIC', 'LTC', 'UNI', 'LINK', 'ATOM',
            'USDT', 'USDC', 'BUSD', 'DAI', 'WBTC', 'AAVE', 'MKR',
            'COMP', 'YFI', 'SUSHI', 'CRV', 'SNX', 'BAL', 'REN'
        ]
        
        # Request headers
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

    def _setup_logging(self):
        """Setup logging configuration."""
        # Create logger
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)

        # Remove existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # Create file handler
        file_handler = logging.FileHandler(self.log_file, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.INFO)

        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        # Prevent propagation to root logger
        logger.propagate = False
    
    # Note: Binary and config detection methods removed
    # These are now handled by CrawlAdapter's ProxyClient automatically

    def _create_proxy_client_with_sources(self) -> Optional[ProxyClient]:
        """Create proxy client with custom sources or nodes."""
        try:
            # Create proxy client - binary and config detection is automatic
            proxy_client = ProxyClient(
                config_dir=self.clash_config_path or './clash_configs'
            )
            self.logger.info("ProxyClient created with automatic binary/config detection")

            # If custom sources are provided, configure node fetcher
            if self.custom_sources:
                self.logger.info(f"Using custom sources")
                self.logger.info(f"Clash sources: {len(self.custom_sources.get('clash', []))}")
                self.logger.info(f"V2Ray sources: {len(self.custom_sources.get('v2ray', []))}")

                custom_node_fetcher = NodeFetcher(custom_sources=self.custom_sources)
                proxy_client.node_fetcher = custom_node_fetcher

                self.logger.info("✅ Custom NodeFetcher configured")

            return proxy_client

        except Exception as e:
            self.logger.error(f"Failed to create proxy client: {e}")
            return None

    async def start(self) -> bool:
        """
        Start the crawler and initialize components.

        Returns:
            True if started successfully
        """
        try:
            self.logger.info("🚀 Starting PanewsLab crawler...")

            # Initialize proxy client if enabled
            if self.proxy_enabled:
                self.proxy_client = self._create_proxy_client_with_sources()

                if self.proxy_client:
                    # Apply pending health check URLs if any
                    if self._pending_health_check_urls:
                        self.proxy_client.set_health_check_urls(self._pending_health_check_urls)
                        self.logger.info(f"Applied {len(self._pending_health_check_urls)} pending health check URLs")
                        self._pending_health_check_urls = None

                    # Start proxy client
                    try:
                        success = await self.proxy_client.start(rules=self.proxy_rules)
                        if success:
                            self.logger.info("✅ Proxy client started")
                        else:
                            self.logger.warning("⚠️ Proxy client failed to start")
                            self.logger.info("   Continuing with direct connection...")
                            self.proxy_client = None
                    except Exception as e:
                        self.logger.warning(f"⚠️ Proxy client failed to start: {e}")
                        self.logger.info("   Continuing with direct connection...")
                        self.proxy_client = None
                else:
                    self.logger.warning("⚠️ Failed to create proxy client")
                    self.proxy_client = None

            # Create HTTP session
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=self.headers
            )

            self.logger.info("✅ Crawler started successfully")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to start crawler: {e}")
            return False
    
    async def stop(self) -> None:
        """Stop the crawler and cleanup resources."""
        self.logger.info("🛑 Stopping PanewsLab crawler...")

        # Close HTTP session
        if self.session:
            await self.session.close()
            self.session = None

        # Stop proxy client
        if self.proxy_client:
            await self.proxy_client.stop()
            self.proxy_client = None

        self.logger.info("✅ Crawler stopped")

    def set_health_check_urls(self, urls: List[str]) -> None:
        """
        Set custom health check URLs.

        Args:
            urls: List of URLs to use for health checking
        """
        if self.proxy_client:
            self.proxy_client.set_health_check_urls(urls)
            self.logger.info(f"Updated health check URLs: {len(urls)} URLs")
        else:
            # Store for later use when proxy client is created
            self._pending_health_check_urls = urls
            self.logger.info(f"Stored health check URLs for later use: {len(urls)} URLs")

    async def get_proxy_status(self) -> dict:
        """Get detailed proxy status information."""
        if not self.proxy_client:
            return {
                'proxy_enabled': False,
                'status': 'disabled'
            }

        try:
            # Check if proxy client is running
            if not self.proxy_client.is_running:
                return {
                    'proxy_enabled': True,
                    'status': 'not_running'
                }

            # Get proxy info
            proxy_info = await self.proxy_client.get_proxy_info()

            # Get current proxy URL
            current_proxy = await self.proxy_client.get_proxy_url()

            # Check current IP
            current_ip = await self._check_current_ip(current_proxy)

            return {
                'proxy_enabled': True,
                'status': 'active' if current_proxy else 'no_proxy_available',
                'current_proxy': current_proxy,
                'current_ip': current_ip,
                'proxy_info': proxy_info
            }
        except Exception as e:
            return {
                'proxy_enabled': True,
                'status': 'error',
                'error': str(e)
            }

    async def switch_proxy(self, strategy: str = 'round_robin') -> bool:
        """Manually switch to a different proxy."""
        if not self.proxy_client:
            self.logger.warning("⚠️ Proxy client not available")
            return False

        if not self.proxy_client.is_running:
            self.logger.warning("⚠️ Proxy client not running")
            return False

        try:
            self.logger.info(f"🔄 Switching proxy using strategy: {strategy}")

            # Get current state before switch
            old_proxy = await self.proxy_client.get_proxy_url()
            old_ip = await self._check_current_ip(old_proxy)

            # Switch proxy
            switch_success = await self.proxy_client.switch_proxy(strategy=strategy)

            if switch_success:
                # Wait for switch to take effect
                await asyncio.sleep(2)

                # Get new state after switch
                new_proxy = await self.proxy_client.get_proxy_url()
                new_ip = await self._check_current_ip(new_proxy)

                # Compare states
                if old_ip != new_ip:
                    self.logger.info(f"🌐 IP: {old_ip} → {new_ip}")
                    self.logger.info(f"🔄 Proxy switched successfully")
                    return True
                else:
                    self.logger.warning(f"⚠️ IP unchanged after switch: {old_ip}")
                    return False
            else:
                self.logger.warning("⚠️ Proxy switch failed")
                return False

        except Exception as e:
            self.logger.error(f"❌ Failed to switch proxy: {e}")
            return False

    async def _get_proxy_url(self, url: str) -> Optional[str]:
        """Get proxy URL for the given target URL."""
        if not self.proxy_client or not self.proxy_client.is_running:
            return None

        try:
            return await self.proxy_client.get_proxy(url)
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to get proxy for {url}: {e}")
            return None

    async def _check_current_ip(self, proxy_url: Optional[str] = None) -> Optional[str]:
        """Check current IP address to monitor proxy switching."""
        try:
            # Use a reliable IP checking service
            check_url = "http://httpbin.org/ip"

            async with self.session.get(check_url, proxy=proxy_url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('origin', 'Unknown')
                else:
                    return None
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to check IP: {e}")
            return None

    async def fetch_newsflash(self, limit: int = 20) -> List[NewsItem]:
        """
        Fetch latest newsflash from PanewsLab.

        Args:
            limit: Maximum number of news items to fetch

        Returns:
            List of NewsItem objects
        """
        if not self.session:
            raise RuntimeError("Crawler not started. Call start() first.")

        try:
            # Note: Proxy switching is handled automatically by CrawlAdapter

            # Build API URL using the correct PanewsLab API endpoint
            api_url = urljoin(self.base_url, f"/webapi/flashnews?LId=1&Rn={limit}&tw=0")

            # Get proxy URL if available
            proxy_url = await self._get_proxy_url(api_url)

            self.logger.info(f"📡 Fetching newsflash from API: {api_url}")

            # Check and display current IP information
            if proxy_url:
                self.logger.info(f"🔄 Using proxy: {proxy_url}")
                current_ip = await self._check_current_ip(proxy_url)
                if current_ip:
                    self.logger.info(f"🌐 Current IP: {current_ip}")
                else:
                    self.logger.warning("🌐 Current IP: Unable to detect")
            else:
                self.logger.info("🔄 Using direct connection (no proxy)")
                current_ip = await self._check_current_ip(None)
                if current_ip:
                    self.logger.info(f"🌐 Current IP: {current_ip}")

            # Make request to API endpoint
            async with self.session.get(api_url, proxy=proxy_url) as response:
                if response.status != 200:
                    self.logger.error(f"❌ HTTP {response.status}: {response.reason}")
                    return []

                # Parse JSON response
                json_data = await response.json()
                self.logger.info(f"✅ Received JSON data with {len(str(json_data))} characters")

                # Parse news items from JSON
                news_items = self._parse_newsflash_json(json_data, limit)
                self.logger.info(f"📰 Parsed {len(news_items)} news items")

                # Request completed successfully
                self.logger.debug("📊 Request completed successfully")

                return news_items

        except Exception as e:
            self.logger.error(f"❌ Failed to fetch newsflash: {e}")
            return []

    def _parse_newsflash_json(self, json_data: dict, limit: int) -> List[NewsItem]:
        """
        Parse newsflash JSON data to extract news items.

        Args:
            json_data: JSON response from PanewsLab API
            limit: Maximum number of items to parse

        Returns:
            List of NewsItem objects
        """
        try:
            news_items = []

            # Navigate the actual JSON structure: response.data.flashNews[0].list
            if not json_data or 'data' not in json_data:
                self.logger.warning("⚠️ Invalid JSON structure: missing 'data' field")
                return []

            data = json_data['data']
            if not isinstance(data, dict) or 'flashNews' not in data:
                self.logger.warning("⚠️ Invalid JSON structure: missing 'flashNews' field")
                return []

            flash_news = data['flashNews']
            if not isinstance(flash_news, list) or len(flash_news) == 0:
                self.logger.warning("⚠️ Invalid JSON structure: 'flashNews' is not a valid list")
                return []

            # Get the first flashNews item and its list
            first_flash_news = flash_news[0]
            if not isinstance(first_flash_news, dict) or 'list' not in first_flash_news:
                self.logger.warning("⚠️ Invalid JSON structure: missing 'list' in flashNews")
                return []

            news_list = first_flash_news['list']
            if not isinstance(news_list, list):
                self.logger.warning("⚠️ Invalid JSON structure: 'list' is not a valid list")
                return []

            self.logger.info(f"🎯 Found {len(news_list)} news items in API response")

            # Parse each news item
            for i, item in enumerate(news_list[:limit]):
                try:
                    news_item = self._parse_json_news_item(item, i)
                    if news_item:
                        news_items.append(news_item)
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to parse news item {i}: {e}")
                    continue

            return news_items

        except Exception as e:
            self.logger.error(f"❌ Failed to parse JSON: {e}")
            return []

    def _parse_json_news_item(self, item: dict, index: int) -> Optional[NewsItem]:
        """
        Parse a single news item from JSON data.

        Args:
            item: JSON news item from PanewsLab API
            index: Item index for fallback

        Returns:
            NewsItem object or None
        """
        try:
            # Extract title
            title = item.get('title', f'News Item {index + 1}')
            if not title or len(title.strip()) < 3:
                return None

            # Extract content/description
            content = item.get('desc', '').replace('\r\n原文链接', '').replace('\\r\\n', '\n')

            # Extract publish time
            publish_time_timestamp = item.get('publishTime', 0)
            if publish_time_timestamp:
                # Convert timestamp to readable format
                from datetime import datetime
                dt = datetime.fromtimestamp(publish_time_timestamp)
                publish_time = dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                publish_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Extract URL - for flashnews, use different URL pattern
            article_id = item.get('id', '')
            item_type = item.get('type', 0)

            if article_id:
                if item_type == 2:  # Flash news type
                    url = urljoin(self.base_url, f"/zh/newsflash/{article_id}")
                else:
                    url = urljoin(self.base_url, f"/zh/articledetails/{article_id}.html")
            else:
                url = ""

            # Extract author information
            author_info = item.get('author', {})
            if isinstance(author_info, dict):
                author_name = author_info.get('name', '')
            else:
                author_name = ''

            # Extract tags/category
            tags = item.get('tags')
            if isinstance(tags, list) and tags:
                category = ', '.join(str(tag) for tag in tags)
            elif tags:
                category = str(tags)
            else:
                category = 'flashnews'

            # Add author to category if available
            if author_name:
                category = f"{category} | {author_name}"

            # Extract symbols from title and content
            symbols = self._extract_symbols(f"{title} {content}")

            return NewsItem(
                title=title,
                content=content,
                publish_time=publish_time,
                url=url,
                symbols=symbols,
                category=category
            )

        except Exception as e:
            self.logger.warning(f"⚠️ Error parsing JSON news item: {e}")
            return None

    def _parse_newsflash_html(self, html: str, limit: int) -> List[NewsItem]:
        """
        Parse newsflash HTML content to extract news items.

        Args:
            html: HTML content from newsflash page
            limit: Maximum number of items to parse

        Returns:
            List of NewsItem objects
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            news_items = []

            # Try different selectors for news items
            selectors = [
                '.newsflash-item',
                '.news-item',
                '.flash-item',
                '[class*="news"]',
                '[class*="flash"]',
                'article',
                '.item'
            ]

            elements = []
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    print(f"🎯 Found {len(elements)} elements with selector: {selector}")
                    break

            # If no specific selectors work, try generic approach
            if not elements:
                # Look for divs that might contain news
                elements = soup.find_all('div', class_=re.compile(r'(news|flash|item)', re.I))
                if not elements:
                    elements = soup.find_all(['div', 'article', 'section'])[:limit * 2]
                print(f"🔍 Fallback: Found {len(elements)} generic elements")

            # Parse each element
            for i, element in enumerate(elements[:limit]):
                try:
                    news_item = self._parse_news_element(element, i)
                    if news_item and news_item.title.strip():
                        news_items.append(news_item)
                except Exception as e:
                    print(f"⚠️ Failed to parse element {i}: {e}")
                    continue

            return news_items

        except Exception as e:
            print(f"❌ Failed to parse HTML: {e}")
            return []

    def _parse_news_element(self, element, index: int) -> Optional[NewsItem]:
        """
        Parse a single news element.

        Args:
            element: BeautifulSoup element
            index: Element index for fallback title

        Returns:
            NewsItem object or None
        """
        try:
            # Extract title
            title = self._extract_title(element, index)
            if not title or len(title.strip()) < 5:
                return None

            # Extract content
            content = self._extract_content(element)

            # Extract time
            publish_time = self._extract_time(element)

            # Extract URL
            url = self._extract_url(element)

            # Extract symbols
            symbols = self._extract_symbols(f"{title} {content}")

            return NewsItem(
                title=title,
                content=content,
                publish_time=publish_time,
                url=url,
                symbols=symbols,
                category="newsflash"
            )

        except Exception as e:
            print(f"⚠️ Error parsing news element: {e}")
            return None

    def _extract_title(self, element, index: int) -> str:
        """Extract title from element."""
        # Try different title selectors
        title_selectors = [
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            '.title', '.headline', '.news-title',
            'a[href*="article"]', 'a[href*="news"]',
            'a', 'strong', 'b'
        ]

        for selector in title_selectors:
            title_elem = element.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                if title and len(title) > 5:
                    return title

        # Fallback: use element text
        text = element.get_text(strip=True)
        if text and len(text) > 5:
            # Take first line or first 100 characters
            lines = text.split('\n')
            return lines[0][:100] if lines[0] else f"News Item {index + 1}"

        return f"News Item {index + 1}"

    def _extract_content(self, element) -> str:
        """Extract content from element."""
        # Try content selectors
        content_selectors = [
            '.content', '.description', '.summary',
            'p', '.text', '.body'
        ]

        for selector in content_selectors:
            content_elem = element.select_one(selector)
            if content_elem:
                content = content_elem.get_text(strip=True)
                if content and len(content) > 10:
                    return content[:500]  # Limit content length

        # Fallback: use all text but limit length
        text = element.get_text(strip=True)
        return text[:300] if text else ""

    def _extract_time(self, element) -> str:
        """Extract publish time from element."""
        # Try time selectors
        time_selectors = [
            'time', '.time', '.date', '.publish-time',
            '[datetime]', '.timestamp', '.ago'
        ]

        for selector in time_selectors:
            time_elem = element.select_one(selector)
            if time_elem:
                # Try datetime attribute first
                time_str = time_elem.get('datetime') or time_elem.get_text(strip=True)
                if time_str:
                    return time_str

        # Look for time patterns in text
        text = element.get_text()
        time_patterns = [
            r'\d+分钟前', r'\d+小时前', r'\d+天前',
            r'\d{4}-\d{2}-\d{2}', r'\d{2}:\d{2}'
        ]

        for pattern in time_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group()

        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _extract_url(self, element) -> str:
        """Extract article URL from element."""
        # Try to find links
        link_elem = element.find('a', href=True)
        if link_elem:
            href = link_elem['href']
            if href.startswith('http'):
                return href
            elif href.startswith('/'):
                return urljoin(self.base_url, href)

        return ""

    def _extract_symbols(self, text: str) -> List[str]:
        """Extract cryptocurrency symbols from text."""
        if not text:
            return []

        text_upper = text.upper()
        found_symbols = []

        for symbol in self.crypto_symbols:
            # Look for symbol as whole word
            pattern = r'\b' + re.escape(symbol) + r'\b'
            if re.search(pattern, text_upper):
                found_symbols.append(symbol)

        return list(set(found_symbols))  # Remove duplicates

    # Note: Complex proxy management methods removed
    # All proxy switching and management is now handled by CrawlAdapter's ProxyClient
    # This keeps the crawler focused on web scraping functionality only




# Utility functions
async def save_news_to_json(news_items: List[NewsItem], filename: str = "panewslab_news.json"):
    """Save news items to JSON file."""
    try:
        data = {
            'timestamp': datetime.now().isoformat(),
            'count': len(news_items),
            'news': [item.to_dict() for item in news_items]
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"💾 Saved {len(news_items)} news items to {filename}")

    except Exception as e:
        print(f"❌ Failed to save news to JSON: {e}")


def print_news_summary(news_items: List[NewsItem]):
    """Print a summary of news items."""
    if not news_items:
        print("📭 No news items found")
        return

    print(f"\n📰 Found {len(news_items)} news items:")
    print("=" * 80)

    for i, item in enumerate(news_items, 1):
        print(f"\n{i}. {item.title}")
        print(f"   ⏰ Time: {item.publish_time}")
        if item.symbols:
            print(f"   💰 Symbols: {', '.join(item.symbols)}")
        if item.content:
            content_preview = item.content[:100] + "..." if len(item.content) > 100 else item.content
            print(f"   📝 Content: {content_preview}")
        if item.url:
            print(f"   🔗 URL: {item.url}")
        print("-" * 40)


# Example usage functions
async def example_basic_usage():
    """Basic usage example."""
    print("🔥 Basic PanewsLab Crawler Example")
    print("=" * 50)

    # Create crawler with proxy enabled
    crawler = PanewsLabCrawler(
        proxy_enabled=True,
        proxy_rules=['*.panewslab.com', 'panewslab.com']
    )

    try:
        # Start crawler
        if not await crawler.start():
            print("❌ Failed to start crawler")
            return

        # Fetch news
        news_items = await crawler.fetch_newsflash(limit=10)

        # Display results
        print_news_summary(news_items)

        # Save to JSON
        await save_news_to_json(news_items)

    except Exception as e:
        print(f"❌ Error in basic usage: {e}")

    finally:
        await crawler.stop()


async def example_without_proxy():
    """Example without proxy."""
    print("\n🌐 PanewsLab Crawler Example (No Proxy)")
    print("=" * 50)

    # Create crawler without proxy
    crawler = PanewsLabCrawler(proxy_enabled=False)

    try:
        if not await crawler.start():
            print("❌ Failed to start crawler")
            return

        news_items = await crawler.fetch_newsflash(limit=5)
        print_news_summary(news_items)

    except Exception as e:
        print(f"❌ Error without proxy: {e}")

    finally:
        await crawler.stop()


async def example_custom_config():
    """Example with custom configuration."""
    print("\n⚙️ PanewsLab Crawler Example (Custom Config)")
    print("=" * 50)

    # Create crawler with custom settings
    crawler = PanewsLabCrawler(
        proxy_enabled=True,
        proxy_rules=['*.panewslab.com', '*.coindesk.com'],  # Multiple domains
        base_url="https://www.panewslab.com",
        timeout=15
    )

    try:
        if not await crawler.start():
            print("❌ Failed to start crawler")
            return

        # Show initial proxy status
        status = await crawler.get_proxy_status()
        print(f"\n📊 Initial Proxy Status:")
        print(f"   Enabled: {status['proxy_enabled']}")
        print(f"   Status: {status['status']}")
        if status.get('current_ip'):
            print(f"   Current IP: {status['current_ip']}")

        # Fetch news first time
        print(f"\n📰 First fetch:")
        news_items = await crawler.fetch_newsflash(limit=5)

        # Test proxy switching
        print(f"\n🔄 Testing proxy switching...")
        switch_success = await crawler.switch_proxy('round_robin')
        if switch_success:
            print("✅ Proxy switched successfully")
        else:
            print("⚠️ Proxy switch failed or no change")

        # Fetch news second time to see if IP changed
        print(f"\n📰 Second fetch (after proxy switch):")
        news_items2 = await crawler.fetch_newsflash(limit=3)

        # Filter news with crypto symbols
        all_news = news_items + news_items2
        crypto_news = [item for item in all_news if item.symbols]

        print(f"\n🪙 Found {len(crypto_news)} news items with crypto symbols:")
        print_news_summary(crypto_news)

        # Save filtered news
        await save_news_to_json(crypto_news, "crypto_news.json")

    except Exception as e:
        print(f"❌ Error in custom config: {e}")

    finally:
        await crawler.stop()


async def main():
    """Main function to run all examples."""
    print("🚀 PanewsLab Crawler Examples")
    print("=" * 60)

    try:
        # Run basic example
        await example_basic_usage()

        # Wait a bit between examples
        await asyncio.sleep(2)

        # Run without proxy example
        await example_without_proxy()

        # Wait a bit between examples
        await asyncio.sleep(2)

        # Run custom config example
        await example_custom_config()

        print("\n✅ All examples completed!")

    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")


if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())
