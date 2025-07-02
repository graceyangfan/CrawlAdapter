"""
Simplified News Strategy - Subscribe to news crawling and print latest news
"""
from nautilus_trader.trading.strategy import Strategy, StrategyConfig
from nautilus_trader.model.data import DataType, CustomData
from nautilus_trader.model.identifiers import ClientId
from nautilus_trader.core.data import Data
from pa_news_data_client import PANewsData


class SimpleNewsStrategyConfig(StrategyConfig, frozen=True):
    """Simplified news strategy configuration"""
    news_client_id: str = "PANEWS"


class SimpleNewsStrategy(Strategy):
    """
    Simplified News Strategy

    Features:
    1. Subscribe to PANews data only
    2. Receive news in CustomData format
    3. Print latest news titles and content
    """
    
    def __init__(self, config: SimpleNewsStrategyConfig):
        super().__init__(config)

        # Configuration
        self.news_client_id = ClientId(config.news_client_id)

        # State
        self.news_count = 0

    def on_start(self):
        """Subscribe to news data when strategy starts"""
        self.log.info("🚀 Starting simplified news strategy")

        # Subscribe to news data only (CustomData format)
        self.subscribe_data(
            data_type=DataType(PANewsData, metadata={"source": "PANews"}),
            client_id=self.news_client_id
        )

        self.log.info(f"✅ Subscribed to news data, client: {self.news_client_id}")
    
    def on_data(self, data: Data):
        """Process received data"""
        self.log.info(f"📨 Received data: {type(data)} - {data}")

        # Check if it's PANewsData type news (direct reception, not CustomData wrapped)
        if isinstance(data, PANewsData):
            self.news_count += 1
            self._print_news(data, self.news_count)
        # Also check CustomData format (just in case)
        elif isinstance(data, CustomData):
            # Get wrapped news data
            news_data = data.data

            if isinstance(news_data, PANewsData):
                self.news_count += 1
                self._print_news(news_data, self.news_count)
        else:
            self.log.warning(f"⚠️ Received unknown data type: {type(data)}")
    
    def _print_news(self, news: PANewsData, count: int):
        """Print news information"""
        self.log.info("=" * 80)
        self.log.info(f"📰 News #{count}")
        self.log.info("=" * 80)
        self.log.info(f"🏷️  Title: {news.title}")
        self.log.info(f"⏰ Time: {news.publish_time}")
        self.log.info(f"🔗 Link: {news.url}")

        # Display content (limit length)
        content_preview = news.content[:200] + "..." if len(news.content) > 200 else news.content
        self.log.info(f"📝 Content: {content_preview}")

        # Display related trading symbols
        if news.symbols:
            symbols_list = news.get_symbols_list()
            self.log.info(f"💰 Related symbols: {', '.join(symbols_list)}")

        # Display category
        if news.category:
            self.log.info(f"📂 Category: {news.category}")

        # Display if cryptocurrency related
        if news.is_crypto_related():
            self.log.info("🪙 Cryptocurrency related news")

        self.log.info("=" * 80)
    
    def on_stop(self):
        """Strategy stop"""
        self.log.info(f"🛑 Strategy stopped, processed {self.news_count} news items")

    def on_reset(self):
        """Strategy reset"""
        self.news_count = 0
        self.log.info("🔄 Strategy reset")

    def on_dispose(self):
        """Strategy disposal"""
        self.log.info("🗑️ Strategy disposed")


# Usage example
if __name__ == "__main__":
    import asyncio
    from nautilus_trader.config import TradingNodeConfig
    from nautilus_trader.live.node import TradingNode
    from nautilus_trader.trading.config import ImportableStrategyConfig
    from pa_news_data_client import (
        PANewsDataClientFactory,
        PANewsDataClientConfig
    )

    async def run_simple_news_strategy():
        """Run simplified news strategy example"""
        print("🚀 Starting simplified news strategy example")

        # Create news client configuration (users can set scraping interval and proxy parameters)
        news_config = PANewsDataClientConfig(
            scraping_interval=120,  # User setting: scrape every 2 minutes
            enable_proxy=True,
            max_news_per_request=3,  # Get only latest 3 news items

            # User customizable proxy configuration
            clash_config_dir="/workspaces/codespaces-blank/clash_configs",  # Clash config directory
            clash_binary_path="/workspaces/codespaces-blank/mihomo_proxy/mihomo",  # Custom Clash binary path if needed
            proxy_port=7890,  # Proxy port
            api_port=9090,  # API port
            enable_rules=True,  # Enable proxy rules
        )

        # Create strategy configuration - using ImportableStrategyConfig
        strategy_config = ImportableStrategyConfig(
            strategy_path="simple_news_strategy:SimpleNewsStrategy",
            config_path="simple_news_strategy:SimpleNewsStrategyConfig",
            config={
                "news_client_id": "PANEWS"
            }
        )

        # Create trading node configuration
        config = TradingNodeConfig(
            trader_id="SimpleNewsTrader-001",
            data_clients={
                "PANEWS": news_config
            },
            strategies=[strategy_config],  # Pass ImportableStrategyConfig object list
            # Increase timeout to accommodate proxy client initialization
            timeout_connection=180.0,  # 3-minute connection timeout
            timeout_reconciliation=30.0,
            timeout_portfolio=30.0,
            timeout_disconnection=30.0,
            timeout_post_stop=10.0,
        )

        # Create trading node
        node = TradingNode(config=config)

        # Register news data client factory
        node.add_data_client_factory("PANEWS", PANewsDataClientFactory)

        # Build and start
        node.build()

        try:
            print("✅ Node started, waiting for news data...")
            print("📝 Strategy will print received latest news")
            print("⏹️  Press Ctrl+C to stop")

            await node.run_async()

        except KeyboardInterrupt:
            print("\n⏹️ User interrupted")
        finally:
            node.stop()
            print("✅ Node stopped")

    # Run example
    asyncio.run(run_simple_news_strategy())
