"""Map discovery source names to their implementations."""
from typing import Callable, Any
from .config import config


# Registry of available discovery sources
SOURCE_REGISTRY: dict[str, dict[str, Any]] = {
    "yc_directory": {
        "enabled": config.enable_yc,
        "module": "src.sourcing.discovery.yc_directory",
        "description": "Y Combinator company directory",
        "rate_limit": 2.0,
    },
    "hacker_news": {
        "enabled": config.enable_hacker_news,
        "module": "src.sourcing.discovery.hacker_news",
        "description": "Hacker News Show HN and top posts",
        "rate_limit": 1.0,
    },
    "product_hunt": {
        "enabled": config.enable_product_hunt,
        "module": "src.sourcing.discovery.product_hunt",
        "description": "Product Hunt daily/weekly launches",
        "rate_limit": 1.0,
    },
    "opencorporates": {
        "enabled": config.enable_opencorporates,
        "module": "src.sourcing.discovery.opencorporates",
        "description": "OpenCorporates company registry",
        "rate_limit": 0.5,
    },
}


def get_enabled_sources() -> list[str]:
    """Return names of all enabled discovery sources."""
    return [name for name, meta in SOURCE_REGISTRY.items() if meta["enabled"]]


def get_source_config(source_name: str) -> dict[str, Any]:
    """Get configuration for a specific source."""
    if source_name not in SOURCE_REGISTRY:
        raise ValueError(f"Unknown discovery source: {source_name}")
    return SOURCE_REGISTRY[source_name]
