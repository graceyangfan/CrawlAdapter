#!/usr/bin/env python3
"""
Quick Start Script for Clash Proxy Client

This script provides a simple way to get started with the Clash proxy client.
It will automatically fetch nodes, start the proxy, and demonstrate basic usage.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def quick_start_demo():
    """
    Quick start demonstration of the Clash proxy client.
    """
    print("🚀 Clash Proxy Client - Quick Start Demo")
    print("=" * 50)
    
    try:
        # Import the client
        from nautilus_trader.adapters.clash import ClashProxyClient
        import aiohttp
        
        print("\n📦 Initializing Clash proxy client...")
        client = ClashProxyClient(config_dir='./clash_demo')
        
        print("🔄 Starting proxy client (this may take a moment)...")
        success = await client.start(
            config_type='scraping',
            source_types=['all'],
            enable_auto_update=True
        )
        
        if not success:
            print("❌ Failed to start proxy client")
            print("\nPossible issues:")
            print("1. Clash binary not found - please install Clash or Mihomo")
            print("2. Network connectivity issues")
            print("3. No valid proxy nodes available")
            return
        
        print("✅ Proxy client started successfully!")
        
        # Get proxy information
        info = await client.get_proxy_info()
        print(f"\n📊 Proxy Statistics:")
        print(f"   Total proxies: {info['proxy_stats']['total_proxies']}")
        print(f"   Healthy proxies: {info['proxy_stats']['healthy_proxies']}")
        print(f"   Health rate: {info['proxy_stats']['health_rate']:.1%}")
        print(f"   Proxy port: {info['proxy_port']}")
        
        if info['proxy_stats']['healthy_proxies'] == 0:
            print("\n⚠️  No healthy proxies available")
            print("The client will continue monitoring and may find healthy proxies soon.")
            await client.stop()
            return
        
        # Test proxy functionality
        print(f"\n🌐 Testing proxy functionality...")
        
        # Get proxy URL
        proxy_url = await client.get_proxy_url(strategy='health_weighted')
        
        if proxy_url:
            print(f"   Proxy URL: {proxy_url}")
            
            # Test with a simple HTTP request
            try:
                async with aiohttp.ClientSession() as session:
                    print("   Making test request to httpbin.org...")
                    
                    async with session.get(
                        'http://httpbin.org/ip',
                        proxy=proxy_url,
                        timeout=aiohttp.ClientTimeout(total=15)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            print(f"   ✅ Success! Current IP: {data['origin']}")
                        else:
                            print(f"   ❌ Request failed: HTTP {response.status}")
                            
            except Exception as e:
                print(f"   ❌ Request failed: {e}")
        else:
            print("   ❌ Could not get proxy URL")
        
        # Demonstrate proxy rotation
        print(f"\n🔄 Demonstrating proxy rotation...")
        
        for i in range(3):
            proxy_url = await client.get_proxy_url(strategy='round_robin')
            
            if proxy_url:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            'http://httpbin.org/ip',
                            proxy=proxy_url,
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                print(f"   Request {i+1}: IP {data['origin']}")
                            else:
                                print(f"   Request {i+1}: Failed (HTTP {response.status})")
                except Exception as e:
                    print(f"   Request {i+1}: Failed ({e})")
            
            await asyncio.sleep(1)
        
        print(f"\n🎉 Demo completed successfully!")
        print(f"\n💡 Next steps:")
        print(f"   1. Check examples.py for more usage patterns")
        print(f"   2. Read README.md for detailed documentation")
        print(f"   3. Integrate with your scraping projects")
        print(f"   4. Monitor proxy health and performance")
        
        # Stop the client
        print(f"\n🛑 Stopping proxy client...")
        await client.stop()
        print("✅ Proxy client stopped")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("\nPlease ensure all dependencies are installed:")
        print("pip install aiohttp pyyaml psutil")
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        logger.exception("Quick start demo failed")


def check_dependencies():
    """Check if required dependencies are available."""
    print("🔍 Checking dependencies...")
    
    missing_deps = []
    
    try:
        import aiohttp
        print("   ✅ aiohttp")
    except ImportError:
        missing_deps.append("aiohttp")
        print("   ❌ aiohttp")
    
    try:
        import yaml
        print("   ✅ PyYAML")
    except ImportError:
        missing_deps.append("PyYAML")
        print("   ❌ PyYAML")
    
    try:
        import psutil
        print("   ✅ psutil")
    except ImportError:
        missing_deps.append("psutil")
        print("   ❌ psutil")
    
    if missing_deps:
        print(f"\n❌ Missing dependencies: {', '.join(missing_deps)}")
        print("Please install them with:")
        print(f"pip install {' '.join(missing_deps)}")
        return False
    
    print("✅ All dependencies available")
    return True


def check_clash_binary():
    """Check if Clash binary is available."""
    print("\n🔍 Checking for Clash binary...")
    
    import shutil
    
    # Check for common Clash binaries
    binaries = ['clash', 'mihomo', 'clash.exe', 'mihomo.exe']
    
    for binary in binaries:
        if shutil.which(binary):
            print(f"   ✅ Found {binary} in PATH")
            return True
    
    print("   ❌ No Clash binary found in PATH")
    print("\n💡 To install Clash:")
    print("   1. Download from: https://github.com/Dreamacro/clash/releases")
    print("   2. Or Mihomo: https://github.com/MetaCubeX/mihomo/releases")
    print("   3. Add to PATH or specify path in ClashProxyClient(clash_binary_path='...')")
    
    return False


async def main():
    """Main function."""
    print("Clash Proxy Client - Quick Start")
    print("=" * 40)
    
    # Check dependencies
    if not check_dependencies():
        return False
    
    # Check Clash binary
    has_clash = check_clash_binary()
    
    if not has_clash:
        print("\n⚠️  Clash binary not found, but continuing with demo...")
        print("The demo may fail at the proxy start step.")
    
    # Run the demo
    print("\n" + "=" * 50)
    await quick_start_demo()
    
    return True


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
