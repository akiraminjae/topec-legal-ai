from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "TOPEC Legal AI"
    ENVIRONMENT: str = "development"
    TIMEZONE: str = "Asia/Seoul"
    SECRET_KEY: str = "dev-secret-key-change-me"
    SESSION_COOKIE_NAME: str = "topec_legal_session"
    SESSION_TTL_MINUTES: int = 60
    CSRF_COOKIE_NAME: str = "topec_legal_csrf"
    COOKIE_SECURE: bool = False  # set true behind HTTPS in production
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Database
    DATABASE_URL: str = "postgresql+psycopg://topec:topec@postgres:5432/topec_legal_ai"

    # Redis / Celery
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # MinIO / S3
    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "topec_minio"
    S3_SECRET_KEY: str = "topec_minio_secret"
    S3_BUCKET: str = "topec-legal-documents"
    S3_REGION: str = "us-east-1"
    S3_USE_SSL: bool = False

    # Auth
    LOGIN_MAX_FAILED_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15
    FORCE_PASSWORD_CHANGE_ON_FIRST_LOGIN: bool = True

    # ---- 회원가입 (이메일 인증) ----
    # 콤마로 구분된 허용 도메인 목록. 비워두면 모든 이메일 도메인의 가입을 허용한다.
    SIGNUP_ALLOWED_EMAIL_DOMAINS: str = "topec.co.kr"
    SIGNUP_VERIFICATION_TOKEN_TTL_HOURS: int = 24
    # 인증 메일 링크에 사용할 프론트엔드 공개 URL (마지막 슬래시 없이)
    APP_PUBLIC_URL: str = "http://localhost:3000"

    # ---- 메일 발송 ----
    # RESEND_API_KEY가 설정되어 있으면 Resend HTTP API(포트 443)로 발송한다 — SMTP 포트가
    # 클라우드 사업자에 의해 차단된 환경(예: DigitalOcean 기본 정책)에서도 동작하므로 우선한다.
    # 없으면 SMTP_HOST 설정을 사용하고, 그것도 없으면 서버 로그에 인증 링크만 출력한다(개발용).
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "no-reply@topecai.co.kr"

    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USE_SSL: bool = True
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "TOPEC Legal AI"

    # AI Provider
    AI_PROVIDER: str = "mock"  # mock | anthropic | openai | azure_openai | gemini | local
    AI_MODEL: str = "claude-sonnet-5"
    AI_API_KEY: str = ""
    AI_BASE_URL: str = ""
    AI_REQUEST_TIMEOUT: int = 180
    AI_MAX_TOKENS: int = 16000
    LOCAL_MODEL_ENDPOINT: str = ""  # required for CONFIDENTIAL documents if set

    # 보조 AI (듀얼 AI 교차검토) — 주 분석 결과를 다른 모델이 2차 검증한다.
    # 비워두면 교차검토 없이 기존 단일 프로바이더 동작 그대로.
    SECONDARY_AI_PROVIDER: str = ""  # "" (비활성) | gemini | anthropic | openai | mock
    SECONDARY_AI_MODEL: str = ""
    SECONDARY_AI_API_KEY: str = ""
    SECONDARY_AI_BASE_URL: str = ""

    # Embeddings (RAG)
    EMBEDDING_PROVIDER: str = "mock"  # mock | anthropic-compatible | openai
    EMBEDDING_DIM: int = 384

    # File limits
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: str = "pdf,jpg,jpeg,png,docx,hwpx,hwp,txt"

    # LibreOffice conversion
    LIBREOFFICE_BASE_URL: str = "http://libreoffice:2004"

    # Virus scan (interface only unless ClamAV configured)
    CLAMAV_HOST: str = ""
    CLAMAV_PORT: int = 3310

    # ---- 법률정보 연계: API 유형별로 분리 ----
    # 둘 다 사용자가 직접 신청/발급받는 값이며 여기에 하드코딩하지 않는다. 미설정 시 해당
    # Provider는 조용히 건너뛰고 내부 지식베이스만 사용한다(파이프라인이 끊기지 않음).

    # 1) 공공데이터포털(data.go.kr) REST API — 법제처 국가법령정보 공유서비스
    #    법령·행정규칙 "목록 및 메타정보" 전용. serviceKey는 반드시 디코딩(Decoding)된 값을
    #    사용한다 — httpx가 params를 인코딩할 때 이미 인코딩된 키를 넣으면 이중 인코딩되어
    #    인증이 깨진다.
    PUBLIC_DATA_SERVICE_KEY: str = ""
    PUBLIC_DATA_PORTAL_BASE_URL: str = "https://apis.data.go.kr/1170000/law"

    # 2) 국가법령정보 공동활용 LINK API — law.go.kr DRF 엔드포인트, OC 인증
    #    판례 목록/본문 + 법령 상세본문(조문) 전용. 공공데이터포털 serviceKey는 여기 쓰지 않는다.
    OPEN_LAW_OC: str = ""
    OPEN_LAW_BASE_URL: str = "http://www.law.go.kr/DRF"

    EXTERNAL_LEGAL_TIMEOUT: int = 15
    EXTERNAL_LEGAL_MAX_RESULTS: int = 5
    EXTERNAL_LEGAL_RATE_LIMIT_PER_MINUTE: int = 30

    # ---- 소송·분쟁 사건 다중 PDF 일괄 업로드 제한 ----
    LITIGATION_BATCH_MAX_FILES: int = 100
    LITIGATION_BATCH_MAX_TOTAL_SIZE_MB: int = 1000
    LITIGATION_SINGLE_FILE_MAX_SIZE_MB: int = 200
    LITIGATION_MAX_PAGES_PER_FILE: int = 2000
    LITIGATION_PARALLEL_PROCESSING_COUNT: int = 3

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_extensions_list(self) -> list[str]:
        return [e.strip().lower() for e in self.ALLOWED_EXTENSIONS.split(",") if e.strip()]

    @property
    def signup_allowed_email_domains_list(self) -> list[str]:
        return [d.strip().lower() for d in self.SIGNUP_ALLOWED_EMAIL_DOMAINS.split(",") if d.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
