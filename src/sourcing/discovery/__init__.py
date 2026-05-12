"""
Discovery source registry — ordered roughly by data_sourcing_map fallback chains.
Tier A: YC, Product Hunt, Open Corporates; Tier B: HN, LinkedIn.
"""
from __future__ import annotations

from discovery.base import DiscoveryContext, DiscoveryResult, DiscoverySource
from discovery.hacker_news import HackerNewsDiscovery
from discovery.linkedin_company import LinkedInCompanyDiscovery
from discovery.opencorporates import OpenCorporatesDiscovery
from discovery.product_hunt import ProductHuntDiscovery
from discovery.yc_directory import YCDirectoryDiscovery

DISCOVERY_SOURCES: list[DiscoverySource] = [
    YCDirectoryDiscovery(),
    ProductHuntDiscovery(),
    OpenCorporatesDiscovery(),
    HackerNewsDiscovery(),
    LinkedInCompanyDiscovery(),
]

__all__ = [
    "DISCOVERY_SOURCES",
    "DiscoveryContext",
    "DiscoveryResult",
    "DiscoverySource",
]
