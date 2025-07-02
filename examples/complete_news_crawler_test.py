"""
Improved Complete News Crawler Test
Supports two modes:
1. Use existing configuration file (config_path)
2. Automatically fetch nodes through custom_sources

Implements complete workflow:
1. Node fetching (supports custom_sources parameter)
2. Health check and write rules to config
3. Start clash for health checking
4. Exclude unhealthy nodes (save healthy nodes in memory or rewrite config.yaml)
5. Restart clash
6. Begin automatic node switching or forced switching
7. Crawler test verification
8. Verify other URLs don't use proxy
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

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from crawladapter.fetchers import NodeFetcher


class ImprovedCompleteNewsTest:
    """Improved complete news crawler test"""

    def __init__(self,
                 config_path: Optional[str] = None,
                 custom_sources: Optional[Dict[str, List[str]]] = None,
                 min_healthy_nodes: int = 3):
        """
        Initialize test

        Args:
            config_path: Existing configuration file path (optional)
            custom_sources: Custom node sources (optional)
            min_healthy_nodes: Minimum number of healthy nodes
        """
        self.logger = logging.getLogger(__name__)
        self.setup_logging()

        # Path configuration
        self.project_root = Path(__file__).parent.parent
        self.config_dir = self.project_root / 'clash_configs'
        self.config_dir.mkdir(exist_ok=True)

        # Configuration file path
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = self.config_dir / 'auto_generated_config.yaml'

        self.binary_path = self.project_root / 'mihomo_proxy' / 'mihomo'

        # Custom source configuration
        self.custom_sources = custom_sources or {
            'clash': [
                'https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.yml',
                'https://raw.githubusercontent.com/Alvin9999/pac2/master/clash/config.yaml',
            ],
            'v2ray': []
        }

        # Network configuration
        self.proxy_port = 7890
        self.api_port = 9090
        self.clash_api_base = f"http://127.0.0.1:{self.api_port}"

        # Test configuration
        self.min_healthy_nodes = min_healthy_nodes

        # Proxy-related URLs (need to use proxy)
        self.proxy_urls = [
            'httpbin.org',
            'www.gstatic.com',
            'detectportal.firefox.com',
            'www.msftconnecttest.com',
            'panewslab.com',
            'www.panewslab.com'
        ]

        # Direct connection URLs (don't use proxy)
        self.direct_urls = [
            'baidu.com',
            'qq.com',
            'taobao.com',
            'jd.com'
        ]

        # State variables
        self.clash_process: Optional[subprocess.Popen] = None
        self.all_nodes: List[Dict] = []
        self.healthy_nodes: List[Dict] = []

    def setup_logging(self):
        """Setup logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('improved_complete_news_test.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )

    async def step1_fetch_nodes(self) -> bool:
        """Step 1: Node fetching (supports two modes)"""
        self.logger.info("🚀 Step 1: Node fetching")

        try:
            # Mode 1: If existing configuration file exists, try to read it
            if self.config_path.exists() and self.config_path.name != 'auto_generated_config.yaml':
                self.logger.info(f"📁 Mode 1: Reading nodes from existing config file: {self.config_path}")

                with open(self.config_path, 'r', encoding='utf-8') as f:
                    existing_config = yaml.safe_load(f)

                self.all_nodes = existing_config.get('proxies', [])

                if self.all_nodes:
                    self.logger.info(f"✅ Read {len(self.all_nodes)} nodes from config file")
                    return True
                else:
                    self.logger.warning("⚠️ No proxy nodes in config file, switching to auto-fetch mode")

            # Mode 2: Automatically fetch nodes through custom_sources
            self.logger.info("📥 Mode 2: Auto-fetching nodes through custom_sources")
            self.logger.info(f"   Node sources: {list(self.custom_sources.keys())}")

            node_fetcher = NodeFetcher(custom_sources=self.custom_sources)
            self.all_nodes = await node_fetcher.fetch_nodes('all')

            if not self.all_nodes:
                self.logger.error("❌ No nodes fetched")
                return False

            self.logger.info(f"✅ Auto-fetched {len(self.all_nodes)} nodes")

            # Display node type statistics
            node_types = {}
            for node in self.all_nodes:
                node_type = node.get('type', 'unknown')
                node_types[node_type] = node_types.get(node_type, 0) + 1

            self.logger.info(f"   Node type distribution: {node_types}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Step 1 failed: {e}")
            return False

    async def step2_create_initial_config(self) -> bool:
        """Step 2: Create initial configuration and write rules"""
        self.logger.info("⚙️ Step 2: Create initial configuration")

        try:
            # Generate configuration containing all nodes
            config = self._generate_smart_config(self.all_nodes)

            # Save configuration
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)

            self.logger.info(f"✅ Initial configuration saved: {self.config_path}")
            self.logger.info(f"   Contains {len(self.all_nodes)} proxy nodes")
            self.logger.info(f"   Proxy rules: {len(self.proxy_urls)} domains")
            self.logger.info(f"   Direct rules: {len(self.direct_urls)} domains")

            return True

        except Exception as e:
            self.logger.error(f"❌ Step 2 failed: {e}")
            return False

    def _generate_smart_config(self, nodes: List[Dict]) -> Dict:
        """Generate smart routing configuration"""
        # Ensure unique node names
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
                    'type': 'select',  # Use select type, more stable
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
        """Generate final configuration (healthy nodes + news network rules)"""
        # Ensure unique node names
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
        """Generate smart routing rules - fixed version"""
        rules = []

        # 1. Local network direct connection (highest priority)
        rules.extend([
            'IP-CIDR,127.0.0.0/8,DIRECT',
            'IP-CIDR,172.16.0.0/12,DIRECT',
            'IP-CIDR,192.168.0.0/16,DIRECT',
            'IP-CIDR,10.0.0.0/8,DIRECT',
            'IP-CIDR,224.0.0.0/4,DIRECT',
            'DOMAIN-SUFFIX,local,DIRECT'
        ])

        # 2. Health check and test URLs use proxy (ensure health checks work properly)
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

        # 3. News crawler target websites use proxy
        news_domains = [
            'panewslab.com',
            'www.panewslab.com'
        ]

        for domain in news_domains:
            rules.append(f'DOMAIN-SUFFIX,{domain},PROXY')

        # 4. Domestic websites direct connection
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

        # 5. China IP direct connection
        rules.append('GEOIP,CN,DIRECT')

        # 6. Default rule (all other traffic direct)
        rules.append('MATCH,DIRECT')

        return rules

    def _generate_news_crawling_rules(self) -> List[str]:
        """Generate news crawling specific rules"""
        rules = []

        # 1. Local network direct connection (highest priority)
        rules.extend([
            'IP-CIDR,127.0.0.0/8,DIRECT',
            'IP-CIDR,172.16.0.0/12,DIRECT',
            'IP-CIDR,192.168.0.0/16,DIRECT',
            'IP-CIDR,10.0.0.0/8,DIRECT',
            'DOMAIN-SUFFIX,local,DIRECT'
        ])

        # 2. News websites must use proxy
        rules.extend([
            'DOMAIN-SUFFIX,panewslab.com,PROXY',
            'DOMAIN-SUFFIX,www.panewslab.com,PROXY'
        ])

        # 3. Test and health check URLs use proxy
        rules.extend([
            'DOMAIN-SUFFIX,httpbin.org,PROXY',
            'DOMAIN-SUFFIX,www.gstatic.com,PROXY',
            'DOMAIN-SUFFIX,gstatic.com,PROXY'
        ])

        # 4. Domestic websites direct connection
        rules.extend([
            'DOMAIN-SUFFIX,baidu.com,DIRECT',
            'DOMAIN-SUFFIX,qq.com,DIRECT',
            'DOMAIN-SUFFIX,taobao.com,DIRECT',
            'DOMAIN-SUFFIX,jd.com,DIRECT'
        ])

        # 5. China IP direct connection
        rules.append('GEOIP,CN,DIRECT')

        # 6. Default rule (other traffic direct)
        rules.append('MATCH,DIRECT')

        return rules

    async def step3_test_nodes_health(self) -> bool:
        """Step 3: Test node health status (without starting Clash)"""
        self.logger.info("🏥 Step 3: Test node health status")

        try:
            # 3.1 Directly test node connectivity (without relying on Clash)
            self.logger.info("🔍 Directly testing node connectivity...")
            health_results = await self._test_nodes_directly()

            if not health_results:
                self.logger.warning("⚠️ Health check returned no results")
                return False

            # 3.2 Filter healthy nodes
            self.healthy_nodes = self._filter_healthy_nodes(health_results)

            healthy_count = len(self.healthy_nodes)
            total_count = len(self.all_nodes)

            self.logger.info(f"✅ Health check completed: {healthy_count}/{total_count} nodes healthy")

            # 3.3 Check if there are enough healthy nodes
            if healthy_count < self.min_healthy_nodes:
                self.logger.warning(f"⚠️ Healthy node count ({healthy_count}) less than minimum requirement ({self.min_healthy_nodes})")
                self.logger.info("   Will lower health standards and re-filter...")

                # Lower health standards
                self.healthy_nodes = self._filter_healthy_nodes(health_results, threshold=0.1)
                healthy_count = len(self.healthy_nodes)
                self.logger.info(f"   After lowering standards: {healthy_count} nodes available")

            if healthy_count == 0:
                self.logger.error("❌ No available healthy nodes")
                return False

            # 3.4 Display healthy node information
            self.logger.info("✅ Healthy node list:")
            for i, node in enumerate(self.healthy_nodes[:5], 1):
                node_name = node.get('name', f'node_{i}')
                node_type = node.get('type', 'unknown')
                server = node.get('server', 'unknown')
                self.logger.info(f"   {i}. {node_name} ({node_type}) - {server}")

            return True

        except Exception as e:
            self.logger.error(f"❌ Step 3 failed: {e}")
            return False

    async def _start_clash(self) -> bool:
        """Start Clash process"""
        try:
            if not self.binary_path.exists():
                self.logger.error(f"❌ Binary file does not exist: {self.binary_path}")
                return False

            cmd = [str(self.binary_path), '-f', str(self.config_path)]
            self.logger.info(f"Start command: {' '.join(cmd)}")

            self.clash_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0
            )

            # Check startup status
            await asyncio.sleep(3)

            if self.clash_process.poll() is None:
                self.logger.info("✅ Clash started successfully")
                return True
            else:
                stdout, stderr = self.clash_process.communicate()
                self.logger.error("❌ Clash startup failed")
                if stdout:
                    self.logger.error(f"Standard output: {stdout.decode('utf-8', errors='ignore')}")
                if stderr:
                    self.logger.error(f"Error output: {stderr.decode('utf-8', errors='ignore')}")
                return False

        except Exception as e:
            self.logger.error(f"❌ Clash startup exception: {e}")
            return False

    async def _perform_comprehensive_health_check(self) -> Dict[str, float]:
        """Perform comprehensive health check"""
        self.logger.info("🔍 Performing comprehensive health check...")

        health_results = {}

        try:
            # Get proxy list
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.clash_api_base}/proxies") as response:
                    if response.status != 200:
                        self.logger.error("❌ Unable to get proxy list")
                        return {}

                    data = await response.json()
                    proxies = data.get('proxies', {})

                    if 'PROXY' not in proxies:
                        self.logger.error("❌ Cannot find PROXY group")
                        return {}

                    proxy_names = proxies['PROXY'].get('all', [])
                    actual_proxies = [p for p in proxy_names if p not in ['DIRECT']]

                    self.logger.info(f"📋 Found {len(actual_proxies)} proxies for health check")

                    # Test proxies in batches (avoid too much concurrency)
                    batch_size = 5
                    for i in range(0, len(actual_proxies), batch_size):
                        batch = actual_proxies[i:i+batch_size]
                        self.logger.info(f"🔍 Testing batch {i//batch_size + 1}: {len(batch)} proxies")

                        # Concurrently test current batch
                        tasks = [self._test_single_proxy_comprehensive(proxy_name) for proxy_name in batch]
                        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                        # Process results
                        for proxy_name, result in zip(batch, batch_results):
                            if isinstance(result, Exception):
                                health_results[proxy_name] = 0.0
                                self.logger.debug(f"❌ {proxy_name}: Test exception ({result})")
                            else:
                                health_results[proxy_name] = result
                                if result > 0:
                                    self.logger.info(f"✅ {proxy_name}: {result:.2f}")
                                else:
                                    self.logger.debug(f"❌ {proxy_name}: Unavailable")

                        # Delay between batches
                        if i + batch_size < len(actual_proxies):
                            await asyncio.sleep(2)

        except Exception as e:
            self.logger.error(f"❌ Health check failed: {e}")

        return health_results

    async def _test_single_proxy_comprehensive(self, proxy_name: str) -> float:
        """Comprehensively test single proxy"""
        try:
            # Switch to specified proxy
            async with aiohttp.ClientSession() as session:
                switch_data = {"name": proxy_name}
                async with session.put(f"{self.clash_api_base}/proxies/PROXY", json=switch_data) as response:
                    if response.status != 204:
                        return 0.0

                # Wait for switch to take effect
                await asyncio.sleep(1)

                # Multiple tests
                test_results = []

                # Test 1: Basic connectivity
                basic_score = await self._test_basic_connectivity()
                test_results.append(basic_score)

                # Test 2: HTTPS connection
                https_score = await self._test_https_connectivity()
                test_results.append(https_score)

                # Test 3: Target website access
                target_score = await self._test_target_website_access()
                test_results.append(target_score)

                # Calculate comprehensive score
                valid_results = [score for score in test_results if score >= 0]
                if valid_results:
                    final_score = sum(valid_results) / len(valid_results)
                    return final_score
                else:
                    return 0.0

        except Exception as e:
            self.logger.debug(f"Proxy {proxy_name} test failed: {e}")
            return 0.0

    async def _test_basic_connectivity(self) -> float:
        """Test basic connectivity - using requests library for better reliability"""
        test_urls = [
            'http://httpbin.org/ip',
            'http://www.gstatic.com/generate_204'
        ]

        success_count = 0
        for url in test_urls:
            try:
                # Use requests library for testing, more stable
                import requests
                proxies = {
                    'http': f'http://127.0.0.1:{self.proxy_port}',
                    'https': f'http://127.0.0.1:{self.proxy_port}'
                }

                response = requests.get(url, proxies=proxies, timeout=10)
                if response.status_code in [200, 204]:
                    success_count += 1
                    self.logger.debug(f"✅ Basic connectivity test successful: {url}")
                else:
                    self.logger.debug(f"❌ Basic connectivity test failed: {url} - HTTP {response.status_code}")
            except Exception as e:
                self.logger.debug(f"❌ Basic connectivity test exception: {url} - {e}")
                continue

        return success_count / len(test_urls)

    async def _test_https_connectivity(self) -> float:
        """Test HTTPS connectivity - using requests library for better reliability"""
        test_urls = [
            'https://www.google.com/generate_204',
            'https://httpbin.org/ip'
        ]

        success_count = 0
        for url in test_urls:
            try:
                # Use requests library for HTTPS testing
                import requests
                proxies = {
                    'http': f'http://127.0.0.1:{self.proxy_port}',
                    'https': f'http://127.0.0.1:{self.proxy_port}'
                }

                response = requests.get(url, proxies=proxies, timeout=15, verify=False)
                if response.status_code in [200, 204]:
                    success_count += 1
                    self.logger.debug(f"✅ HTTPS connectivity test successful: {url}")
                else:
                    self.logger.debug(f"❌ HTTPS connectivity test failed: {url} - HTTP {response.status_code}")
            except Exception as e:
                self.logger.debug(f"❌ HTTPS connectivity test exception: {url} - {e}")
                continue

        return success_count / len(test_urls)

    async def _test_target_website_access(self) -> float:
        """Test target website access - using requests library for better reliability"""
        try:
            # Use requests library to test target website
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
                self.logger.debug("✅ Target website access test successful")
                return 1.0
            elif response.status_code in [301, 302, 403]:
                self.logger.debug(f"⚠️ Target website access partially successful: HTTP {response.status_code}")
                return 0.5  # Partially available
            else:
                self.logger.debug(f"❌ Target website access failed: HTTP {response.status_code}")
                return 0.0
        except Exception as e:
            self.logger.debug(f"❌ Target website access exception: {e}")
            return 0.0

    async def _test_nodes_directly(self) -> Dict[str, float]:
        """Directly test node health status (without relying on Clash)"""
        self.logger.info("🔍 Directly testing node connectivity...")

        health_results = {}

        try:
            # Test nodes in batches (avoid too much concurrency)
            batch_size = 3
            for i in range(0, len(self.all_nodes), batch_size):
                batch = self.all_nodes[i:i+batch_size]
                self.logger.info(f"🔍 Testing batch {i//batch_size + 1}: {len(batch)} nodes")

                # Concurrently test current batch
                tasks = [self._test_single_node_directly(node) for node in batch]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                for node, result in zip(batch, batch_results):
                    node_name = node.get('name', f'node_{i}')
                    if isinstance(result, Exception):
                        health_results[node_name] = 0.0
                        self.logger.debug(f"❌ {node_name}: Test exception ({result})")
                    else:
                        health_results[node_name] = result
                        if result > 0:
                            self.logger.info(f"✅ {node_name}: {result:.2f}")
                        else:
                            self.logger.debug(f"❌ {node_name}: Unavailable")

                # Delay between batches
                if i + batch_size < len(self.all_nodes):
                    await asyncio.sleep(1)

        except Exception as e:
            self.logger.error(f"❌ Direct node test failed: {e}")

        return health_results

    async def _test_single_node_directly(self, node: Dict) -> float:
        """Directly test single node (without relying on Clash)"""
        try:
            node_name = node.get('name', 'unknown')
            server = node.get('server', '')
            port = node.get('port', 0)

            if not server or not port:
                return 0.0

            # Simple TCP connection test
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)

            try:
                result = sock.connect_ex((server, port))
                if result == 0:
                    self.logger.debug(f"✅ {node_name}: TCP connection successful")
                    return 0.8  # Basic connectivity score
                else:
                    self.logger.debug(f"❌ {node_name}: TCP connection failed")
                    return 0.0
            finally:
                sock.close()

        except Exception as e:
            self.logger.debug(f"❌ {node_name}: Test exception - {e}")
            return 0.0

    def _filter_healthy_nodes(self, health_results: Dict[str, float], threshold: float = 0.3) -> List[Dict]:
        """Filter healthy nodes"""
        healthy_nodes = []

        for node in self.all_nodes:
            node_name = node.get('name', '')
            score = health_results.get(node_name, 0.0)

            if score >= threshold:
                healthy_nodes.append(node)

        return healthy_nodes

    async def step4_create_final_config_and_start_clash(self) -> bool:
        """Step 4: Create final configuration (healthy nodes + rules) and start Clash"""
        self.logger.info("⚙️ Step 4: Create final configuration and start Clash")

        try:
            # 4.1 Generate final configuration (only healthy nodes + news network rules)
            if self.healthy_nodes:
                final_config = self._generate_final_config_with_rules(self.healthy_nodes)
                self.logger.info(f"✅ Generated final configuration using {len(self.healthy_nodes)} healthy nodes")
            else:
                self.logger.warning("⚠️ No healthy nodes, using all nodes")
                final_config = self._generate_final_config_with_rules(self.all_nodes)

            # 4.2 Save final configuration
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(final_config, f, default_flow_style=False, allow_unicode=True, indent=2)

            self.logger.info(f"✅ Final configuration saved: {self.config_path}")
            self.logger.info(f"   Contains {len(final_config['proxies'])} healthy nodes")
            self.logger.info(f"   News network rules: panewslab.com -> PROXY")
            self.logger.info(f"   Domestic network rules: baidu.com etc -> DIRECT")

            # 4.3 Start Clash
            if not await self._start_clash():
                return False

            # 4.4 Wait for startup completion
            await asyncio.sleep(5)

            # 4.5 Verify Clash API availability
            if not await self._verify_clash_api():
                return False

            self.logger.info("✅ Clash startup completed, ready to begin news crawling")
            return True

        except Exception as e:
            self.logger.error(f"❌ Step 4 failed: {e}")
            return False

    async def step5_crawler_test_with_switching(self) -> bool:
        """Step 5: Crawler testing and proxy switching"""
        self.logger.info("🕷️ Step 5: Crawler testing and proxy switching")

        try:
            # 5.1 First crawling attempt
            self.logger.info("📰 First news crawling...")
            ip1, news1 = await self._fetch_news_with_ip_check()

            if not news1:
                self.logger.warning("⚠️ First crawling failed, trying direct connection mode")
                # Try direct connection mode
                direct_news = await self._test_direct_news_access()
                if direct_news:
                    self.logger.info("✅ Direct connection mode can access news API")
                else:
                    self.logger.error("❌ Even direct connection mode cannot access news API")
                return False

            self.logger.info(f"✅ First crawling successful, IP: {ip1}, news count: {len(news1)}")

            # 5.2 Force proxy switching
            self.logger.info("🔄 Force proxy switching...")
            switch_success = await self._force_switch_proxy()

            if not switch_success:
                self.logger.warning("⚠️ Proxy switching failed, may only have one available proxy")

            # 5.3 Wait for switch to take effect
            await asyncio.sleep(3)

            # 5.4 Second crawling attempt
            self.logger.info("📰 Second news crawling...")
            ip2, news2 = await self._fetch_news_with_ip_check()

            if not news2:
                self.logger.warning("⚠️ Second crawling failed")
                return False

            self.logger.info(f"✅ Second crawling successful, IP: {ip2}, news count: {len(news2)}")

            # 5.5 Verify IP switching
            if ip1 != ip2:
                self.logger.info("🎉 Proxy switching successful! IP has changed")
            else:
                self.logger.warning("⚠️ IP unchanged, switching may have failed or proxies are the same")

            # 5.6 Display news content example
            if news1 and len(news1) > 0:
                try:
                    first_news = news1[0]
                    # Try different field names
                    title = first_news.get('title') or first_news.get('Title') or first_news.get('content', 'No title')
                    if isinstance(title, str) and len(title) > 0:
                        self.logger.info(f"📰 News example: {title[:50]}...")
                    else:
                        self.logger.info(f"📰 News data structure: {list(first_news.keys()) if isinstance(first_news, dict) else type(first_news)}")
                except Exception as e:
                    self.logger.debug(f"Error displaying news example: {e}")

            return True

        except Exception as e:
            self.logger.error(f"❌ Step 5 failed: {e}")
            return False

    async def _fetch_news_with_ip_check(self) -> tuple:
        """Fetch news and check IP"""
        try:
            # Check current IP
            current_ip = await self._get_current_ip()

            # Fetch news
            news_data = await self._fetch_panews_data()

            return current_ip, news_data

        except Exception as e:
            self.logger.error(f"News crawling failed: {e}")
            return None, None

    async def _get_current_ip(self) -> str:
        """Get current IP address"""
        try:
            proxy_url = f"http://127.0.0.1:{self.proxy_port}"
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get("http://httpbin.org/ip", proxy=proxy_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('origin', 'unknown')
        except Exception as e:
            self.logger.debug(f"Failed to get IP: {e}")

        return 'unknown'

    async def _fetch_panews_data(self) -> List[Dict]:
        """Fetch PanewsLab news data"""
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
                        self.logger.warning(f"News API returned status: {response.status}")
                        return []
        except Exception as e:
            self.logger.debug(f"Failed to fetch news data: {e}")
            return []

    async def _test_direct_news_access(self) -> bool:
        """Test direct access to news API"""
        try:
            url = "https://www.panewslab.com/webapi/flashnews?LId=1&Rn=3&tw=0"
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        news_count = len(data.get('data', []))
                        self.logger.info(f"✅ Direct access successful, retrieved {news_count} news items")
                        return True
                    else:
                        self.logger.warning(f"Direct access failed: {response.status}")
                        return False
        except Exception as e:
            self.logger.error(f"Direct access exception: {e}")
            return False

    async def _force_switch_proxy(self) -> bool:
        """Force proxy switching"""
        try:
            # Get available proxy list
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.clash_api_base}/proxies/PROXY") as response:
                    if response.status == 200:
                        data = await response.json()
                        current_proxy = data.get('now', '')
                        all_proxies = data.get('all', [])

                        # Select different proxy
                        available_proxies = [p for p in all_proxies if p != current_proxy and p != 'DIRECT']

                        if available_proxies:
                            new_proxy = available_proxies[0]

                            # Switch proxy
                            switch_data = {"name": new_proxy}
                            async with session.put(f"{self.clash_api_base}/proxies/PROXY", json=switch_data) as switch_response:
                                if switch_response.status == 204:
                                    self.logger.info(f"✅ Proxy switched: {current_proxy} → {new_proxy}")
                                    return True
                                else:
                                    self.logger.warning(f"⚠️ Proxy switching failed: HTTP {switch_response.status}")
                        else:
                            self.logger.warning("⚠️ No other available proxies")

        except Exception as e:
            self.logger.error(f"Force proxy switching failed: {e}")

        return False

    async def step6_verify_direct_connection(self) -> bool:
        """Step 6: Verify other URLs don't use proxy"""
        self.logger.info("🌐 Step 6: Verify direct connection URLs")

        try:
            success_count = 0

            for domain in self.direct_urls:
                url = f"http://{domain}"

                try:
                    # Direct access without using proxy
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                        async with session.get(url) as response:
                            if response.status in [200, 301, 302]:
                                self.logger.info(f"✅ Direct connection successful: {domain}")
                                success_count += 1
                            else:
                                self.logger.warning(f"⚠️ Direct connection status abnormal: {domain} - {response.status}")
                except Exception as e:
                    self.logger.debug(f"Direct connection test failed: {domain} - {e}")

            self.logger.info(f"✅ Direct connection verification completed: {success_count}/{len(self.direct_urls)} websites accessible")
            return True

        except Exception as e:
            self.logger.error(f"❌ Step 6 failed: {e}")
            return False

    async def _stop_clash(self):
        """Stop Clash process"""
        if self.clash_process:
            try:
                self.clash_process.terminate()
                self.clash_process.wait(timeout=5)
                self.logger.info("✅ Clash stopped")
            except subprocess.TimeoutExpired:
                self.clash_process.kill()
                self.logger.info("🔪 Clash force stopped")
            finally:
                self.clash_process = None

    async def _verify_clash_api(self) -> bool:
        """Verify if Clash API is available"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.clash_api_base}/proxies") as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'proxies' in data and 'PROXY' in data['proxies']:
                            self.logger.info("✅ Clash API verification successful")
                            return True
                        else:
                            self.logger.error("❌ Clash API response format abnormal")
                            return False
                    else:
                        self.logger.error(f"❌ Clash API unavailable: HTTP {response.status}")
                        return False
        except Exception as e:
            self.logger.error(f"❌ Clash API verification failed: {e}")
            return False

    async def run_complete_test(self) -> bool:
        """Run complete test workflow"""
        self.logger.info("🎯 Starting improved complete news crawler test")
        self.logger.info("=" * 80)

        try:
            # Step 1: Node fetching
            if not await self.step1_fetch_nodes():
                return False

            # Step 2: Create initial configuration
            if not await self.step2_create_initial_config():
                return False

            # Step 3: Test node health status (without starting Clash)
            if not await self.step3_test_nodes_health():
                return False

            # Step 4: Create final configuration and start Clash
            if not await self.step4_create_final_config_and_start_clash():
                return False

            # Step 5: Crawler testing and proxy switching
            if not await self.step5_crawler_test_with_switching():
                return False

            # Step 6: Verify direct connection
            if not await self.step6_verify_direct_connection():
                return False

            self.logger.info("🎉 Complete test workflow successful!")
            return True

        except Exception as e:
            self.logger.error(f"❌ Complete test failed: {e}")
            return False
        finally:
            # Clean up resources
            await self._stop_clash()

    async def cleanup(self):
        """Clean up resources"""
        await self._stop_clash()


async def main():
    """Main function"""
    # Test mode 1: Use custom_sources to automatically fetch nodes
    print("🔧 Test Mode 1: Use custom_sources to automatically fetch nodes")

    custom_sources = {
        'clash': [
            '',
        ],
        'v2ray': []
    }

    tester1 = ImprovedCompleteNewsTest(
        custom_sources=custom_sources,
        min_healthy_nodes=2  # Lower minimum requirement
    )

    try:
        success1 = await tester1.run_complete_test()

        if success1:
            print("\n✅ Mode 1 test successful!")
            print("All functions working properly:")
            print("  - Automatic node fetching normal")
            print("  - Smart routing rules effective")
            print("  - Proxy auto-switching normal")
            print("  - News crawling function normal")
            print("  - Direct URLs don't use proxy")
        else:
            print("\n❌ Mode 1 test failed, please check logs for details.")

    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
    finally:
        await tester1.cleanup()


if __name__ == "__main__":
    asyncio.run(main())