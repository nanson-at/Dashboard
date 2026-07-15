#!/usr/bin/env python3
"""Build e1002.html + e1002.png for SenseCraft (no browser JS)."""
from __future__ import annotations

import base64
import html as htmlmod
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

HK = ZoneInfo("Asia/Hong_Kong")
HEADERS = {"User-Agent": "Dashboard-E1002-GHA/1.0", "Accept": "application/json"}
EVENTS_URL = "https://raw.githubusercontent.com/nanson-at/Dashboard/main/data/events.json"
ROOT = Path(__file__).resolve().parents[1]

BUS_CONFIGS = [
    {"type": "KMB", "route": "251A", "url": "https://data.etabus.gov.hk/v1/transport/kmb/stop-eta/7AA3F7F89AD36B1B", "filterRoute": "251A", "dest": "上村"},
    {"type": "KMB", "route": "64K", "url": "https://data.etabus.gov.hk/v1/transport/kmb/stop-eta/7AA3F7F89AD36B1B", "filterRoute": "64K", "dest": "大埔墟站"},
    {"type": "KMB", "route": "64K", "url": "https://data.etabus.gov.hk/v1/transport/kmb/stop-eta/3D29F886079F85E9", "filterRoute": "64K", "dest": "元朗(西)"},
    {"type": "GMB", "route": "71", "url": "https://data.etagmb.gov.hk/eta/route-stop/2008290/20016485", "filterRouteSeq": 1, "dest": "河背"},
    {"type": "GMB", "route": "71", "url": "https://data.etagmb.gov.hk/eta/route-stop/2008290/20016474", "filterRouteSeq": 2, "dest": "元朗"},
    {"type": "GMB", "route": "71A", "url": "https://data.etagmb.gov.hk/eta/route-stop/2008388/20016485", "filterRouteSeq": 2, "dest": "長莆"},
    {"type": "GMB", "route": "71A", "url": "https://data.etagmb.gov.hk/eta/route-stop/2008388/20016474", "filterRouteSeq": 1, "dest": "錦上路站"},
]


def fmt_eta_minutes(eta_iso: str | None, now: datetime) -> str:
    if not eta_iso:
        return "-"
    try:
        t = str(eta_iso).replace("Z", "+00:00")
        eta = datetime.fromisoformat(t)
        if eta.tzinfo is None:
            eta = eta.replace(tzinfo=HK)
        mins = int(round((eta.astimezone(HK) - now.astimezone(HK)).total_seconds() / 60))
        if mins <= 0:
            return "即將到"
        if mins <= 3:
            return f"{mins}分鐘內"
        return f"{mins}分鐘"
    except Exception:
        return "-"


def fetch_bus_rows(now: datetime) -> list[dict[str, Any]]:
    rows = []
    for cfg in BUS_CONFIGS:
        etas: list[str] = []
        try:
            r = requests.get(cfg["url"], timeout=15, headers=HEADERS)
            r.raise_for_status()
            data = r.json()
            if cfg["type"] == "KMB":
                items = [x for x in (data.get("data") or []) if x.get("route") == cfg["filterRoute"] and x.get("eta")]
                items.sort(key=lambda x: x.get("eta") or "")
                for it in items[:3]:
                    etas.append(fmt_eta_minutes(it.get("eta"), now))
            else:
                items = data.get("data") or []
                flat = []
                if isinstance(items, list):
                    for it in items:
                        if isinstance(it, dict) and (it.get("timestamp") or it.get("eta") or it.get("diff") is not None):
                            flat.append(it)
                        elif isinstance(it, dict):
                            for e in it.get("eta") or []:
                                if isinstance(e, dict):
                                    flat.append(e)
                flat.sort(key=lambda x: str(x.get("timestamp") or x.get("eta") or ""))
                for it in flat[:3]:
                    if it.get("diff") is not None and not (it.get("timestamp") or it.get("eta")):
                        d = int(it["diff"])
                        etas.append("即將到" if d <= 0 else (f"{d}分鐘內" if d <= 3 else f"{d}分鐘"))
                    else:
                        etas.append(fmt_eta_minutes(it.get("timestamp") or it.get("eta"), now))
        except Exception:
            etas = ["暫無"]
        rows.append({"route": cfg["route"], "dest": cfg["dest"], "type": cfg["type"], "etas": etas or ["暫無班次"]})
    return rows


