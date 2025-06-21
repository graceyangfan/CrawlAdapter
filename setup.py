"""
Setup script for CrawlAdapter

A comprehensive and extensible proxy management library built on Clash, designed
for web scraping applications that require intelligent proxy rotation, custom
routing rules, and seamless integration with various scraping frameworks.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_path.exists():
    requirements = requirements_path.read_text(encoding="utf-8").strip().split('\n')
    requirements = [req.strip() for req in requirements if req.strip() and not req.startswith('#')]

setup(
    name="crawladapter",
    version="1.0.0",
    author="CrawlAdapter Team",
    author_email="contact@crawladapter.com",
    description="Universal Proxy Management for Web Scraping",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/graceyangfan/CrawlAdapter",
    packages=find_packages(exclude=["tests*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Networking",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-asyncio>=0.18.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "flake8>=3.8",
            "mypy>=0.800",
        ],
    },
    entry_points={
        "console_scripts": [
            "crawladapter-setup=clash_installer:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.yml", "*.json", "*.txt", "*.md"],
    },
    keywords="proxy, web scraping, clash, http, networking, automation",
    project_urls={
        "Bug Reports": "https://github.com/graceyangfan/CrawlAdapter/issues",
        "Source": "https://github.com/graceyangfan/CrawlAdapter",
        "Documentation": "https://github.com/graceyangfan/CrawlAdapter/blob/main/README.md",
    },
)
