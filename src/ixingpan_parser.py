"""Parse ixingpan.com chart HTML into structured JSON."""
from __future__ import annotations

import json
import re
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag


# Cookie values for enabling all planets per chart type
_ALL_PLANETS_CSV = "0,1,2,3,4,5,6,7,8,9,10,12,15,17,18,19,20,23,25,26,27,28,29,30,116,117"
_CHART_TYPES = ["natal", "marks", "comparision", "composite", "timespacemid",
                "synastry", "transit", "progressed", "secprogressed",
                "thirdprogressed", "solarreturn", "lunarreturn", "solararc"]


def fetch_chart(url: str, timeout: int = 15) -> str:
    session = requests.Session()
    # Set planet cookies for all chart types so all asteroids are included
    for ct in _CHART_TYPES:
        session.cookies.set(f"xp_planets_{ct}", _ALL_PLANETS_CSV, domain="xp.ixingpan.com")
    resp = session.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _parse_table(table: Tag) -> list[list[str]]:
    rows = []
    for tr in table.find_all("tr"):
        cells = [_clean(td.get_text()) for td in tr.find_all(["td", "th"])]
        if cells:
            rows.append(cells)
    return rows


def _parse_axes(table: Tag) -> dict:
    rows = _parse_table(table)
    if len(rows) < 2:
        return {}
    headers = rows[0]  # 上升 下降 中天 天底
    values = rows[1]
    axes = {}
    name_map = {"上升": "ascendant", "下降": "descendant", "中天": "midheaven", "天底": "imum_coeli"}
    for i, h in enumerate(headers):
        key = name_map.get(h, h)
        if i < len(values):
            val = values[i]
            m = re.match(r"(\S+?)\s*(\d+°\d+)", val)
            if m:
                axes[key] = {"sign": m.group(1), "degree": m.group(2)}
            else:
                axes[key] = {"sign": val}
    return axes


def _parse_planets(table: Tag) -> list[dict]:
    rows = _parse_table(table)
    planets = []
    for row in rows[1:]:  # skip header
        if len(row) < 4:
            continue
        planet_name = row[0]
        # sign + degree
        sign_info = row[1]
        m = re.match(r"(\S+?)\(?(\d+°\d+)", sign_info)
        sign = m.group(1) if m else sign_info
        degree = m.group(2) if m else ""

        # house + house_degree
        house_info = row[2]
        m2 = re.match(r"(\d+)宫\s*(\d+°\d+)", house_info)
        if m2:
            house = int(m2.group(1))
            house_degree = m2.group(2)
        else:
            m3 = re.match(r"(\d+)", house_info)
            house = int(m3.group(1)) if m3 else 0
            house_degree = ""

        retro = "√" in row[3] if len(row) > 3 else False

        # dignity (庙/旺/弱/陷)
        dignity = None
        for d in ("庙", "旺", "弱", "陷"):
            if d in sign_info or (len(row) > 4 and d in row[4]):
                dignity = d
                break

        planets.append({
            "planet": planet_name,
            "sign": sign,
            "degree": degree,
            "house": house,
            "house_degree": house_degree,
            "retrograde": retro,
            "dignity": dignity,
        })
    return planets


def _parse_houses(table: Tag) -> list[dict]:
    rows = _parse_table(table)
    houses = []
    for row in rows[1:]:
        if len(row) < 4:
            continue
        house_num = re.search(r"(\d+)", row[0])
        if not house_num:
            continue
        sign_info = row[1]
        m = re.match(r"(\S+?)\(?(\d+°\d+)", sign_info)
        sign = m.group(1) if m else sign_info
        degree = m.group(2) if m else ""

        ruler_info = row[2]
        ruler_parts = re.findall(r"(\S+?)（(\S+?)）", ruler_info)

        ruler_sign_house = row[3] if len(row) > 3 else ""
        fly_match = re.findall(r"(\S+?)\s*(\d+)宫", ruler_sign_house)

        h = {"house": int(house_num.group(1)), "sign": sign, "degree": degree}

        if ruler_parts:
            h["ruler"] = ruler_parts[0][0]
            h["ruler_sign"] = ruler_parts[0][1] if len(ruler_parts[0]) > 1 else ""
            if fly_match:
                h["ruler_house"] = int(fly_match[0][1])
                if len(fly_match[0]) > 0:
                    h["ruler_sign"] = fly_match[0][0]
            if len(ruler_parts) > 1:
                h["co_ruler"] = ruler_parts[1][0]
                if len(fly_match) > 1:
                    h["co_ruler_sign"] = fly_match[1][0]
                    h["co_ruler_house"] = int(fly_match[1][1])
        else:
            # Simple format: just ruler name
            h["ruler"] = ruler_info.strip()
            if fly_match:
                h["ruler_sign"] = fly_match[0][0]
                h["ruler_house"] = int(fly_match[0][1])

        houses.append(h)
    return houses


