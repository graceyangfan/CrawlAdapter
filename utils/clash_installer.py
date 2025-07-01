#!/usr/bin/env python3
"""
Clash Binary Installer

Automatically downloads and configures Mihomo (Clash Meta) binary for CrawlAdapter.
"""

import os
import sys
import platform
import zipfile
import tarfile
import requests
from pathlib import Path
from typing import Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mihomo release information
MIHOMO_RELEASES_URL = "https://api.github.com/repos/MetaCubeX/mihomo/releases/latest"
MIHOMO_DOWNLOAD_BASE = "https://github.com/MetaCubeX/mihomo/releases/download"

def get_system_info() -> Tuple[str, str]:
    """
    Get system architecture and OS information.
    
    Returns:
        Tuple of (os_name, arch_name) for download URL
    """
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    # Map system names
    os_map = {
        'windows': 'windows',
        'darwin': 'darwin',
        'linux': 'linux'
    }
    
    # Map architecture names
    arch_map = {
        'x86_64': 'amd64',
        'amd64': 'amd64',
        'i386': '386',
        'i686': '386',
        'arm64': 'arm64',
        'aarch64': 'arm64',
        'armv7l': 'armv7'
    }
    
    os_name = os_map.get(system, 'linux')
    arch_name = arch_map.get(machine, 'amd64')
    
    return os_name, arch_name

def get_latest_release_info() -> dict:
    """
    Get latest Mihomo release information from GitHub API.
    
    Returns:
        Release information dictionary
    """
    try:
        response = requests.get(MIHOMO_RELEASES_URL, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to get release info: {e}")
        # Fallback to a known version
        return {
            'tag_name': 'v1.18.0',
            'name': 'v1.18.0'
        }

def download_clash_binary(
    install_dir: Optional[Path] = None,
    force_download: bool = False
) -> Path:
    """
    Download Mihomo (Clash Meta) binary.
    
    Args:
        install_dir: Directory to install binary (default: ./mihomo_proxy)
        force_download: Force re-download even if binary exists
        
    Returns:
        Path to the downloaded binary
    """
    if install_dir is None:
        install_dir = Path('./mihomo_proxy')
    
    install_dir.mkdir(parents=True, exist_ok=True)
    
    # Get system information
    os_name, arch_name = get_system_info()
    
    # Determine binary name
    binary_name = 'mihomo.exe' if os_name == 'windows' else 'mihomo'
    binary_path = install_dir / binary_name
    
    # Check if binary already exists
    if binary_path.exists() and not force_download:
        logger.info(f"✅ Clash binary already exists: {binary_path}")
        return binary_path
    
    logger.info("🔄 Downloading latest Mihomo release...")
    
    # Get release information
    release_info = get_latest_release_info()
    version = release_info['tag_name']
    
    logger.info(f"📦 Latest version: {version}")
    
    # Construct download URL
    if os_name == 'windows':
        archive_name = f"mihomo-{os_name}-{arch_name}-{version}.zip"
    else:
        archive_name = f"mihomo-{os_name}-{arch_name}-{version}.gz"
    
    download_url = f"{MIHOMO_DOWNLOAD_BASE}/{version}/{archive_name}"
    
    logger.info(f"⬇️  Downloading from: {download_url}")
    
    try:
        # Download the archive
        response = requests.get(download_url, timeout=300, stream=True)
        response.raise_for_status()
        
        archive_path = install_dir / archive_name
        
        # Save archive
        with open(archive_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"✅ Downloaded: {archive_path}")
        
        # Extract binary
        if archive_name.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(install_dir)
        else:
            # For .gz files (not .tar.gz), use gzip directly
            import gzip
            try:
                with gzip.open(archive_path, 'rb') as gz_file:
                    with open(binary_path, 'wb') as out_file:
                        out_file.write(gz_file.read())
            except Exception as gz_error:
                logger.warning(f"Gzip extraction failed: {gz_error}")
                # Try as regular file (sometimes the download is not actually gzipped)
                import shutil
                shutil.copy2(archive_path, binary_path)
        
        # Make binary executable on Unix systems
        if os_name != 'windows':
            binary_path.chmod(0o755)
        
        # Clean up archive
        archive_path.unlink()
        
        logger.info(f"✅ Clash binary installed: {binary_path}")
        return binary_path
        
    except Exception as e:
        logger.error(f"❌ Failed to download Clash binary: {e}")
        raise

def check_clash_installation() -> Optional[Path]:
    """
    Check if Clash binary is available.
    
    Returns:
        Path to Clash binary if found, None otherwise
    """
    # Check common locations
    possible_paths = [
        Path('./mihomo_proxy/mihomo'),
        Path('./mihomo_proxy/mihomo.exe'),
        Path('./clash_configs/mihomo'),
        Path('./clash_configs/mihomo.exe'),
    ]
    
    # Check if mihomo is in PATH
    import shutil
    if shutil.which('mihomo'):
        return Path(shutil.which('mihomo'))
    
    # Check local installations
    for path in possible_paths:
        if path.exists() and path.is_file():
            return path
    
    return None

def get_clash_binary_path() -> Optional[Path]:
    """
    Get path to Clash binary, download if necessary.
    
    Returns:
        Path to Clash binary
    """
    # First check if already installed
    existing_path = check_clash_installation()
    if existing_path:
        return existing_path
    
    # Download if not found
    try:
        return download_clash_binary()
    except Exception as e:
        logger.error(f"Failed to get Clash binary: {e}")
        return None

def setup_clash_environment() -> bool:
    """
    Set up complete Clash environment.
    
    Returns:
        True if setup successful, False otherwise
    """
    try:
        logger.info("🚀 Setting up Clash environment...")
        
        # Download binary
        binary_path = download_clash_binary()
        
        # Create config directory
        config_dir = Path('./clash_configs')
        config_dir.mkdir(exist_ok=True)
        
        logger.info(f"✅ Clash environment setup complete!")
        logger.info(f"   Binary: {binary_path}")
        logger.info(f"   Config directory: {config_dir}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to setup Clash environment: {e}")
        return False

def main():
    """Main entry point for clash installer."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Clash Binary Installer")
    parser.add_argument(
        '--install-dir', 
        type=Path, 
        default=Path('./mihomo_proxy'),
        help='Installation directory'
    )
    parser.add_argument(
        '--force', 
        action='store_true',
        help='Force re-download even if binary exists'
    )
    parser.add_argument(
        '--check', 
        action='store_true',
        help='Check current installation'
    )
    
    args = parser.parse_args()
    
    if args.check:
        path = check_clash_installation()
        if path:
            print(f"✅ Clash binary found: {path}")
        else:
            print("❌ Clash binary not found")
        return
    
    try:
        binary_path = download_clash_binary(args.install_dir, args.force)
        print(f"✅ Success! Clash binary available at: {binary_path}")
    except Exception as e:
        print(f"❌ Failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
