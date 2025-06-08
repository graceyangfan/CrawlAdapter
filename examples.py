"""
Clash Proxy Client Usage Examples

This module provides comprehensive examples of how to use the Clash proxy client
for web scraping applications with automatic IP rotation and load balancing.
"""

import asyncio
import logging
import time
from typing import List

import aiohttp
import requests

from .client import ClashProxyClient


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def basic_usage_example():
    """
    Basic usage example showing how to start and use the Clash proxy client.
    """
    print("=== Basic Usage Example ===")
    
    # Initialize and start the client
    client = ClashProxyClient(config_dir='./clash_configs')
    
    try:
        # Start the client with scraping-optimized configuration
        success = await client.start(config_type='scraping', enable_auto_update=True)
        
        if not success:
            print("Failed to start Clash proxy client")
            return
        
        # Get proxy URL for use with HTTP clients
        proxy_url = await client.get_proxy_url(strategy='health_weighted')
        print(f"Proxy URL: {proxy_url}")
        
        # Test the proxy
        if proxy_url:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    'http://httpbin.org/ip',
                    proxy=proxy_url,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"Current IP: {data['origin']}")
                    else:
                        print(f"Request failed: HTTP {response.status}")
        
        # Get client information
        info = await client.get_proxy_info()
        print(f"Proxy statistics: {info['proxy_stats']}")
        
    finally:
        await client.stop()


async def web_scraping_example():
    """
    Example of using Clash proxy client for web scraping with automatic rotation.
    """
    print("\n=== Web Scraping Example ===")
    
    urls_to_scrape = [
        'http://httpbin.org/ip',
        'http://httpbin.org/user-agent',
        'http://httpbin.org/headers',
        'http://httpbin.org/get?param=test1',
        'http://httpbin.org/get?param=test2'
    ]
    
    async with ClashProxyClient() as client:
        results = []
        
        for i, url in enumerate(urls_to_scrape):
            try:
                # Get a fresh proxy for each request (load balancing)
                proxy_url = await client.get_proxy_url(strategy='round_robin')
                
                if not proxy_url:
                    print(f"No proxy available for request {i+1}")
                    continue
                
                # Make request through proxy
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url,
                        proxy=proxy_url,
                        timeout=aiohttp.ClientTimeout(total=15)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            results.append({
                                'url': url,
                                'ip': data.get('origin', 'unknown'),
                                'status': 'success'
                            })
                            print(f"Request {i+1}: {url} -> IP: {data.get('origin', 'unknown')}")
                        else:
                            print(f"Request {i+1} failed: HTTP {response.status}")
                
                # Small delay between requests
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"Request {i+1} error: {e}")
        
        print(f"\nCompleted {len(results)} successful requests")
        
        # Show unique IPs used
        unique_ips = set(result['ip'] for result in results)
        print(f"Unique IPs used: {len(unique_ips)}")


def synchronous_usage_example():
    """
    Example of using Clash proxy client with synchronous requests library.
    """
    print("\n=== Synchronous Usage Example ===")
    
    async def setup_and_get_proxy():
        client = ClashProxyClient()
        await client.start()
        proxy_url = await client.get_proxy_url()
        return client, proxy_url
    
    # Setup proxy client
    client, proxy_url = asyncio.run(setup_and_get_proxy())
    
    if proxy_url:
        try:
            # Use with requests library
            proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
            
            response = requests.get('http://httpbin.org/ip', proxies=proxies, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"Synchronous request IP: {data['origin']}")
            else:
                print(f"Synchronous request failed: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"Synchronous request error: {e}")
        
        finally:
            # Cleanup
            asyncio.run(client.stop())
    else:
        print("Failed to get proxy URL")


async def proxy_testing_example():
    """
    Example of testing individual proxies and monitoring health.
    """
    print("\n=== Proxy Testing Example ===")
    
    client = ClashProxyClient()
    
    try:
        await client.start()
        
        # Get proxy information
        info = await client.get_proxy_info()
        proxy_stats = info['proxy_stats']
        
        print(f"Total proxies: {proxy_stats['total_proxies']}")
        print(f"Healthy proxies: {proxy_stats['healthy_proxies']}")
        print(f"Health rate: {proxy_stats['health_rate']:.2%}")
        
        # Test specific proxies
        healthy_proxies = client.proxy_manager.get_healthy_proxy_names()
        
        if healthy_proxies:
            print(f"\nTesting top 3 healthy proxies:")
            
            for i, proxy_name in enumerate(healthy_proxies[:3]):
                test_result = await client.test_proxy(proxy_name)
                
                if test_result['success']:
                    print(f"{i+1}. {proxy_name}: IP={test_result['ip']}, "
                          f"Latency={test_result['latency']}ms")
                else:
                    print(f"{i+1}. {proxy_name}: Failed - {test_result['error']}")
        
        # Show health statistics
        health_stats = info['health_stats']
        print(f"\nHealth Statistics:")
        print(f"Average score: {health_stats['average_score']}")
        print(f"Health rate: {health_stats['health_rate']:.2%}")
        
    finally:
        await client.stop()


async def load_balancing_strategies_example():
    """
    Example demonstrating different load balancing strategies.
    """
    print("\n=== Load Balancing Strategies Example ===")
    
    strategies = ['health_weighted', 'round_robin', 'least_used', 'random']
    
    async with ClashProxyClient() as client:
        for strategy in strategies:
            print(f"\nTesting strategy: {strategy}")
            
            # Make 5 requests with each strategy
            ips_used = []
            
            for i in range(5):
                proxy_url = await client.get_proxy_url(strategy=strategy)
                
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
                                    ip = data['origin']
                                    ips_used.append(ip)
                                    print(f"  Request {i+1}: {ip}")
                    except Exception as e:
                        print(f"  Request {i+1}: Error - {e}")
                
                await asyncio.sleep(0.5)
            
            unique_ips = len(set(ips_used))
            print(f"  Strategy '{strategy}': {unique_ips} unique IPs out of {len(ips_used)} requests")


async def error_handling_example():
    """
    Example demonstrating error handling and recovery.
    """
    print("\n=== Error Handling Example ===")
    
    client = ClashProxyClient()
    
    try:
        await client.start()
        
        # Simulate making requests with error handling
        for i in range(10):
            try:
                proxy_url = await client.get_proxy_url()
                
                if not proxy_url:
                    print(f"Request {i+1}: No proxy available, retrying...")
                    await asyncio.sleep(2)
                    continue
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        'http://httpbin.org/delay/1',  # Endpoint with 1s delay
                        proxy=proxy_url,
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        if response.status == 200:
                            print(f"Request {i+1}: Success")
                        else:
                            print(f"Request {i+1}: HTTP {response.status}")
                            
            except asyncio.TimeoutError:
                print(f"Request {i+1}: Timeout - switching proxy")
                # Switch to a different proxy
                await client.switch_proxy(strategy='health_weighted')
                
            except Exception as e:
                print(f"Request {i+1}: Error - {e}")
            
            await asyncio.sleep(1)
    
    finally:
        await client.stop()


async def main():
    """Run all examples."""
    print("Clash Proxy Client Examples")
    print("=" * 50)
    
    # Run examples
    await basic_usage_example()
    await web_scraping_example()
    synchronous_usage_example()
    await proxy_testing_example()
    await load_balancing_strategies_example()
    await error_handling_example()
    
    print("\n" + "=" * 50)
    print("All examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
