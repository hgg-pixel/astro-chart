# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A local macOS astrological calculation system (西方占星/命理) that combines three divination systems:
- **Western Astrology (西盘)**: Using Kerykeion + PySwissEph for natal chart calculations
- **Bazi/Eight Characters (八字)**: Using lunar-python for traditional Chinese astrology
- **Ziwei Doushu (紫微斗数)**: Using iztro JS (official npm package) for Ziwei calculations

All calculations run locally. The main interface is a Streamlit web app (`app.py`) that presents data in human-readable tables and exports minimal JSON payloads optimized for AI analysis (low token consumption).

### Key Dependencies
- **streamlit==1.42.0**: Web UI framework
- **kerykeion==5.7.2**: Western astrology charts (SVG generation)
- **pyswisseph==2.10.3.2**: Swiss Ephemeris for planet positions and aspects
- **lunar-python==1.4.8**: Gregorian ↔ Lunar calendar conversion and Eight Characters calculations
- **iztro (npm)**: Ziwei Doushu engine (called via subprocess in Node.js)

## Development Commands

### Setup
```bash
cd /Users/xinyangguo/Codex/western_astrology_chart
source .venv/bin/activate
pip install -r requirements.txt
npm install --prefix tools/ziwei_node/
```

### Run
```bash
streamlit run app.py
```

### CLI (Alternative)
```bash
python src/cli.py --name "TestName" --year 1995 --month 8 --day 15 --hour 14 --minute 30 \
  --tz "Asia/Shanghai" --lat 31.2304 --lon 121.4737 --out-dir output
```

## Architecture

### Core Modules

**`src/engines/swiss_ephemeris.py`**
- Low-level Swiss Ephemeris wrapper using pyswisseph
- Core functions: `compute_swiss_chart(birth_date, birth_time, tz_str, lat, lon)`
- Returns: `SwissChart` dataclass with planets (positions, signs, houses), house cusps, and aspects
- Aspect calculation: Supports conjunction, sextile, square, trine, opposition with orb tolerances
- House assignment uses Placidus system (default, customizable via `house_system` parameter)

**`src/chinese_systems.py`**
- Orchestrates Bazi and Ziwei calculations
- `bazi_payload(date, time)`: Returns (DataFrame, compact_dict) with Eight Characters data
  - Uses `lunar-python` for conversion and calculation
  - Output includes pillars, Five Elements, Nayin, ShiShen
- `ziwei_payload(date, time, gender)`: Returns (DataFrame, compact_dict, year_transforms)
  - Converts Gregorian→Lunar using `lunar-python` (ensures consistency with Bazi)
  - Calls Node.js subprocess: `tools/ziwei_node/ziwei_calc.mjs` with iztro official package
  - Passes lunar_date, hour, gender, is_leap_month to Node script
  - Extracts palaces, major/minor/adjective stars, body palace, origin palace

**`src/cli.py`**
- Simple CLI entry point for batch natal chart generation via Kerykeion
- Useful for testing or integration pipelines

### Main App (`app.py`)

**Dual-Engine Logic** (lines 177-191)
- Generates both Kerykeion and SwissEphemeris charts in parallel
- User can select "双引擎(推荐)" [Dual Engine - Recommended], "SwissEphemeris", or "Kerykeion"
- For dual mode: Uses SwissEphemeris output by default but warns if 10 major planets differ in sign between engines
- Both engines produce identical data structure: (planets_df, houses_df, aspects_df, compact_json)

**Data Output Format** (7 tabs)
1. **星盘图** (Chart): SVG rendering via Kerykeion + HTML embed
2. **星体位置** (Planets): Planet names, signs, degrees, houses, retrograde status
3. **宫位星座** (Houses): House cusps, rulers, and "flying in" planets (飞入)
4. **行星相位** (Aspects): Major aspects with orbs and applicability direction
5. **AI报告** (Western AI Report): Compact JSON of western astrology data
6. **八字** (Bazi): Eight Characters table + compact JSON
7. **紫微斗数** (Ziwei): Palaces table + year transformations + compact JSON
8. **总AI包** (Combined): All three systems in single JSON

