"""
Rule Management for CrawlAdapter

Consolidates RuleManager, RuleTemplates, and routing rule functionality.
"""

import logging
import re
import ipaddress
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse
from enum import Enum


class RuleCategory(Enum):
    """Categories of routing rules."""
    IP_TESTING = "ip_testing"
    NEWS_SCRAPING = "news_scraping"
    LOCAL_NETWORK = "local_network"
    DEVELOPMENT = "development"
    CDN_RESOURCES = "cdn_resources"
    FINANCIAL_APIS = "financial_apis"
    REGIONAL_SITES = "regional_sites"


class RuleTemplates:
    """
    Modular rule templates for different use cases.
    
    This class provides pre-defined rule sets that can be mixed and matched
    based on user requirements, making the configuration more flexible and maintainable.
    """
    
    @staticmethod
    def get_ip_testing_rules() -> List[str]:
        """Rules for IP testing and verification services."""
        return [
            'DOMAIN-SUFFIX,httpbin.org,PROXY',
            'DOMAIN-SUFFIX,ipinfo.io,PROXY',
            'DOMAIN-SUFFIX,ifconfig.co,PROXY',
            'DOMAIN-SUFFIX,ifconfig.me,PROXY',
            'DOMAIN-SUFFIX,checkip.amazonaws.com,PROXY',
            'DOMAIN-SUFFIX,ipify.org,PROXY',
            'DOMAIN-SUFFIX,icanhazip.com,PROXY',
            'DOMAIN-SUFFIX,ident.me,PROXY',
            'DOMAIN-SUFFIX,gstatic.com,PROXY',
            'DOMAIN-SUFFIX,detectportal.firefox.com,PROXY',
            'DOMAIN-SUFFIX,connectivitycheck.platform.hicloud.com,PROXY',
            'DOMAIN-KEYWORD,whatismyip,PROXY',
            'DOMAIN-KEYWORD,checkip,PROXY',
            'DOMAIN-KEYWORD,myip,PROXY',
        ]
    
    @staticmethod
    def get_news_scraping_rules() -> List[str]:
        """Rules for news and content scraping."""
        return [
            'DOMAIN-SUFFIX,panewslab.com,PROXY',
            'DOMAIN-KEYWORD,panewslab,PROXY',
            # Common news sites that may require proxy
            'DOMAIN-SUFFIX,coindesk.com,PROXY',
            'DOMAIN-SUFFIX,cointelegraph.com,PROXY',
            'DOMAIN-SUFFIX,decrypt.co,PROXY',
            'DOMAIN-SUFFIX,theblock.co,PROXY',
        ]
    
    @staticmethod
    def get_local_network_rules() -> List[str]:
        """Rules for local network traffic."""
        return [
            'DOMAIN-SUFFIX,local,DIRECT',
            'IP-CIDR,127.0.0.0/8,DIRECT',
            'IP-CIDR,172.16.0.0/12,DIRECT',
            'IP-CIDR,192.168.0.0/16,DIRECT',
            'IP-CIDR,10.0.0.0/8,DIRECT',
        ]
    
    @staticmethod
    def get_development_rules() -> List[str]:
        """Rules for development tools and package managers."""
        return [
            'DOMAIN-SUFFIX,pypi.org,DIRECT',
            'DOMAIN-SUFFIX,npmjs.com,DIRECT',
            'DOMAIN-SUFFIX,maven.org,DIRECT',
            'DOMAIN-SUFFIX,gradle.org,DIRECT',
            'DOMAIN-SUFFIX,github.com,DIRECT',
            'DOMAIN-SUFFIX,githubusercontent.com,DIRECT',
        ]
    
    @staticmethod
    def get_cdn_rules() -> List[str]:
        """Rules for CDN and static resources."""
        return [
            'DOMAIN-SUFFIX,cloudflare.com,DIRECT',
            'DOMAIN-SUFFIX,jsdelivr.net,DIRECT',
            'DOMAIN-SUFFIX,unpkg.com,DIRECT',
            'DOMAIN-SUFFIX,cdnjs.cloudflare.com,DIRECT',
            'DOMAIN-SUFFIX,googleapis.com,DIRECT',
        ]
    
    @staticmethod
    def get_financial_api_rules() -> List[str]:
        """Rules for financial and trading APIs."""
        return [
            'DOMAIN-SUFFIX,binance.com,DIRECT',
            'DOMAIN-SUFFIX,coinbase.com,DIRECT',
            'DOMAIN-SUFFIX,kraken.com,DIRECT',
            'DOMAIN-SUFFIX,okx.com,DIRECT',
        ]
    
    @staticmethod
    def get_minimal_rules() -> List[str]:
        """Minimal rule set for basic functionality."""
        return [
            # Local network
            'IP-CIDR,127.0.0.0/8,DIRECT',
            'IP-CIDR,192.168.0.0/16,DIRECT',
            'IP-CIDR,10.0.0.0/8,DIRECT',
            # Default
            'MATCH,DIRECT'
        ]
    
    @staticmethod
    def build_custom_rules(categories: List[RuleCategory], 
                          custom_rules: Optional[List[str]] = None,
                          default_action: str = 'DIRECT') -> List[str]:
        """
        Build custom rule set from selected categories.
        
        Args:
            categories: List of rule categories to include
            custom_rules: Additional custom rules to include
            default_action: Default action for unmatched traffic ('DIRECT' or 'PROXY')
            
        Returns:
            Combined list of rules
        """
        rules = []
        
        # Add rules from selected categories
        for category in categories:
            if category == RuleCategory.IP_TESTING:
                rules.extend(RuleTemplates.get_ip_testing_rules())
            elif category == RuleCategory.NEWS_SCRAPING:
                rules.extend(RuleTemplates.get_news_scraping_rules())
            elif category == RuleCategory.LOCAL_NETWORK:
                rules.extend(RuleTemplates.get_local_network_rules())
            elif category == RuleCategory.DEVELOPMENT:
                rules.extend(RuleTemplates.get_development_rules())
            elif category == RuleCategory.CDN_RESOURCES:
                rules.extend(RuleTemplates.get_cdn_rules())
            elif category == RuleCategory.FINANCIAL_APIS:
                rules.extend(RuleTemplates.get_financial_api_rules())
        
        # Add custom rules if provided
        if custom_rules:
            rules.extend(custom_rules)
        
        # Add default rule
        rules.append(f'MATCH,{default_action}')
        
        return rules
    
    @staticmethod
    def get_available_categories() -> Dict[str, str]:
        """Get available rule categories with descriptions."""
        return {
            RuleCategory.IP_TESTING.value: "IP testing and verification services",
            RuleCategory.NEWS_SCRAPING.value: "News and content scraping sites",
            RuleCategory.LOCAL_NETWORK.value: "Local network traffic",
            RuleCategory.DEVELOPMENT.value: "Development tools and package managers",
            RuleCategory.CDN_RESOURCES.value: "CDN and static resources",
            RuleCategory.FINANCIAL_APIS.value: "Financial and trading APIs",
        }


