"""调用 DeepSeek API 对邮件分类并提取关键信息。"""
import datetime
import json
import re

import requests

import config

SYSTEM_PROMPT = (
    "你是秋招求职邮件助理。根据给定的邮件内容，判断这封邮件属于哪一类，并提取关键信息。\n"
    "\n"
    "分类 type 只能是以下之一：面试、测评、笔试、宣讲会、Offer、拒信、其他\n"
    "其中「宣讲会」指校园宣讲会/空中宣讲会，即邀请你参加公司介绍、岗位分享等活动的邮件，它不是面试也不是笔试。\n"
    "\n"
    "请严格输出如下 JSON（不要输出任何多余文字）：\n"
    '{"type": "面试|测评|笔试|宣讲会|Offer|拒信|其他", '
    '"company": "公司名，不知道就填未知", '
    '"summary": "一句话说清这封邮件要你做什么，50字以内", '
    '"deadline": "这封邮件的截止/关键时间（原文或转述），没有就填无", '
    '"event_date": "你需要行动的关键日期：面试日期、笔试日期、测评或答题的截止/失效日期、宣讲会日期。格式 YYYY-MM-DD，如 2026-09-28。邮件里只要写了具体时间就务必提取，不要填无；确实没写才填 无；没写年份默认 2026 年", '
    '"event_time": "当天的时间点，格式如 14:00-17:00、18:00、19:00、08:14；邮件写了当天几点就务必提取，没写才填 无", '
    '"urgency": "高|中|低"}\n'
    "\n"
    "特别注意：测评/笔试类邮件里「作答链接将在 X 失效」「有效期至 X」「请于 X 前完成」的 X 就是 event_date，X 里的几点就是 event_time；面试/宣讲会邮件里「时间 X」的 X 就是 event_date 和 event_time。"
)


def _parse_json(content):
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
    return json.loads(content)


def _normalize_date(value):
    """把各种日期写法统一成 YYYY-MM-DD，无法识别则原样返回。"""
    import re
    s = str(value or "").strip()
    if not s or s == "无":
        return "无"
    m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return s


def _relative_deadline(email_dict):
    """识别「72小时内 / 3天内 / 有效期72小时」这类相对截止。
    返回 (截止 datetime, 时长数字, 时长单位)；无则返回 None。"""
    text = " ".join([email_dict.get("subject", "") or "", email_dict.get("body", "") or ""])
    candidates = []
    for pat in (
        r"(\d{1,3})\s*(小时|时|天|日|周)\s*(?:内|有效|失效)",
        r"(?:有效|失效)[期为]?\s*(\d{1,3})\s*(小时|时|天|日|周)",
    ):
        for m in re.finditer(pat, text):
            candidates.append((m.start(), int(m.group(1)), m.group(2)))
    if not candidates:
        return None
    _, amount, unit = min(candidates, key=lambda x: x[0])
    date_str = str(email_dict.get("date", "") or "").strip()
    try:
        dt = datetime.datetime.fromisoformat(date_str)
    except Exception:
        return None
    if unit in ("小时", "时"):
        deadline = dt + datetime.timedelta(hours=amount)
    elif unit in ("天", "日"):
        deadline = dt + datetime.timedelta(days=amount)
    else:  # 周
        deadline = dt + datetime.timedelta(weeks=amount)
    return deadline, amount, unit


def classify(email_dict, cfg=None):
    """返回 {type, company, summary, deadline, urgency}。"""
    cfg = cfg or config.config
    body = (email_dict.get("body") or "")[: cfg.max_body_chars]
    user_content = (
        f"发件人: {email_dict.get('from', '')}\n"
        f"主题: {email_dict.get('subject', '')}\n"
        f"时间: {email_dict.get('date', '')}\n"
        f"正文:\n{body}"
    )

    resp = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": f"Bearer {cfg.deepseek_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": cfg.deepseek_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 600,
        },
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    data = _parse_json(content)
    event_date = _normalize_date(data.get("event_date", "无"))
    event_time = data.get("event_time", "无")
    deadline = data.get("deadline", "无")
    # 兜底：邮件只写「72小时内 / 3天内」这类相对截止、没给出具体时分时，
    # 用邮件接收时间推算精确截止时间，避免「无截止时间」。
    rel = _relative_deadline(email_dict)
    if rel is not None and event_time == "无":
        rel_dt, amount, unit = rel
        computed_date = rel_dt.strftime("%Y-%m-%d")
        if event_date == "无" or event_date == computed_date:
            event_date = computed_date
            event_time = rel_dt.strftime("%H:%M")
            deadline = f"{event_date} {event_time} 截止（邮件后{amount}{unit}）"
    return {
        "type": data.get("type", "其他"),
        "company": data.get("company", "未知"),
        "summary": data.get("summary", ""),
        "deadline": deadline,
        "event_date": event_date,
        "event_time": event_time,
        "urgency": data.get("urgency", "低"),
    }
