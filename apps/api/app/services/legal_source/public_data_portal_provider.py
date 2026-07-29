"""공공데이터포털(data.go.kr) REST API — 법제처 국가법령정보 공유서비스.

법령·행정규칙의 "목록 및 메타정보" 조회 전용. 판례는 이 서비스가 아니라 공공데이터포털 화면상
LINK 유형으로 안내되는 `OpenLawProvider`(law.go.kr DRF, OC 인증)로 처리한다 — 이 Provider의
serviceKey를 판례 API에 사용하지 않는다.
"""
import xml.etree.ElementTree as ET

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from app.core.config import get_settings
from app.services.legal_source.base import ExternalLegalHit, LegalSourceNotConfiguredError, LegalSourceProvider
from app.services.legal_source.rate_limit import check_rate_limit
from app.services.legal_source.xml_utils import first, text_map

settings = get_settings()


class PublicDataPortalProvider(LegalSourceProvider):
    """법령·행정규칙 목록/메타정보. 본문(조문) 조회는 다루지 않는다 — 필요하면
    `OpenLawProvider.get_statute_detail`로 이어서 조회한다."""

    name = "public_data_portal"

    def _require_key(self) -> str:
        if not settings.PUBLIC_DATA_SERVICE_KEY:
            raise LegalSourceNotConfiguredError(
                "공공데이터포털 서비스키(PUBLIC_DATA_SERVICE_KEY)가 설정되지 않았습니다. "
                "https://www.data.go.kr 에서 '법제처_국가법령정보 공동활용' 활용신청 후 "
                "디코딩된 서비스키를 .env에 설정하세요."
            )
        return settings.PUBLIC_DATA_SERVICE_KEY

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_fixed(1),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
        reraise=True,
    )
    def _get(self, path: str, params: dict) -> ET.Element:
        # serviceKey는 디코딩된 값을 그대로 넘긴다 — httpx가 params 인코딩을 한 번만 수행하도록
        # 하기 위함이다(이미 인코딩된 키를 넣으면 이중 인코딩되어 인증이 실패한다).
        with httpx.Client(timeout=settings.EXTERNAL_LEGAL_TIMEOUT) as client:
            response = client.get(f"{settings.PUBLIC_DATA_PORTAL_BASE_URL.rstrip('/')}/{path}", params=params)
            response.raise_for_status()
            return ET.fromstring(response.content)

    def search(self, query: str, limit: int, target: str = "law") -> list[ExternalLegalHit]:
        """target: "law"(법령) | "admrul"(행정규칙, 공식 문서상 이 엔드포인트의 target은 "law"
        고정값으로 안내되어 있어 동작이 보장되지 않는다 — 필요 시 별도 상품/엔드포인트 확인 필요)."""
        service_key = self._require_key()
        check_rate_limit(self.name)

        # 공공데이터포털 공식 명세(data.go.kr/data/15000115/openapi.do)의 필수 파라미터는
        # serviceKey/target/query/numOfRows/pageNo 다섯 개다. 이전에는 "display"라는 존재하지
        # 않는 파라미터명을 쓰고 필수인 "pageNo"를 아예 빼먹어서 law.go.kr 쪽에서 요청 자체를
        # 인식하지 못해 500(페이지를 찾을 수 없습니다 오류 페이지)으로 응답했다 — 이 부분이
        # 실제 원인이었다.
        root = self._get(
            "lawSearchList.do",
            {
                "serviceKey": service_key,
                "target": target,
                "type": "XML",
                "query": query,
                "numOfRows": limit,
                "pageNo": 1,
            },
        )

        hits: list[ExternalLegalHit] = []
        record_tag = "admrul" if target == "admrul" else "law"
        for elem in root.iter(record_tag):
            fields = text_map(elem)
            name = first(fields, "법령명한글", "행정규칙명", "법령명")
            if not name:
                continue
            mst = first(fields, "법령일련번호", "행정규칙일련번호", "MST")
            effective_date = first(fields, "시행일자")
            detail_link = first(fields, "법령상세링크", "행정규칙상세링크")
            detail_url = (
                f"http://www.law.go.kr{detail_link}" if detail_link and detail_link.startswith("/") else detail_link
            )

            hits.append(
                ExternalLegalHit(
                    source_type="STATUTE" if target == "law" else "ADMIN_RULE",
                    title=name,
                    excerpt=f"{name} (시행일자: {effective_date or '확인 필요'}). 조문 본문은 상세조회가 필요합니다.",
                    dedup_key=f"pdp:{target}:{mst or name}",
                    law_name=name,
                    effective_date=effective_date,
                    detail_url=detail_url,
                    mst=mst,
                )
            )
            if len(hits) >= limit:
                break
        return hits
