#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from kerykeion import AstrologicalSubject, KerykeionChartSVG


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate natal chart by kerykeion module.")
    parser.add_argument("--name", default="native")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--day", type=int, required=True)
    parser.add_argument("--hour", type=int, required=True)
    parser.add_argument("--minute", type=int, required=True)
    parser.add_argument("--tz", required=True, help="IANA timezone, e.g. Asia/Shanghai")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--out-dir", default="output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    subject = AstrologicalSubject(
        name=args.name,
        year=args.year,
        month=args.month,
        day=args.day,
        hour=args.hour,
        minute=args.minute,
        lat=args.lat,
        lng=args.lon,
        tz_str=args.tz,
        online=False,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    chart = KerykeionChartSVG(subject, chart_type="Natal", new_output_directory=str(out_dir))
    chart.makeSVG()

    print(f"SVG: {out_dir / (args.name + ' - Natal Chart.svg')}")
    for pname in ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto"]:
        p = getattr(subject, pname)
        print(f"{p.name:8} {p.sign:>3} {p.position:05.2f}° {p.house}")


if __name__ == "__main__":
    main()
