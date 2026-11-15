"""Setup configuration for the Godlike SEO Toolkit."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [
        line.strip() for line in fh if line.strip() and not line.startswith("#")
    ]

setup(
    name="godlike-seo-toolkit",
    version="3.3.1",
    author="Godlike SEO Team",
    author_email="team@godlikeseo.dev",
    license="GPL-3.0-or-later",
    description=(
        "A comprehensive, production-grade Python SEO analysis toolkit "
        "featuring async web crawling, on-page analysis, SERP tracking, "
        "competitor comparison, and automated reporting."
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/godlike-seo/godlike-seo",
    project_urls={
        "Bug Tracker": "https://github.com/godlike-seo/godlike-seo/issues",
        "Documentation": "https://github.com/godlike-seo/godlike-seo/wiki",
        "Source Code": "https://github.com/godlike-seo/godlike-seo",
    },
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "Topic :: Internet :: WWW/HTTP :: Site Management",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Framework :: Flask",
        "Typing :: Typed",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-asyncio>=0.21",
            "pytest-cov>=4.0",
            "black>=23.0",
            "ruff>=0.1.0",
            "mypy>=1.5",
        ],
        "playwright": [
            "playwright>=1.40.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "godlike-seo=godlike_seo.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords=[
        "seo",
        "search-engine-optimization",
        "web-crawler",
        "site-audit",
        "serp-analysis",
        "seo-analysis",
        "competitor-analysis",
        "web-scraping",
    ],
)
