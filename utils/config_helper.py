#!/usr/bin/env python3
"""
CrawlAdapter Configuration Helper

Tools for managing CrawlAdapter configuration files.
"""

import os
import sys
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

def get_config_paths() -> Dict[str, Path]:
    """Get all possible configuration file paths."""
    return {
        'user_config': Path.home() / '.crawladapter' / 'config.yaml',
        'system_config': Path('/etc/crawladapter/config.yaml'),
        'local_config': Path('./crawladapter_config.yaml'),
        'user_dir': Path.home() / '.crawladapter',
        'clash_configs': Path('./clash_configs'),
        'mihomo_proxy': Path('./mihomo_proxy')
    }

def create_user_config_dir():
    """Create user configuration directory."""
    paths = get_config_paths()
    user_dir = paths['user_dir']
    
    try:
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / 'logs').mkdir(exist_ok=True)
        print(f"✅ Created user config directory: {user_dir}")
        return True
    except Exception as e:
        print(f"❌ Failed to create user config directory: {e}")
        return False

def generate_sample_config(output_path: Optional[Path] = None) -> bool:
    """Generate a sample configuration file."""
    if output_path is None:
        paths = get_config_paths()
        output_path = paths['user_config']
    
    # Sample configuration
    sample_config = {
        'proxy': {
            'port': 7890,
            'api_port': 9090,
            'timeout': 30,
            'max_retries': 3
        },
        'health_check': {
            'timeout': 15,
            'max_concurrent': 10,
            'min_success_rate': 0.25,
            'retry_count': 3,
            'test_urls': [
                'http://httpbin.org/ip',
                'http://www.gstatic.com/generate_204',
                'https://api.ipify.org',
                'http://icanhazip.com'
            ],
            'adaptive': {
                'base_interval': 300,
                'min_interval': 60,
                'max_interval': 1800
            }
        },
        'node_fetching': {
            'timeout': 30,
            'max_retries': 3,
            'default_sources': {
                'clash': [
                    'https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.yml'
                ],
                'v2ray': []
            }
        },
        'routing': {
            'enable_default_rules': True,
            'default_rules': [
                '*.panewslab.com',
                '*.httpbin.org',
                '*.ifconfig.co'
            ]
        },
        'logging': {
            'level': 'INFO',
            'enable_file_logging': False,
            'log_file': 'crawladapter.log'
        }
    }
    
    try:
        # Create directory if it doesn't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write configuration
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(sample_config, f, default_flow_style=False, indent=2)
        
        print(f"✅ Generated sample config: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to generate config: {e}")
        return False

def show_current_config():
    """Show current configuration from all sources."""
    print("🔍 CrawlAdapter Configuration Status")
    print("=" * 50)
    
    paths = get_config_paths()
    
    # Check configuration files
    print("\n📁 Configuration Files:")
    for name, path in paths.items():
        if name.endswith('_config'):
            if path.exists():
                print(f"   ✅ {name}: {path}")
                try:
                    with open(path, 'r') as f:
                        config = yaml.safe_load(f)
                    print(f"      Size: {len(str(config))} chars")
                except Exception as e:
                    print(f"      ❌ Error reading: {e}")
            else:
                print(f"   ❌ {name}: {path} (not found)")
    
    # Check directories
    print("\n📂 Directories:")
    for name, path in paths.items():
        if name.endswith('_dir') or name in ['clash_configs', 'mihomo_proxy']:
            if path.exists():
                print(f"   ✅ {name}: {path}")
                if path.is_dir():
                    files = list(path.iterdir())
                    print(f"      Files: {len(files)}")
            else:
                print(f"   ❌ {name}: {path} (not found)")
    
    # Check environment variables
    print("\n🌍 Environment Variables:")
    env_vars = [k for k in os.environ.keys() if k.startswith('CRAWLADAPTER_')]
    if env_vars:
        for var in env_vars:
            print(f"   ✅ {var}={os.environ[var]}")
    else:
        print("   ❌ No CRAWLADAPTER_* environment variables found")

def validate_config(config_path: Optional[Path] = None):
    """Validate a configuration file."""
    if config_path is None:
        paths = get_config_paths()
        config_path = paths['user_config']
    
    print(f"🔍 Validating configuration: {config_path}")
    
    if not config_path.exists():
        print(f"❌ Configuration file not found: {config_path}")
        return False
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if not isinstance(config, dict):
            print("❌ Configuration must be a dictionary")
            return False
        
        # Basic validation
        required_sections = ['proxy', 'health_check', 'routing']
        for section in required_sections:
            if section not in config:
                print(f"⚠️  Missing section: {section}")
        
        # Validate proxy section
        if 'proxy' in config:
            proxy = config['proxy']
            if 'port' in proxy and not isinstance(proxy['port'], int):
                print("❌ proxy.port must be an integer")
                return False
            if 'api_port' in proxy and not isinstance(proxy['api_port'], int):
                print("❌ proxy.api_port must be an integer")
                return False
        
        print("✅ Configuration validation passed")
        return True
        
    except yaml.YAMLError as e:
        print(f"❌ YAML syntax error: {e}")
        return False
    except Exception as e:
        print(f"❌ Validation error: {e}")
        return False

def setup_config_environment():
    """Set up complete configuration environment."""
    print("🚀 Setting up CrawlAdapter configuration environment...")
    
    success = True
    
    # Create user config directory
    if not create_user_config_dir():
        success = False
    
    # Generate sample config if it doesn't exist
    paths = get_config_paths()
    user_config = paths['user_config']
    
    if not user_config.exists():
        if not generate_sample_config(user_config):
            success = False
    else:
        print(f"✅ User config already exists: {user_config}")
    
    # Create working directories
    for dir_name in ['clash_configs', 'mihomo_proxy']:
        dir_path = paths[dir_name]
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created directory: {dir_path}")
        except Exception as e:
            print(f"❌ Failed to create directory {dir_path}: {e}")
            success = False
    
    if success:
        print("\n🎉 Configuration environment setup complete!")
        print(f"\n📝 Edit your config: {user_config}")
        print("🔍 Check status: python utils/config_helper.py --status")
    else:
        print("\n❌ Setup completed with errors")
    
    return success

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="CrawlAdapter Configuration Helper")
    parser.add_argument('--status', action='store_true', help='Show configuration status')
    parser.add_argument('--setup', action='store_true', help='Set up configuration environment')
    parser.add_argument('--generate', type=str, help='Generate sample config file')
    parser.add_argument('--validate', type=str, help='Validate configuration file')
    
    args = parser.parse_args()
    
    if args.status:
        show_current_config()
    elif args.setup:
        setup_config_environment()
    elif args.generate:
        generate_sample_config(Path(args.generate))
    elif args.validate:
        validate_config(Path(args.validate))
    else:
        # Default: show status
        show_current_config()

if __name__ == '__main__':
    main()
