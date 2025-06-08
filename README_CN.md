# Clash代理客户端 - 爬虫IP防封解决方案

一个专为网络爬虫设计的综合性Clash代理客户端，通过自动代理轮换和负载均衡来避免IP被封禁。

## 🌟 核心特性

- **自动节点获取**：从getNode项目和其他源自动获取免费代理节点
- **多格式支持**：支持Clash和V2Ray节点格式，自动转换
- **健康监控**：全面的健康检查，包含延迟测量和成功率跟踪
- **负载均衡**：多种策略包括健康权重、轮询、最少使用和随机选择
- **自动故障转移**：智能代理切换，节点失效时自动切换
- **简易集成**：简单的API，易于与现有爬虫框架集成
- **后台更新**：自动代理列表更新和健康监控
- **配置管理**：基于模板的配置生成，支持备份

## 📦 安装配置

### 前置要求

1. **安装Clash二进制文件**
   ```bash
   # 方式1：下载官方版本
   # 访问 https://github.com/Dreamacro/clash/releases
   
   # 方式2：下载Mihomo (clash-verge-rev核心)
   # 访问 https://github.com/MetaCubeX/mihomo/releases
   
   # 方式3：使用包管理器 (以Ubuntu为例)
   wget https://github.com/MetaCubeX/mihomo/releases/download/v1.18.0/mihomo-linux-amd64-v1.18.0.gz
   gunzip mihomo-linux-amd64-v1.18.0.gz
   chmod +x mihomo-linux-amd64-v1.18.0
   sudo mv mihomo-linux-amd64-v1.18.0 /usr/local/bin/mihomo
   ```

2. **安装Python依赖**
   ```bash
   pip install aiohttp pyyaml psutil requests
   ```

### 快速开始

```python
import asyncio
from nautilus_trader.adapters.clash import ClashProxyClient

async def main():
    # 初始化客户端
    client = ClashProxyClient(config_dir='./clash_configs')
    
    try:
        # 启动客户端（爬虫优化配置）
        await client.start(config_type='scraping')
        
        # 获取代理URL
        proxy_url = await client.get_proxy_url()
        print(f"代理地址: {proxy_url}")
        
        # 使用代理进行请求
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'http://httpbin.org/ip',
                proxy=proxy_url
            ) as response:
                data = await response.json()
                print(f"当前IP: {data['origin']}")
    
    finally:
        await client.stop()

# 运行示例
asyncio.run(main())
```

## 🚀 与爬虫框架集成

### 1. 与aiohttp集成（推荐）

```python
import asyncio
import aiohttp
from nautilus_trader.adapters.clash import ClashProxyClient

class ProxySpider:
    def __init__(self):
        self.proxy_client = ClashProxyClient()
        self.session = None
    
    async def start(self):
        """启动爬虫和代理客户端"""
        # 启动代理客户端
        await self.proxy_client.start(config_type='scraping')
        
        # 创建HTTP会话
        self.session = aiohttp.ClientSession()
        print("爬虫和代理客户端已启动")
    
    async def fetch_with_proxy(self, url, max_retries=3):
        """使用代理获取URL内容"""
        for attempt in range(max_retries):
            try:
                # 获取代理URL（使用健康权重策略）
                proxy_url = await self.proxy_client.get_proxy_url(
                    strategy='health_weighted'
                )
                
                if not proxy_url:
                    print(f"第{attempt+1}次尝试：无可用代理")
                    await asyncio.sleep(2)
                    continue
                
                # 发起请求
                async with self.session.get(
                    url,
                    proxy=proxy_url,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 200:
                        content = await response.text()
                        print(f"成功获取 {url}，使用代理: {proxy_url}")
                        return content
                    else:
                        print(f"HTTP错误 {response.status}，切换代理重试")
                        
            except asyncio.TimeoutError:
                print(f"第{attempt+1}次尝试超时，切换代理")
                # 切换到不同的代理
                await self.proxy_client.switch_proxy(strategy='round_robin')
                
            except Exception as e:
                print(f"第{attempt+1}次尝试失败: {e}")
            
            await asyncio.sleep(1)
        
        print(f"获取 {url} 失败，已重试{max_retries}次")
        return None
    
    async def crawl_urls(self, urls):
        """批量爬取URL列表"""
        results = []
        
        for i, url in enumerate(urls):
            print(f"正在爬取第{i+1}/{len(urls)}个URL: {url}")
            
            content = await self.fetch_with_proxy(url)
            if content:
                results.append({
                    'url': url,
                    'content': content[:200] + '...',  # 只显示前200字符
                    'status': 'success'
                })
            else:
                results.append({
                    'url': url,
                    'content': None,
                    'status': 'failed'
                })
            
            # 请求间隔，避免过于频繁
            await asyncio.sleep(2)
        
        return results
    
    async def stop(self):
        """停止爬虫和代理客户端"""
        if self.session:
            await self.session.close()
        await self.proxy_client.stop()
        print("爬虫和代理客户端已停止")

# 使用示例
async def spider_example():
    spider = ProxySpider()
    
    try:
        await spider.start()
        
        # 要爬取的URL列表
        urls = [
            'http://httpbin.org/ip',
            'http://httpbin.org/user-agent',
            'http://httpbin.org/headers',
            'https://api.github.com',
            'http://httpbin.org/get?test=1'
        ]
        
        # 开始爬取
        results = await spider.crawl_urls(urls)
        
        # 显示结果
        print(f"\n爬取完成，成功: {sum(1 for r in results if r['status'] == 'success')}/{len(results)}")
        
    finally:
        await spider.stop()

# 运行爬虫示例
# asyncio.run(spider_example())
```

