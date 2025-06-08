"""
简化爬虫集成示例

提供简单易用的同步和异步爬虫类，可以快速集成到现有项目中。
适合初学者和需要快速集成的场景。
"""

import asyncio
import json
import logging
import random
import time
from typing import Dict, List, Optional, Union

import requests

from .client import ClashProxyClient


class SimpleProxySpider:
    """
    简化的代理爬虫类
    
    特点：
    - 简单易用的API
    - 自动代理管理
    - 内置重试机制
    - 支持同步和异步操作
    """
    
    def __init__(self, config_dir: str = './clash_configs'):
        self.proxy_client = None
        self.current_proxy = None
        self.config_dir = config_dir
        self.session_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 统计信息
        self.total_requests = 0
        self.successful_requests = 0
        
        # 配置日志
        self.logger = logging.getLogger(__name__)
    
    def start(self) -> bool:
        """
        启动代理爬虫（同步方式）
        
        Returns:
            bool: 启动是否成功
        """
        try:
            # 在新的事件循环中启动代理客户端
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def _start():
                self.proxy_client = ClashProxyClient(config_dir=self.config_dir)
                success = await self.proxy_client.start(config_type='scraping')
                if success:
                    self.current_proxy = await self.proxy_client.get_proxy_url()
                return success
            
            success = loop.run_until_complete(_start())
            
            if success:
                self.logger.info(f"代理爬虫启动成功，当前代理: {self.current_proxy}")
            else:
                self.logger.error("代理爬虫启动失败")
            
            return success
            
        except Exception as e:
            self.logger.error(f"启动代理爬虫时出错: {e}")
            return False
    
    def stop(self):
        """停止代理爬虫（同步方式）"""
        if self.proxy_client:
            try:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self.proxy_client.stop())
                
                # 输出统计信息
                if self.total_requests > 0:
                    success_rate = (self.successful_requests / self.total_requests) * 100
                    self.logger.info(f"爬虫统计: 总请求{self.total_requests}, 成功{self.successful_requests}, 成功率{success_rate:.1f}%")
                
                self.logger.info("代理爬虫已停止")
                
            except Exception as e:
                self.logger.error(f"停止代理爬虫时出错: {e}")
    
    def get_new_proxy(self) -> Optional[str]:
        """
        获取新的代理地址（同步方式）
        
        Returns:
            str: 新的代理URL，失败时返回None
        """
        if not self.proxy_client:
            return None
        
        try:
            loop = asyncio.get_event_loop()
            
            async def _get_proxy():
                return await self.proxy_client.get_proxy_url(strategy='round_robin')
            
            self.current_proxy = loop.run_until_complete(_get_proxy())
            return self.current_proxy
            
        except Exception as e:
            self.logger.error(f"获取新代理时出错: {e}")
            return None
    
    def fetch(
        self,
        url: str,
        method: str = 'GET',
        headers: Optional[Dict] = None,
        data: Optional[Union[Dict, str]] = None,
        timeout: int = 15,
        max_retries: int = 3
    ) -> Optional[requests.Response]:
        """
        发起HTTP请求（同步方式）
        
        Args:
            url: 目标URL
            method: HTTP方法
            headers: 请求头
            data: 请求数据
            timeout: 超时时间
            max_retries: 最大重试次数
            
        Returns:
            requests.Response: 响应对象，失败时返回None
        """
        self.total_requests += 1
        
        # 合并请求头
        request_headers = self.session_headers.copy()
        if headers:
            request_headers.update(headers)
        
        for attempt in range(max_retries + 1):
            try:
                # 确保有可用的代理
                if not self.current_proxy:
                    self.get_new_proxy()
                
                if not self.current_proxy:
                    self.logger.error("无可用代理")
                    break
                
                # 设置代理
                proxies = {
                    'http': self.current_proxy,
                    'https': self.current_proxy
                }
                
                # 发起请求
                response = requests.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    data=data,
                    proxies=proxies,
                    timeout=timeout,
                    allow_redirects=True
                )
                
                # 检查响应状态
                if response.status_code == 200:
                    self.successful_requests += 1
                    self.logger.debug(f"成功请求: {url}")
                    return response
                
                elif response.status_code in [403, 429, 503]:
                    # 可能被反爬虫检测，切换代理
                    self.logger.warning(f"可能被检测 (HTTP {response.status_code}): {url}, 切换代理")
                    self.get_new_proxy()
                
                else:
                    self.logger.warning(f"HTTP错误 {response.status_code}: {url}")
                
            except requests.exceptions.Timeout:
                self.logger.warning(f"第{attempt+1}次尝试超时: {url}")
                self.get_new_proxy()
                
            except requests.exceptions.ProxyError:
                self.logger.warning(f"代理错误，切换代理: {url}")
                self.get_new_proxy()
                
            except Exception as e:
                self.logger.error(f"第{attempt+1}次尝试失败: {url}, 错误: {e}")
            
            # 重试前等待
            if attempt < max_retries:
                time.sleep(random.uniform(1, 3))
        
        self.logger.error(f"请求失败 (已重试{max_retries}次): {url}")
        return None
    
    def get(self, url: str, **kwargs) -> Optional[requests.Response]:
        """GET请求的便捷方法"""
        return self.fetch(url, method='GET', **kwargs)
    
    def post(self, url: str, data=None, **kwargs) -> Optional[requests.Response]:
        """POST请求的便捷方法"""
        return self.fetch(url, method='POST', data=data, **kwargs)
    
    def get_json(self, url: str, **kwargs) -> Optional[Dict]:
        """
        获取JSON数据的便捷方法
        
        Args:
            url: API接口URL
            **kwargs: 其他请求参数
            
        Returns:
            Dict: JSON数据，失败时返回None
        """
        response = self.get(url, **kwargs)
        if response:
            try:
                return response.json()
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON解析失败: {url}, 错误: {e}")
        return None
    
    def download_file(self, url: str, filename: str, **kwargs) -> bool:
        """
        下载文件的便捷方法
        
        Args:
            url: 文件URL
            filename: 保存的文件名
            **kwargs: 其他请求参数
            
        Returns:
            bool: 下载是否成功
        """
        response = self.get(url, **kwargs)
        if response:
            try:
                with open(filename, 'wb') as f:
                    f.write(response.content)
                self.logger.info(f"文件下载成功: {filename}")
                return True
            except Exception as e:
                self.logger.error(f"文件保存失败: {filename}, 错误: {e}")
        return False
    
    def crawl_urls(self, urls: List[str], delay: float = 2.0) -> List[Dict]:
        """
        批量爬取URL列表
        
        Args:
            urls: URL列表
            delay: 请求间隔时间
            
        Returns:
            List[Dict]: 爬取结果列表
        """
        results = []
        
        for i, url in enumerate(urls):
            self.logger.info(f"爬取 {i+1}/{len(urls)}: {url}")
            
            response = self.get(url)
            
            if response:
                result = {
                    'url': url,
                    'status_code': response.status_code,
                    'content': response.text,
                    'headers': dict(response.headers),
                    'success': True
                }
            else:
                result = {
                    'url': url,
                    'status_code': None,
                    'content': None,
                    'headers': None,
                    'success': False
                }
            
            results.append(result)
            
            # 请求间隔
            if i < len(urls) - 1:
                time.sleep(delay)
        
        return results
    
    def get_proxy_info(self) -> Dict:
        """
        获取代理信息（同步方式）
        
        Returns:
            Dict: 代理信息
        """
        if not self.proxy_client:
            return {'error': '代理客户端未启动'}
        
        try:
            loop = asyncio.get_event_loop()
            
            async def _get_info():
                return await self.proxy_client.get_proxy_info()
            
            return loop.run_until_complete(_get_info())
            
        except Exception as e:
            return {'error': str(e)}


