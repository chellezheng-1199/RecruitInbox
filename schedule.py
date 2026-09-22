"""刷新时间策略。

按配置在夜间、周末、法定节假日跳过抓取，其余时间正常刷新。
配置保存在 settings.json，可在看板右上角「⚙️ 刷新设置」或通过 /api/settings 修改。
"""
import datetime
import json
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "night_start": 0,    # 不刷新起始小时（含）
    "night_end": 9,      # 不刷新结束小时（不含）；填 24 表示到当天结束
    "skip_weekend": True,   # 周六、周日不刷新
    "skip_holidays": True,  # 法定节假日不刷新
    "poll_interval_minutes": 60,  # 刷新间隔（分钟）
}

# 中国法定节假日「放假」日期（不含调休补班）。
# ⚠️ 每年国务院办公厅公布放假安排后请在此更新；下面是 2026 年的安排，
# 如与官方有出入请以官方为准（也可以直接增删这里的日期）。
HOLIDAYS = {
    # 元旦
    "2026-01-01", "2026-01-02", "2026-01-03",
    # 春节（除夕至初六，约 2/15-2/22）
    "2026-02-15", "2026-02-16", "2026-02-17", "2026-02-18",
    "2026-02-19", "2026-02-20", "2026-02-21", "2026-02-22",
    # 清明
    "2026-04-04", "2026-04-05", "2026-04-06",
    # 劳动节
    "2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05",
    # 端午
    "2026-06-19", "2026-06-20", "2026-06-21",
    # 中秋
    "2026-09-25", "2026-09-26", "2026-09-27",
    # 国庆
    "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04",
    "2026-10-05", "2026-10-06", "2026-10-07",
}

_lock = threading.Lock()


def load_settings():
    """读取刷新配置；文件不存在或损坏时返回默认值。"""
    if not SETTINGS_PATH.exists():
        return dict(DEFAULT_SETTINGS)
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_SETTINGS)
    out = dict(DEFAULT_SETTINGS)
    for k in DEFAULT_SETTINGS:
        if k in data:
            out[k] = data[k]
    return out


def save_settings(settings):
    """保存刷新配置，只保留已知字段，原子写入。"""
    out = dict(DEFAULT_SETTINGS)
    for k in DEFAULT_SETTINGS:
        if k in settings:
            out[k] = settings[k]
    with _lock:
        tmp = SETTINGS_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(SETTINGS_PATH)
    return out


def should_refresh(now=None, settings=None):
    """当前是否应该刷新。now 便于测试，默认取当前时间。"""
    now = now or datetime.datetime.now()
    s = settings if settings is not None else load_settings()

    # 夜间不刷新
    start = int(s.get("night_start", 0))
    end = int(s.get("night_end", 9))
    if start != end:
        h = now.hour
        if start < end and start <= h < end:
            return False
        if start > end and (h >= start or h < end):  # 跨午夜，如 22:00-6:00
            return False

    # 周末不刷新
    if s.get("skip_weekend", True) and now.weekday() >= 5:
        return False

    # 法定节假日不刷新
    if s.get("skip_holidays", True) and now.strftime("%Y-%m-%d") in HOLIDAYS:
        return False

    return True