### 2. 与requests集成（同步方式）

```python
import requests
import asyncio
import time
from nautilus_trader.adapters.clash import ClashProxyClient

class SyncProxySpider:
    def __init__(self):
        self.proxy_client = None
        self.current_proxy = None
    
    def start(self):
        """启动代理客户端"""
        async def _start():
            self.proxy_client = ClashProxyClient()
            await self.proxy_client.start(config_type='scraping')
            self.current_proxy = await self.proxy_client.get_proxy_url()
        
        asyncio.run(_start())
        print(f"代理客户端已启动，当前代理: {self.current_proxy}")
    
    def get_new_proxy(self):
        """获取新的代理"""
        async def _get_proxy():
            return await self.proxy_client.get_proxy_url(strategy='round_robin')
        
        self.current_proxy = asyncio.run(_get_proxy())
        return self.current_proxy
    
    def fetch_with_proxy(self, url, max_retries=3):
        """使用代理获取URL"""
        for attempt in range(max_retries):
            try:
                if not self.current_proxy:
                    self.get_new_proxy()
                
                proxies = {
                    'http': self.current_proxy,
                    'https': self.current_proxy
                }
                
                response = requests.get(
                    url,
                    proxies=proxies,
                    timeout=15,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                )
                
                if response.status_code == 200:
                    print(f"成功获取 {url}")
                    return response.text
                else:
                    print(f"HTTP错误 {response.status_code}，切换代理重试")
                    self.get_new_proxy()
                    
            except requests.exceptions.Timeout:
                print(f"第{attempt+1}次尝试超时，切换代理")
                self.get_new_proxy()
                
            except Exception as e:
                print(f"第{attempt+1}次尝试失败: {e}")
                self.get_new_proxy()
            
            time.sleep(1)
        
        return None
    
    def stop(self):
        """停止代理客户端"""
        async def _stop():
            if self.proxy_client:
                await self.proxy_client.stop()
        
        asyncio.run(_stop())
        print("代理客户端已停止")

# 使用示例
def sync_spider_example():
    spider = SyncProxySpider()
    
    try:
        spider.start()
        
        urls = [
            'http://httpbin.org/ip',
            'http://httpbin.org/user-agent',
            'https://api.github.com'
        ]
        
        for url in urls:
            content = spider.fetch_with_proxy(url)
            if content:
                print(f"获取到内容长度: {len(content)}")
            time.sleep(2)
    
    finally:
        spider.stop()
```

### 3. 与Scrapy集成

