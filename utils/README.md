# CrawlAdapter Utilities

This directory contains utility tools for setting up and managing CrawlAdapter.

## Quick Setup

### 1. Automatic Setup (Recommended)

Run the setup script from the project root:

```bash
python setup_clash_binary.py
```

This will automatically:
- Download the latest Mihomo (Clash Meta) binary
- Set up the configuration directory
- Prepare the environment for CrawlAdapter

### 2. Manual Setup

If you prefer manual setup:

```python
from utils import setup_clash_environment

# Set up complete environment
success = setup_clash_environment()
if success:
    print("✅ Setup complete!")
else:
    print("❌ Setup failed")
```

### 3. Check Installation

```python
from utils import check_clash_installation

binary_path = check_clash_installation()
if binary_path:
    print(f"✅ Clash binary found: {binary_path}")
else:
    print("❌ Clash binary not found")
```

## Available Tools

### clash_installer.py

Main installer for Mihomo (Clash Meta) binary.

**Functions:**
- `download_clash_binary()` - Download latest binary
- `setup_clash_environment()` - Complete environment setup
- `check_clash_installation()` - Check if binary exists
- `get_clash_binary_path()` - Get binary path or download

**Command Line Usage:**
```bash
# Download binary
python utils/clash_installer.py

# Force re-download
python utils/clash_installer.py --force

# Check current installation
python utils/clash_installer.py --check

# Custom install directory
python utils/clash_installer.py --install-dir ./custom_dir
```

## Supported Platforms

The installer automatically detects your platform and downloads the appropriate binary:

- **Windows**: `mihomo-windows-amd64.zip`
- **macOS**: `mihomo-darwin-amd64.gz` / `mihomo-darwin-arm64.gz`
- **Linux**: `mihomo-linux-amd64.gz` / `mihomo-linux-arm64.gz`

## Directory Structure

After setup, you'll have:

```
project_root/
├── mihomo_proxy/          # Clash binary directory
│   └── mihomo(.exe)       # Clash binary
├── clash_configs/         # Configuration directory
│   └── (config files)    # Generated configurations
└── utils/                 # This directory
    ├── __init__.py
    ├── clash_installer.py
    └── README.md
```

## Troubleshooting

### Download Issues

If download fails:

1. **Check internet connection**
2. **Try with VPN** if GitHub is blocked
3. **Manual download**: Visit [Mihomo Releases](https://github.com/MetaCubeX/mihomo/releases)
4. **Use system package manager**:
   ```bash
   # Ubuntu/Debian
   sudo apt install clash
   
   # macOS
   brew install clash
   
   # Arch Linux
   sudo pacman -S clash
   ```

### Permission Issues

On Unix systems, ensure the binary is executable:
```bash
chmod +x mihomo_proxy/mihomo
```

### Path Issues

If the binary isn't found, check these locations:
- `./mihomo_proxy/mihomo`
- `./clash_configs/mihomo`
- System PATH

## Integration with CrawlAdapter

Once setup is complete, CrawlAdapter will automatically find and use the binary:

```python
from crawladapter import ProxyClient

# CrawlAdapter automatically detects the binary
client = ProxyClient()
await client.start()
```

## Advanced Usage

### Custom Binary Location

```python
from utils import download_clash_binary
from pathlib import Path

# Download to custom location
binary_path = download_clash_binary(
    install_dir=Path('./custom_clash'),
    force_download=True
)
```

### Environment Variables

Set these environment variables for custom behavior:

- `CRAWLADAPTER_CLASH_BINARY` - Custom binary path
- `CRAWLADAPTER_CONFIG_DIR` - Custom config directory

## Support

For issues with the utilities:

1. Check the [main README](../README.md)
2. Verify your platform is supported
3. Try manual installation
4. Check GitHub Issues

## License

Same as CrawlAdapter main project (MIT License).
