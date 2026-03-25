"""Gmail SMTP 邮件发送 + 多渠道联系方式提取工具。"""

import os
import re
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GMAIL_USER = os.getenv("GMAIL_USER") or os.getenv("IMAP_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD") or os.getenv("IMAP_PASSWORD", "")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
)

_NOISE_DOMAINS = {"example.com", "email.com", "your.com", "domain.com"}

# ── 多渠道联系方式正则 ──

_TELEGRAM_LINK_RE = re.compile(r"(?:https?://)?t\.me/([A-Za-z0-9_+]+)", re.I)
_TELEGRAM_ID_RE = re.compile(
    r"(?:telegram|tg)\s*[:：]\s*(@?[A-Za-z0-9_]{3,})", re.I,
)

_WHATSAPP_LINK_RE = re.compile(r"(?:https?://)?wa\.me/(\+?[\d]+)", re.I)
_WHATSAPP_ID_RE = re.compile(
    r"whatsapp\s*[:：]\s*(\+?[\d\s\-()]{7,})", re.I,
)

_WECHAT_RE = re.compile(
    r"(?:wechat|微信|WeChat)\s*(?:[(（]wechat[)）])?\s*[:：]\s*([A-Za-z0-9_\-]{4,})", re.I,
)

_PHONE_RE = re.compile(
    r"(?:电话|電話|热线|熱線|手机|手機|phone|tel)\s*[:：]\s*(\+?[\d\s\-()]{7,})",
    re.I,
)
_STANDALONE_PHONE_RE = re.compile(r"(\+\d{1,4}[\s\-]?\d[\d\s\-]{6,})")

_FACEBOOK_RE = re.compile(
    r"(?:https?://)?(?:www\.)?facebook\.com/(\S+)", re.I,
)
_THREADS_RE = re.compile(
    r"(?:https?://)?(?:www\.)?threads\.net/@(\S+)", re.I,
)
_THREADS_HANDLE_RE = re.compile(
    r"threads\s*[-:：]\s*(@?[A-Za-z0-9_.]+)", re.I,
)
_X_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:x\.com|twitter\.com)/(\S+)", re.I,
)
_INSTAGRAM_LINK_RE = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/(@?[A-Za-z0-9_.]+)", re.I,
)
_INSTAGRAM_HANDLE_RE = re.compile(
    r"instagram\s*[-:：]\s*(@?[A-Za-z0-9_.]+)", re.I,
)


def extract_emails(text: str) -> list[str]:
    """从任意文本中提取有效邮箱地址，去重并过滤常见占位域名。"""
    if not text:
        return []
    found = _EMAIL_RE.findall(text)
    seen: set[str] = set()
    result: list[str] = []
    for addr in found:
        addr_lower = addr.lower()
        domain = addr_lower.rsplit("@", 1)[-1]
        if addr_lower in seen or domain in _NOISE_DOMAINS:
            continue
        seen.add(addr_lower)
        result.append(addr)
    return result


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for v in items:
        v = v.strip().rstrip("/")
        key = v.lower()
        if key and key not in seen:
            seen.add(key)
            result.append(v)
    return result


def _clean_phone(raw: str) -> str:
    return re.sub(r"[() ]", "", raw).strip().rstrip("/")