class RuleManager:
    """
    Manages custom routing rules for selective proxy usage.
    
    Consolidates rule management functionality with enhanced pattern matching.
    """

    def __init__(self):
        """Initialize rule manager."""
        self.domain_rules: Set[str] = set()
        self.ip_rules: List[ipaddress.IPv4Network] = []
        self.pattern_rules: List[re.Pattern] = []
        self.cache: Dict[str, bool] = {}
        self.cache_size_limit = 1000
        self.logger = logging.getLogger(__name__)

    def add_rules(self, rules: List[str]) -> None:
        """
        Add routing rules.

        Args:
            rules: List of rules (domains, IPs, or patterns)
        """
        for rule in rules:
            self.add_rule(rule)
        
        self.logger.info(f"Added {len(rules)} routing rules")

    def add_rule(self, rule: str) -> None:
        """
        Add a single routing rule.

        Args:
            rule: Rule string (domain, IP/CIDR, or pattern)
        """
        rule = rule.strip()
        if not rule:
            return

        try:
            # Check if it's an IP or CIDR
            if '/' in rule:
                # CIDR notation
                network = ipaddress.IPv4Network(rule, strict=False)
                self.ip_rules.append(network)
            elif self._is_ip_address(rule):
                # Single IP
                network = ipaddress.IPv4Network(f"{rule}/32", strict=False)
                self.ip_rules.append(network)
            elif '*' in rule or '?' in rule:
                # Pattern with wildcards
                pattern = self._wildcard_to_regex(rule)
                compiled_pattern = re.compile(pattern, re.IGNORECASE)
                self.pattern_rules.append(compiled_pattern)
            else:
                # Domain rule
                self.domain_rules.add(rule.lower())

        except Exception as e:
            self.logger.warning(f"Invalid rule '{rule}': {e}")

    def should_use_proxy(self, url_or_host: str) -> bool:
        """
        Check if URL or hostname should use proxy.

        Args:
            url_or_host: URL or hostname to check

        Returns:
            True if should use proxy
        """
        # Check cache first
        if url_or_host in self.cache:
            return self.cache[url_or_host]

        # Extract hostname from URL if needed
        hostname = self._extract_hostname(url_or_host)
        if not hostname:
            return False

        # Check rules
        result = self._check_rules(hostname)

        # Cache result (with size limit)
        if len(self.cache) >= self.cache_size_limit:
            # Remove oldest entries (simple FIFO)
            oldest_keys = list(self.cache.keys())[:100]
            for key in oldest_keys:
                del self.cache[key]

        self.cache[url_or_host] = result
        return result

    def _check_rules(self, hostname: str) -> bool:
        """Check hostname against all rules."""
        # Check IP rules first
        if self._is_ip_address(hostname):
            try:
                ip = ipaddress.IPv4Address(hostname)
                for network in self.ip_rules:
                    if ip in network:
                        return True
            except ValueError:
                pass

        # Check domain rules
        hostname_lower = hostname.lower()
        
        # Exact match
        if hostname_lower in self.domain_rules:
            return True

        # Check subdomains
        parts = hostname_lower.split('.')
        for i in range(len(parts)):
            subdomain = '.'.join(parts[i:])
            if subdomain in self.domain_rules:
                return True

        # Check pattern rules
        for pattern in self.pattern_rules:
            if pattern.search(hostname):
                return True

        return False

    def _extract_hostname(self, url_or_host: str) -> str:
        """Extract hostname from URL or return hostname as-is."""
        if '://' in url_or_host:
            # It's a URL
            try:
                parsed = urlparse(url_or_host)
                return parsed.hostname or ''
            except Exception:
                return ''
        else:
            # It's already a hostname
            return url_or_host

    def _is_ip_address(self, text: str) -> bool:
        """Check if text is an IP address."""
        try:
            ipaddress.IPv4Address(text)
            return True
        except ValueError:
            return False

    def _wildcard_to_regex(self, pattern: str) -> str:
        """Convert wildcard pattern to regex."""
        # Escape special regex characters except * and ?
        escaped = re.escape(pattern)
        # Replace escaped wildcards with regex equivalents
        escaped = escaped.replace(r'\*', '.*')
        escaped = escaped.replace(r'\?', '.')
        return f'^{escaped}$'

    def get_rules(self) -> Dict[str, List[str]]:
        """
        Get current rules organized by type.

        Returns:
            Dictionary with rule types and their values
        """
        return {
            'domains': list(self.domain_rules),
            'ips': [str(network) for network in self.ip_rules],
            'patterns': [pattern.pattern for pattern in self.pattern_rules]
        }

    def clear_rules(self) -> None:
        """Clear all rules and cache."""
        self.domain_rules.clear()
        self.ip_rules.clear()
        self.pattern_rules.clear()
        self.cache.clear()
        self.logger.info("Cleared all routing rules")

    def load_default_rules(self) -> None:
        """Load default routing rules for common use cases."""
        default_rules = [
            # Local development
            'localhost',
            '127.0.0.1',
            '192.168.*',
            '10.*',
            '172.16.*',
            
            # Common development domains
            '*.local',
            '*.dev',
            '*.test',
            
            # Package managers and development tools
            'pypi.org',
            'npmjs.com',
            'github.com',
            'githubusercontent.com',
        ]
        
        self.add_rules(default_rules)
        self.logger.info("Loaded default routing rules")

    def get_statistics(self) -> Dict[str, int]:
        """Get rule statistics."""
        return {
            'domain_rules': len(self.domain_rules),
            'ip_rules': len(self.ip_rules),
            'pattern_rules': len(self.pattern_rules),
            'cache_entries': len(self.cache),
            'total_rules': len(self.domain_rules) + len(self.ip_rules) + len(self.pattern_rules)
        }
