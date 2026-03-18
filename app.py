#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from kerykeion import AstrologicalSubject, KerykeionChartSVG, NatalAspects

from src.chinese_systems import bazi_payload, ziwei_payload
from src.engines.swiss_ephemeris import compute_swiss_chart

OUT_DIR = Path(__file__).parent / "output"
OUT_DIR.mkdir(exist_ok=True)

DEFAULT_TZ = "Asia/Shanghai"
DEFAULT_LAT = 31.2304
DEFAULT_LON = 121.4737

SIGNS_ZH = {
    "Ari": "白羊", "Tau": "金牛", "Gem": "双子", "Can": "巨蟹", "Leo": "狮子", "Vir": "处女",
    "Lib": "天秤", "Sco": "天蝎", "Sag": "射手", "Cap": "摩羯", "Aqu": "水瓶", "Pis": "双鱼",
}

HOUSE_ATTRS = [
    "first_house", "second_house", "third_house", "fourth_house", "fifth_house", "sixth_house",
    "seventh_house", "eighth_house", "ninth_house", "tenth_house", "eleventh_house", "twelfth_house",
]

PLANET_ATTRS = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto"]

SIGN_RULERS = {
    "Ari": ["Mars"], "Tau": ["Venus"], "Gem": ["Mercury"], "Can": ["Moon"], "Leo": ["Sun"], "Vir": ["Mercury"],
    "Lib": ["Venus"], "Sco": ["Mars", "Pluto"], "Sag": ["Jupiter"], "Cap": ["Saturn"], "Aqu": ["Saturn", "Uranus"], "Pis": ["Jupiter", "Neptune"],
}

ASPECT_ZH = {"conjunction": "合", "sextile": "六合", "square": "刑", "trine": "拱", "opposition": "冲"}
ASPECT_RULES = [
    ("conjunction", 0, 8.0),
    ("sextile", 60, 5.0),
    ("square", 90, 6.0),
    ("trine", 120, 6.0),
    ("opposition", 180, 8.0),
]
SIGN_KEYS = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]
MARX_KEYS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "True_North_Lunar_Node", "Chiron", "Mean_Lilith"]

ABBR = {
    "Sun": "Su", "Moon": "Mo", "Mercury": "Me", "Venus": "Ve", "Mars": "Ma", "Jupiter": "Ju", "Saturn": "Sa",
    "Uranus": "Ur", "Neptune": "Ne", "Pluto": "Pl", "True_North_Lunar_Node": "NN", "Chiron": "Ch", "Mean_Lilith": "Li",
}


def norm_deg(x: float) -> float:
    return x % 360.0


def angle_mid(a: float, b: float) -> float:
    a1 = norm_deg(a)
    b1 = norm_deg(b)
    diff = (b1 - a1) % 360.0
    if diff > 180.0:
        diff -= 360.0
    return norm_deg(a1 + diff / 2.0)


def angle_dist(a: float, b: float) -> float:
    d = abs(norm_deg(a - b))
    return min(d, 360.0 - d)


def lon_mid(a_lon: float, b_lon: float) -> float:
    a = norm_deg(a_lon)
    b = norm_deg(b_lon)
    m = angle_mid(a, b)
    return m - 360.0 if m > 180.0 else m


def midpoint_datetime(a_d: date, a_t: time, b_d: date, b_t: time, tz: str) -> tuple[date, time]:
    tzinfo = ZoneInfo(tz)
    a_local = datetime(a_d.year, a_d.month, a_d.day, a_t.hour, a_t.minute, tzinfo=tzinfo)
    b_local = datetime(b_d.year, b_d.month, b_d.day, b_t.hour, b_t.minute, tzinfo=tzinfo)
    a_ts = a_local.astimezone(timezone.utc).timestamp()
    b_ts = b_local.astimezone(timezone.utc).timestamp()
    mid_ts = (a_ts + b_ts) / 2.0
    mid_local = datetime.fromtimestamp(mid_ts, tz=timezone.utc).astimezone(tzinfo)
    return mid_local.date(), mid_local.time().replace(second=0, microsecond=0)


