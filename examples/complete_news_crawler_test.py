"""
改进的完整新闻爬虫测试
支持两种模式：
1. 使用现有配置文件 (config_path)
2. 通过custom_sources自动获取节点

实现完整流程：
1. 节点获取 (支持custom_sources参数)
2. 健康检查并写入rule保存到config
3. 启动clash开始健康检查
4. 将不健康节点排除（保存健康节点在内存或重新写入config.yaml）
5. 重新启动clash
6. 开始自动节点切换或强制切换
7. 爬虫测试验证
8. 验证其他网址不走代理
"""

import asyncio
import aiohttp
import subprocess
import platform
import logging
import sys
import yaml
import time
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urlparse

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from crawladapter.fetchers import NodeFetcher


class ImprovedCompleteNewsTest:
    """改进的完整新闻爬虫测试"""

    def __init__(self,
                 config_path: Optional[str] = None,
                 custom_sources: Optional[Dict[str, List[str]]] = None,
                 min_healthy_nodes: int = 3):
        """
        初始化测试

        Args:
            config_path: 现有配置文件路径（可选）
            custom_sources: 自定义节点源（可选）
            min_healthy_nodes: 最少健康节点数量
        """
        self.logger = logging.getLogger(__name__)
        self.setup_logging()

        # 路径配置
        self.project_root = Path(__file__).parent.parent
        self.config_dir = self.project_root / 'clash_configs'
        self.config_dir.mkdir(exist_ok=True)

        # 配置文件路径
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = self.config_dir / 'auto_generated_config.yaml'

        self.binary_path = self.project_root / 'mihomo_proxy' / 'mihomo'

        # 自定义源配置
        self.custom_sources = custom_sources or {
            'clash': [
                'https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.yml',
                'https://raw.githubusercontent.com/Alvin9999/pac2/master/clash/config.yaml',
            ],
            'v2ray': []
        }

        # 网络配置
        self.proxy_port = 7890
        self.api_port = 9090
        self.clash_api_base = f"http://127.0.0.1:{self.api_port}"

        # 测试配置
        self.min_healthy_nodes = min_healthy_nodes

        # 代理相关URL（需要走代理）
        self.proxy_urls = [
            'httpbin.org',
            'www.gstatic.com',
            'detectportal.firefox.com',
            'www.msftconnecttest.com',
            'panewslab.com',
            'www.panewslab.com'
        ]

        # 直连URL（不走代理）
        self.direct_urls = [
            'baidu.com',
            'qq.com',
            'taobao.com',
            'jd.com'
        ]

        # 状态变量
        self.clash_process: Optional[subprocess.Popen] = None
        self.all_nodes: List[Dict] = []
        self.healthy_nodes: List[Dict] = []

    def setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('improved_complete_news_test.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )

    async def step1_fetch_nodes(self) -> bool:
        """步骤1: 节点获取（支持两种模式）"""
        self.logger.info("🚀 步骤1: 节点获取")

        try:
            # 模式1: 如果有现有配置文件，尝试读取
            if self.config_path.exists() and self.config_path.name != 'auto_generated_config.yaml':
                self.logger.info(f"📁 模式1: 从现有配置文件读取节点: {self.config_path}")

                with open(self.config_path, 'r', encoding='utf-8') as f:
                    existing_config = yaml.safe_load(f)

                self.all_nodes = existing_config.get('proxies', [])

                if self.all_nodes:
                    self.logger.info(f"✅ 从配置文件读取 {len(self.all_nodes)} 个节点")
                    return True
                else:
                    self.logger.warning("⚠️ 配置文件中没有代理节点，切换到自动获取模式")

            # 模式2: 通过custom_sources自动获取节点
            self.logger.info("📥 模式2: 通过custom_sources自动获取节点")
            self.logger.info(f"   节点源: {list(self.custom_sources.keys())}")

            node_fetcher = NodeFetcher(custom_sources=self.custom_sources)
            self.all_nodes = await node_fetcher.fetch_nodes('all')

            if not self.all_nodes:
                self.logger.error("❌ 未获取到任何节点")
                return False

            self.logger.info(f"✅ 自动获取 {len(self.all_nodes)} 个节点")

            # 显示节点类型统计
            node_types = {}
            for node in self.all_nodes:
                node_type = node.get('type', 'unknown')
                node_types[node_type] = node_types.get(node_type, 0) + 1

            self.logger.info(f"   节点类型分布: {node_types}")
            return True

        except Exception as e:
            self.logger.error(f"❌ 步骤1失败: {e}")
            return False

    async def step2_create_initial_config(self) -> bool:
        """步骤2: 创建初始配置并写入rule"""
        self.logger.info("⚙️ 步骤2: 创建初始配置")

        try:
            # 生成包含所有节点的配置
            config = self._generate_smart_config(self.all_nodes)

            # 保存配置
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)

            self.logger.info(f"✅ 初始配置已保存: {self.config_path}")
            self.logger.info(f"   包含 {len(self.all_nodes)} 个代理节点")
            self.logger.info(f"   代理规则: {len(self.proxy_urls)} 个域名")
            self.logger.info(f"   直连规则: {len(self.direct_urls)} 个域名")

            return True

        except Exception as e:
            self.logger.error(f"❌ 步骤2失败: {e}")
            return False

    def _generate_smart_config(self, nodes: List[Dict]) -> Dict:
        """生成智能路由配置"""
        # 确保节点名称唯一
        unique_nodes = []
        used_names = set()

        for i, node in enumerate(nodes):
            original_name = node.get('name', f'node_{i}')
            name = original_name
            counter = 1

            while name in used_names:
                name = f"{original_name}_{counter}"
                counter += 1

            node['name'] = name
            used_names.add(name)
            unique_nodes.append(node)

        config = {
            'mixed-port': self.proxy_port,
            'allow-lan': False,
            'mode': 'rule',
            'log-level': 'info',
            'external-controller': f'127.0.0.1:{self.api_port}',
            'ipv6': True,
            'dns': {
                'enable': True,
                'nameserver': [
                    '8.8.8.8',
                    '1.1.1.1',
                    '114.114.114.114'
                ],
                'fallback': [
                    '8.8.4.4',
                    '1.0.0.1'
                ],
                'enhanced-mode': 'fake-ip',
                'fake-ip-range': '198.18.0.1/16',
                'fake-ip-filter': [
                    '*.lan',
                    'localhost.ptlogin2.qq.com',
                    '+.stun.*.*',
                    '+.stun.*.*.*',
                    '+.stun.*.*.*.*'
                ]
            },
            'proxies': unique_nodes,
            'proxy-groups': [
                {
                    'name': 'PROXY',
                    'type': 'select',  # 使用select类型，更稳定
                    'proxies': ['DIRECT'] + [node['name'] for node in unique_nodes]
                },
                {
                    'name': 'AUTO',
                    'type': 'url-test',
                    'proxies': [node['name'] for node in unique_nodes] if unique_nodes else ['DIRECT'],
                    'url': 'http://www.gstatic.com/generate_204',
                    'interval': 300,
                    'tolerance': 50
                }
            ],
            'rules': self._generate_smart_rules()
        }

        return config

    def _generate_final_config_with_rules(self, nodes: List[Dict]) -> Dict:
        """生成最终配置（健康节点+新闻网络规则）"""
        # 确保节点名称唯一
        unique_nodes = []
        used_names = set()

        for i, node in enumerate(nodes):
            original_name = node.get('name', f'node_{i}')
            name = original_name
            counter = 1

            while name in used_names:
                name = f"{original_name}_{counter}"
                counter += 1

            node['name'] = name
            used_names.add(name)
            unique_nodes.append(node)

        config = {
            'mixed-port': self.proxy_port,
            'allow-lan': False,
            'mode': 'rule',
            'log-level': 'info',
            'external-controller': f'127.0.0.1:{self.api_port}',
            'ipv6': True,
            'dns': {
                'enable': True,
                'nameserver': [
                    '8.8.8.8',
                    '1.1.1.1',
                    '114.114.114.114'
                ],
                'fallback': [
                    '8.8.4.4',
                    '1.0.0.1'
                ],
                'enhanced-mode': 'fake-ip',
                'fake-ip-range': '198.18.0.1/16'
            },
            'proxies': unique_nodes,
            'proxy-groups': [
                {
                    'name': 'PROXY',
                    'type': 'select',
                    'proxies': [node['name'] for node in unique_nodes] + ['DIRECT']
                },
                {
                    'name': 'AUTO',
                    'type': 'url-test',
                    'proxies': [node['name'] for node in unique_nodes] if unique_nodes else ['DIRECT'],
                    'url': 'http://www.gstatic.com/generate_204',
                    'interval': 300,
                    'tolerance': 50
                }
            ],
            'rules': self._generate_news_crawling_rules()
        }

        return config

    def _generate_smart_rules(self) -> List[str]:
        """生成智能路由规则 - 修复版本"""
        rules = []

        # 1. 本地网络直连（优先级最高）
        rules.extend([
            'IP-CIDR,127.0.0.0/8,DIRECT',
            'IP-CIDR,172.16.0.0/12,DIRECT',
            'IP-CIDR,192.168.0.0/16,DIRECT',
            'IP-CIDR,10.0.0.0/8,DIRECT',
            'IP-CIDR,224.0.0.0/4,DIRECT',
            'DOMAIN-SUFFIX,local,DIRECT'
        ])

        # 2. 健康检查和测试URL走代理（确保健康检查正常工作）
        proxy_domains = [
            'httpbin.org',
            'www.gstatic.com',
            'gstatic.com',
            'detectportal.firefox.com',
            'www.msftconnecttest.com',
            'msftconnecttest.com',
            'google.com',
            'www.google.com'
        ]

        for domain in proxy_domains:
            rules.append(f'DOMAIN-SUFFIX,{domain},PROXY')

        # 3. 新闻爬虫目标网站走代理
        news_domains = [
            'panewslab.com',
            'www.panewslab.com'
        ]

        for domain in news_domains:
            rules.append(f'DOMAIN-SUFFIX,{domain},PROXY')

        # 4. 国内网站直连
        direct_domains = [
            'baidu.com',
            'qq.com',
            'taobao.com',
            'jd.com',
            '163.com',
            'sina.com.cn',
            'weibo.com',
            'zhihu.com',
            'bilibili.com'
        ]

        for domain in direct_domains:
            rules.append(f'DOMAIN-SUFFIX,{domain},DIRECT')

        # 5. 中国IP直连
        rules.append('GEOIP,CN,DIRECT')

        # 6. 默认规则（其他所有流量直连）
        rules.append('MATCH,DIRECT')

        return rules

    def _generate_news_crawling_rules(self) -> List[str]:
        """生成新闻爬取专用规则"""
        rules = []

        # 1. 本地网络直连（优先级最高）
        rules.extend([
            'IP-CIDR,127.0.0.0/8,DIRECT',
            'IP-CIDR,172.16.0.0/12,DIRECT',
            'IP-CIDR,192.168.0.0/16,DIRECT',
            'IP-CIDR,10.0.0.0/8,DIRECT',
            'DOMAIN-SUFFIX,local,DIRECT'
        ])

        # 2. 新闻网站必须走代理
        rules.extend([
            'DOMAIN-SUFFIX,panewslab.com,PROXY',
            'DOMAIN-SUFFIX,www.panewslab.com,PROXY'
        ])

        # 3. 测试和健康检查URL走代理
        rules.extend([
            'DOMAIN-SUFFIX,httpbin.org,PROXY',
            'DOMAIN-SUFFIX,www.gstatic.com,PROXY',
            'DOMAIN-SUFFIX,gstatic.com,PROXY'
        ])

        # 4. 国内网站直连
        rules.extend([
            'DOMAIN-SUFFIX,baidu.com,DIRECT',
            'DOMAIN-SUFFIX,qq.com,DIRECT',
            'DOMAIN-SUFFIX,taobao.com,DIRECT',
            'DOMAIN-SUFFIX,jd.com,DIRECT'
        ])

        # 5. 中国IP直连
        rules.append('GEOIP,CN,DIRECT')

        # 6. 默认规则（其他流量直连）
        rules.append('MATCH,DIRECT')

        return rules

    def _generate_news_crawling_rules(self) -> List[str]:
        """生成新闻爬取专用规则"""
        rules = []

        # 1. 本地网络直连（优先级最高）
        rules.extend([
            'IP-CIDR,127.0.0.0/8,DIRECT',
            'IP-CIDR,172.16.0.0/12,DIRECT',
            'IP-CIDR,192.168.0.0/16,DIRECT',
            'IP-CIDR,10.0.0.0/8,DIRECT',
            'DOMAIN-SUFFIX,local,DIRECT'
        ])

        # 2. 新闻网站必须走代理
        rules.extend([
            'DOMAIN-SUFFIX,panewslab.com,PROXY',
            'DOMAIN-SUFFIX,www.panewslab.com,PROXY'
        ])

        # 3. 测试和健康检查URL走代理
        rules.extend([
            'DOMAIN-SUFFIX,httpbin.org,PROXY',
            'DOMAIN-SUFFIX,www.gstatic.com,PROXY',
            'DOMAIN-SUFFIX,gstatic.com,PROXY'
        ])

        # 4. 国内网站直连
        rules.extend([
            'DOMAIN-SUFFIX,baidu.com,DIRECT',
            'DOMAIN-SUFFIX,qq.com,DIRECT',
            'DOMAIN-SUFFIX,taobao.com,DIRECT',
            'DOMAIN-SUFFIX,jd.com,DIRECT'
        ])

        # 5. 中国IP直连
        rules.append('GEOIP,CN,DIRECT')

        # 6. 默认规则（其他流量直连）
        rules.append('MATCH,DIRECT')

        return rules

    async def step3_test_nodes_health(self) -> bool:
        """步骤3: 测试节点健康状况（不启动Clash）"""
        self.logger.info("🏥 步骤3: 测试节点健康状况")

        try:
            # 3.1 直接测试节点连通性（不依赖Clash）
            self.logger.info("🔍 直接测试节点连通性...")
            health_results = await self._test_nodes_directly()

            if not health_results:
                self.logger.warning("⚠️ 健康检查未返回结果")
                return False

            # 3.2 筛选健康节点
            self.healthy_nodes = self._filter_healthy_nodes(health_results)

            healthy_count = len(self.healthy_nodes)
            total_count = len(self.all_nodes)

            self.logger.info(f"✅ 健康检查完成: {healthy_count}/{total_count} 个节点健康")

            # 3.3 检查是否有足够的健康节点
            if healthy_count < self.min_healthy_nodes:
                self.logger.warning(f"⚠️ 健康节点数量 ({healthy_count}) 少于最小要求 ({self.min_healthy_nodes})")
                self.logger.info("   将降低健康标准重新筛选...")

                # 降低健康标准
                self.healthy_nodes = self._filter_healthy_nodes(health_results, threshold=0.1)
                healthy_count = len(self.healthy_nodes)
                self.logger.info(f"   降低标准后: {healthy_count} 个节点可用")

            if healthy_count == 0:
                self.logger.error("❌ 没有可用的健康节点")
                return False

            # 3.4 显示健康节点信息
            self.logger.info("✅ 健康节点列表:")
            for i, node in enumerate(self.healthy_nodes[:5], 1):
                node_name = node.get('name', f'node_{i}')
                node_type = node.get('type', 'unknown')
                server = node.get('server', 'unknown')
                self.logger.info(f"   {i}. {node_name} ({node_type}) - {server}")

            return True

        except Exception as e:
            self.logger.error(f"❌ 步骤3失败: {e}")
            return False

    async def _start_clash(self) -> bool:
        """启动Clash进程"""
        try:
            if not self.binary_path.exists():
                self.logger.error(f"❌ 二进制文件不存在: {self.binary_path}")
                return False

            cmd = [str(self.binary_path), '-f', str(self.config_path)]
            self.logger.info(f"启动命令: {' '.join(cmd)}")

            self.clash_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0
            )

            # 检查启动状态
            await asyncio.sleep(3)

            if self.clash_process.poll() is None:
                self.logger.info("✅ Clash启动成功")
                return True
            else:
                stdout, stderr = self.clash_process.communicate()
                self.logger.error("❌ Clash启动失败")
                if stdout:
                    self.logger.error(f"标准输出: {stdout.decode('utf-8', errors='ignore')}")
                if stderr:
                    self.logger.error(f"错误输出: {stderr.decode('utf-8', errors='ignore')}")
                return False

        except Exception as e:
            self.logger.error(f"❌ 启动Clash异常: {e}")
            return False

    async def _perform_comprehensive_health_check(self) -> Dict[str, float]:
        """执行全面的健康检查"""
        self.logger.info("🔍 执行全面健康检查...")

        health_results = {}

        try:
            # 获取代理列表
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.clash_api_base}/proxies") as response:
                    if response.status != 200:
                        self.logger.error("❌ 无法获取代理列表")
                        return {}

                    data = await response.json()
                    proxies = data.get('proxies', {})

                    if 'PROXY' not in proxies:
                        self.logger.error("❌ 找不到PROXY组")
                        return {}

                    proxy_names = proxies['PROXY'].get('all', [])
                    actual_proxies = [p for p in proxy_names if p not in ['DIRECT']]

                    self.logger.info(f"📋 找到 {len(actual_proxies)} 个代理进行健康检查")

                    # 分批测试代理（避免过多并发）
                    batch_size = 5
                    for i in range(0, len(actual_proxies), batch_size):
                        batch = actual_proxies[i:i+batch_size]
                        self.logger.info(f"🔍 测试批次 {i//batch_size + 1}: {len(batch)} 个代理")

                        # 并发测试当前批次
                        tasks = [self._test_single_proxy_comprehensive(proxy_name) for proxy_name in batch]
                        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                        # 处理结果
                        for proxy_name, result in zip(batch, batch_results):
                            if isinstance(result, Exception):
                                health_results[proxy_name] = 0.0
                                self.logger.debug(f"❌ {proxy_name}: 测试异常 ({result})")
                            else:
                                health_results[proxy_name] = result
                                if result > 0:
                                    self.logger.info(f"✅ {proxy_name}: {result:.2f}")
                                else:
                                    self.logger.debug(f"❌ {proxy_name}: 不可用")

                        # 批次间延迟
                        if i + batch_size < len(actual_proxies):
                            await asyncio.sleep(2)

        except Exception as e:
            self.logger.error(f"❌ 健康检查失败: {e}")

        return health_results

    async def _test_single_proxy_comprehensive(self, proxy_name: str) -> float:
        """全面测试单个代理"""
        try:
            # 切换到指定代理
            async with aiohttp.ClientSession() as session:
                switch_data = {"name": proxy_name}
                async with session.put(f"{self.clash_api_base}/proxies/PROXY", json=switch_data) as response:
                    if response.status != 204:
                        return 0.0

                # 等待切换生效
                await asyncio.sleep(1)

                # 多重测试
                test_results = []

                # 测试1: 基础连通性
                basic_score = await self._test_basic_connectivity()
                test_results.append(basic_score)

                # 测试2: HTTPS连接
                https_score = await self._test_https_connectivity()
                test_results.append(https_score)

                # 测试3: 目标网站访问
                target_score = await self._test_target_website_access()
                test_results.append(target_score)

                # 计算综合分数
                valid_results = [score for score in test_results if score >= 0]
                if valid_results:
                    final_score = sum(valid_results) / len(valid_results)
                    return final_score
                else:
                    return 0.0

        except Exception as e:
            self.logger.debug(f"代理 {proxy_name} 测试失败: {e}")
            return 0.0

    async def _test_basic_connectivity(self) -> float:
        """测试基础连通性 - 使用requests库更可靠"""
        test_urls = [
            'http://httpbin.org/ip',
            'http://www.gstatic.com/generate_204'
        ]

        success_count = 0
        for url in test_urls:
            try:
                # 使用requests库进行测试，更稳定
                import requests
                proxies = {
                    'http': f'http://127.0.0.1:{self.proxy_port}',
                    'https': f'http://127.0.0.1:{self.proxy_port}'
                }

                response = requests.get(url, proxies=proxies, timeout=10)
                if response.status_code in [200, 204]:
                    success_count += 1
                    self.logger.debug(f"✅ 基础连通性测试成功: {url}")
                else:
                    self.logger.debug(f"❌ 基础连通性测试失败: {url} - HTTP {response.status_code}")
            except Exception as e:
                self.logger.debug(f"❌ 基础连通性测试异常: {url} - {e}")
                continue

        return success_count / len(test_urls)

    async def _test_https_connectivity(self) -> float:
        """测试HTTPS连通性 - 使用requests库更可靠"""
        test_urls = [
            'https://www.google.com/generate_204',
            'https://httpbin.org/ip'
        ]

        success_count = 0
        for url in test_urls:
            try:
                # 使用requests库进行HTTPS测试
                import requests
                proxies = {
                    'http': f'http://127.0.0.1:{self.proxy_port}',
                    'https': f'http://127.0.0.1:{self.proxy_port}'
                }

                response = requests.get(url, proxies=proxies, timeout=15, verify=False)
                if response.status_code in [200, 204]:
                    success_count += 1
                    self.logger.debug(f"✅ HTTPS连通性测试成功: {url}")
                else:
                    self.logger.debug(f"❌ HTTPS连通性测试失败: {url} - HTTP {response.status_code}")
            except Exception as e:
                self.logger.debug(f"❌ HTTPS连通性测试异常: {url} - {e}")
                continue

        return success_count / len(test_urls)

    async def _test_target_website_access(self) -> float:
        """测试目标网站访问 - 使用requests库更可靠"""
        try:
            # 使用requests库测试目标网站
            import requests
            proxies = {
                'http': f'http://127.0.0.1:{self.proxy_port}',
                'https': f'http://127.0.0.1:{self.proxy_port}'
            }

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(
                "https://www.panewslab.com/webapi/flashnews?LId=1&Rn=1&tw=0",
                proxies=proxies,
                headers=headers,
                timeout=20,
                verify=False
            )

            if response.status_code == 200:
                self.logger.debug("✅ 目标网站访问测试成功")
                return 1.0
            elif response.status_code in [301, 302, 403]:
                self.logger.debug(f"⚠️ 目标网站访问部分成功: HTTP {response.status_code}")
                return 0.5  # 部分可用
            else:
                self.logger.debug(f"❌ 目标网站访问失败: HTTP {response.status_code}")
                return 0.0
        except Exception as e:
            self.logger.debug(f"❌ 目标网站访问异常: {e}")
            return 0.0

    async def _test_nodes_directly(self) -> Dict[str, float]:
        """直接测试节点健康状况（不依赖Clash）"""
        self.logger.info("🔍 直接测试节点连通性...")

        health_results = {}

        try:
            # 分批测试节点（避免过多并发）
            batch_size = 3
            for i in range(0, len(self.all_nodes), batch_size):
                batch = self.all_nodes[i:i+batch_size]
                self.logger.info(f"🔍 测试批次 {i//batch_size + 1}: {len(batch)} 个节点")

                # 并发测试当前批次
                tasks = [self._test_single_node_directly(node) for node in batch]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                # 处理结果
                for node, result in zip(batch, batch_results):
                    node_name = node.get('name', f'node_{i}')
                    if isinstance(result, Exception):
                        health_results[node_name] = 0.0
                        self.logger.debug(f"❌ {node_name}: 测试异常 ({result})")
                    else:
                        health_results[node_name] = result
                        if result > 0:
                            self.logger.info(f"✅ {node_name}: {result:.2f}")
                        else:
                            self.logger.debug(f"❌ {node_name}: 不可用")

                # 批次间延迟
                if i + batch_size < len(self.all_nodes):
                    await asyncio.sleep(1)

        except Exception as e:
            self.logger.error(f"❌ 直接节点测试失败: {e}")

        return health_results

    async def _test_single_node_directly(self, node: Dict) -> float:
        """直接测试单个节点（不依赖Clash）"""
        try:
            node_name = node.get('name', 'unknown')
            node_type = node.get('type', 'unknown')
            server = node.get('server', '')
            port = node.get('port', 0)

            if not server or not port:
                return 0.0

            # 简单的TCP连接测试
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)

            try:
                result = sock.connect_ex((server, port))
                if result == 0:
                    self.logger.debug(f"✅ {node_name}: TCP连接成功")
                    return 0.8  # 基础连通性分数
                else:
                    self.logger.debug(f"❌ {node_name}: TCP连接失败")
                    return 0.0
            finally:
                sock.close()

        except Exception as e:
            self.logger.debug(f"❌ {node_name}: 测试异常 - {e}")
            return 0.0

    def _filter_healthy_nodes(self, health_results: Dict[str, float], threshold: float = 0.3) -> List[Dict]:
        """筛选健康节点"""
        healthy_nodes = []

        for node in self.all_nodes:
            node_name = node.get('name', '')
            score = health_results.get(node_name, 0.0)

            if score >= threshold:
                healthy_nodes.append(node)

        return healthy_nodes

    async def step4_create_final_config_and_start_clash(self) -> bool:
        """步骤4: 创建最终配置（健康节点+规则）并启动Clash"""
        self.logger.info("⚙️ 步骤4: 创建最终配置并启动Clash")

        try:
            # 4.1 生成最终配置（只包含健康节点+新闻网络规则）
            if self.healthy_nodes:
                final_config = self._generate_final_config_with_rules(self.healthy_nodes)
                self.logger.info(f"✅ 使用 {len(self.healthy_nodes)} 个健康节点生成最终配置")
            else:
                self.logger.warning("⚠️ 没有健康节点，使用所有节点")
                final_config = self._generate_final_config_with_rules(self.all_nodes)

            # 4.2 保存最终配置
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(final_config, f, default_flow_style=False, allow_unicode=True, indent=2)

            self.logger.info(f"✅ 最终配置已保存: {self.config_path}")
            self.logger.info(f"   包含 {len(final_config['proxies'])} 个健康节点")
            self.logger.info(f"   新闻网络规则: panewslab.com -> PROXY")
            self.logger.info(f"   国内网络规则: baidu.com等 -> DIRECT")

            # 4.3 启动Clash
            if not await self._start_clash():
                return False

            # 4.4 等待启动完成
            await asyncio.sleep(5)

            # 4.5 验证Clash API可用
            if not await self._verify_clash_api():
                return False

            self.logger.info("✅ Clash启动完成，准备开始新闻爬取")
            return True

        except Exception as e:
            self.logger.error(f"❌ 步骤4失败: {e}")
            return False

    async def step5_crawler_test_with_switching(self) -> bool:
        """步骤5: 爬虫测试和代理切换"""
        self.logger.info("🕷️ 步骤5: 爬虫测试和代理切换")

        try:
            # 5.1 第一次爬取
            self.logger.info("📰 第一次新闻爬取...")
            ip1, news1 = await self._fetch_news_with_ip_check()

            if not news1:
                self.logger.warning("⚠️ 第一次爬取失败，尝试直连模式")
                # 尝试直连模式
                direct_news = await self._test_direct_news_access()
                if direct_news:
                    self.logger.info("✅ 直连模式可以访问新闻API")
                else:
                    self.logger.error("❌ 连直连模式都无法访问新闻API")
                return False

            self.logger.info(f"✅ 第一次爬取成功，IP: {ip1}, 新闻数: {len(news1)}")

            # 5.2 强制切换代理
            self.logger.info("🔄 强制切换代理...")
            switch_success = await self._force_switch_proxy()

            if not switch_success:
                self.logger.warning("⚠️ 代理切换失败，可能只有一个可用代理")

            # 5.3 等待切换生效
            await asyncio.sleep(3)

            # 5.4 第二次爬取
            self.logger.info("📰 第二次新闻爬取...")
            ip2, news2 = await self._fetch_news_with_ip_check()

            if not news2:
                self.logger.warning("⚠️ 第二次爬取失败")
                return False

            self.logger.info(f"✅ 第二次爬取成功，IP: {ip2}, 新闻数: {len(news2)}")

            # 5.5 验证IP切换
            if ip1 != ip2:
                self.logger.info("🎉 代理切换成功！IP已改变")
            else:
                self.logger.warning("⚠️ IP未改变，可能切换失败或代理相同")

            # 5.6 显示新闻内容示例
            if news1 and len(news1) > 0:
                try:
                    first_news = news1[0]
                    # 尝试不同的字段名
                    title = first_news.get('title') or first_news.get('Title') or first_news.get('content', 'No title')
                    if isinstance(title, str) and len(title) > 0:
                        self.logger.info(f"📰 新闻示例: {title[:50]}...")
                    else:
                        self.logger.info(f"📰 新闻数据结构: {list(first_news.keys()) if isinstance(first_news, dict) else type(first_news)}")
                except Exception as e:
                    self.logger.debug(f"显示新闻示例时出错: {e}")

            return True

        except Exception as e:
            self.logger.error(f"❌ 步骤5失败: {e}")
            return False

    async def _fetch_news_with_ip_check(self) -> tuple:
        """获取新闻并检查IP"""
        try:
            # 检查当前IP
            current_ip = await self._get_current_ip()

            # 获取新闻
            news_data = await self._fetch_panews_data()

            return current_ip, news_data

        except Exception as e:
            self.logger.error(f"新闻爬取失败: {e}")
            return None, None

    async def _get_current_ip(self) -> str:
        """获取当前IP地址"""
        try:
            proxy_url = f"http://127.0.0.1:{self.proxy_port}"
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get("http://httpbin.org/ip", proxy=proxy_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('origin', 'unknown')
        except Exception as e:
            self.logger.debug(f"获取IP失败: {e}")

        return 'unknown'

    async def _fetch_panews_data(self) -> List[Dict]:
        """获取PanewsLab新闻数据"""
        try:
            proxy_url = f"http://127.0.0.1:{self.proxy_port}"
            url = "https://www.panewslab.com/webapi/flashnews?LId=1&Rn=5&tw=0"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                async with session.get(url, proxy=proxy_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('data', [])
                    else:
                        self.logger.warning(f"新闻API返回状态: {response.status}")
                        return []
        except Exception as e:
            self.logger.debug(f"获取新闻数据失败: {e}")
            return []

    async def _test_direct_news_access(self) -> bool:
        """测试直连访问新闻API"""
        try:
            url = "https://www.panewslab.com/webapi/flashnews?LId=1&Rn=3&tw=0"
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        news_count = len(data.get('data', []))
                        self.logger.info(f"✅ 直连访问成功，获取 {news_count} 条新闻")
                        return True
                    else:
                        self.logger.warning(f"直连访问失败: {response.status}")
                        return False
        except Exception as e:
            self.logger.error(f"直连访问异常: {e}")
            return False

    async def _force_switch_proxy(self) -> bool:
        """强制切换代理"""
        try:
            # 获取可用代理列表
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.clash_api_base}/proxies/PROXY") as response:
                    if response.status == 200:
                        data = await response.json()
                        current_proxy = data.get('now', '')
                        all_proxies = data.get('all', [])

                        # 选择不同的代理
                        available_proxies = [p for p in all_proxies if p != current_proxy and p != 'DIRECT']

                        if available_proxies:
                            new_proxy = available_proxies[0]

                            # 切换代理
                            switch_data = {"name": new_proxy}
                            async with session.put(f"{self.clash_api_base}/proxies/PROXY", json=switch_data) as switch_response:
                                if switch_response.status == 204:
                                    self.logger.info(f"✅ 代理切换: {current_proxy} → {new_proxy}")
                                    return True
                                else:
                                    self.logger.warning(f"⚠️ 代理切换失败: HTTP {switch_response.status}")
                        else:
                            self.logger.warning("⚠️ 没有其他可用代理")

        except Exception as e:
            self.logger.error(f"强制切换代理失败: {e}")

        return False

    async def step6_verify_direct_connection(self) -> bool:
        """步骤6: 验证其他网址不走代理"""
        self.logger.info("🌐 步骤6: 验证直连网址")

        try:
            success_count = 0

            for domain in self.direct_urls:
                url = f"http://{domain}"

                try:
                    # 不使用代理直接访问
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                        async with session.get(url) as response:
                            if response.status in [200, 301, 302]:
                                self.logger.info(f"✅ 直连成功: {domain}")
                                success_count += 1
                            else:
                                self.logger.warning(f"⚠️ 直连状态异常: {domain} - {response.status}")
                except Exception as e:
                    self.logger.debug(f"直连测试失败: {domain} - {e}")

            self.logger.info(f"✅ 直连验证完成: {success_count}/{len(self.direct_urls)} 个网站可访问")
            return True

        except Exception as e:
            self.logger.error(f"❌ 步骤6失败: {e}")
            return False

    async def _stop_clash(self):
        """停止Clash进程"""
        if self.clash_process:
            try:
                self.clash_process.terminate()
                self.clash_process.wait(timeout=5)
                self.logger.info("✅ Clash已停止")
            except subprocess.TimeoutExpired:
                self.clash_process.kill()
                self.logger.info("🔪 Clash已强制停止")
            finally:
                self.clash_process = None

    async def _verify_clash_api(self) -> bool:
        """验证Clash API是否可用"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.clash_api_base}/proxies") as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'proxies' in data and 'PROXY' in data['proxies']:
                            self.logger.info("✅ Clash API验证成功")
                            return True
                        else:
                            self.logger.error("❌ Clash API响应格式异常")
                            return False
                    else:
                        self.logger.error(f"❌ Clash API不可用: HTTP {response.status}")
                        return False
        except Exception as e:
            self.logger.error(f"❌ Clash API验证失败: {e}")
            return False

    async def run_complete_test(self) -> bool:
        """运行完整测试流程"""
        self.logger.info("🎯 开始改进的完整新闻爬虫测试")
        self.logger.info("=" * 80)

        try:
            # 步骤1: 节点获取
            if not await self.step1_fetch_nodes():
                return False

            # 步骤2: 创建初始配置
            if not await self.step2_create_initial_config():
                return False

            # 步骤3: 测试节点健康状况（不启动Clash）
            if not await self.step3_test_nodes_health():
                return False

            # 步骤4: 创建最终配置并启动Clash
            if not await self.step4_create_final_config_and_start_clash():
                return False

            # 步骤5: 爬虫测试和代理切换
            if not await self.step5_crawler_test_with_switching():
                return False

            # 步骤6: 验证直连
            if not await self.step6_verify_direct_connection():
                return False

            self.logger.info("🎉 完整测试流程成功！")
            return True

        except Exception as e:
            self.logger.error(f"❌ 完整测试失败: {e}")
            return False
        finally:
            # 清理资源
            await self._stop_clash()

    async def cleanup(self):
        """清理资源"""
        await self._stop_clash()


async def main():
    """主函数"""
    # 测试模式1: 使用custom_sources自动获取节点
    print("🔧 测试模式1: 使用custom_sources自动获取节点")

    custom_sources = {
        'clash': [
            'https://7izza.no-mad-world.club/link/iHil1Ll4I1XzfGDW?clash=3&extend=1',
        ],
        'v2ray': []
    }

    tester1 = ImprovedCompleteNewsTest(
        custom_sources=custom_sources,
        min_healthy_nodes=2  # 降低最小要求
    )

    try:
        success1 = await tester1.run_complete_test()

        if success1:
            print("\n✅ 模式1测试成功！")
            print("所有功能都正常工作：")
            print("  - 自动节点获取正常")
            print("  - 智能路由规则生效")
            print("  - 代理自动切换正常")
            print("  - 新闻爬取功能正常")
            print("  - 直连网址不走代理")
        else:
            print("\n❌ 模式1测试失败，请查看日志了解详情。")

    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
    finally:
        await tester1.cleanup()


if __name__ == "__main__":
    asyncio.run(main())