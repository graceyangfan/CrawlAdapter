"""
CrawlAdapter Process Manager

Handles Clash binary detection, process management, and lifecycle operations.
Separated from core.py to improve modularity and maintainability.
"""

import asyncio
import logging
import os
import platform
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional

from .exceptions import ClashProcessError, ConfigurationError
from .types import ProxyConfig


class ClashProcessManager:
    """Manages Clash binary detection and process lifecycle."""
    
    def __init__(self, config: ProxyConfig):
        """Initialize the process manager."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.clash_process: Optional[subprocess.Popen] = None
        self.binary_path: Optional[str] = None
        
    async def detect_clash_binary(self) -> str:
        """
        Detect Clash binary path automatically.
        
        Returns:
            Path to Clash binary
            
        Raises:
            ClashProcessError: If binary not found
        """
        if self.config.clash_binary_path:
            if Path(self.config.clash_binary_path).exists():
                self.binary_path = self.config.clash_binary_path
                return self.binary_path
            else:
                raise ClashProcessError(
                    f"Specified Clash binary not found: {self.config.clash_binary_path}",
                    binary_path=self.config.clash_binary_path
                )
        
        # Search in common locations
        search_paths = self._get_search_paths()
        
        for path in search_paths:
            if path.exists():
                self.binary_path = str(path)
                self.logger.info(f"Found Clash binary: {self.binary_path}")
                return self.binary_path
        
        # Try system PATH
        system_binary = shutil.which('clash') or shutil.which('mihomo')
        if system_binary:
            self.binary_path = system_binary
            self.logger.info(f"Found Clash binary in PATH: {self.binary_path}")
            return self.binary_path
        
        raise ClashProcessError(
            "Clash binary not found. Please install Clash or specify binary path."
        )
    
    def _get_search_paths(self) -> list[Path]:
        """Get list of paths to search for Clash binary."""
        base_dir = Path(self.config.config_dir).parent
        system = platform.system().lower()
        
        search_paths = [
            # Local mihomo_proxy directory
            base_dir / 'mihomo_proxy' / 'mihomo',
            base_dir / 'mihomo_proxy' / 'mihomo.exe',
            base_dir / 'mihomo_proxy' / 'clash',
            base_dir / 'mihomo_proxy' / 'clash.exe',
            
            # Current directory
            Path.cwd() / 'mihomo',
            Path.cwd() / 'clash',
        ]
        
        if system == 'windows':
            search_paths.extend([
                Path.cwd() / 'mihomo.exe',
                Path.cwd() / 'clash.exe',
            ])
        
        return search_paths
    
    async def kill_existing_processes(self) -> None:
        """Kill any existing Clash processes."""
        try:
            if platform.system() == "Windows":
                # Windows: use taskkill
                for process_name in ['clash.exe', 'mihomo.exe']:
                    try:
                        subprocess.run(['taskkill', '/F', '/IM', process_name], 
                                     capture_output=True, check=False)
                    except Exception:
                        pass
            else:
                # Unix-like: use pkill
                for process_name in ['clash', 'mihomo']:
                    try:
                        subprocess.run(['pkill', '-f', process_name], 
                                     capture_output=True, check=False)
                    except Exception:
                        pass
            
            # Wait a moment for processes to terminate
            await asyncio.sleep(1)
            self.logger.info("Killed existing Clash processes")
            
        except Exception as e:
            self.logger.warning(f"Error killing existing processes: {e}")
    
    async def start_clash_process(self, config_path: str) -> bool:
        """
        Start Clash process with given configuration.
        
        Args:
            config_path: Path to Clash configuration file
            
        Returns:
            True if started successfully
            
        Raises:
            ClashProcessError: If process fails to start
        """
        try:
            if not self.binary_path:
                await self.detect_clash_binary()
            
            if not Path(config_path).exists():
                raise ConfigurationError(
                    f"Configuration file not found: {config_path}",
                    config_path=config_path
                )
            
            # Kill existing processes first
            await self.kill_existing_processes()
            
            # Start new process (ensure all paths are strings)
            cmd = [str(self.binary_path), '-f', str(config_path)]
            self.logger.info(f"Starting Clash: {' '.join(cmd)}")

            self.clash_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(Path(config_path).parent)
            )
            
            # Wait a moment and check if process is still running
            await asyncio.sleep(2)
            
            if self.clash_process.poll() is not None:
                # Process has terminated
                stdout, stderr = self.clash_process.communicate()
                error_msg = f"Clash process failed to start. Exit code: {self.clash_process.returncode}"
                if stderr:
                    error_msg += f"\nError: {stderr.decode()}"
                
                raise ClashProcessError(
                    error_msg,
                    binary_path=self.binary_path,
                    config_path=config_path
                )
            
            # Test API connectivity
            if not await self._test_api_connectivity():
                raise ClashProcessError(
                    "Clash API is not accessible after startup",
                    binary_path=self.binary_path,
                    config_path=config_path
                )
            
            self.logger.info("✅ Clash process started successfully")
            return True
            
        except ClashProcessError:
            raise
        except Exception as e:
            raise ClashProcessError(
                f"Failed to start Clash process: {str(e)}",
                binary_path=self.binary_path,
                config_path=config_path
            )
    
    async def _test_api_connectivity(self, max_retries: int = 10) -> bool:
        """Test if Clash API is accessible."""
        import aiohttp
        
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.config.clash_api_base}/version",
                        timeout=aiohttp.ClientTimeout(total=2)
                    ) as response:
                        if response.status == 200:
                            return True
            except Exception:
                pass
            
            await asyncio.sleep(0.5)
        
        return False
    
    async def stop_clash_process(self) -> None:
        """Stop the Clash process gracefully."""
        if self.clash_process:
            try:
                # Try graceful termination first
                self.clash_process.terminate()
                
                # Wait for process to terminate
                try:
                    await asyncio.wait_for(
                        asyncio.create_task(self._wait_for_process()),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    # Force kill if graceful termination fails
                    self.clash_process.kill()
                    await asyncio.create_task(self._wait_for_process())
                
                self.logger.info("Clash process stopped")
                
            except Exception as e:
                self.logger.error(f"Error stopping Clash process: {e}")
            finally:
                self.clash_process = None
    
    async def _wait_for_process(self) -> None:
        """Wait for process to terminate (async wrapper)."""
        if self.clash_process:
            while self.clash_process.poll() is None:
                await asyncio.sleep(0.1)
    
    def is_running(self) -> bool:
        """Check if Clash process is running."""
        return self.clash_process is not None and self.clash_process.poll() is None
