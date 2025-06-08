"""
Configuration Manager Module

Manages Clash proxy configurations with persistence, backup, and validation.
Provides template generation and configuration optimization features.
"""

import logging
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional

import yaml


class ConfigurationManager:
    """
    Manage proxy configurations with persistence and backup.

    Features:
    - Automatic configuration backup
    - Template-based config generation
    - Configuration validation
    - Optimization for different use cases
    """

    def __init__(self, config_dir: str = './clash_configs'):
        """
        Initialize configuration manager.

        Args:
            config_dir: Directory to store configurations
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        self.backup_dir = self.config_dir / 'backups'
        self.backup_dir.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)

    def generate_clash_config(self, proxies: List[Dict], config_type: str = 'scraping') -> Dict:
        """
        Generate optimized Clash configuration for specific use cases.

        Args:
            proxies: List of proxy configurations
            config_type: Configuration type ('scraping', 'general', 'speed')

        Returns:
            Complete Clash configuration dictionary
        """
        if not proxies:
            raise ValueError("No proxies provided for configuration generation")

        proxy_names = [proxy['name'] for proxy in proxies]

        # Base configuration template
        base_config = {
            'mixed-port': 7890,
            'allow-lan': False,
            'mode': 'rule',
            'log-level': 'info',
            'external-controller': '127.0.0.1:9090',
            'secret': '',
            'proxies': proxies
        }

        # Generate proxy groups based on config type
        if config_type == 'scraping':
            base_config.update(self._get_scraping_config(proxy_names))
        elif config_type == 'speed':
            base_config.update(self._get_speed_config(proxy_names))
        else:
            base_config.update(self._get_general_config(proxy_names))

        self.logger.info(f"Generated {config_type} configuration with {len(proxies)} proxies")
        return base_config

    def _get_scraping_config(self, proxy_names: List[str]) -> Dict:
        """Generate configuration optimized for web scraping."""
        return {
            'proxy-groups': [
                {
                    'name': 'PROXY',
                    'type': 'select',
                    'proxies': ['auto-fallback', 'load-balance'] + proxy_names
                },
                {
                    'name': 'auto-fallback',
                    'type': 'fallback',
                    'proxies': proxy_names,
                    'url': 'http://www.gstatic.com/generate_204',
                    'interval': 300,
                    'tolerance': 150
                },
                {
                    'name': 'load-balance',
                    'type': 'load-balance',
                    'proxies': proxy_names,
                    'url': 'http://www.gstatic.com/generate_204',
                    'interval': 300,
                    'strategy': 'round-robin'
                }
            ],
            'rules': [
                'DOMAIN-SUFFIX,googleapis.com,DIRECT',
                'DOMAIN-SUFFIX,gstatic.com,DIRECT',
                'MATCH,PROXY'
            ]
        }

    def _get_speed_config(self, proxy_names: List[str]) -> Dict:
        """Generate configuration optimized for speed."""
        return {
            'proxy-groups': [
                {
                    'name': 'PROXY',
                    'type': 'select',
                    'proxies': ['auto-speed'] + proxy_names
                },
                {
                    'name': 'auto-speed',
                    'type': 'url-test',
                    'proxies': proxy_names,
                    'url': 'http://www.gstatic.com/generate_204',
                    'interval': 180,
                    'tolerance': 50
                }
            ],
            'rules': [
                'MATCH,PROXY'
            ]
        }

    def _get_general_config(self, proxy_names: List[str]) -> Dict:
        """Generate general purpose configuration."""
        return {
            'proxy-groups': [
                {
                    'name': 'PROXY',
                    'type': 'select',
                    'proxies': ['auto'] + proxy_names
                },
                {
                    'name': 'auto',
                    'type': 'url-test',
                    'proxies': proxy_names,
                    'url': 'http://www.gstatic.com/generate_204',
                    'interval': 300
                }
            ],
            'rules': [
                'DOMAIN-SUFFIX,local,DIRECT',
                'IP-CIDR,127.0.0.0/8,DIRECT',
                'IP-CIDR,172.16.0.0/12,DIRECT',
                'IP-CIDR,192.168.0.0/16,DIRECT',
                'IP-CIDR,10.0.0.0/8,DIRECT',
                'MATCH,PROXY'
            ]
        }

    def save_configuration(self, config: Dict, config_name: str = 'clash_config.yaml') -> Path:
        """
        Save configuration with automatic backup.

        Args:
            config: Configuration dictionary
            config_name: Name of the configuration file

        Returns:
            Path to the saved configuration file
        """
        config_path = self.config_dir / config_name

        # Create backup if config exists
        if config_path.exists():
            backup_name = f"{config_name}.backup.{int(time.time())}"
            backup_path = self.backup_dir / backup_name
            shutil.copy2(config_path, backup_path)

            # Keep only recent backups (last 10)
            self._cleanup_old_backups(config_name)

        # Validate configuration before saving
        if not self.validate_configuration(config):
            raise ValueError("Invalid configuration provided")

        # Save new configuration
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)

        self.logger.info(f"Configuration saved to {config_path}")
        return config_path

    def load_configuration(self, config_name: str = 'clash_config.yaml') -> Optional[Dict]:
        """
        Load configuration from file.

        Args:
            config_name: Name of the configuration file

        Returns:
            Configuration dictionary or None if not found
        """
        config_path = self.config_dir / config_name

        if not config_path.exists():
            self.logger.warning(f"Configuration file not found: {config_path}")
            return None

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            if self.validate_configuration(config):
                self.logger.info(f"Configuration loaded from {config_path}")
                return config
            else:
                self.logger.error(f"Invalid configuration in {config_path}")
                return None

        except Exception as e:
            self.logger.error(f"Failed to load configuration from {config_path}: {e}")
            return None

    def validate_configuration(self, config: Dict) -> bool:
        """
        Validate Clash configuration.

        Args:
            config: Configuration dictionary

        Returns:
            True if configuration is valid
        """
        required_fields = ['proxies', 'proxy-groups', 'rules']

        # Check required top-level fields
        for field in required_fields:
            if field not in config:
                self.logger.error(f"Missing required field: {field}")
                return False

        # Validate proxies
        if not isinstance(config['proxies'], list) or not config['proxies']:
            self.logger.error("Proxies must be a non-empty list")
            return False

        # Validate proxy groups
        if not isinstance(config['proxy-groups'], list) or not config['proxy-groups']:
            self.logger.error("Proxy groups must be a non-empty list")
            return False

        # Validate rules
        if not isinstance(config['rules'], list) or not config['rules']:
            self.logger.error("Rules must be a non-empty list")
            return False

        return True

    def _cleanup_old_backups(self, config_name: str, keep_count: int = 10):
        """
        Clean up old backup files.

        Args:
            config_name: Name of the configuration file
            keep_count: Number of backups to keep
        """
        backup_pattern = f"{config_name}.backup.*"
        backup_files = list(self.backup_dir.glob(backup_pattern))

        if len(backup_files) > keep_count:
            # Sort by modification time and remove oldest
            backup_files.sort(key=lambda x: x.stat().st_mtime)
            for old_backup in backup_files[:-keep_count]:
                old_backup.unlink()
                self.logger.debug(f"Removed old backup: {old_backup}")

    def list_configurations(self) -> List[str]:
        """
        List all available configuration files.

        Returns:
            List of configuration file names
        """
        config_files = [f.name for f in self.config_dir.glob('*.yaml') if f.is_file()]
        return sorted(config_files)

    def get_configuration_info(self, config_name: str) -> Optional[Dict]:
        """
        Get information about a configuration file.

        Args:
            config_name: Name of the configuration file

        Returns:
            Dictionary with configuration information
        """
        config_path = self.config_dir / config_name

        if not config_path.exists():
            return None

        stat = config_path.stat()
        config = self.load_configuration(config_name)

        info = {
            'name': config_name,
            'path': str(config_path),
            'size': stat.st_size,
            'modified': stat.st_mtime,
            'valid': config is not None
        }

        if config:
            info.update({
                'proxy_count': len(config.get('proxies', [])),
                'group_count': len(config.get('proxy-groups', [])),
                'rule_count': len(config.get('rules', []))
            })

        return info
