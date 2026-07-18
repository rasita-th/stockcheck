from .common import build_registry_entry, canonical_url, classify_headline, entity_confidence, headline_similarity
from .dedupe import deduplicate_events
from .discovery import collect_gdelt, collect_ir, gdelt_query_url, parse_feed
from .pipeline import NewsCollectionResult, collect_news_events

__all__ = ["NewsCollectionResult", "build_registry_entry", "canonical_url", "classify_headline", "collect_gdelt", "collect_ir", "collect_news_events", "deduplicate_events", "entity_confidence", "gdelt_query_url", "headline_similarity", "parse_feed"]