```python
# middlewares.py
import asyncio
from scrapy.downloadermiddlewares.httpproxy import HttpProxyMiddleware
from scrapy.exceptions import NotConfigured
from nautilus_trader.adapters.clash import ClashProxyClient

class ClashProxyMiddleware:
    def __init__(self):
        self.proxy_client = None
        self.loop = None
    
    @classmethod
    def from_crawler(cls, crawler):
        return cls()
    
    def open_spider(self, spider):
        """爬虫启动时初始化代理客户端"""
        async def _start_proxy():
            self.proxy_client = ClashProxyClient()
            await self.proxy_client.start(config_type='scraping')
        
        # 创建新的事件循环
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(_start_proxy())
        
        spider.logger.info("Clash代理中间件已启动")
    
    def close_spider(self, spider):
        """爬虫关闭时停止代理客户端"""
        async def _stop_proxy():
            if self.proxy_client:
                await self.proxy_client.stop()
        
        if self.loop:
            self.loop.run_until_complete(_stop_proxy())
            self.loop.close()
        
        spider.logger.info("Clash代理中间件已停止")
    
    def process_request(self, request, spider):
        """为每个请求设置代理"""
        async def _get_proxy():
            return await self.proxy_client.get_proxy_url(strategy='health_weighted')
        
        try:
            proxy_url = self.loop.run_until_complete(_get_proxy())
            if proxy_url:
                request.meta['proxy'] = proxy_url
                spider.logger.debug(f"使用代理: {proxy_url}")
        except Exception as e:
            spider.logger.error(f"获取代理失败: {e}")
        
        return None

# settings.py 配置
DOWNLOADER_MIDDLEWARES = {
    'myproject.middlewares.ClashProxyMiddleware': 350,
}

# 爬虫示例
import scrapy

class ExampleSpider(scrapy.Spider):
    name = 'example'
    start_urls = [
        'http://httpbin.org/ip',
        'http://httpbin.org/user-agent',
        'http://httpbin.org/headers'
    ]
    
    def parse(self, response):
        self.logger.info(f"响应状态: {response.status}")
        self.logger.info(f"响应内容: {response.text[:200]}")
        
        yield {
            'url': response.url,
            'status': response.status,
            'content_length': len(response.text)
        }
```

## 🔧 高级配置

### 负载均衡策略

```python
# 健康权重策略（推荐用于爬虫）
proxy_url = await client.get_proxy_url(strategy='health_weighted')

# 轮询策略（均匀分布请求）
proxy_url = await client.get_proxy_url(strategy='round_robin')

# 最少使用策略（负载均衡）
proxy_url = await client.get_proxy_url(strategy='least_used')

# 随机策略（简单随机选择）
proxy_url = await client.get_proxy_url(strategy='random')
```

### 配置类型选择

```python
# 爬虫优化配置（默认，包含故障转移和负载均衡）
await client.start(config_type='scraping')

# 速度优化配置（选择最快的代理）
await client.start(config_type='speed')

# 通用配置（平衡性能和稳定性）
await client.start(config_type='general')
```

### 监控和统计

```python
# 获取代理统计信息
info = await client.get_proxy_info()
print(f"总代理数: {info['proxy_stats']['total_proxies']}")
print(f"健康代理数: {info['proxy_stats']['healthy_proxies']}")
print(f"健康率: {info['proxy_stats']['health_rate']:.1%}")

# 测试特定代理
test_result = await client.test_proxy('proxy_name')
if test_result['success']:
    print(f"代理IP: {test_result['ip']}")
    print(f"延迟: {test_result['latency']}ms")
```

## 🛠️ 故障排除

### 常见问题

1. **找不到Clash二进制文件**
   ```bash
   # 解决方案1：安装到系统PATH
   sudo cp mihomo /usr/local/bin/
   
   # 解决方案2：指定路径
   client = ClashProxyClient(clash_binary_path='/path/to/clash')
   ```

2. **没有健康的代理**
   ```python
   # 检查代理状态
   info = await client.get_proxy_info()
   if info['proxy_stats']['healthy_proxies'] == 0:
       print("等待代理健康检查完成...")
       await asyncio.sleep(30)
   ```

3. **请求超时频繁**
   ```python
   # 调整超时设置
   async with session.get(url, proxy=proxy_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
       pass
   ```

### 调试模式

```python
import logging

# 启用详细日志
logging.basicConfig(level=logging.DEBUG)

# 或者只启用Clash相关日志
logging.getLogger('nautilus_trader.adapters.clash').setLevel(logging.DEBUG)
```

## 📊 性能优化建议

