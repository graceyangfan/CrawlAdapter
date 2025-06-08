#!/usr/bin/env python3
"""
Test script for Clash Proxy Client

Simple test script to verify the Clash proxy client functionality.
Run this script to test the basic features of the proxy client.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the parent directory to the path to import the clash module
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from nautilus_trader.adapters.clash import ClashProxyClient


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_basic_functionality():
    """Test basic functionality of the Clash proxy client."""
    print("=" * 60)
    print("Testing Clash Proxy Client Basic Functionality")
    print("=" * 60)
    
    client = ClashProxyClient(config_dir='./test_clash_configs')
    
    try:
        print("\n1. Starting Clash proxy client...")
        success = await client.start(
            config_type='scraping',
            source_types=['all'],
            enable_auto_update=False  # Disable for testing
        )
        
        if not success:
            print("❌ Failed to start Clash proxy client")
            return False
        
        print("✅ Clash proxy client started successfully")
        
        print("\n2. Getting proxy information...")
        info = await client.get_proxy_info()
        
        print(f"   - Running: {info['is_running']}")
        print(f"   - Proxy port: {info['proxy_port']}")
        print(f"   - Total proxies: {info['proxy_stats']['total_proxies']}")
        print(f"   - Healthy proxies: {info['proxy_stats']['healthy_proxies']}")
        print(f"   - Health rate: {info['proxy_stats']['health_rate']:.2%}")
        
        if info['proxy_stats']['total_proxies'] == 0:
            print("❌ No proxies loaded")
            return False
        
        print("✅ Proxy information retrieved successfully")
        
        print("\n3. Testing proxy URL retrieval...")
        proxy_url = await client.get_proxy_url(strategy='health_weighted')
        
        if proxy_url:
            print(f"   - Proxy URL: {proxy_url}")
            print("✅ Proxy URL retrieved successfully")
        else:
            print("❌ Failed to get proxy URL")
            return False
        
        print("\n4. Testing proxy switching...")
        healthy_proxies = client.proxy_manager.get_healthy_proxy_names()
        
        if healthy_proxies:
            test_proxy = healthy_proxies[0]
            success = await client.switch_proxy(test_proxy)
            
            if success:
                print(f"   - Switched to proxy: {test_proxy}")
                print("✅ Proxy switching successful")
            else:
                print("❌ Failed to switch proxy")
                return False
        else:
            print("⚠️  No healthy proxies available for switching test")
        
        print("\n5. Testing individual proxy...")
        if healthy_proxies:
            test_result = await client.test_proxy(healthy_proxies[0])
            
            if test_result['success']:
                print(f"   - Test successful")
                print(f"   - IP: {test_result['ip']}")
                print(f"   - Latency: {test_result['latency']}ms")
                print("✅ Individual proxy test successful")
            else:
                print(f"   - Test failed: {test_result['error']}")
                print("❌ Individual proxy test failed")
        else:
            print("⚠️  No healthy proxies available for individual test")
        
        print("\n6. Testing different load balancing strategies...")
        strategies = ['health_weighted', 'round_robin', 'least_used', 'random']
        
        for strategy in strategies:
            proxy_url = await client.get_proxy_url(strategy=strategy)
            if proxy_url:
                print(f"   - {strategy}: ✅")
            else:
                print(f"   - {strategy}: ❌")
        
        print("✅ Load balancing strategies tested")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        logger.exception("Test failed")
        return False
        
    finally:
        print("\n7. Stopping Clash proxy client...")
        await client.stop()
        print("✅ Clash proxy client stopped")


async def test_node_fetching():
    """Test node fetching functionality."""
    print("\n" + "=" * 60)
    print("Testing Node Fetching Functionality")
    print("=" * 60)
    
    from nautilus_trader.adapters.clash.node_fetcher import NodeFetcher
    
    fetcher = NodeFetcher()
    
    try:
        print("\n1. Testing Clash node fetching...")
        clash_nodes = await fetcher._fetch_clash_nodes()
        print(f"   - Fetched {len(clash_nodes)} Clash nodes")
        
        print("\n2. Testing V2Ray node fetching...")
        v2ray_nodes = await fetcher._fetch_v2ray_nodes()
        print(f"   - Fetched {len(v2ray_nodes)} V2Ray nodes")
        
        print("\n3. Testing combined node fetching...")
        all_nodes = await fetcher.fetch_nodes('all')
        print(f"   - Fetched {len(all_nodes)} total nodes")
        
        print("\n4. Testing node validation...")
        valid_nodes = await fetcher.validate_nodes(all_nodes)
        print(f"   - {len(valid_nodes)} valid nodes out of {len(all_nodes)}")
        
        if len(valid_nodes) > 0:
            print("✅ Node fetching tests passed")
            return True
        else:
            print("❌ No valid nodes found")
            return False
            
    except Exception as e:
        print(f"❌ Node fetching test failed: {e}")
        logger.exception("Node fetching test failed")
        return False


async def test_configuration_management():
    """Test configuration management functionality."""
    print("\n" + "=" * 60)
    print("Testing Configuration Management")
    print("=" * 60)
    
    from nautilus_trader.adapters.clash.config_manager import ConfigurationManager
    from nautilus_trader.adapters.clash.node_fetcher import NodeFetcher
    
    config_manager = ConfigurationManager('./test_configs')
    fetcher = NodeFetcher()
    
    try:
        print("\n1. Fetching test nodes...")
        nodes = await fetcher.fetch_nodes('all')
        valid_nodes = await fetcher.validate_nodes(nodes)
        
        if not valid_nodes:
            print("❌ No valid nodes for configuration test")
            return False
        
        # Limit to first 10 nodes for testing
        test_nodes = valid_nodes[:10]
        print(f"   - Using {len(test_nodes)} nodes for testing")
        
        print("\n2. Testing configuration generation...")
        config_types = ['scraping', 'speed', 'general']
        
        for config_type in config_types:
            config = config_manager.generate_clash_config(test_nodes, config_type)
            
            if config_manager.validate_configuration(config):
                print(f"   - {config_type} configuration: ✅")
            else:
                print(f"   - {config_type} configuration: ❌")
                return False
        
        print("\n3. Testing configuration save/load...")
        test_config = config_manager.generate_clash_config(test_nodes, 'scraping')
        
        # Save configuration
        config_path = config_manager.save_configuration(test_config, 'test_config.yaml')
        print(f"   - Configuration saved to: {config_path}")
        
        # Load configuration
        loaded_config = config_manager.load_configuration('test_config.yaml')
        
        if loaded_config and config_manager.validate_configuration(loaded_config):
            print("   - Configuration loaded and validated: ✅")
        else:
            print("   - Configuration load/validation failed: ❌")
            return False
        
        print("✅ Configuration management tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Configuration management test failed: {e}")
        logger.exception("Configuration management test failed")
        return False


async def main():
    """Run all tests."""
    print("Clash Proxy Client Test Suite")
    print("=" * 60)
    
    test_results = []
    
    # Test node fetching first
    result1 = await test_node_fetching()
    test_results.append(("Node Fetching", result1))
    
    # Test configuration management
    result2 = await test_configuration_management()
    test_results.append(("Configuration Management", result2))
    
    # Test basic functionality (requires working nodes)
    if result1 and result2:
        result3 = await test_basic_functionality()
        test_results.append(("Basic Functionality", result3))
    else:
        print("\n⚠️  Skipping basic functionality test due to previous failures")
        test_results.append(("Basic Functionality", False))
    
    # Print summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    all_passed = True
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:<25}: {status}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All tests passed! Clash proxy client is working correctly.")
    else:
        print("⚠️  Some tests failed. Please check the logs above.")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        logger.exception("Unexpected error in test")
        sys.exit(1)
