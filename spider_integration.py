"""
爬虫集成示例

本文件提供了多种爬虫框架与Clash代理客户端集成的完整示例，
包括电商数据采集、新闻爬取、API数据获取等实际应用场景。
"""

import asyncio
import json
import logging
import random
import time
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import aiohttp
import requests
from bs4 import BeautifulSoup

from .client import ClashProxyClient


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AdvancedProxySpider:
    """
    高级代理爬虫类
    
    提供完整的爬虫功能，包括：
    - 智能代理管理
    - 请求重试机制
    - 反爬虫对抗
    - 数据解析和存储
    """
    
    def __init__(self, config_dir: str = './clash_configs'):
        self.proxy_client = ClashProxyClient(config_dir=config_dir)
        self.session = None
        self.request_count = 0
        self.success_count = 0
        self.failed_urls = []
        
        # 反爬虫设置
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
    
    async def start(self):
        """启动爬虫系统"""
        logger.info("启动高级代理爬虫系统...")
        
        # 启动代理客户端
        success = await self.proxy_client.start(
            config_type='scraping',
            enable_auto_update=True
        )
        
        if not success:
            raise RuntimeError("代理客户端启动失败")
        
        # 创建HTTP会话
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=10)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        )
        
        logger.info("爬虫系统启动成功")
    
    async def stop(self):
        """停止爬虫系统"""
        logger.info("停止爬虫系统...")
        
        if self.session:
            await self.session.close()
        
        await self.proxy_client.stop()
        
        # 输出统计信息
        success_rate = (self.success_count / self.request_count * 100) if self.request_count > 0 else 0
        logger.info(f"爬虫统计: 总请求{self.request_count}, 成功{self.success_count}, 成功率{success_rate:.1f}%")
        
        if self.failed_urls:
            logger.warning(f"失败的URL数量: {len(self.failed_urls)}")
    
    async def fetch_with_retry(
        self,
        url: str,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        **kwargs
    ) -> Optional[Dict]:
        """
        带重试机制的请求方法
        
        Args:
            url: 目标URL
            max_retries: 最大重试次数
            retry_delay: 重试延迟
            **kwargs: 额外的请求参数
            
        Returns:
            包含响应信息的字典或None
        """
        self.request_count += 1
        
        for attempt in range(max_retries + 1):
            try:
                # 获取代理
                proxy_url = await self.proxy_client.get_proxy_url(
                    strategy='health_weighted' if attempt == 0 else 'round_robin'
                )
                
                if not proxy_url:
                    logger.warning(f"第{attempt+1}次尝试: 无可用代理")
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        break
                
                # 准备请求头
                headers = kwargs.get('headers', {})
                headers.update({
                    'User-Agent': random.choice(self.user_agents),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                })
                
                # 发起请求
                async with self.session.get(
                    url,
                    proxy=proxy_url,
                    headers=headers,
                    **{k: v for k, v in kwargs.items() if k != 'headers'}
                ) as response:
                    
                    # 检查响应状态
                    if response.status == 200:
                        content = await response.text()
                        self.success_count += 1
                        
                        logger.info(f"成功获取: {url} (尝试{attempt+1}次)")
                        
                        return {
                            'url': url,
                            'status': response.status,
                            'content': content,
                            'headers': dict(response.headers),
                            'proxy_used': proxy_url,
                            'attempt': attempt + 1
                        }
                    
                    elif response.status in [403, 429, 503]:
                        # 可能被反爬虫检测，切换代理重试
                        logger.warning(f"可能被检测 (HTTP {response.status}): {url}, 切换代理重试")
                        await self.proxy_client.switch_proxy(strategy='random')
                        
                    else:
                        logger.warning(f"HTTP错误 {response.status}: {url}")
                
            except asyncio.TimeoutError:
                logger.warning(f"第{attempt+1}次尝试超时: {url}")
                # 超时时切换代理
                await self.proxy_client.switch_proxy(strategy='health_weighted')
                
            except Exception as e:
                logger.error(f"第{attempt+1}次尝试失败: {url}, 错误: {e}")
            
            # 重试前等待
            if attempt < max_retries:
                delay = retry_delay * (2 ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(delay)
        
        # 所有重试都失败
        logger.error(f"获取失败 (已重试{max_retries}次): {url}")
        self.failed_urls.append(url)
        return None
    
    async def crawl_ecommerce_products(self, product_urls: List[str]) -> List[Dict]:
        """
        电商产品信息爬取示例
        
        Args:
            product_urls: 产品页面URL列表
            
        Returns:
            产品信息列表
        """
        logger.info(f"开始爬取{len(product_urls)}个产品页面")
        
        products = []
        
        for i, url in enumerate(product_urls):
            logger.info(f"爬取产品 {i+1}/{len(product_urls)}: {url}")
            
            result = await self.fetch_with_retry(url)
            
            if result:
                try:
                    # 解析产品信息
                    soup = BeautifulSoup(result['content'], 'html.parser')
                    
                    # 这里是示例解析逻辑，实际需要根据目标网站调整
                    product_info = {
                        'url': url,
                        'title': self._extract_text(soup, ['h1', '.product-title', '.title']),
                        'price': self._extract_text(soup, ['.price', '.product-price', '.cost']),
                        'description': self._extract_text(soup, ['.description', '.product-desc']),
                        'images': [img.get('src') for img in soup.find_all('img') if img.get('src')],
                        'crawl_time': time.time(),
                        'proxy_used': result['proxy_used']
                    }
                    
                    products.append(product_info)
                    logger.info(f"成功解析产品: {product_info.get('title', 'Unknown')}")
                    
                except Exception as e:
                    logger.error(f"解析产品页面失败: {url}, 错误: {e}")
            
            # 请求间隔，避免被检测
            await asyncio.sleep(random.uniform(2, 5))
        
        logger.info(f"产品爬取完成，成功{len(products)}个")
        return products
    
    async def crawl_news_articles(self, news_urls: List[str]) -> List[Dict]:
        """
        新闻文章爬取示例
        
        Args:
            news_urls: 新闻文章URL列表
            
        Returns:
            新闻文章信息列表
        """
        logger.info(f"开始爬取{len(news_urls)}篇新闻文章")
        
        articles = []
        
        for i, url in enumerate(news_urls):
            logger.info(f"爬取新闻 {i+1}/{len(news_urls)}: {url}")
            
            result = await self.fetch_with_retry(url)
            
            if result:
                try:
                    soup = BeautifulSoup(result['content'], 'html.parser')
                    
                    article_info = {
                        'url': url,
                        'title': self._extract_text(soup, ['h1', '.article-title', '.news-title']),
                        'content': self._extract_text(soup, ['.article-content', '.news-content', '.content']),
                        'author': self._extract_text(soup, ['.author', '.writer', '.by-author']),
                        'publish_time': self._extract_text(soup, ['.publish-time', '.date', '.time']),
                        'tags': [tag.get_text().strip() for tag in soup.find_all(['a'], class_=['tag', 'label'])],
                        'crawl_time': time.time(),
                        'proxy_used': result['proxy_used']
                    }
                    
                    articles.append(article_info)
                    logger.info(f"成功解析文章: {article_info.get('title', 'Unknown')}")
                    
                except Exception as e:
                    logger.error(f"解析新闻页面失败: {url}, 错误: {e}")
            
            await asyncio.sleep(random.uniform(1, 3))
        
        logger.info(f"新闻爬取完成，成功{len(articles)}篇")
        return articles
    
    async def crawl_api_data(self, api_urls: List[str]) -> List[Dict]:
        """
        API数据爬取示例
        
        Args:
            api_urls: API接口URL列表
            
        Returns:
            API响应数据列表
        """
        logger.info(f"开始爬取{len(api_urls)}个API接口")
        
        api_data = []
        
        for i, url in enumerate(api_urls):
            logger.info(f"请求API {i+1}/{len(api_urls)}: {url}")
            
            # API请求通常需要特殊的请求头
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            result = await self.fetch_with_retry(url, headers=headers)
            
            if result:
                try:
                    # 尝试解析JSON响应
                    data = json.loads(result['content'])
                    
                    api_response = {
                        'url': url,
                        'data': data,
                        'status': result['status'],
                        'crawl_time': time.time(),
                        'proxy_used': result['proxy_used']
                    }
                    
                    api_data.append(api_response)
                    logger.info(f"成功获取API数据: {url}")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析失败: {url}, 错误: {e}")
                except Exception as e:
                    logger.error(f"处理API响应失败: {url}, 错误: {e}")
            
            await asyncio.sleep(random.uniform(0.5, 2))
        
        logger.info(f"API爬取完成，成功{len(api_data)}个")
        return api_data
    
    def _extract_text(self, soup: BeautifulSoup, selectors: List[str]) -> str:
        """
        从HTML中提取文本内容
        
        Args:
            soup: BeautifulSoup对象
            selectors: CSS选择器列表
            
        Returns:
            提取的文本内容
        """
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text().strip()
        return ""
    
    async def save_results(self, data: List[Dict], filename: str):
        """
        保存爬取结果到文件
        
        Args:
            data: 要保存的数据
            filename: 文件名
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"结果已保存到: {filename}")
            
        except Exception as e:
            logger.error(f"保存结果失败: {e}")


# 使用示例
async def ecommerce_crawling_example():
    """电商爬虫示例"""
    print("\n=== 电商产品爬取示例 ===")
    
    spider = AdvancedProxySpider()
    
    try:
        await spider.start()
        
        # 示例产品URL（实际使用时替换为真实URL）
        product_urls = [
            'http://httpbin.org/html',  # 模拟产品页面
            'http://httpbin.org/json',  # 模拟API响应
            'http://httpbin.org/xml',   # 模拟XML数据
        ]
        
        # 爬取产品信息
        products = await spider.crawl_ecommerce_products(product_urls)
        
        # 保存结果
        await spider.save_results(products, 'products.json')
        
        print(f"成功爬取{len(products)}个产品")
        
    finally:
        await spider.stop()


async def news_crawling_example():
    """新闻爬虫示例"""
    print("\n=== 新闻文章爬取示例 ===")
    
    spider = AdvancedProxySpider()
    
    try:
        await spider.start()
        
        # 示例新闻URL
        news_urls = [
            'http://httpbin.org/html',
            'http://httpbin.org/robots.txt',
        ]
        
        # 爬取新闻文章
        articles = await spider.crawl_news_articles(news_urls)
        
        # 保存结果
        await spider.save_results(articles, 'news.json')
        
        print(f"成功爬取{len(articles)}篇文章")
        
    finally:
        await spider.stop()


async def api_crawling_example():
    """API数据爬取示例"""
    print("\n=== API数据爬取示例 ===")
    
    spider = AdvancedProxySpider()
    
    try:
        await spider.start()
        
        # 示例API URL
        api_urls = [
            'http://httpbin.org/json',
            'http://httpbin.org/ip',
            'http://httpbin.org/user-agent',
            'http://httpbin.org/headers',
        ]
        
        # 爬取API数据
        api_data = await spider.crawl_api_data(api_urls)
        
        # 保存结果
        await spider.save_results(api_data, 'api_data.json')
        
        print(f"成功爬取{len(api_data)}个API接口")
        
    finally:
        await spider.stop()


async def main():
    """运行所有爬虫示例"""
    print("高级代理爬虫集成示例")
    print("=" * 50)
    
    # 运行各种爬虫示例
    await ecommerce_crawling_example()
    await news_crawling_example()
    await api_crawling_example()
    
    print("\n" + "=" * 50)
    print("所有爬虫示例运行完成！")


if __name__ == "__main__":
    asyncio.run(main())
