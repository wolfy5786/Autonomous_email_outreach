"""
Discovery source registry — ordered roughly by data_sourcing_map fallback chains.
Software: YC → Product Hunt → HN. Healthcare: NIH → YC. Tier B sources last.
"""
from __future__ import annotations

from discovery.base import DiscoveryContext, DiscoveryResult, DiscoverySource
from discovery.crunchbase import CrunchbaseDiscovery
from discovery.github_trending import GitHubTrendingDiscovery
from discovery.hacker_news import HackerNewsDiscovery
from discovery.linkedin_company import LinkedInCompanyDiscovery
from discovery.nih_reporter import NIHReporterDiscovery
from discovery.opencorporates import OpenCorporatesDiscovery
from discovery.product_hunt import ProductHuntDiscovery
from discovery.yc_directory import YCDirectoryDiscovery

DISCOVERY_SOURCES: list[DiscoverySource] = [
    YCDirectoryDiscovery(),
    NIHReporterDiscovery(),
    ProductHuntDiscovery(),
    CrunchbaseDiscovery(),
    OpenCorporatesDiscovery(),
    GitHubTrendingDiscovery(),
    HackerNewsDiscovery(),
    LinkedInCompanyDiscovery(),
]

__all__ = [
    "DISCOVERY_SOURCES",
    "DiscoveryContext",
    "DiscoveryResult",
    "DiscoverySource",
]
