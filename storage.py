"""把分类结果持久化到 JSON 文件。"""
import json
import threading

import config

_lock = threading.Lock()

DEFAULT_STATE = {"items": [], "skipped_ids": [], "last_updated": None, "errors": []}


def load(cfg=None):
    cfg = cfg or config.config
    path = cfg.store_path
    if not path.exists():
        return dict(DEFAULT_STATE)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_STATE)


def save(data, cfg=None):
    cfg = cfg or config.config
    with _lock:
        tmp = cfg.store_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(cfg.store_path)