def extract_contacts(text: str) -> dict[str, list[str]]:
    """从文本中提取所有渠道的联系方式，返回 {channel: [value, ...]}，空渠道不出现。"""
    if not text:
        return {}

    channels: dict[str, list[str]] = {}

    emails = extract_emails(text)
    if emails:
        channels["email"] = emails

    tg = [f"https://t.me/{m}" for m in _TELEGRAM_LINK_RE.findall(text)]
    tg += [m for m in _TELEGRAM_ID_RE.findall(text)]
    tg = _dedup(tg)
    if tg:
        channels["telegram"] = tg

    wa = [f"+{m}" if not m.startswith("+") else m for m in _WHATSAPP_LINK_RE.findall(text)]
    wa += [_clean_phone(m) for m in _WHATSAPP_ID_RE.findall(text)]
    wa = _dedup(wa)
    if wa:
        channels["whatsapp"] = wa

    wc = _dedup(_WECHAT_RE.findall(text))
    if wc:
        channels["wechat"] = wc

    phones_labeled = [_clean_phone(m) for m in _PHONE_RE.findall(text)]
    phones_standalone = [_clean_phone(m) for m in _STANDALONE_PHONE_RE.findall(text)]
    wa_set = {v.replace("-", "").replace(" ", "") for v in channels.get("whatsapp", [])}
    all_phones = _dedup(phones_labeled + phones_standalone)
    all_phones = [p for p in all_phones if p.replace("-", "") not in wa_set]
    if all_phones:
        channels["phone"] = all_phones

    fb = _dedup(_FACEBOOK_RE.findall(text))
    fb = [v for v in fb if v.lower() not in ("share", "share/")]
    if fb:
        channels["facebook"] = [f"https://facebook.com/{v}" for v in fb]

    threads = _dedup(
        [f"@{m}" if not m.startswith("@") else m for m in _THREADS_RE.findall(text)]
        + _THREADS_HANDLE_RE.findall(text)
    )
    if threads:
        channels["threads"] = threads

    x = _dedup(_X_RE.findall(text))
    x = [v for v in x if v.lower() not in ("share", "intent")]
    if x:
        channels["x"] = [f"https://x.com/{v}" for v in x]

    _ig_noise = {"https", "http", "www", "share", "p", "reel", "stories"}
    ig_links = _INSTAGRAM_LINK_RE.findall(text)
    ig_handles = _INSTAGRAM_HANDLE_RE.findall(text)
    ig = _dedup(
        [f"@{m}" if not m.startswith("@") else m for m in ig_links]
        + [f"@{m}" if not m.startswith("@") else m for m in ig_handles]
    )
    ig = [h for h in ig if h.lstrip("@").lower() not in _ig_noise]
    if ig:
        channels["instagram"] = ig

    return channels


def send_email(
    to: str,
    subject: str,
    body_html: str,
    from_name: str = "",
) -> dict:
    """发送单封 HTML 邮件，返回 {"success": bool, "error": str}。"""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        return {"success": False, "error": "Gmail 未配置（GMAIL_USER / GMAIL_APP_PASSWORD）"}

    msg = MIMEMultipart("alternative")
    sender = f"{from_name} <{GMAIL_USER}>" if from_name else GMAIL_USER
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.sendmail(GMAIL_USER, [to], msg.as_string())
        return {"success": True, "error": ""}
    except smtplib.SMTPAuthenticationError:
        return {"success": False, "error": "Gmail 认证失败，请检查应用密码"}
    except (TimeoutError, OSError) as e:
        return {"success": False, "error": f"SMTP 连接超时: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_bulk(
    recipients: list[dict],
    subject: str,
    body_html: str,
    from_name: str = "",
    delay: float = 1.0,
) -> list[dict]:
    """批量发送邮件。

    recipients: [{"email": str, "name": str, ...}, ...]
    body_html 中 {{name}} 会被替换为收件人名称。
    返回每个收件人的发送结果列表。
    """
    results: list[dict] = []
    for i, r in enumerate(recipients):
        email = r.get("email", "")
        name = r.get("name", "")
        if not email:
            results.append({"email": email, "name": name, "success": False, "error": "邮箱为空"})
            continue

        personalized = body_html.replace("{{name}}", name)
        personalized_subject = subject.replace("{{name}}", name)
        res = send_email(email, personalized_subject, personalized, from_name)
        res["email"] = email
        res["name"] = name
        results.append(res)

        if i < len(recipients) - 1:
            time.sleep(delay)

    return results


def merge_contacts(
    base: dict[str, list[str]],
    extra: dict[str, list[str]],
) -> dict[str, list[str]]:
    """合并两个 contact_channels 字典，extra 中的值补充到 base（去重）。"""
    merged = {k: list(v) for k, v in base.items()}
    for ch, vals in extra.items():
        existing = {v.lower() for v in merged.get(ch, [])}
        for v in vals:
            if v.lower() not in existing:
                merged.setdefault(ch, []).append(v)
                existing.add(v.lower())
    return merged
