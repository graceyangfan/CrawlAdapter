"""
Clash Proxy Client

Main client for managing Clash proxy operations including process management,
health monitoring, and providing proxy services for web scraping.
"""

import asyncio
import logging
import os
import platform
import signal
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiohttp
import psutil

from .config_manager import ConfigurationManager
from .health_checker import EnhancedHealthChecker
from .node_fetcher import NodeFetcher
from .proxy_manager import UnifiedProxyConfigManager


class ClashProxyClient:
    """
    Main Clash proxy client for web scraping applications.
    
    Features:
    - Automatic Clash process management
    - Health monitoring and failover
    - Load balancing and proxy rotation
    - Easy integration with scraping frameworks
    """
    
    def __init__(
        self,
        config_dir: str = './clash_configs',
        clash_binary_path: Optional[str] = None,
        auto_update_interval: int = 3600
    ):
        """
        Initialize Clash proxy client.
        
        Args:
            config_dir: Directory for storing configurations
            clash_binary_path: Path to Clash binary (auto-detected if None)
            auto_update_interval: Interval for automatic proxy updates (seconds)
        """
        self.config_dir = Path(config_dir)
        self.clash_binary_path = clash_binary_path
        self.auto_update_interval = auto_update_interval
        
        # Initialize components
        self.node_fetcher = NodeFetcher()
        self.config_manager = ConfigurationManager(config_dir)
        self.proxy_manager = UnifiedProxyConfigManager(self.node_fetcher)
        self.health_checker = EnhancedHealthChecker()
        
        # Process management
        self.clash_process = None
        self.clash_api_base = "http://127.0.0.1:9090"
        self.proxy_port = 7890
        
        # State management
        self.is_running = False
        self.last_health_check = 0
        self.health_check_interval = 300  # 5 minutes
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Auto-update task
        self._auto_update_task = None
        self._health_monitor_task = None
    
    async def start(
        self,
        config_type: str = 'scraping',
        source_types: List[str] = None,
        enable_auto_update: bool = True
    ) -> bool:
        """
        Start the Clash proxy client.
        
        Args:
            config_type: Type of configuration ('scraping', 'speed', 'general')
            source_types: List of proxy source types to use
            enable_auto_update: Enable automatic proxy updates
            
        Returns:
            True if started successfully
        """
        try:
            self.logger.info("Starting Clash proxy client...")
            
            # Initialize proxy manager
            if not await self.proxy_manager.initialize(source_types):
                self.logger.error("Failed to initialize proxy manager")
                return False
            
            # Generate and save configuration
            config = self.proxy_manager.generate_clash_config(config_type)
            config_path = self.config_manager.save_configuration(config)
            
            # Start Clash process
            if not await self._start_clash_process(config_path):
                self.logger.error("Failed to start Clash process")
                return False
            
            # Wait for Clash to be ready
            if not await self._wait_for_clash_ready():
                self.logger.error("Clash failed to become ready")
                await self.stop()
                return False
            
            # Perform initial health check
            await self._perform_health_check()
            
            # Start background tasks
            if enable_auto_update:
                self._auto_update_task = asyncio.create_task(self._auto_update_loop())
            
            self._health_monitor_task = asyncio.create_task(self._health_monitor_loop())
            
            self.is_running = True
            self.logger.info(f"Clash proxy client started successfully on port {self.proxy_port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start Clash proxy client: {e}")
            await self.stop()
            return False
    
    async def stop(self):
        """Stop the Clash proxy client and cleanup resources."""
        self.logger.info("Stopping Clash proxy client...")
        
        self.is_running = False
        
        # Cancel background tasks
        if self._auto_update_task:
            self._auto_update_task.cancel()
            try:
                await self._auto_update_task
            except asyncio.CancelledError:
                pass
        
        if self._health_monitor_task:
            self._health_monitor_task.cancel()
            try:
                await self._health_monitor_task
            except asyncio.CancelledError:
                pass
        
        # Stop Clash process
        await self._stop_clash_process()
        
        self.logger.info("Clash proxy client stopped")
    
    async def get_proxy_url(self, strategy: str = 'health_weighted') -> Optional[str]:
        """
        Get proxy URL for use with HTTP clients.
        
        Args:
            strategy: Proxy selection strategy
            
        Returns:
            Proxy URL string or None
        """
        if not self.is_running:
            return None
        
        # Get best proxy and switch to it
        proxy = self.proxy_manager.get_best_proxy(strategy)
        if not proxy:
            return None
        
        # Switch Clash to use this proxy
        success = await self._switch_proxy(proxy['name'])
        if success:
            return f"http://127.0.0.1:{self.proxy_port}"
        
        return None
    
    async def get_proxy_info(self) -> Dict:
        """
        Get current proxy information and statistics.
        
        Returns:
            Dictionary with proxy information
        """
        info = {
            'is_running': self.is_running,
            'proxy_port': self.proxy_port,
            'api_base': self.clash_api_base,
            'proxy_stats': self.proxy_manager.get_proxy_statistics(),
            'health_stats': self.health_checker.get_proxy_statistics()
        }
        
        if self.is_running:
            # Get current proxy from Clash API
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.clash_api_base}/proxies/PROXY") as response:
                        if response.status == 200:
                            data = await response.json()
                            info['current_proxy'] = data.get('now', 'unknown')
            except Exception as e:
                self.logger.debug(f"Failed to get current proxy info: {e}")
        
        return info
    
    async def switch_proxy(self, proxy_name: Optional[str] = None, strategy: str = 'health_weighted') -> bool:
        """
        Switch to a specific proxy or select using strategy.
        
        Args:
            proxy_name: Specific proxy name to switch to
            strategy: Selection strategy if proxy_name is None
            
        Returns:
            True if switch successful
        """
        if not self.is_running:
            return False
        
        if proxy_name:
            return await self._switch_proxy(proxy_name)
        else:
            proxy = self.proxy_manager.get_best_proxy(strategy)
            if proxy:
                return await self._switch_proxy(proxy['name'])
        
        return False
    
    async def test_proxy(self, proxy_name: str, test_url: str = 'http://httpbin.org/ip') -> Dict:
        """
        Test a specific proxy.
        
        Args:
            proxy_name: Name of proxy to test
            test_url: URL to test with
            
        Returns:
            Test results dictionary
        """
        if not self.is_running:
            return {'success': False, 'error': 'Client not running'}
        
        try:
            # Switch to the proxy
            if not await self._switch_proxy(proxy_name):
                return {'success': False, 'error': 'Failed to switch proxy'}
            
            # Test the proxy
            start_time = time.time()
            
            async with aiohttp.ClientSession() as session:
                proxy_url = f"http://127.0.0.1:{self.proxy_port}"
                async with session.get(test_url, proxy=proxy_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    end_time = time.time()
                    
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'success': True,
                            'latency': round((end_time - start_time) * 1000, 2),
                            'ip': data.get('origin', 'unknown'),
                            'status_code': response.status
                        }
                    else:
                        return {
                            'success': False,
                            'error': f'HTTP {response.status}',
                            'latency': round((end_time - start_time) * 1000, 2)
                        }
                        
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _start_clash_process(self, config_path: Path) -> bool:
        """Start the Clash process with given configuration."""
        try:
            # Find Clash binary
            clash_binary = self._find_clash_binary()
            if not clash_binary:
                self.logger.error("Clash binary not found")
                return False
            
            # Start Clash process
            cmd = [str(clash_binary), '-f', str(config_path)]
            
            self.clash_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.config_dir
            )
            
            self.logger.info(f"Started Clash process with PID {self.clash_process.pid}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start Clash process: {e}")
            return False
    
    async def _stop_clash_process(self):
        """Stop the Clash process."""
        if self.clash_process:
            try:
                # Try graceful shutdown first
                self.clash_process.terminate()
                
                # Wait for process to exit
                try:
                    self.clash_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if graceful shutdown failed
                    self.clash_process.kill()
                    self.clash_process.wait()
                
                self.logger.info("Clash process stopped")
                
            except Exception as e:
                self.logger.error(f"Error stopping Clash process: {e}")
            
            finally:
                self.clash_process = None

    def _find_clash_binary(self) -> Optional[Path]:
        """Find Clash binary in system or download if needed."""
        if self.clash_binary_path:
            binary_path = Path(self.clash_binary_path)
            if binary_path.exists():
                return binary_path

        # Check common locations
        system = platform.system().lower()
        binary_name = 'clash' if system != 'windows' else 'clash.exe'

        # Check in PATH
        import shutil
        binary_in_path = shutil.which(binary_name)
        if binary_in_path:
            return Path(binary_in_path)

        # Check in config directory
        local_binary = self.config_dir / binary_name
        if local_binary.exists():
            return local_binary

        # Check for mihomo (clash-verge-rev core)
        mihomo_name = 'mihomo' if system != 'windows' else 'mihomo.exe'
        mihomo_in_path = shutil.which(mihomo_name)
        if mihomo_in_path:
            return Path(mihomo_in_path)

        local_mihomo = self.config_dir / mihomo_name
        if local_mihomo.exists():
            return local_mihomo

        self.logger.warning("Clash binary not found. Please install Clash or set clash_binary_path")
        return None

    async def _wait_for_clash_ready(self, timeout: int = 30) -> bool:
        """Wait for Clash to be ready to accept connections."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.clash_api_base}/proxies") as response:
                        if response.status == 200:
                            self.logger.info("Clash is ready")
                            return True
            except Exception:
                pass

            await asyncio.sleep(1)

        self.logger.error("Timeout waiting for Clash to be ready")
        return False

    async def _switch_proxy(self, proxy_name: str) -> bool:
        """Switch Clash to use specific proxy."""
        try:
            switch_url = f"{self.clash_api_base}/proxies/PROXY"
            switch_data = {"name": proxy_name}

            async with aiohttp.ClientSession() as session:
                async with session.put(switch_url, json=switch_data) as response:
                    if response.status == 204:
                        self.logger.debug(f"Switched to proxy: {proxy_name}")
                        return True
                    else:
                        self.logger.warning(f"Failed to switch proxy: HTTP {response.status}")
                        return False

        except Exception as e:
            self.logger.error(f"Error switching proxy: {e}")
            return False

    async def _perform_health_check(self):
        """Perform health check on all proxies."""
        try:
            health_results = await self.health_checker.check_all_proxies(
                self.proxy_manager.active_proxies,
                self.clash_api_base
            )

            self.proxy_manager.update_proxy_health(health_results)
            self.last_health_check = time.time()

            # Log health summary
            stats = self.health_checker.get_proxy_statistics()
            self.logger.info(
                f"Health check completed: {stats['healthy_proxies']}/{stats['total_proxies']} "
                f"healthy (avg score: {stats['average_score']})"
            )

        except Exception as e:
            self.logger.error(f"Health check failed: {e}")

    async def _auto_update_loop(self):
        """Background task for automatic proxy updates."""
        while self.is_running:
            try:
                await asyncio.sleep(self.auto_update_interval)

                if self.is_running:
                    self.logger.info("Performing automatic proxy update...")

                    # Update proxy list
                    if await self.proxy_manager.update_proxies():
                        # Generate new configuration
                        config = self.proxy_manager.generate_clash_config('scraping')
                        config_path = self.config_manager.save_configuration(config)

                        # Restart Clash with new configuration
                        await self._stop_clash_process()
                        if await self._start_clash_process(config_path):
                            await self._wait_for_clash_ready()
                            await self._perform_health_check()
                            self.logger.info("Automatic update completed successfully")
                        else:
                            self.logger.error("Failed to restart Clash after update")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in auto-update loop: {e}")

    async def _health_monitor_loop(self):
        """Background task for periodic health monitoring."""
        while self.is_running:
            try:
                await asyncio.sleep(self.health_check_interval)

                if self.is_running:
                    await self._perform_health_check()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in health monitor loop: {e}")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
