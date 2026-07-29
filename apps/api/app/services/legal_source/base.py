"""LegalSourceProvider interface (see docs/PROJECT_PLAN.md §7).

`InternalKnowledgeProvider` (admin-uploaded material, see app/services/knowledge/)
was already implemented. This module adds the two providers that were previously
interface-only stubs, split by authentication scheme:
  - `PublicDataPortalProvider` (data.go.kr, serviceKey) — statute/admin-rule lists
  - `OpenLawProvider` (law.go.kr DRF, OC) — court cases + statute article detail
Both are sanctioned, documented public APIs meant for exactly this kind of
programmatic access, not an unauthorized scrape of the sites' HTML pages.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


class LegalSourceNotConfiguredError(Exception):
    """Raised when a provider requires an OC (기관코드) that hasn't been set."""


@dataclass
class ExternalLegalHit:
    source_type: str  # "STATUTE" | "COURT_CASE" | "ADMIN_RULE"
    title: str
    excerpt: str
    dedup_key: str  # stable identity used to avoid re-caching the same item
    law_name: str | None = None
    article_no: str | None = None
    case_number: str | None = None
    court: str | None = None
    decision_date: str | None = None
    effective_date: str | None = None
    detail_url: str | None = None
    mst: str | None = None  # 법령일련번호 — OpenLawProvider.get_statute_detail에 이어서 사용


class LegalSourceProvider(ABC):
    name: str = "base"

    @abstractmethod
    def search(self, query: str, limit: int) -> list[ExternalLegalHit]:
        ...