def fetch_events(now: datetime) -> list[dict[str, Any]]:
    try:
        # prefer local events in repo when running in Actions checkout
        local = ROOT / "data" / "events.json"
        if local.exists():
            data = json.loads(local.read_text(encoding="utf-8"))
        else:
            data = requests.get(EVENTS_URL, timeout=15, headers=HEADERS).json()
        events = data.get("events") if isinstance(data, dict) else data
        out = []
        today = now.astimezone(HK).date()
        for ev in events or []:
            if not isinstance(ev, dict):
                continue
            date_s = str(ev.get("date") or "")[:10]
            title = str(ev.get("title") or ev.get("name") or "")
            if not date_s or not title:
                continue
            try:
                d = datetime.strptime(date_s, "%Y-%m-%d").date()
            except Exception:
                continue
            if d < today - timedelta(days=1) or d > today + timedelta(days=45):
                continue
            out.append({
                "date": date_s,
                "time": str(ev.get("time") or ""),
                "title": title,
                "people": str(ev.get("people") or ev.get("who") or ""),
                "today": d == today,
                "past": d < today,
            })
        out.sort(key=lambda x: (x["date"], x["time"]))
        return out[:25]
    except Exception as e:
        return [{"date": "", "time": "", "title": f"活動失敗 {e}", "people": "", "today": False, "past": False}]


def fetch_weather() -> str:
    try:
        rhr = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc", timeout=15, headers=HEADERS).json()
        flw = requests.get("https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=flw&lang=tc", timeout=15, headers=HEADERS).json()
        temp_txt = "-"
        for t in rhr.get("temperature", {}).get("data") or []:
            if t.get("place") == "元朗公園":
                temp_txt = f"{t.get('value')}C 元朗公園"
                break
            if temp_txt == "-":
                temp_txt = f"{t.get('value')}C {t.get('place')}"
        hum = "-"
        for h in rhr.get("humidity", {}).get("data") or []:
            hum = f"{h.get('value')}%"
            break
        forecast = (flw.get("forecastDesc") or "")[:60]
        rain = "2h內雨機會低"
        if any(x in forecast for x in ("雷暴", "驟雨", "有雨")):
            rain = "2h內有機會雨"
        return f"石崗 {temp_txt} 濕度{hum} | {rain} | {forecast}"
    except Exception as e:
        return f"天氣無法載入 {e}"