def _parse_aspects(table: Tag) -> list[dict]:
    rows = _parse_table(table)
    aspects = []
    for row in rows[1:]:
        if len(row) < 5:
            continue
        direction = row[3] if row[3] in ("入相", "出相") else None
        aspects.append({
            "planet1": row[0],
            "aspect": row[1],
            "planet2": row[2],
            "direction": direction,
            "orb": row[4],
        })
    return aspects


def _parse_statistics(table: Tag) -> dict:
    rows = _parse_table(table)
    stats = {}
    for row in rows[1:]:
        if len(row) >= 3:
            stats[row[0]] = {"count": row[1], "detail": row[2]}
    return stats


def _parse_patterns(table: Tag) -> list[dict]:
    rows = _parse_table(table)
    patterns = []
    for row in rows[1:]:
        if len(row) >= 2:
            patterns.append({"name": row[0], "detail": row[1]})
    return patterns


def _parse_person_info(table: Tag) -> dict:
    rows = _parse_table(table)
    info = {}
    if rows:
        cells = rows[0]
        for i in range(0, len(cells) - 1, 2):
            key = cells[i].rstrip("：:").strip()
            val = cells[i + 1]
            if key == "出生时间":
                parts = val.split()
                if len(parts) >= 2:
                    info["birth_date"] = parts[0]
                    info["birth_time"] = parts[1]
            elif key == "出生地点":
                info["birth_place"] = val
            elif key == "所属星座":
                info["sun_sign"] = val
    return info


def parse_chart_html(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")

    result: dict[str, Any] = {}

    # Classify tables by their headers
    for table in tables:
        rows = _parse_table(table)
        if not rows:
            continue
        header = rows[0]
        header_str = " ".join(header)

        if "出生时间" in header_str:
            if "person_a" not in result:
                result["person_a"] = _parse_person_info(table)
            elif "person_b" not in result:
                result["person_b"] = _parse_person_info(table)
        elif "上升" in header and "下降" in header:
            result["axes"] = _parse_axes(table)
        elif "星体" in header and "落入星座" in header_str:
            result["planets"] = _parse_planets(table)
        elif "宫位" in header and "宫主星" in header_str:
            result["houses"] = _parse_houses(table)
        elif "星体1" in header and "相位" in header:
            result["aspects"] = _parse_aspects(table)
        elif "分类法" in header:
            result["statistics"] = _parse_statistics(table)
        elif "格局名称" in header:
            result["patterns"] = _parse_patterns(table)

    # Chart type from title
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text()
        for ct in ("马克思盘", "本命盘", "比较盘", "组合盘", "时空盘", "行运盘", "次限盘", "三限盘", "日返照", "月返照"):
            if ct in title:
                result["chart_type"] = ct
                break

    # System info
    for table in tables:
        rows = _parse_table(table)
        if rows and "黄道系统" in " ".join(rows[0]):
            cells = rows[0]
            result["system"] = {}
            for i in range(0, len(cells) - 1, 2):
                key = cells[i].rstrip("：:").strip()
                if "黄道" in key:
                    result["system"]["zodiac"] = cells[i + 1]
                elif "宫位" in key:
                    result["system"]["house_system"] = cells[i + 1].split()[0]

    return result


# All available planet IDs on ixingpan
ALL_PLANETS = [
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9,  # 日月水金火木土天海冥
    25, 26, 27, 28,                   # 上升 中天 下降 天底
    10, 23,                           # 北交 南交
    12,                               # 莉莉丝
    15,                               # 凯龙
    17, 18, 19, 20,                   # 谷神 智神 婚神 灶神
    116, 117,                         # 爱神 灵神
    29, 30,                           # 福点 宿命点
]


def add_planets_to_url(url: str, planets: list[int] | None = None) -> str:
    """Append planets[] params to a URL if not already present."""
    if "planets" in url:
        return url
    ps = planets or ALL_PLANETS
    sep = "&" if "?" in url else "?"
    params = sep + "&".join(f"planets%5B%5D={p}" for p in ps)
    # Strip hash fragment, append params, re-add hash
    base, _, frag = url.partition("#")
    result = base + params
    if frag:
        result += "#" + frag
    return result


def fetch_and_parse(url: str, all_planets: bool = True) -> dict:
    if all_planets:
        url = add_planets_to_url(url)
    html = fetch_chart(url)
    return parse_chart_html(html)


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else input("URL: ")
    data = fetch_and_parse(url)
    print(json.dumps(data, ensure_ascii=False, indent=2))
