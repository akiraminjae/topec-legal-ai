import html
import logging
import smtplib
from email.message import EmailMessage

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def send_email(to: str, subject: str, html_body: str, text_body: str | None = None) -> None:
    """Send an e-mail. Tries, in order: Resend HTTP API (works even where outbound
    SMTP ports are blocked, e.g. DigitalOcean's default policy) -> SMTP -> log-only
    fallback, matching the "미설정 시 조용히 건너뛰기" pattern used for the other
    optional external integrations in this project (see config.py)."""
    if settings.RESEND_API_KEY:
        _send_via_resend(to, subject, html_body, text_body)
        return
    if settings.SMTP_HOST:
        _send_via_smtp(to, subject, html_body, text_body)
        return
    logger.info("No email provider configured — would send email to=%s subject=%s\n%s", to, subject, text_body or html_body)


def _send_via_resend(to: str, subject: str, html_body: str, text_body: str | None) -> None:
    response = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}", "Content-Type": "application/json"},
        json={
            "from": f"{settings.SMTP_FROM_NAME} <{settings.RESEND_FROM_EMAIL}>",
            "to": [to],
            "subject": subject,
            "html": html_body,
            "text": text_body or "",
        },
        timeout=15,
    )
    response.raise_for_status()


def _send_via_smtp(to: str, subject: str, html_body: str, text_body: str | None) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME}>"
    message["To"] = to
    message.set_content(text_body or "이 메일은 HTML 형식으로 작성되었습니다. HTML을 지원하는 메일 클라이언트에서 열어주세요.")
    message.add_alternative(html_body, subtype="html")

    if settings.SMTP_USE_SSL:
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as client:
            if settings.SMTP_USERNAME:
                client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            client.send_message(message)
    else:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as client:
            client.starttls()
            if settings.SMTP_USERNAME:
                client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            client.send_message(message)


def send_signup_verification_email(to: str, full_name: str, verification_url: str) -> None:
    subject = "[TOPEC Legal AI] 회원가입 이메일 인증 안내"
    html_body = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 480px; margin: 0 auto; color: #1e293b;">
      <h2 style="color: #0f4c81;">TOPEC Legal AI 회원가입 인증</h2>
      <p>{full_name}님, 안녕하세요.</p>
      <p>아래 버튼을 클릭하면 회원가입 인증이 완료되고 로그인하실 수 있습니다.</p>
      <p style="margin: 24px 0;">
        <a href="{verification_url}" style="background:#0f4c81;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;">이메일 인증하기</a>
      </p>
      <p style="font-size: 13px; color: #64748b;">버튼이 동작하지 않으면 아래 링크를 브라우저에 붙여넣으세요.<br>{verification_url}</p>
      <p style="font-size: 13px; color: #64748b;">본 인증 링크는 24시간 동안만 유효합니다. 본인이 요청하지 않았다면 이 메일을 무시하세요.</p>
    </div>
    """
    text_body = f"{full_name}님, 아래 링크를 클릭해 이메일 인증을 완료해주세요 (24시간 유효):\n{verification_url}"
    send_email(to, subject, html_body, text_body)


def send_admin_approval_request_email(
    to: str, full_name: str, employee_no: str, email: str, admin_approvals_url: str
) -> None:
    subject = f"[TOPEC Legal AI] 신규 가입 승인 요청 — {full_name}"
    html_body = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 480px; margin: 0 auto; color: #1e293b;">
      <h2 style="color: #0f4c81;">신규 가입 승인 요청이 있습니다</h2>
      <p>아래 사용자가 이메일 인증을 완료하고 관리자 승인을 기다리고 있습니다.</p>
      <table style="border-collapse: collapse; margin: 16px 0; font-size: 14px;">
        <tr><td style="color:#64748b;padding:4px 12px 4px 0;">이름</td><td>{full_name}</td></tr>
        <tr><td style="color:#64748b;padding:4px 12px 4px 0;">사용자 ID</td><td>{employee_no}</td></tr>
        <tr><td style="color:#64748b;padding:4px 12px 4px 0;">이메일</td><td>{email}</td></tr>
      </table>
      <p style="margin: 24px 0;">
        <a href="{admin_approvals_url}" style="background:#0f4c81;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;">가입 승인 화면으로 이동</a>
      </p>
      <p style="font-size: 13px; color: #64748b;">버튼이 동작하지 않으면 아래 링크를 브라우저에 붙여넣으세요.<br>{admin_approvals_url}</p>
    </div>
    """
    text_body = (
        f"신규 가입 승인 요청: {full_name} ({employee_no}, {email})\n"
        f"승인 화면: {admin_approvals_url}"
    )
    send_email(to, subject, html_body, text_body)


_AI_ALERT_GUIDE = {
    "credit_exhausted": (
        "AI 크레딧 소진",
        "AI 공급자 계정의 크레딧(이용 한도)이 소진되어 모든 AI 분석이 실패하고 있습니다.",
        "AI 공급자 콘솔의 결제(Plans &amp; Billing) 메뉴에서 크레딧을 충전해 주세요. "
        "재발 방지를 위해 자동 충전(auto-reload) 설정을 권장합니다.",
    ),
    "auth": (
        "AI API 인증 실패",
        "AI 공급자가 API 키를 거부하여 모든 AI 분석이 실패하고 있습니다.",
        "서버 .env의 AI_API_KEY가 유효한지(만료·삭제·권한 변경 여부) 확인해 주세요.",
    ),
}


def send_ai_provider_alert_email(to: str, kind: str, provider: str, detail: str, admin_url: str) -> None:
    title, situation, action = _AI_ALERT_GUIDE[kind]
    subject = f"[TOPEC Legal AI] {title} — AI 분석이 중단되었습니다"
    detail_block = (
        f'<pre style="background:#f1f5f9;padding:12px;border-radius:6px;font-size:12px;'
        f'white-space:pre-wrap;">{html.escape(detail)}</pre>'
        if detail
        else ""
    )
    html_body = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 520px; margin: 0 auto; color: #1e293b;">
      <h2 style="color: #b91c1c;">{title}</h2>
      <p>{situation}</p>
      <p><b>조치:</b> {action}</p>
      <p>조치 후 실패한 문서는 문서 화면의 <b>[재분석 시도]</b>로 다시 분석할 수 있습니다.</p>
      <table style="border-collapse: collapse; margin: 16px 0; font-size: 14px;">
        <tr><td style="color:#64748b;padding:4px 12px 4px 0;">AI 공급자</td><td>{html.escape(provider or "-")}</td></tr>
      </table>
      {detail_block}
      <p style="margin: 24px 0;">
        <a href="{admin_url}" style="background:#0f4c81;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;">관리자 화면으로 이동</a>
      </p>
      <p style="font-size: 13px; color: #64748b;">같은 원인의 알림은 6시간에 한 번만 발송됩니다.</p>
    </div>
    """
    text_body = "\n".join(
        [
            f"{title} ({provider or '-'})",
            situation,
            f"조치: {action.replace('&amp;', '&')}",
            "조치 후 실패한 문서는 [재분석 시도]로 다시 분석할 수 있습니다.",
            detail,
            f"관리자 화면: {admin_url}",
        ]
    )
    send_email(to, subject, html_body, text_body)
