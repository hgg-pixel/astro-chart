from __future__ import annotations

import json
import subprocess
from datetime import date, time
from pathlib import Path

import pandas as pd
from lunar_python import Solar


def _lunar_ctx(d: date, t: time):
    s = Solar.fromYmdHms(d.year, d.month, d.day, t.hour, t.minute, 0)
    l = s.getLunar()
    ec = l.getEightChar()
    return l, ec


def bazi_payload(d: date, t: time) -> tuple[pd.DataFrame, dict]:
    l, ec = _lunar_ctx(d, t)

    rows = [
        {
            "柱": "年",
            "天干地支": ec.getYear(),
            "五行": ec.getYearWuXing(),
            "纳音": ec.getYearNaYin(),
            "十神(干)": ec.getYearShiShenGan(),
            "十神(支)": "/".join(ec.getYearShiShenZhi()),
        },
        {
            "柱": "月",
            "天干地支": ec.getMonth(),
            "五行": ec.getMonthWuXing(),
            "纳音": ec.getMonthNaYin(),
            "十神(干)": ec.getMonthShiShenGan(),
            "十神(支)": "/".join(ec.getMonthShiShenZhi()),
        },
        {
            "柱": "日",
            "天干地支": ec.getDay(),
            "五行": ec.getDayWuXing(),
            "纳音": ec.getDayNaYin(),
            "十神(干)": ec.getDayShiShenGan(),
            "十神(支)": "/".join(ec.getDayShiShenZhi()),
        },
        {
            "柱": "时",
            "天干地支": ec.getTime(),
            "五行": ec.getTimeWuXing(),
            "纳音": ec.getTimeNaYin(),
            "十神(干)": ec.getTimeShiShenGan(),
            "十神(支)": "/".join(ec.getTimeShiShenZhi()),
        },
    ]

    compact = {
        "v": 1,
        "src": "lunar-python",
        "cal": "bazi",
        "p": [ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()],
        "wx": [ec.getYearWuXing(), ec.getMonthWuXing(), ec.getDayWuXing(), ec.getTimeWuXing()],
        "ny": [ec.getYearNaYin(), ec.getMonthNaYin(), ec.getDayNaYin(), ec.getTimeNaYin()],
        "ssg": [ec.getYearShiShenGan(), ec.getMonthShiShenGan(), ec.getDayShiShenGan(), ec.getTimeShiShenGan()],
        "ssz": [ec.getYearShiShenZhi(), ec.getMonthShiShenZhi(), ec.getDayShiShenZhi(), ec.getTimeShiShenZhi()],
        "mg": ec.getMingGong(),
        "sg": ec.getShenGong(),
        "ty": ec.getTaiYuan(),
        "tx": ec.getTaiXi(),
        "lunar": [l.getYear(), l.getMonth(), l.getDay()],
    }
    return pd.DataFrame(rows), compact


def _ensure_node_modules():
    """Auto-install iztro if node_modules is missing (for Streamlit Cloud)."""
    project_root = Path(__file__).resolve().parents[1]
    nm = project_root / "tools" / "ziwei_node" / "node_modules"
    if not nm.exists():
        subprocess.run(
            ["npm", "install"],
            cwd=str(project_root / "tools" / "ziwei_node"),
            check=True, capture_output=True,
        )

def ziwei_payload(d: date, t: time, gender: str) -> tuple[pd.DataFrame, dict]:
    _ensure_node_modules()
    # Use the same lunar conversion chain as Bazi.
    l, ec = _lunar_ctx(d, t)
    lunar_year = l.getYear()
    lunar_month_raw = l.getMonth()
    lunar_day = l.getDay()
    is_leap_month = lunar_month_raw < 0
    lunar_month = abs(lunar_month_raw)
    lunar_date = f"{lunar_year}-{lunar_month}-{lunar_day}"

    project_root = Path(__file__).resolve().parents[1]
    node_runner = project_root / "tools" / "ziwei_node" / "ziwei_calc.mjs"
    payload = {
        "lunar_date": lunar_date,
        "hour": t.hour,
        "gender": gender,
        "is_leap_month": is_leap_month,
    }
    proc = subprocess.run(
        ["node", str(node_runner), json.dumps(payload, ensure_ascii=False)],
        check=True,
        capture_output=True,
        text=True,
    )
    z = json.loads(proc.stdout)

    transforms = z.get("transforms", {})
    year_mutagens = transforms.get("yearMutagen", [])

    palace_rows = []
    for p in z.get("palaces", []):
        main = [x.get("name") for x in p.get("majorStars", [])]
        minor = [x.get("name") for x in p.get("minorStars", [])]
        adj = [x.get("name") for x in p.get("adjectiveStars", [])]
        palace_rows.append(
            {
                "宫位": p.get("name"),
                "天干": p.get("heavenlyStem"),
                "地支": p.get("earthlyBranch"),
                "主星": "、".join(main),
                "辅星": "、".join(minor + adj),
                "身宫": "是" if p.get("bodyPalace") else "否",
                "来因宫": "是" if p.get("originPalace") else "否",
            }
        )

    compact_palaces = []
    for p in z.get("palaces", []):
        compact_palaces.append(
            [
                p.get("name"),
                p.get("heavenlyStem"),
                p.get("earthlyBranch"),
                [x.get("name") for x in p.get("majorStars", [])],
            ]
        )

    year_transform_text = "；".join(
        f"{item.get('type')}:{item.get('star')}->{item.get('to', '')}"
        for item in year_mutagens
    ) if year_mutagens else ""

    compact = {
        "v": 1,
        "src": "iztro(js)",
        "cal": "ziwei",
        "gender": z.get("gender"),
        "sd": z.get("solarDate"),
        "ld": z.get("lunarDate"),
        "cd": z.get("chineseDate"),
        "tm": z.get("time"),
        "tr": z.get("timeRange"),
        "in": {
            "birth_date": d.strftime("%Y-%m-%d"),
            "birth_time": t.strftime("%H:%M"),
            "lunar_date_for_calc": lunar_date,
            "is_leap_month": is_leap_month,
            "calc_hour": t.hour,
            "bazi_pillars": [ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()],
        },
        "sgn": z.get("sign"),
        "zod": z.get("zodiac"),
        "soul": z.get("soul"),
        "body": z.get("body"),
        "fec": z.get("fiveElementsClass"),
        "p": compact_palaces,
        "year_transform": year_transform_text,
    }
    return pd.DataFrame(palace_rows), compact, year_transform_text