def house_of(abs_pos: float, cusps: list[float]) -> int:
    x = norm_deg(abs_pos)
    c = [norm_deg(v) for v in cusps]
    for i in range(12):
        start = c[i]
        end = c[(i + 1) % 12]
        if start <= end:
            if start <= x < end:
                return i + 1
        else:
            if x >= start or x < end:
                return i + 1
    return 12


def zh_sign(sign: str) -> str:
    return SIGNS_ZH.get(sign, sign)


def fmt_deg(x: float) -> str:
    d = int(x)
    m = int(round((x - d) * 60))
    if m == 60:
        d += 1
        m = 0
    return f"{d}°{m:02d}"


def k_subject(name: str, d: date, t: time, tz: str, lat: float, lon: float) -> AstrologicalSubject:
    return AstrologicalSubject(
        name=name, year=d.year, month=d.month, day=d.day, hour=t.hour, minute=t.minute,
        lat=lat, lng=lon, tz_str=tz, online=False
    )


def render_svg(subject: AstrologicalSubject) -> tuple[str, str]:
    chart = KerykeionChartSVG(subject, chart_type="Natal", new_output_directory=str(OUT_DIR))
    chart.makeSVG()
    p = OUT_DIR / f"{subject.name} - Natal Chart.svg"
    return p.name, p.read_text(encoding="utf-8")


def write_compact_json(file_name: str, payload: dict) -> tuple[str, bytes]:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    path = OUT_DIR / file_name
    path.write_text(text, encoding="utf-8")
    return str(path), text.encode("utf-8")


def data_from_kerykeion(subject: AstrologicalSubject) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    p_rows = []
    planet_house = {}
    for attr in PLANET_ATTRS:
        p = getattr(subject, attr)
        house_num = int(p.house.split("_")[0].replace("First", "1").replace("Second", "2").replace("Third", "3").replace("Fourth", "4").replace("Fifth", "5").replace("Sixth", "6").replace("Seventh", "7").replace("Eighth", "8").replace("Ninth", "9").replace("Tenth", "10").replace("Eleventh", "11").replace("Twelfth", "12"))
        planet_house[p.name] = house_num
        p_rows.append({"星体": p.name, "星座": zh_sign(p.sign), "度数": fmt_deg(p.position), "宫位": house_num, "逆行": "是" if p.retrograde else "否"})

    extra = [
        ("NorthNode", getattr(subject, "true_north_lunar_node", None)),
        ("Chiron", getattr(subject, "chiron", None)),
        ("Lilith", getattr(subject, "mean_lilith", None)),
        ("ASC", getattr(subject, "first_house", None)),
        ("MC", getattr(subject, "tenth_house", None)),
    ]
    for n, p in extra:
        if p is None:
            continue
        p_rows.append({"星体": n, "星座": zh_sign(p.sign), "度数": fmt_deg(p.position), "宫位": "-", "逆行": "-"})

    hs_rows = []
    for i, attr in enumerate(HOUSE_ATTRS, start=1):
        h = getattr(subject, attr)
        for j, r in enumerate(SIGN_RULERS.get(h.sign, ["-"])):
            hs_rows.append({"宫位": i if j == 0 else "", "宫头星座": f"{zh_sign(h.sign)} {fmt_deg(h.position)}" if j == 0 else "", "宫主星": r, "飞入": planet_house.get(r, "-")})

    asp_rows = []
    for i, a in enumerate(sorted(NatalAspects(subject).relevant_aspects, key=lambda x: x.orbit), start=1):
        asp_rows.append({"序": i, "星体1": a.p1_name, "相位": ASPECT_ZH.get(a.aspect, a.aspect), "星体2": a.p2_name, "方向": "入相" if a.aspect_movement == "Applying" else "出相", "容许度": fmt_deg(abs(a.orbit))})

    compact = {
        "v": 1,
        "src": "kerykeion",
        "p": [[ABBR.get(r["星体"], r["星体"][:2]), r["星座"], r["度数"], r["宫位"], 1 if r["逆行"] == "是" else 0] for r in p_rows if r["星体"] in ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]],
        "a": [[ABBR.get(x["星体1"], x["星体1"][:2]), x["相位"], ABBR.get(x["星体2"], x["星体2"][:2]), x["容许度"], 1 if x["方向"] == "入相" else 0] for x in asp_rows[:24]],
    }
    return pd.DataFrame(p_rows), pd.DataFrame(hs_rows), pd.DataFrame(asp_rows), compact


