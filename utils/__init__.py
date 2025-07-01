"""
CrawlAdapter Utilities

Utility functions and tools for CrawlAdapter setup and management.
"""

from .clash_installer import (
    download_clash_binary,
    setup_clash_environment,
    check_clash_installation,
    get_clash_binary_path
)

from .config_helper import (
    get_config_paths,
    create_user_config_dir,
    generate_sample_config,
    show_current_config,
    validate_config,
    setup_config_environment
)

__all__ = [
    # Clash installer
    'download_clash_binary',
    'setup_clash_environment',
    'check_clash_installation',
    'get_clash_binary_path',

    # Config helper
    'get_config_paths',
    'create_user_config_dir',
    'generate_sample_config',
    'show_current_config',
    'validate_config',
    'setup_config_environment'
]