1. **合理设置请求间隔**：避免过于频繁的请求导致IP被封
2. **使用健康权重策略**：优先使用性能好的代理
3. **启用自动更新**：保持代理列表的新鲜度
4. **监控健康状态**：定期检查代理健康率
5. **设置合理超时**：平衡速度和成功率

## 🎯 最佳实践

1. **错误处理**：始终包含重试逻辑和异常处理
2. **代理轮换**：定期切换代理避免单一IP过度使用
3. **请求头设置**：使用真实的User-Agent和其他请求头
4. **速率限制**：控制请求频率，模拟人类行为
5. **监控日志**：关注代理健康状态和错误信息

## 🎯 实际应用场景

### 场景1：电商数据采集

```python
from nautilus_trader.adapters.clash.simple_spider import SimpleProxySpider
import time

def crawl_product_prices():
    """爬取电商产品价格"""
    spider = SimpleProxySpider()

    try:
        spider.start()

        # 产品URL列表
        product_urls = [
            'https://example-shop.com/product/123',
            'https://example-shop.com/product/456',
            # ... 更多产品URL
        ]

        for url in product_urls:
            response = spider.get(url)
            if response:
                # 解析价格信息
                # price = parse_price(response.text)
                print(f"成功获取产品页面: {url}")

            time.sleep(3)  # 避免请求过于频繁

    finally:
        spider.stop()
```

### 场景2：新闻资讯监控

```python
from nautilus_trader.adapters.clash.spider_integration import AdvancedProxySpider
import asyncio

async def monitor_news():
    """监控新闻网站更新"""
    spider = AdvancedProxySpider()

    try:
        await spider.start()

        news_sites = [
            'https://news-site1.com/latest',
            'https://news-site2.com/breaking',
            # ... 更多新闻源
        ]

        articles = await spider.crawl_news_articles(news_sites)

        # 保存到数据库或文件
        await spider.save_results(articles, 'latest_news.json')

    finally:
        await spider.stop()

# 定时运行
# asyncio.run(monitor_news())
```

### 场景3：API数据采集

```python
def collect_api_data():
    """采集API数据"""
    spider = SimpleProxySpider()

    try:
        spider.start()

        # API接口列表
        api_endpoints = [
            'https://api.example.com/v1/data',
            'https://api.example.com/v1/stats',
            # ... 更多API
        ]

        for endpoint in api_endpoints:
            # 添加API密钥等认证信息
            headers = {
                'Authorization': 'Bearer YOUR_API_KEY',
                'Accept': 'application/json'
            }

            json_data = spider.get_json(endpoint, headers=headers)
            if json_data:
                print(f"成功获取API数据: {endpoint}")
                # 处理数据
                # process_api_data(json_data)

    finally:
        spider.stop()
```

### 场景4：社交媒体数据采集

```python
async def crawl_social_media():
    """爬取社交媒体数据"""
    spider = AdvancedProxySpider()

    try:
        await spider.start()

        # 社交媒体页面
        social_urls = [
            'https://social-platform.com/user/profile1',
            'https://social-platform.com/user/profile2',
            # ... 更多用户页面
        ]

        for url in social_urls:
            result = await spider.fetch_with_retry(url, max_retries=5)
            if result:
                # 解析用户信息、帖子等
                # user_data = parse_social_profile(result['content'])
                print(f"成功获取社交媒体数据: {url}")

            # 较长的间隔，避免被检测
            await asyncio.sleep(random.uniform(5, 10))

    finally:
        await spider.stop()
```

## 🔄 与现有项目集成

### 集成到Django项目

```python
# views.py
from django.http import JsonResponse
from nautilus_trader.adapters.clash.simple_spider import SimpleProxySpider
import threading
import time

class DataCollectionView:
    def __init__(self):
        self.spider = SimpleProxySpider()
        self.spider.start()

    def collect_data(self, request):
        """数据采集接口"""
        urls = request.POST.getlist('urls')

        results = []
        for url in urls:
            response = self.spider.get(url)
            if response:
                results.append({
                    'url': url,
                    'status': 'success',
                    'data': response.text[:500]  # 截取前500字符
                })
            else:
                results.append({
                    'url': url,
                    'status': 'failed'
                })

        return JsonResponse({'results': results})

    def __del__(self):
        if hasattr(self, 'spider'):
            self.spider.stop()
```

### 集成到Flask项目

