from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import swisseph as swe

PLANETS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
    "True_North_Lunar_Node": swe.TRUE_NODE,
    "Mean_North_Lunar_Node": swe.MEAN_NODE,
    "Chiron": swe.CHIRON,
    "Mean_Lilith": swe.MEAN_APOG,
}

SIGNS = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]

ASPECTS = [
    ("conjunction", 0, 8.0),
    ("sextile", 60, 5.0),
    ("square", 90, 6.0),
    ("trine", 120, 6.0),
    ("opposition", 180, 8.0),
]


@dataclass
class Point:
    name: str
    abs_pos: float
    sign: str
    pos: float
    house: int | None
    retro: bool


@dataclass
class Aspect:
    p1: str
    asp: str
    p2: str
    orb: float
    applying: bool


@dataclass
class SwissChart:
    points: dict[str, Point]
    houses: list[float]
    aspects: list[Aspect]


def _norm(x: float) -> float:
    return x % 360.0


def _sign_pos(abs_pos: float) -> tuple[str, float]:
    i = int(_norm(abs_pos) // 30)
    return SIGNS[i], _norm(abs_pos) % 30


def _house_of(abs_pos: float, cusps: list[float]) -> int:
    x = _norm(abs_pos)
    c = [_norm(v) for v in cusps]
    for i in range(12):
        a = c[i]
        b = c[(i + 1) % 12]
        if a <= b:
            if a <= x < b:
                return i + 1
        else:
            if x >= a or x < b:
                return i + 1
    return 12


def _ang_dist(a: float, b: float) -> float:
    d = abs(_norm(a - b))
    return min(d, 360 - d)


def _is_applying(lon1: float, sp1: float, lon2: float, sp2: float, exact: float) -> bool:
    # Small-step approximation: if future distance to exact is smaller, treat as applying.
    d_now = abs(_ang_dist(lon1, lon2) - exact)
    n1 = _norm(lon1 + sp1)
    n2 = _norm(lon2 + sp2)
    d_next = abs(_ang_dist(n1, n2) - exact)
    return d_next < d_now


def compute_swiss_chart(
    birth_date: date,
    birth_time: time,
    tz_str: str,
    lat: float,
    lon: float,
    house_system: str = "P",
) -> SwissChart:
    local_dt = datetime(
        birth_date.year,
        birth_date.month,
        birth_date.day,
        birth_time.hour,
        birth_time.minute,
        birth_time.second,
        tzinfo=ZoneInfo(tz_str),
    )
    utc = local_dt.astimezone(ZoneInfo("UTC"))
    hour = utc.hour + utc.minute / 60 + utc.second / 3600
    jd = swe.julday(utc.year, utc.month, utc.day, hour, swe.GREG_CAL)

    cusps, _ = swe.houses_ex(jd, lat, lon, house_system.encode("ascii"))
    houses = list(cusps)

    points: dict[str, Point] = {}
    speeds: dict[str, float] = {}
    for name, code in PLANETS.items():
        try:
            xx, _ = swe.calc_ut(jd, code)
        except swe.Error:
            # Optional points (e.g. Chiron) may require extra eph files; skip when unavailable.
            continue
        abs_pos = _norm(xx[0])
        sign, pos = _sign_pos(abs_pos)
        retro = xx[3] < 0
        points[name] = Point(
            name=name,
            abs_pos=abs_pos,
            sign=sign,
            pos=pos,
            house=_house_of(abs_pos, houses),
            retro=retro,
        )
        speeds[name] = xx[3]

    aspects: list[Aspect] = []
    keys = [k for k in ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "True_North_Lunar_Node", "Chiron"] if k in points]
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            p1 = points[keys[i]]
            p2 = points[keys[j]]
            dist = _ang_dist(p1.abs_pos, p2.abs_pos)
            for asp_name, deg, orb_max in ASPECTS:
                orb = abs(dist - deg)
                if orb <= orb_max:
                    aspects.append(
                        Aspect(
                            p1=p1.name,
                            asp=asp_name,
                            p2=p2.name,
                            orb=orb,
                            applying=_is_applying(p1.abs_pos, speeds[p1.name], p2.abs_pos, speeds[p2.name], deg),
                        )
                    )
                    break

    aspects.sort(key=lambda x: x.orb)
    return SwissChart(points=points, houses=houses, aspects=aspects)
