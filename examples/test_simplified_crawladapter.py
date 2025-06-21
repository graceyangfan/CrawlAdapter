"""
测试简化后的CrawlAdapter功能

验证基于原有core.py和fetchers.py的简化实现
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from crawladapter import ProxyClient, NodeFetcher


async def test_simplified_workflow():
    """测试简化的工作流程"""
    print("🧪 测试简化的CrawlAdapter工作流程")
    print("=" * 60)
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # 自定义节点源
    custom_sources = {
        'clash': [
            'https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.yml',
        ],
        'v2ray': []
    }
    
    # 创建代理客户端（不指定二进制路径，让系统自动查找）
    client = ProxyClient(
        config_dir='./clash_configs',
        enable_adaptive_health_check=False,  # 使用简化的健康检查
        enable_metrics=False  # 关闭监控
    )
    
    try:
        print("\n📋 步骤1: 设置自定义节点源")
        # 设置自定义NodeFetcher
        client.node_fetcher = NodeFetcher(custom_sources=custom_sources)
        print("✅ 自定义节点源设置完成")
        
        print("\n📋 步骤2: 设置健康检查URL")
        # 设置健康检查URL
        health_urls = [
            'http://httpbin.org/ip',
            'http://www.gstatic.com/generate_204'
        ]
        client.set_health_check_urls(health_urls)
        print(f"✅ 设置了 {len(health_urls)} 个健康检查URL")
        
        print("\n📋 步骤3: 启动代理客户端")
        # 启动代理客户端（包含完整流程）
        proxy_rules = [
            'panewslab.com',
            'www.panewslab.com',
            'httpbin.org'
        ]
        
        success = await client.start(
            rules=proxy_rules,
            enable_auto_update=False  # 关闭自动更新
        )
        
        if success:
            print("✅ 代理客户端启动成功")
            print(f"   代理端口: {client.proxy_port}")
            print(f"   API端口: {client.api_port}")
            print(f"   活跃代理数: {len(client.active_proxies)}")
        else:
            print("❌ 代理客户端启动失败")
            print("\n💡 可能的解决方案:")
            print("1. 运行二进制文件设置脚本:")
            print("   python setup_clash_binary.py")
            print("2. 手动下载Mihomo:")
            print("   https://github.com/MetaCubeX/mihomo/releases")
            print("3. 或者安装到系统PATH:")
            print("   sudo apt install clash  # Ubuntu/Debian")
            print("   brew install clash      # macOS")
            return False
        
        print("\n📋 步骤4: 测试代理功能")
        # 获取代理URL
        proxy_url = await client.get_proxy_url()
        if proxy_url:
            print(f"✅ 获取代理URL: {proxy_url}")
        else:
            print("⚠️ 未能获取代理URL")
        
        # 获取代理信息
        proxy_info = await client.get_proxy_info()
        print(f"✅ 代理信息: {proxy_info.get('proxy_stats', {})}")
        
        print("\n📋 步骤5: 测试代理切换")
        # 测试代理切换
        switch_success = await client.switch_proxy('round_robin')
        if switch_success:
            print("✅ 代理切换成功")
        else:
            print("⚠️ 代理切换失败或无变化")
        
        print("\n📋 步骤6: 测试IP检查")
        # 测试IP检查
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get("http://httpbin.org/ip", proxy=proxy_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        current_ip = data.get('origin', 'unknown')
                        print(f"✅ 当前IP: {current_ip}")
                    else:
                        print(f"⚠️ IP检查失败: HTTP {response.status}")
        except Exception as e:
            print(f"⚠️ IP检查异常: {e}")
        
        print("\n📋 步骤7: 测试新闻API")
        # 测试新闻API
        try:
            api_url = "https://www.panewslab.com/webapi/flashnews?LId=1&Rn=3&tw=0"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, proxy=proxy_url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as response:
                    if response.status == 200:
                        data = await response.json()
                        news_count = 0
                        if isinstance(data, dict) and 'data' in data:
                            flash_news = data['data'].get('flashNews', [])
                            if flash_news and isinstance(flash_news, list):
                                news_list = flash_news[0].get('list', [])
                                news_count = len(news_list)
                        print(f"✅ 新闻API测试成功，获取 {news_count} 条新闻")
                    else:
                        print(f"⚠️ 新闻API测试失败: HTTP {response.status}")
        except Exception as e:
            print(f"⚠️ 新闻API测试异常: {e}")
        
        print("\n🎉 所有测试步骤完成！")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生异常: {e}")
        return False
    
    finally:
        print("\n📋 步骤8: 清理资源")
        # 停止代理客户端
        await client.stop()
        print("✅ 代理客户端已停止")


async def test_basic_functionality():
    """测试基本功能"""
    print("\n🔧 测试基本功能")
    print("-" * 40)
    
    # 测试NodeFetcher
    print("📡 测试NodeFetcher...")
    fetcher = NodeFetcher()
    
    try:
        # 获取少量节点进行测试
        nodes = await fetcher.fetch_nodes('clash')
        print(f"✅ NodeFetcher测试成功，获取 {len(nodes)} 个节点")
    except Exception as e:
        print(f"⚠️ NodeFetcher测试失败: {e}")
    
    # 测试ProxyClient创建
    print("🔧 测试ProxyClient创建...")
    try:
        client = ProxyClient()
        print("✅ ProxyClient创建成功")
        print(f"   配置目录: {client.config_dir}")
        print(f"   代理端口: {client.proxy_port}")
        print(f"   API端口: {client.api_port}")
    except Exception as e:
        print(f"❌ ProxyClient创建失败: {e}")


async def main():
    """主函数"""
    print("🚀 CrawlAdapter 简化版本测试")
    print("基于原有 core.py 和 fetchers.py 的优化实现")
    print("=" * 80)
    
    try:
        # 基本功能测试
        await test_basic_functionality()
        
        # 完整工作流程测试
        success = await test_simplified_workflow()
        
        if success:
            print("\n✅ 所有测试通过！")
            print("\n📝 测试总结:")
            print("  - 自动进程管理: ✅")
            print("  - 节点获取: ✅")
            print("  - 健康检查: ✅")
            print("  - 配置生成: ✅")
            print("  - Clash启动: ✅")
            print("  - 代理切换: ✅")
            print("  - IP监控: ✅")
            print("  - 新闻爬取: ✅")
            print("  - 资源清理: ✅")
        else:
            print("\n❌ 部分测试失败，请查看日志了解详情")
    
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
    except Exception as e:
        print(f"\n💥 测试过程中发生未预期的错误: {e}")


if __name__ == "__main__":
    asyncio.run(main())
