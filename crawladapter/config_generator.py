#!/usr/bin/env python3
"""
CrawlAdapter Configuration Generator

Utility to generate configuration files for CrawlAdapter.
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, Any
import yaml

from .config_loader import ConfigLoader


def generate_user_config(output_path: Path, template: str = 'minimal') -> None:
    """
    Generate a user configuration file.
    
    Args:
        output_path: Path where to save the configuration file
        template: Template type ('minimal', 'full', 'scraping', 'speed')
    """
    templates = {
        'minimal': _get_minimal_config(),
        'full': _get_full_config(),
        'scraping': _get_scraping_config(),
        'speed': _get_speed_config()
    }
    
    if template not in templates:
        raise ValueError(f"Unknown template: {template}. Available: {list(templates.keys())}")
    
    config = templates[template]
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write configuration file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# CrawlAdapter Configuration\n")
        f.write(f"# Generated using template: {template}\n")
        f.write("# Modify as needed for your use case\n\n")
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, indent=2)
    
    print(f"✅ Configuration file generated: {output_path}")
    print(f"   Template: {template}")
    print(f"   Edit the file to customize your settings")


def _get_minimal_config() -> Dict[str, Any]:
    """Get minimal configuration template."""
    return {
        'proxy': {
            'port': 7890,
            'api_port': 9090
        },
        'health_check': {
            'timeout': 15,
            'test_urls': [
                'http://httpbin.org/ip',
                'http://www.gstatic.com/generate_204'
            ]
        },
        'routing': {
            'enable_default_rules': True,
            'default_rules': [
                '*.panewslab.com',
                '*.httpbin.org'
            ]
        }
    }


def _get_full_config() -> Dict[str, Any]:
    """Get full configuration template with all options."""
    loader = ConfigLoader()
    return loader.load_default_config()


def _get_scraping_config() -> Dict[str, Any]:
    """Get configuration optimized for web scraping."""
    return {
        'proxy': {
            'port': 7890,
            'api_port': 9090,
            'timeout': 30
        },
        'health_check': {
            'timeout': 15,
            'max_concurrent': 10,
            'min_success_rate': 0.1,
            'test_urls': [
                'http://httpbin.org/ip',
                'http://www.gstatic.com/generate_204',
                'https://ifconfig.co/json'
            ]
        },
        'routing': {
            'enable_default_rules': True,
            'default_rules': [
                '*.panewslab.com',
                '*.coindesk.com',
                '*.cointelegraph.com',
                '*.httpbin.org',
                '*.ifconfig.co'
            ]
        },
        'node_fetching': {
            'timeout': 30,
            'max_retries': 3
        },
        'logging': {
            'level': 'INFO'
        }
    }


def _get_speed_config() -> Dict[str, Any]:
    """Get configuration optimized for speed."""
    return {
        'proxy': {
            'port': 7890,
            'api_port': 9090,
            'timeout': 15
        },
        'health_check': {
            'timeout': 10,
            'max_concurrent': 20,
            'min_success_rate': 0.2,
            'test_urls': [
                'http://www.gstatic.com/generate_204'
            ],
            'adaptive': {
                'base_interval': 180,  # 3 minutes
                'min_interval': 30,    # 30 seconds
                'max_interval': 900    # 15 minutes
            }
        },
        'routing': {
            'enable_default_rules': False
        },
        'performance': {
            'enable_monitoring': True,
            'metrics_interval': 30
        },
        'logging': {
            'level': 'WARNING'
        }
    }


def validate_config_file(config_path: Path) -> bool:
    """
    Validate a configuration file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        True if valid, False otherwise
    """
    try:
        loader = ConfigLoader()
        config = loader.load_config_file(config_path)
        
        # Basic validation
        required_sections = ['proxy']
        for section in required_sections:
            if section not in config:
                print(f"❌ Missing required section: {section}")
                return False
        
        # Validate proxy section
        proxy_config = config.get('proxy', {})
        if 'port' not in proxy_config:
            print("❌ Missing proxy.port configuration")
            return False
        
        if not isinstance(proxy_config['port'], int):
            print("❌ proxy.port must be an integer")
            return False
        
        if not (1 <= proxy_config['port'] <= 65535):
            print("❌ proxy.port must be between 1 and 65535")
            return False
        
        print("✅ Configuration file is valid")
        return True
        
    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
        return False


def show_config_info(config_path: Path = None) -> None:
    """
    Show information about current configuration.
    
    Args:
        config_path: Optional path to specific config file
    """
    try:
        loader = ConfigLoader()
        
        if config_path:
            config = loader.load_config_file(config_path)
            print(f"Configuration from: {config_path}")
        else:
            config = loader.load_complete_config()
            print("Complete configuration (all sources merged)")
        
        print("\nConfiguration summary:")
        print(f"  Proxy port: {config.get('proxy', {}).get('port', 'not set')}")
        print(f"  API port: {config.get('proxy', {}).get('api_port', 'not set')}")
        print(f"  Health check timeout: {config.get('health_check', {}).get('timeout', 'not set')}")
        print(f"  Default rules enabled: {config.get('routing', {}).get('enable_default_rules', 'not set')}")
        
        # Show test URLs
        test_urls = config.get('health_check', {}).get('test_urls', [])
        if test_urls:
            print(f"  Test URLs ({len(test_urls)}):")
            for url in test_urls[:3]:  # Show first 3
                print(f"    - {url}")
            if len(test_urls) > 3:
                print(f"    ... and {len(test_urls) - 3} more")
        
        # Show default rules
        default_rules = config.get('routing', {}).get('default_rules', [])
        if default_rules:
            print(f"  Default rules ({len(default_rules)}):")
            for rule in default_rules[:3]:  # Show first 3
                print(f"    - {rule}")
            if len(default_rules) > 3:
                print(f"    ... and {len(default_rules) - 3} more")
        
    except Exception as e:
        print(f"❌ Failed to show configuration info: {e}")


def main():
    """Main entry point for configuration generator."""
    parser = argparse.ArgumentParser(
        description="CrawlAdapter Configuration Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate minimal configuration
  python -m crawladapter.config_generator generate --template minimal

  # Generate full configuration with all options
  python -m crawladapter.config_generator generate --template full --output ~/.crawladapter/config.yaml

  # Generate scraping-optimized configuration
  python -m crawladapter.config_generator generate --template scraping

  # Validate existing configuration
  python -m crawladapter.config_generator validate --config ~/.crawladapter/config.yaml

  # Show current configuration info
  python -m crawladapter.config_generator info
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Generate command
    generate_parser = subparsers.add_parser('generate', help='Generate configuration file')
    generate_parser.add_argument(
        '--template', 
        choices=['minimal', 'full', 'scraping', 'speed'],
        default='minimal',
        help='Configuration template to use'
    )
    generate_parser.add_argument(
        '--output', '-o',
        type=Path,
        default=Path('./crawladapter_config.yaml'),
        help='Output file path'
    )
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate configuration file')
    validate_parser.add_argument(
        '--config', '-c',
        type=Path,
        required=True,
        help='Configuration file to validate'
    )
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show configuration information')
    info_parser.add_argument(
        '--config', '-c',
        type=Path,
        help='Specific configuration file to show (optional)'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        if args.command == 'generate':
            generate_user_config(args.output, args.template)
        elif args.command == 'validate':
            if not validate_config_file(args.config):
                return 1
        elif args.command == 'info':
            show_config_info(args.config)
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
