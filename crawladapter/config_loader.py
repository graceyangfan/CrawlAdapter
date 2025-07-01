"""
CrawlAdapter Configuration Loader

Handles loading and merging configuration from multiple sources:
1. Default configuration (built-in)
2. System configuration file
3. User configuration file
4. Environment variables
5. Runtime parameters
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
import yaml

from .types import ProxyConfig
from .exceptions import ConfigurationError


class ConfigLoader:
    """
    Configuration loader with hierarchical configuration support.
    
    Configuration sources (in order of precedence):
    1. Runtime parameters (highest priority)
    2. Environment variables
    3. User config file (~/.crawladapter/config.yaml)
    4. System config file (/etc/crawladapter/config.yaml)
    5. Default configuration (lowest priority)
    """
    
    def __init__(self):
        """Initialize configuration loader."""
        self.logger = logging.getLogger(__name__)
        self._default_config: Optional[Dict] = None
        self._loaded_config: Optional[Dict] = None
    
    def load_default_config(self) -> Dict[str, Any]:
        """Load default configuration from template."""
        if self._default_config is not None:
            return self._default_config
        
        try:
            # Get path to default config template
            config_template_path = Path(__file__).parent / 'config_templates' / 'default_config.yaml'
            
            if not config_template_path.exists():
                self.logger.warning(f"Default config template not found: {config_template_path}")
                return self._get_fallback_config()
            
            with open(config_template_path, 'r', encoding='utf-8') as f:
                self._default_config = yaml.safe_load(f)
            
            self.logger.debug("Loaded default configuration from template")
            return self._default_config
            
        except Exception as e:
            self.logger.error(f"Failed to load default configuration: {e}")
            return self._get_fallback_config()
    
    def _get_fallback_config(self) -> Dict[str, Any]:
        """Get minimal fallback configuration if default config fails to load."""
        return {
            'proxy': {
                'port': 7890,
                'api_port': 9090,
                'timeout': 30,
                'max_retries': 3
            },
            'health_check': {
                'timeout': 15,
                'max_concurrent': 10,
                'min_success_rate': 0.1,
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
            },
            'logging': {
                'level': 'INFO'
            }
        }
    
    def load_config_file(self, config_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Load configuration from a YAML file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Configuration dictionary
            
        Raises:
            ConfigurationError: If file cannot be loaded
        """
        try:
            config_path = Path(config_path)
            
            if not config_path.exists():
                raise ConfigurationError(
                    f"Configuration file not found: {config_path}",
                    config_path=str(config_path)
                )
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            if not isinstance(config, dict):
                raise ConfigurationError(
                    f"Invalid configuration file format: {config_path}",
                    config_path=str(config_path)
                )
            
            self.logger.info(f"Loaded configuration from: {config_path}")
            return config
            
        except yaml.YAMLError as e:
            raise ConfigurationError(
                f"Invalid YAML in configuration file: {config_path}",
                config_path=str(config_path)
            ) from e
        except Exception as e:
            raise ConfigurationError(
                f"Failed to load configuration file: {config_path}",
                config_path=str(config_path)
            ) from e
    
    def load_from_environment(self) -> Dict[str, Any]:
        """
        Load configuration from environment variables.
        
        Environment variables should be prefixed with CRAWLADAPTER_
        and use double underscores for nested keys.
        
        Examples:
            CRAWLADAPTER_PROXY__PORT=7891
            CRAWLADAPTER_HEALTH_CHECK__TIMEOUT=20
            CRAWLADAPTER_ROUTING__ENABLE_DEFAULT_RULES=false
        
        Returns:
            Configuration dictionary from environment variables
        """
        config = {}
        prefix = 'CRAWLADAPTER_'
        
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            
            # Remove prefix and convert to lowercase
            config_key = key[len(prefix):].lower()
            
            # Split nested keys (double underscore separator)
            key_parts = config_key.split('__')
            
            # Convert string values to appropriate types
            converted_value = self._convert_env_value(value)
            
            # Set nested dictionary value
            current_dict = config
            for part in key_parts[:-1]:
                if part not in current_dict:
                    current_dict[part] = {}
                current_dict = current_dict[part]
            
            current_dict[key_parts[-1]] = converted_value
        
        if config:
            self.logger.debug(f"Loaded {len(config)} configuration sections from environment")
        
        return config
    
    def _convert_env_value(self, value: str) -> Any:
        """Convert environment variable string to appropriate type."""
        # Boolean values
        if value.lower() in ('true', 'yes', '1', 'on'):
            return True
        elif value.lower() in ('false', 'no', '0', 'off'):
            return False
        
        # Numeric values
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # List values (comma-separated)
        if ',' in value:
            return [item.strip() for item in value.split(',')]
        
        # String value
        return value
    
    def merge_configs(self, *configs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge multiple configuration dictionaries.
        
        Later configurations override earlier ones.
        Nested dictionaries are merged recursively.
        
        Args:
            *configs: Configuration dictionaries to merge
            
        Returns:
            Merged configuration dictionary
        """
        result = {}
        
        for config in configs:
            if not config:
                continue
            
            result = self._deep_merge(result, config)
        
        return result
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def load_complete_config(
        self,
        config_file: Optional[Union[str, Path]] = None,
        runtime_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Load complete configuration from all sources.
        
        Args:
            config_file: Optional path to user configuration file
            runtime_config: Optional runtime configuration overrides
            
        Returns:
            Complete merged configuration
        """
        configs_to_merge = []
        
        # 1. Default configuration (lowest priority)
        default_config = self.load_default_config()
        configs_to_merge.append(default_config)
        
        # 2. System configuration file
        system_config_path = Path('/etc/crawladapter/config.yaml')
        if system_config_path.exists():
            try:
                system_config = self.load_config_file(system_config_path)
                configs_to_merge.append(system_config)
            except Exception as e:
                self.logger.warning(f"Failed to load system config: {e}")
        
        # 3. User configuration file
        if config_file:
            user_config = self.load_config_file(config_file)
            configs_to_merge.append(user_config)
        else:
            # Try default user config location
            user_config_path = Path.home() / '.crawladapter' / 'config.yaml'
            if user_config_path.exists():
                try:
                    user_config = self.load_config_file(user_config_path)
                    configs_to_merge.append(user_config)
                except Exception as e:
                    self.logger.warning(f"Failed to load user config: {e}")
        
        # 4. Environment variables
        env_config = self.load_from_environment()
        if env_config:
            configs_to_merge.append(env_config)
        
        # 5. Runtime configuration (highest priority)
        if runtime_config:
            configs_to_merge.append(runtime_config)
        
        # Merge all configurations
        self._loaded_config = self.merge_configs(*configs_to_merge)
        
        self.logger.info(f"Loaded configuration from {len(configs_to_merge)} sources")
        return self._loaded_config
    
    def create_proxy_config(
        self,
        config_file: Optional[Union[str, Path]] = None,
        runtime_config: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ProxyConfig:
        """
        Create ProxyConfig object from loaded configuration.
        
        Args:
            config_file: Optional path to configuration file
            runtime_config: Optional runtime configuration
            **kwargs: Additional runtime parameters
            
        Returns:
            ProxyConfig object
        """
        # Merge kwargs into runtime config
        if kwargs:
            runtime_config = self.merge_configs(runtime_config or {}, kwargs)
        
        # Load complete configuration
        config = self.load_complete_config(config_file, runtime_config)
        
        # Extract proxy-specific configuration
        proxy_config = config.get('proxy', {})
        
        return ProxyConfig(
            config_dir=kwargs.get('config_dir', './clash_configs'),
            clash_binary_path=kwargs.get('clash_binary_path'),
            proxy_port=proxy_config.get('port', 7890),
            api_port=proxy_config.get('api_port', 9090),
            auto_update_interval=kwargs.get('auto_update_interval', 3600),
            enable_default_rules=config.get('routing', {}).get('enable_default_rules', True),
            enable_adaptive_health_check=kwargs.get('enable_adaptive_health_check', False),
            enable_metrics=kwargs.get('enable_metrics', False)
        )
    
    def get_config_value(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path to configuration value (e.g., 'proxy.port')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        if self._loaded_config is None:
            self.load_complete_config()
        
        current = self._loaded_config
        for key in key_path.split('.'):
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        
        return current


# Global configuration loader instance
_config_loader = ConfigLoader()

def get_config_loader() -> ConfigLoader:
    """Get the global configuration loader instance."""
    return _config_loader

def load_config(config_file: Optional[Union[str, Path]] = None, **kwargs) -> Dict[str, Any]:
    """
    Convenience function to load configuration.
    
    Args:
        config_file: Optional path to configuration file
        **kwargs: Runtime configuration parameters
        
    Returns:
        Complete configuration dictionary
    """
    return _config_loader.load_complete_config(config_file, kwargs)

def create_proxy_config(config_file: Optional[Union[str, Path]] = None, **kwargs) -> ProxyConfig:
    """
    Convenience function to create ProxyConfig.
    
    Args:
        config_file: Optional path to configuration file
        **kwargs: Runtime configuration parameters
        
    Returns:
        ProxyConfig object
    """
    return _config_loader.create_proxy_config(config_file, **kwargs)
