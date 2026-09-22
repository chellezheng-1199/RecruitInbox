"""通过 IMAP 从 163 邮箱拉取最近若干天的邮件。"""
import datetime
import hashlib
import imaplib
import re
from email import policy
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parsedate_to_datetime

import config


def _decode(value):
    """解码邮件头里的中文/编码字符。"""
    if value is None:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value)


def _strip_html(html):
    text = re.sub(r"<style.*?</style>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _body_text(msg: Message) -> str:
    """提取正文纯文本，去掉附件；优先 text/plain，其次 text/html。"""
    text_parts = []
    html_parts = []

    def _payload(part):
        try:
            payload = part.get_payload(decode=True)
        except Exception:
            payload = None
        if payload is None:
            return ""
        charset = part.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, errors="replace")
        except Exception:
            return payload.decode("utf-8", errors="replace")

    if msg.is_multipart():
        for part in msg.walk():
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition.lower():
                continue
            ct = part.get_content_type()
            content = _payload(part)
            if ct == "text/plain":
                text_parts.append(content)
            elif ct == "text/html":
                html_parts.append(content)
    else:
        content = _payload(msg)
        if msg.get_content_type() == "text/html":
            html_parts.append(content)
        else:
            text_parts.append(content)

    if text_parts:
        return "\n".join(text_parts).strip()
    if html_parts:
        return _strip_html("\n".join(html_parts))
    return ""


def _imap_id(conn):
    """网易 163/126 要求 SELECT 前发送 IMAP ID 命令，否则报 'Unsafe Login'。"""
    try:
        if "ID" not in imaplib.Commands:
            imaplib.Commands["ID"] = ("AUTH",)
        args = ("name", "email-helper", "version", "1.0", "vendor", "claude")
        typ, dat = conn._simple_command("ID", '("' + '" "'.join(args) + '")')
        conn._untagged_response(typ, dat, "ID")
    except Exception:
        pass  # 其它服务器不支持也不影响


def _account_key(acc) -> str:
    return hashlib.md5(acc.address.encode("utf-8")).hexdigest()[:6]


def _message_id(acc, msg: Message) -> str:
    """用账号 + Message-ID 组合成唯一 ID，避免两个邮箱邮件冲突。"""
    key = _account_key(acc)
    mid = msg.get("Message-ID")
    if mid:
        return f"{key}:mid:{str(mid).strip()}"
    subject = _decode(msg.get("Subject"))
    frm = _decode(msg.get("From"))
    date = _decode(msg.get("Date"))
    h = hashlib.md5(f"{frm}|{subject}|{date}".encode("utf-8")).hexdigest()[:16]
    return f"{key}:hash:{h}"


def fetch_recent_emails(cfg=None, lookback_days=None):
    """拉取所有账号最近 lookback_days 天的邮件，返回 (邮件列表, 错误列表)。"""
    cfg = cfg or config.config
    if lookback_days is None:
        lookback_days = cfg.lookback_days

    results = []
    errors = []
    for acc in cfg.accounts:
        acc_results, err = _fetch_account(acc, lookback_days)
        results.extend(acc_results)
        if err:
            errors.append(f"{acc.address}: {err}")
    results.sort(key=lambda x: x["ts"], reverse=True)
    return results, errors


def _fetch_account(acc, lookback_days):
    """拉取单个账号最近若干天的邮件。返回 (邮件列表, 错误信息或 None)。"""
    conn = None
    try:
        conn = imaplib.IMAP4_SSL(acc.imap_server, acc.imap_port)
        conn.login(acc.address, acc.auth_code)
        _imap_id(conn)  # 网易需要，避免 'Unsafe Login'

        typ_sel, sel_data = conn.select("INBOX")
        if typ_sel != "OK":
            return [], "收件箱打不开：" + str(sel_data)

        since = (datetime.date.today() - datetime.timedelta(days=lookback_days - 1))
        since_str = since.strftime("%d-%b-%Y")  # IMAP 需要这种格式，如 22-Sep-2026
        typ, data = conn.search(None, f'(SINCE "{since_str}")')
        if typ != "OK":
            return [], "搜索邮件失败"

        ids = data[0].split()
        results = []
        # 只处理最近 200 封，避免一次处理过多
        for num in ids[-200:]:
            try:
                typ2, msg_data = conn.fetch(num, "(RFC822)")
                if typ2 != "OK":
                    continue
                raw = msg_data[0][1]
                msg = email_message_from_bytes(raw)
                date_str = _decode(msg.get("Date"))
                try:
                    dt = parsedate_to_datetime(date_str)
                    ts = dt.timestamp()
                    date_iso = dt.isoformat()
                except Exception:
                    dt = None
                    ts = 0
                    date_iso = date_str
                results.append({
                    "id": _message_id(acc, msg),
                    "account": acc.address,
                    "from": _decode(msg.get("From")),
                    "to": _decode(msg.get("To")),
                    "subject": _decode(msg.get("Subject")),
                    "date": date_iso,
                    "ts": ts,
                    "body": _body_text(msg),
                })
            except Exception:
                continue
        return results, None
    except Exception as ex:
        return [], str(ex)
    finally:
        if conn is not None:
            try:
                conn.logout()
            except Exception:
                pass


def email_message_from_bytes(raw):
    # 单独抽出便于测试/替换
    import email
    return email.message_from_bytes(raw, policy=policy.default)
