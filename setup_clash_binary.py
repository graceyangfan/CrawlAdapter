#!/usr/bin/env python3
"""
Clash Binary Setup Script with Absolute Path Configuration

This script downloads Clash binary and sets up absolute paths for reliable operation.
"""

import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_absolute_paths():
    """Get absolute paths for current project."""
    project_root = Path.cwd().resolve()

    paths = {
        'project_root': project_root,
        'mihomo_proxy_dir': project_root / 'mihomo_proxy',
        'clash_configs_dir': project_root / 'clash_configs',
        'binary_path': project_root / 'mihomo_proxy' / 'mihomo',
        'config_path': project_root / 'clash_configs' / 'config.yaml',
    }

    # Add .exe extension on Windows
    if os.name == 'nt':
        paths['binary_path'] = project_root / 'mihomo_proxy' / 'mihomo.exe'

    return paths


def download_clash_binary():
    """Download Clash binary to absolute path."""
    logger.info("📥 Downloading Clash binary...")

    try:
        # Import the installer
        sys.path.insert(0, str(Path(__file__).parent / 'utils'))
        from clash_installer import download_clash_binary as download_binary

        paths = get_absolute_paths()

        # Create directory
        paths['mihomo_proxy_dir'].mkdir(exist_ok=True)

        # Download binary
        binary_path = download_binary(
            install_dir=paths['mihomo_proxy_dir'],
            force_download=False
        )

        # Make executable on Unix systems
        if os.name != 'nt':
            os.chmod(binary_path, 0o755)
            logger.info(f"✅ Made binary executable: {binary_path}")

        logger.info(f"✅ Clash binary downloaded: {binary_path.resolve()}")
        return binary_path.resolve()

    except Exception as e:
        logger.error(f"❌ Failed to download Clash binary: {e}")
        return None

def main():
    """Main setup function."""
    print("🚀 CrawlAdapter Complete Setup")
    print("=" * 50)

    # Import config helper
    from config_helper import setup_config_environment

    success = True

    # Step 1: Set up configuration environment
    print("\n📋 Step 1: Setting up configuration environment...")
    if not setup_config_environment():
        print("⚠️  Configuration setup had issues, but continuing...")

    # Step 2: Check if Clash binary already installed
    print("\n📋 Step 2: Checking Clash binary...")
    existing_path = check_clash_installation()
    if existing_path:
        print(f"✅ Clash binary already installed: {existing_path}")
    else:
        print("📦 Downloading and setting up Clash binary...")
        if not setup_clash_environment():
            print("❌ Clash binary setup failed!")
            success = False

    # Step 3: Final verification
    print("\n📋 Step 3: Final verification...")
    try:
        # Test import
        import sys
        sys.path.insert(0, '.')
        from crawladapter import ProxyClient
        print("✅ CrawlAdapter import successful")

        # Test configuration
        client = ProxyClient()
        print("✅ ProxyClient creation successful")

    except Exception as e:
        print(f"❌ Verification failed: {e}")
        success = False

    # Results
    if success:
        print("\n🎉 Complete setup successful!")
        print("\n📚 Next steps:")
        print("1. Run examples: python examples/simple_panewslab_example.py")
        print("2. Check configuration: python utils/config_helper.py --status")
        print("3. Edit config: ~/.crawladapter/config.yaml")
        print("4. Read documentation: CONFIGURATION.md")
    else:
        print("\n❌ Setup completed with errors!")
        print("\n🔧 Troubleshooting:")
        print("1. Check internet connection")
        print("2. Try with administrator/sudo privileges")
        print("3. Manual setup: python utils/clash_installer.py")
        print("4. Check logs for detailed error information")

if __name__ == '__main__':
    main()