**Default Parameters** (lines 19-21)
- Timezone: Asia/Shanghai
- Location: Shanghai coordinates (31.2304°N, 121.4737°E)
- Birth date in sidebar: 1995-08-15, 14:30

### Cross-System Consistency
- **Lunar Calendar Source**: All three systems (Bazi, Ziwei, Western houses) derive lunar date from `lunar-python`
- **Ziwei metadata** includes: `lunar_date_for_calc`, `is_leap_month`, `bazi_pillars` for audit trail

## Key Implementation Details

### House System
- **Swiss Ephemeris** uses Placidus by default (customizable: "P" = Placidus, other systems available)
- **Kerykeion** uses its own house system (typically Placidus)
- House assignment logic: Normalized celestial longitude mapped to house cusps with wrapping at 360°

### Aspects
- **Allowed aspects**: conjunction (0°±8°), sextile (60°±5°), square (90°±6°), trine (120°±6°), opposition (180°±8°)
- **Applicability**: Calculated using small-step approximation of planet speeds (applying if future distance to exact is smaller)

### Compact JSON Format
- Uses ultra-compact keys (e.g., "Su"=Sun, "Mo"=Moon) to minimize token usage
- Stores only essentials: planet abbreviation, sign, degree, house, retrograde (1/0)
- Aspects: [p1_abbr, aspect_type, p2_abbr, orb, applying(1/0)]

### Node.js Integration
- **Ziwei engine**: Spawns subprocess calling `tools/ziwei_node/ziwei_calc.mjs`
- Node binary path: `.tools/node20/bin/node` (pre-downloaded, not system node)
- JSON IPC via stdout/stderr, arguments passed as JSON string
- **Important**: Must install Node dependencies beforehand: `npm install --prefix tools/ziwei_node/`

## File Structure
```
western_astrology_chart/
├── app.py                           # Main Streamlit app
├── requirements.txt                 # Python dependencies
├── src/
│   ├── chinese_systems.py          # Bazi & Ziwei orchestration
│   ├── cli.py                      # CLI for batch generation
│   └── engines/
│       └── swiss_ephemeris.py      # Low-level ephemeris calculations
├── tools/
│   └── ziwei_node/
│       ├── ziwei_calc.mjs          # Node.js Ziwei calculator
│       ├── package.json            # Node dependencies (iztro)
│       └── package-lock.json
├── .tools/
│   └── node20/                     # Pre-bundled Node.js binary
├── .venv/                          # Python virtual environment
└── output/                         # SVG charts generated at runtime
```

## Testing & Debugging

**No existing test suite.** Manual testing approach:
1. Run `streamlit run app.py`
2. Fill in birth parameters in sidebar
3. Verify consistency across tabs and between dual-engine modes
4. Check JSON compactness in AI report tabs

**Common Issues**:
- Node.js dependency missing: `npm install --prefix tools/ziwei_node/`
- Timezone issues: Ensure IANA timezone string is valid (e.g., "Asia/Shanghai")
- SVG rendering fails: Check Kerykeion installation and font availability

## Code Style & Patterns

- **Type hints**: Uses `from __future__ import annotations` and Python 3.9+ type syntax
- **Dataclasses**: Used for structured data (Point, Aspect, SwissChart)
- **Data pipelines**: Each system (Kerykeion, Swiss, Bazi, Ziwei) produces (DataFrame, compact_dict) tuple
- **Error handling**: Minimal; errors propagate to Streamlit UI for user feedback
- **Localization**: All UI text and column headers are in Chinese (simplified)

## Performance Notes

- All calculations are local and deterministic (no API calls)
- Streamlit reruns entire script on widget interaction; consider caching for large parameter spaces
- ZiWei calculation is slowest (Node subprocess spawn + iztro calculation)
- SVG generation (Kerykeion) is relatively fast but file I/O to output directory
