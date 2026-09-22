"""网页看板 + 后台轮询主程序。

启动：python app.py    然后浏览器打开 http://127.0.0.1:8000
"""
import datetime
import threading
import traceback
import uuid

from flask import Flask, jsonify, render_template, request

import classifier
import config
import mail_fetcher
import schedule
import storage

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True  # 开发期改模板后不用重启

STATE_LOCK = threading.Lock()
RUN_LOCK = threading.Lock()


def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def classify_and_store():
    """拉取新邮件 → 分类 → 存盘。返回 (邮件总数, 新增分类数)。"""
    if not RUN_LOCK.acquire(blocking=False):
        return None  # 已有一次正在跑，跳过
    try:
        cfg = config.config
        emails, fetch_errors = mail_fetcher.fetch_recent_emails(cfg)

        with STATE_LOCK:
            store = storage.load(cfg)
            known = {it["id"]: it for it in store.get("items", [])}
            skipped = set(store.get("skipped_ids", []))

        new_count = 0
        errors = list(store.get("errors", []))
        for fe in fetch_errors:
            errors.append(f"{now_str()} {fe}")
        for e in emails:
            eid = e["id"]
            with STATE_LOCK:
                existing = known.get(eid)
            if existing and existing.get("type"):
                continue  # 已分类过，跳过
            if eid in skipped:
                continue  # 之前判定为「其他」，已丢弃，不重复分类
            try:
                cls = classifier.classify(e, cfg)
            except Exception as ex:
                errors.append(f"{now_str()} 分类失败 [{e.get('subject', '')[:30]}]: {ex}")
                cls = {"type": "其他", "company": "未知",
                       "summary": "(分类失败)", "deadline": "无", "urgency": "低"}
            if cls.get("type") == "其他":
                skipped.add(eid)  # 噪音邮件，丢弃不存储
                continue
            item = {**e, **cls, "done": False}
            with STATE_LOCK:
                known[eid] = item
            new_count += 1

        store["items"] = sorted(known.values(), key=lambda x: x.get("ts", 0), reverse=True)
        store["skipped_ids"] = sorted(skipped)
        store["last_updated"] = now_str()
        store["errors"] = errors[-20:]
        storage.save(store, cfg)
        with STATE_LOCK:
            globals()["_CACHE"] = store
        return len(emails), new_count
    finally:
        RUN_LOCK.release()


def poll_loop():
    """后台定时轮询。按刷新策略跳过夜间/周末/节假日，间隔在刷新设置里配置。"""
    cfg = config.config
    while True:
        if schedule.should_refresh():
            try:
                classify_and_store()
            except Exception:
                with STATE_LOCK:
                    store = storage.load(cfg)
                    store["errors"] = (store.get("errors", []) + [traceback.format_exc()])[-20:]
                    storage.save(store, cfg)
        interval = int(schedule.load_settings().get("poll_interval_minutes", 60)) * 60
        threading.Event().wait(interval)


def get_state():
    with STATE_LOCK:
        return storage.load(config.config)


@app.route("/")
def index():
    store = get_state()
    # 不展示「其他」类邮件（验证码、广告等噪音，对用户无用）
    items = [it for it in store.get("items", []) if it.get("type") != "其他"]
    # 剔除正文等前端用不到的字段，减小页面体积
    items = [{k: v for k, v in it.items() if k != "body"} for it in items]
    return render_template(
        "index.html",
        items=items,
        last_updated=store.get("last_updated"),
        missing=config.missing_fields(),
    )


@app.route("/api/items")
def api_items():
    return jsonify(get_state())


@app.route("/api/refresh")
def api_refresh():
    if config.missing_fields():
        return jsonify({"ok": False, "error": "请先填写 .env 里的配置（" + "、".join(config.missing_fields()) + "）"}), 400
    try:
        result = classify_and_store()
        if result is None:
            return jsonify({"ok": True, "info": "上一次刷新还在进行中"})
        total, new = result
        return jsonify({"ok": True, "total": total, "new": new})
    except Exception as ex:
        return jsonify({"ok": False, "error": str(ex)}), 500


@app.route("/api/toggle", methods=["POST"])
def api_toggle():
    """切换某条事项的完成状态。"""
    data = request.get_json(silent=True) or {}
    item_id = data.get("id")
    if not item_id:
        return jsonify({"ok": False, "error": "缺少 id"}), 400
    cfg = config.config
    store = storage.load(cfg)
    for it in store.get("items", []):
        if it.get("id") == item_id:
            it["done"] = not it.get("done", False)
            storage.save(store, cfg)
            return jsonify({"ok": True, "done": it["done"]})
    return jsonify({"ok": False, "error": "未找到该事项"}), 404


@app.route("/api/add", methods=["POST"])
def api_add():
    """手动添加一条待办（用户自己录入，不是来自邮件）。"""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "请输入事项名称"}), 400
    etype = data.get("type") or "面试"
    event_date = (data.get("date") or "").strip()
    if not event_date:
        return jsonify({"ok": False, "error": "请选择日期"}), 400
    event_time = (data.get("time") or "").strip() or "无"

    ts = 0
    try:
        ts = datetime.datetime.strptime(event_date, "%Y-%m-%d").replace(hour=12).timestamp()
    except Exception:
        pass

    item = {
        "id": "manual:" + uuid.uuid4().hex,
        "manual": True,
        "type": etype,
        "company": name,
        "subject": "",
        "summary": "(手动添加)",
        "deadline": "无",
        "event_date": event_date,
        "event_time": event_time,
        "urgency": "中",
        "done": False,
        "ts": ts,
    }
    cfg = config.config
    store = storage.load(cfg)
    store.setdefault("items", []).append(item)
    store["items"] = sorted(store["items"], key=lambda x: x.get("ts", 0), reverse=True)
    store["last_updated"] = now_str()
    storage.save(store, cfg)
    return jsonify({"ok": True, "id": item["id"]})


@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    return jsonify(schedule.load_settings())


@app.route("/api/settings", methods=["POST"])
def api_set_settings():
    data = request.get_json(silent=True) or {}
    try:
        s = {
            "night_start": int(data.get("night_start", 0)),
            "night_end": int(data.get("night_end", 9)),
            "skip_weekend": bool(data.get("skip_weekend", True)),
            "skip_holidays": bool(data.get("skip_holidays", True)),
            "poll_interval_minutes": int(data.get("poll_interval_minutes", 60)),
        }
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "参数格式不对"}), 400
    s["night_start"] = max(0, min(23, s["night_start"]))
    s["night_end"] = max(0, min(24, s["night_end"]))
    s["poll_interval_minutes"] = max(1, min(10080, s["poll_interval_minutes"]))
    saved = schedule.save_settings(s)
    return jsonify({"ok": True, "settings": saved})


def main():
    if not config.missing_fields():
        t = threading.Thread(target=poll_loop, daemon=True)
        t.start()
    print("看板已启动：http://127.0.0.1:8000  （Ctrl+C 退出）")
    app.run(host="127.0.0.1", port=8000, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()