def render_html(bus_rows, events, weather: str, now: datetime) -> str:
    now_hk = now.astimezone(HK)
    updated = now_hk.strftime("%Y-%m-%d %H:%M")
    clock = now_hk.strftime("%H:%M")
    bus_trs = []
    for row in bus_rows:
        eta = " / ".join(row["etas"][:3])
        bus_trs.append(
            f"<tr><td><b>{htmlmod.escape(row['route'])}</b></td>"
            f"<td>{htmlmod.escape(row['dest'])}</td>"
            f"<td>{htmlmod.escape(eta)}</td></tr>"
        )
    ev_trs = []
    for ev in events:
        mark = "*" if ev["today"] else ""
        line = f"{ev['date']} {ev['time']} {ev['title']}"
        if ev["people"]:
            line += f" ({ev['people']})"
        style = "background:#ffe8a0;" if ev["today"] else ("color:#888;text-decoration:line-through;" if ev["past"] else "")
        ev_trs.append(f'<tr style="{style}"><td>{mark}{htmlmod.escape(line)}</td></tr>')
    return f"""<!DOCTYPE html>
<html lang="zh-HK"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Cache-Control" content="no-cache">
<title>E1002 Dashboard Snapshot</title>
<style>
body{{margin:0;padding:8px;font-family:Arial,'Noto Sans CJK',sans-serif;background:#fff;color:#000;font-size:15px;}}
h2{{font-size:16px;margin:10px 0 4px;border-bottom:2px solid #000;}}
table{{width:100%;border-collapse:collapse;}}
td,th{{border-bottom:1px solid #999;padding:4px 3px;text-align:left;}}
.foot{{margin-top:8px;border-top:2px solid #000;padding-top:6px;font-size:13px;}}
.meta{{font-size:12px;margin-bottom:6px;}}
.col{{width:49%;display:inline-block;vertical-align:top;}}
</style></head><body>
<div class="meta">E1002 SNAPSHOT {htmlmod.escape(updated)} HKT | GitHub Actions | 5min</div>
<div class="col">
<h2>BUS / GMB</h2>
<table><tr><th>路線</th><th>方向</th><th>到站</th></tr>
{''.join(bus_trs)}
</table>
</div>
<div class="col">
<h2>EVENTS</h2>
<table>{''.join(ev_trs) if ev_trs else '<tr><td>暫無活動</td></tr>'}</table>
</div>
<div class="foot"><b>{htmlmod.escape(clock)}</b> &nbsp; {htmlmod.escape(weather)}</div>
</body></html>
"""


def _font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\NotoSansTC-VF.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def render_png(bus_rows, events, weather: str, now: datetime) -> bytes:
    W, H = 800, 480
    img = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    f_title = _font(20)
    f = _font(16)
    f_sm = _font(14)
    now_hk = now.astimezone(HK)
    draw.text((10, 8), f"E1002  {now_hk.strftime('%Y-%m-%d %H:%M')}  (GHA 5min)", fill=(0, 0, 0), font=f_title)
    draw.line((10, 36, W - 10, 36), fill=(0, 0, 0), width=2)
    x0, y0 = 10, 44
    draw.text((x0, y0), "巴士/小巴", fill=(0, 0, 0), font=f_title)
    yy = y0 + 26
    for row in bus_rows:
        line = f"{row['route']} → {row['dest']}  {' / '.join(row['etas'][:2])}"
        draw.text((x0, yy), line[:42], fill=(0, 0, 0), font=f)
        yy += 22
        if yy > H - 90:
            break
    x1 = 410
    draw.line((400, 44, 400, H - 70), fill=(0, 0, 0), width=2)
    draw.text((x1, y0), "活動", fill=(0, 0, 0), font=f_title)
    yy = y0 + 26
    for ev in events[:12]:
        prefix = "*" if ev["today"] else " "
        line = f"{prefix}{ev['date'][5:]} {ev['time']} {ev['title']}"
        draw.text((x1, yy), line[:34], fill=(0, 0, 0), font=f_sm)
        yy += 20
        if yy > H - 90:
            break
    draw.line((10, H - 64, W - 10, H - 64), fill=(0, 0, 0), width=2)
    draw.text((10, H - 56), now_hk.strftime("%H:%M"), fill=(0, 0, 0), font=f_title)
    draw.text((80, H - 54), weather[:70], fill=(0, 0, 0), font=f_sm)
    if len(weather) > 70:
        draw.text((80, H - 34), weather[70:140], fill=(0, 0, 0), font=f_sm)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def main() -> int:
    now = datetime.now(HK)
    print("fetch bus/events/weather...")
    bus = fetch_bus_rows(now)
    events = fetch_events(now)
    weather = fetch_weather()
    html_out = render_html(bus, events, weather, now)
    png_out = render_png(bus, events, weather, now)
    (ROOT / "e1002.html").write_text(html_out, encoding="utf-8")
    (ROOT / "e1002.png").write_bytes(png_out)
    print("wrote", ROOT / "e1002.html", ROOT / "e1002.png")
    print("updated", now.strftime("%Y-%m-%d %H:%M %Z"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