```python
# app.py
from flask import Flask, request, jsonify
from nautilus_trader.adapters.clash.simple_spider import SimpleProxySpider

app = Flask(__name__)

# 全局爬虫实例
spider = SimpleProxySpider()

@app.before_first_request
def initialize():
    """应用启动时初始化爬虫"""
    spider.start()

@app.route('/crawl', methods=['POST'])
def crawl_data():
    """爬取数据接口"""
    data = request.get_json()
    urls = data.get('urls', [])

    results = spider.crawl_urls(urls, delay=1.0)

    return jsonify({
        'total': len(results),
        'successful': sum(1 for r in results if r['success']),
        'results': results
    })

@app.route('/proxy-status')
def proxy_status():
    """代理状态接口"""
    info = spider.get_proxy_info()
    return jsonify(info)

@app.teardown_appcontext
def cleanup(error):
    """应用关闭时清理资源"""
    spider.stop()

if __name__ == '__main__':
    app.run(debug=True)
```

### 集成到Celery任务

```python
# tasks.py
from celery import Celery
from nautilus_trader.adapters.clash.simple_spider import SimpleProxySpider

app = Celery('crawler')

@app.task
def crawl_urls_task(urls):
    """异步爬取任务"""
    spider = SimpleProxySpider()

    try:
        spider.start()
        results = spider.crawl_urls(urls, delay=2.0)

        return {
            'status': 'completed',
            'total': len(results),
            'successful': sum(1 for r in results if r['success']),
            'results': results
        }

    finally:
        spider.stop()

# 使用方式
# from tasks import crawl_urls_task
# result = crawl_urls_task.delay(['http://example.com', 'http://example2.com'])
```

## 📊 监控和维护

### 健康监控脚本

```python
# monitor.py
import asyncio
import time
from nautilus_trader.adapters.clash import ClashProxyClient

async def monitor_proxy_health():
    """监控代理健康状态"""
    client = ClashProxyClient()

    try:
        await client.start()

        while True:
            info = await client.get_proxy_info()
            stats = info['proxy_stats']
            health_stats = info['health_stats']

            print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"总代理: {stats['total_proxies']}")
            print(f"健康代理: {stats['healthy_proxies']}")
            print(f"健康率: {stats['health_rate']:.1%}")
            print(f"平均分数: {health_stats['average_score']}")
            print("-" * 40)

            # 如果健康率过低，发送告警
            if stats['health_rate'] < 0.3:
                print("⚠️ 警告：代理健康率过低！")
                # 这里可以添加邮件或短信告警

            await asyncio.sleep(300)  # 每5分钟检查一次

    finally:
        await client.stop()

if __name__ == "__main__":
    asyncio.run(monitor_proxy_health())
```

### 自动重启脚本

```python
# auto_restart.py
import asyncio
import logging
import time
from nautilus_trader.adapters.clash import ClashProxyClient

async def auto_restart_on_failure():
    """代理客户端自动重启"""
    while True:
        client = ClashProxyClient()

        try:
            success = await client.start()
            if not success:
                logging.error("代理客户端启动失败，等待重试...")
                await asyncio.sleep(60)
                continue

            logging.info("代理客户端启动成功")

            # 监控运行状态
            while True:
                try:
                    info = await client.get_proxy_info()
                    if not info['is_running']:
                        logging.warning("代理客户端已停止运行")
                        break

                    await asyncio.sleep(30)  # 每30秒检查一次

                except Exception as e:
                    logging.error(f"健康检查失败: {e}")
                    break

        except Exception as e:
            logging.error(f"代理客户端运行异常: {e}")

        finally:
            try:
                await client.stop()
            except:
                pass

        logging.info("等待重启...")
        await asyncio.sleep(30)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(auto_restart_on_failure())
```

## 🎯 性能调优建议

1. **代理池大小**：保持50-100个活跃代理为最佳
2. **请求频率**：建议每个请求间隔2-5秒
3. **重试策略**：最大重试3次，指数退避
4. **健康检查**：每5分钟进行一次全面健康检查
5. **代理轮换**：每10-20个请求切换一次代理
6. **错误处理**：对不同HTTP状态码采用不同的处理策略

通过以上配置和集成方式，您可以轻松地将Clash代理客户端与现有的爬虫项目集成，有效避免IP被封禁的问题。