def data_from_swiss(d: date, t: time, tz: str, lat: float, lon: float) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    sc = compute_swiss_chart(d, t, tz, lat, lon)
    p_rows = []
    planet_house = {}
    majors = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
    for n in majors:
        p = sc.points[n]
        planet_house[n] = p.house
        p_rows.append({"星体": n, "星座": zh_sign(p.sign), "度数": fmt_deg(p.pos), "宫位": p.house, "逆行": "是" if p.retro else "否"})
    for n in ["True_North_Lunar_Node", "Chiron", "Mean_Lilith"]:
        if n not in sc.points:
            continue
        p = sc.points[n]
        p_rows.append({"星体": n, "星座": zh_sign(p.sign), "度数": fmt_deg(p.pos), "宫位": p.house, "逆行": "是" if p.retro else "否"})

    hs_rows = []
    for i in range(1, 13):
        h = sc.houses[i - 1]
        sign_idx = int((h % 360) // 30)
        sign = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"][sign_idx]
        pos = (h % 30)
        for j, r in enumerate(SIGN_RULERS.get(sign, ["-"])):
            hs_rows.append({"宫位": i if j == 0 else "", "宫头星座": f"{zh_sign(sign)} {fmt_deg(pos)}" if j == 0 else "", "宫主星": r, "飞入": planet_house.get(r, "-")})

    asp_rows = []
    for i, a in enumerate(sc.aspects, start=1):
        asp_rows.append({"序": i, "星体1": a.p1, "相位": ASPECT_ZH.get(a.asp, a.asp), "星体2": a.p2, "方向": "入相" if a.applying else "出相", "容许度": fmt_deg(a.orb)})

    compact = {
        "v": 1,
        "src": "swisseph",
        "p": [[ABBR.get(n, n[:2]), sc.points[n].sign, round(sc.points[n].pos, 2), sc.points[n].house, 1 if sc.points[n].retro else 0] for n in majors],
        "h": [[i + 1, ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"][int((sc.houses[i] % 360) // 30)], round(sc.houses[i] % 30, 2)] for i in range(12)],
        "a": [[ABBR.get(a.p1, a.p1[:2]), a.asp, ABBR.get(a.p2, a.p2[:2]), round(a.orb, 2), 1 if a.applying else 0] for a in sc.aspects[:24]],
    }
    return pd.DataFrame(p_rows), pd.DataFrame(hs_rows), pd.DataFrame(asp_rows), compact


# DEPRECATED: This function used incorrect angular midpoint algorithm.
# Marks chart should use midpoint of DATE/TIME/LOCATION, not planet positions.
# def build_midpoint_points(base_points: dict, ref_points: dict, ref_houses: list[float]) -> dict:
    out = {}
    for key in MARX_KEYS:
        if key not in base_points or key not in ref_points:
            continue
        lon = angle_mid(base_points[key].abs_pos, ref_points[key]["abs_pos"])
        sign = SIGN_KEYS[int(lon // 30)]
        pos = lon % 30
        out[key] = {
            "name": key,
            "abs_pos": lon,
            "sign": sign,
            "pos": pos,
            "house": house_of(lon, ref_houses),
        }
    return out


# DEPRECATED: See build_midpoint_points above.
# def build_marx_points_aspects(rows_name: str, points: dict, houses: list[float]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    p_rows = []
    for key in MARX_KEYS:
        if key not in points:
            continue
        p = points[key]
        p_rows.append(
            {
                "星体": p["name"],
                "星座": zh_sign(p["sign"]),
                "度数": fmt_deg(p["pos"]),
                "宫位": p["house"],
                "逆行": "-",
            }
        )

    asp_rows = []
    keys = [k for k in MARX_KEYS if k in points]
    idx = 1
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            p1 = points[keys[i]]
            p2 = points[keys[j]]
            dist = angle_dist(p1["abs_pos"], p2["abs_pos"])
            for asp_name, exact, orb_max in ASPECT_RULES:
                orb = abs(dist - exact)
                if orb <= orb_max:
                    asp_rows.append(
                        {
                            "序": idx,
                            "星体1": p1["name"],
                            "相位": ASPECT_ZH.get(asp_name, asp_name),
                            "星体2": p2["name"],
                            "方向": "-",
                            "容许度": fmt_deg(orb),
                        }
                    )
                    idx += 1
                    break

    compact = {
        "name": rows_name,
        "p": [[ABBR.get(r["星体"], r["星体"][:2]), r["星座"], r["度数"], r["宫位"]] for r in p_rows],
        "a": [[ABBR.get(r["星体1"], r["星体1"][:2]), r["相位"], ABBR.get(r["星体2"], r["星体2"][:2]), r["容许度"]] for r in asp_rows[:24]],
        "h": [[i + 1, zh_sign(SIGN_KEYS[int(norm_deg(houses[i]) // 30)]), round(norm_deg(houses[i]) % 30, 2)] for i in range(12)],
    }
    return pd.DataFrame(p_rows), pd.DataFrame(asp_rows), compact


def marx_chart_bundle(
    a_name: str,
    b_name: str,
    a_d: date,
    a_t: time,
    a_lat: float,
    a_lon: float,
    b_d: date,
    b_t: time,
    b_lat: float,
    b_lon: float,
) -> dict:
    # Step 1: Compute Davison spacetime midpoint
    mid_lat = (a_lat + b_lat) / 2.0
    mid_lon = lon_mid(a_lon, b_lon)
    mid_d, mid_t = midpoint_datetime(a_d, a_t, b_d, b_t, DEFAULT_TZ)
    # Clamp latitude to valid range for house calculation
    mid_lat = max(-89.99, min(89.99, mid_lat))
    st_sc = compute_swiss_chart(mid_d, mid_t, DEFAULT_TZ, mid_lat, mid_lon)

    # Step 2: Compute A's Marks chart = midpoint(A natal, Davison) for DATE/TIME/LOCATION
    marx_a_d, marx_a_t = midpoint_datetime(a_d, a_t, mid_d, mid_t, DEFAULT_TZ)
    marx_a_lat = (a_lat + mid_lat) / 2.0
    marx_a_lon = lon_mid(a_lon, mid_lon)

    # Step 3: Compute B's Marks chart = midpoint(B natal, Davison) for DATE/TIME/LOCATION
    marx_b_d, marx_b_t = midpoint_datetime(b_d, b_t, mid_d, mid_t, DEFAULT_TZ)
    marx_b_lat = (b_lat + mid_lat) / 2.0
    marx_b_lon = lon_mid(b_lon, mid_lon)

    # Extract data from swiss charts (reuse existing function)
    a_p, a_h, a_a, a_c = data_from_swiss(marx_a_d, marx_a_t, DEFAULT_TZ, marx_a_lat, marx_a_lon)
    b_p, b_h, b_a, b_c = data_from_swiss(marx_b_d, marx_b_t, DEFAULT_TZ, marx_b_lat, marx_b_lon)

    return {
        "a_points_df": a_p,
        "a_aspects_df": a_a,
        "b_points_df": b_p,
        "b_aspects_df": b_a,
        "compact": {
            "v": 1,
            "type": "marx-davison-derived",
            "tz": DEFAULT_TZ,
            "people": {
                "a": {"name": a_name, "birth": f"{a_d.isoformat()}T{a_t.strftime('%H:%M')}", "loc": [round(a_lat, 4), round(a_lon, 4)]},
                "b": {"name": b_name, "birth": f"{b_d.isoformat()}T{b_t.strftime('%H:%M')}", "loc": [round(b_lat, 4), round(b_lon, 4)]},
            },
            "spacetime": {
                "birth": f"{mid_d.isoformat()}T{mid_t.strftime('%H:%M')}",
                "loc": [round(mid_lat, 4), round(mid_lon, 4)],
                "h": [[i + 1, zh_sign(SIGN_KEYS[int(norm_deg(st_sc.houses[i]) // 30)]), round(norm_deg(st_sc.houses[i]) % 30, 2)] for i in range(12)],
            },
            "marx": {
                "a_view": {
                    "name": f"{a_name}视角",
                    "birth": f"{marx_a_d.isoformat()}T{marx_a_t.strftime('%H:%M')}",
                    "loc": [round(marx_a_lat, 4), round(marx_a_lon, 4)],
                    **a_c,
                },
                "b_view": {
                    "name": f"{b_name}视角",
                    "birth": f"{marx_b_d.isoformat()}T{marx_b_t.strftime('%H:%M')}",
                    "loc": [round(marx_b_lat, 4), round(marx_b_lon, 4)],
                    **b_c,
                },
            },
        },
    }


def main() -> None:
    st.set_page_config(page_title="西方占星本命盘", layout="wide")
    st.title("西方占星本命盘（双引擎本地版）")
    st.caption("参数页对标：星体位置 / 宫位星座 / 行星相位。AI报告采用极简JSON，低token消费。")

    with st.sidebar:
        engine = st.selectbox("参数计算引擎", ["双引擎(推荐)", "SwissEphemeris", "Kerykeion"], index=0)
        gender = st.selectbox("性别(用于紫微斗数)", ["男", "女"], index=0)
        name = st.text_input("A姓名", value="命主A")
        d = st.date_input("A出生日期", value=date(1995, 8, 15), min_value=date(1200, 1, 1), max_value=date(2200, 12, 31))
        tm = st.time_input("A出生时间", value=time(14, 30), step=timedelta(minutes=1))
        tz = DEFAULT_TZ
        lat = st.number_input("A纬度", value=float(DEFAULT_LAT), format="%.6f")
        lon = st.number_input("A经度", value=float(DEFAULT_LON), format="%.6f")
        st.markdown("---")
        b_name = st.text_input("B姓名", value="命主B")
        b_d = st.date_input("B出生日期", value=date(1996, 1, 1), min_value=date(1200, 1, 1), max_value=date(2200, 12, 31))
        b_tm = st.time_input("B出生时间", value=time(12, 0), step=timedelta(minutes=1))
        b_lat = st.number_input("B纬度", value=float(DEFAULT_LAT), format="%.6f")
        b_lon = st.number_input("B经度", value=float(DEFAULT_LON), format="%.6f")
        run = st.button("生成", type="primary")

    if not run:
        st.info("请在左侧填写参数并点击生成")
        return

    try:
        ks = k_subject(name, d, tm, tz, float(lat), float(lon))
    except Exception as exc:
        st.error(f"计算失败: {exc}")
        return

    k_p, k_h, k_a, k_r = data_from_kerykeion(ks)
    s_p, s_h, s_a, s_r = data_from_swiss(d, tm, tz, float(lat), float(lon))

    if engine == "Kerykeion":
        p_df, h_df, a_df, report = k_p, k_h, k_a, k_r
    elif engine == "SwissEphemeris":
        p_df, h_df, a_df, report = s_p, s_h, s_a, s_r
    else:
        p_df, h_df, a_df, report = s_p, s_h, s_a, s_r
        # Quick consistency check on 10 major planets.
        k_map = {row["星体"]: row for _, row in k_p.iterrows() if row["星体"] in ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]}
        s_map = {row["星体"]: row for _, row in s_p.iterrows() if row["星体"] in ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]}
        diffs = [n for n in k_map if k_map[n]["星座"] != s_map[n]["星座"]]
        if diffs:
            st.warning(f"双引擎校验提示：以下星体星座不一致 {diffs}，已默认采用 SwissEphemeris 输出。")

    bazi_df, bazi_compact = bazi_payload(d, tm)
    ziwei_df, ziwei_compact, ziwei_year_transform = ziwei_payload(d, tm, gender)
    marx_bundle = marx_chart_bundle(
        a_name=name,
        b_name=b_name,
        a_d=d,
        a_t=tm,
        a_lat=float(lat),
        a_lon=float(lon),
        b_d=b_d,
        b_t=b_tm,
        b_lat=float(b_lat),
        b_lon=float(b_lon),
    )

    tabs = st.tabs(["星盘图", "星体位置", "宫位星座", "行星相位", "AI报告", "八字", "紫微斗数", "马克思盘", "总AI包"]) 

    with tabs[0]:
        try:
            svg_name, svg_text = render_svg(ks)
            components.html(svg_text, height=640, scrolling=True)
            st.download_button("下载SVG", data=svg_text.encode("utf-8"), file_name=svg_name, mime="image/svg+xml")
        except Exception as exc:
            st.error(f"渲染失败: {exc}")

    with tabs[1]:
        st.dataframe(p_df, use_container_width=True, hide_index=True)

    with tabs[2]:
        st.dataframe(h_df, use_container_width=True, hide_index=True)

    with tabs[3]:
        st.dataframe(a_df, use_container_width=True, hide_index=True)

    with tabs[4]:
        meta = {"v": 1, "tz": tz, "loc": [round(float(lat), 4), round(float(lon), 4)], "sys": "Tropical-Placidus", "engine": engine}
        final = {**meta, **report}
        western_file = f"{name}_western.min.json"
        western_path, western_bytes = write_compact_json(western_file, final)
        st.caption(f"独立JSON: `{western_path}`")
        st.code(western_bytes.decode("utf-8"), language="json")
        st.download_button("下载西盘AI包(JSON)", data=western_bytes, file_name=western_file, mime="application/json")

    with tabs[5]:
        st.caption("引擎: lunar-python（本地）")
        st.dataframe(bazi_df, use_container_width=True, hide_index=True)
        bazi_file = f"{name}_bazi.min.json"
        bazi_path, bazi_bytes = write_compact_json(bazi_file, bazi_compact)
        st.caption(f"独立JSON: `{bazi_path}`")
        st.code(bazi_bytes.decode("utf-8"), language="json")
        st.download_button("下载八字AI包(JSON)", data=bazi_bytes, file_name=bazi_file, mime="application/json")

    with tabs[6]:
        st.caption("引擎: iztro.js（本地）")
        st.info("紫微斗数采用与八字同源的农历换算结果进行排盘。")
        st.dataframe(ziwei_df, use_container_width=True, hide_index=True)
        if ziwei_year_transform:
            st.markdown(f"**生年四化**: {ziwei_year_transform}")
        ziwei_file = f"{name}_ziwei.min.json"
        ziwei_path, ziwei_bytes = write_compact_json(ziwei_file, ziwei_compact)
        st.caption(f"独立JSON: `{ziwei_path}`")
        st.code(ziwei_bytes.decode("utf-8"), language="json")
        st.download_button("下载紫微AI包(JSON)", data=ziwei_bytes, file_name=ziwei_file, mime="application/json")

    with tabs[7]:
        st.caption("马克思盘（A/B本命 + 时空盘 + 各自与时空盘中点）")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader(f"{name}视角马盘")
            st.dataframe(marx_bundle["a_points_df"], use_container_width=True, hide_index=True)
            st.dataframe(marx_bundle["a_aspects_df"], use_container_width=True, hide_index=True)
        with c2:
            st.subheader(f"{b_name}视角马盘")
            st.dataframe(marx_bundle["b_points_df"], use_container_width=True, hide_index=True)
            st.dataframe(marx_bundle["b_aspects_df"], use_container_width=True, hide_index=True)
        marx_file = f"{name}_{b_name}_marx.min.json"
        marx_path, marx_bytes = write_compact_json(marx_file, marx_bundle["compact"])
        st.caption(f"独立JSON: `{marx_path}`")
        st.code(marx_bytes.decode("utf-8"), language="json")
        st.download_button("下载马盘AI包(JSON)", data=marx_bytes, file_name=marx_file, mime="application/json")

    with tabs[8]:
        all_compact = {
            "v": 1,
            "name": name,
            "tz": tz,
            "loc": [round(float(lat), 4), round(float(lon), 4)],
            "western": final,
            "bazi": bazi_compact,
            "ziwei": ziwei_compact,
            "marx": marx_bundle["compact"],
        }
        all_file = f"{name}_all_systems.min.json"
        all_path, all_bytes = write_compact_json(all_file, all_compact)
        st.caption(f"聚合JSON(可选): `{all_path}`")
        st.code(all_bytes.decode("utf-8"), language="json")
        st.download_button("下载总AI包(JSON)", data=all_bytes, file_name=all_file, mime="application/json")


if __name__ == "__main__":
    main()
