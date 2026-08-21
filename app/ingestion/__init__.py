"""Input adapters that normalize external data before chunking/embedding."""

from .contracts import IngestionDocument
from .web_crawler import crawl_page

__all__ = ["IngestionDocument", "crawl_page"]