# 使用示例
def simple_crawling_example():
    """简单爬虫使用示例"""
    print("=== 简单代理爬虫示例 ===")
    
    # 创建爬虫实例
    spider = SimpleProxySpider()
    
    try:
        # 启动爬虫
        if not spider.start():
            print("爬虫启动失败")
            return
        
        print("爬虫启动成功")
        
        # 单个URL爬取
        print("\n1. 单个URL爬取测试")
        response = spider.get('http://httpbin.org/ip')
        if response:
            data = response.json()
            print(f"当前IP: {data['origin']}")
        
        # JSON API爬取
        print("\n2. JSON API爬取测试")
        json_data = spider.get_json('http://httpbin.org/json')
        if json_data:
            print(f"获取到JSON数据: {list(json_data.keys())}")
        
        # 批量URL爬取
        print("\n3. 批量URL爬取测试")
        urls = [
            'http://httpbin.org/ip',
            'http://httpbin.org/user-agent',
            'http://httpbin.org/headers'
        ]
        
        results = spider.crawl_urls(urls, delay=1.0)
        successful = sum(1 for r in results if r['success'])
        print(f"批量爬取完成: {successful}/{len(results)} 成功")
        
        # 显示代理信息
        print("\n4. 代理信息")
        proxy_info = spider.get_proxy_info()
        if 'error' not in proxy_info:
            stats = proxy_info['proxy_stats']
            print(f"总代理数: {stats['total_proxies']}")
            print(f"健康代理数: {stats['healthy_proxies']}")
            print(f"健康率: {stats['health_rate']:.1%}")
        
    finally:
        # 停止爬虫
        spider.stop()


def ecommerce_example():
    """电商爬虫示例"""
    print("\n=== 电商爬虫示例 ===")
    
    spider = SimpleProxySpider()
    
    try:
        if not spider.start():
            print("爬虫启动失败")
            return
        
        # 模拟电商产品页面爬取
        product_urls = [
            'http://httpbin.org/html',  # 模拟产品页面
            'http://httpbin.org/json',  # 模拟产品API
        ]
        
        products = []
        
        for url in product_urls:
            print(f"爬取产品页面: {url}")
            
            response = spider.get(url)
            if response:
                # 这里可以添加具体的产品信息解析逻辑
                product_info = {
                    'url': url,
                    'content_length': len(response.text),
                    'status': 'success'
                }
                products.append(product_info)
                print(f"成功获取产品信息，内容长度: {len(response.text)}")
            
            time.sleep(2)  # 请求间隔
        
        print(f"电商爬取完成，成功获取{len(products)}个产品")
        
    finally:
        spider.stop()


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # 运行示例
    simple_crawling_example()
    ecommerce_example()
    
    print("\n所有示例运行完成！")
