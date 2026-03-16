# macOS 占星/命理本地系统（西盘 + 八字 + 紫微）

已统一为“同源历法链路”并升级紫微引擎：
- 八字：`lunar-python`
- 紫微：先用 `lunar-python` 做公历→农历，再调用官方 `iztro` JS（本地 Node）
- 西盘：`kerykeion + pyswisseph`

## 运行
```bash
cd /Users/xinyangguo/Codex/western_astrology_chart
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## 说明
- 所有计算本地执行。
- 紫微输出 compact JSON 的 `in` 字段里会记录：
  - `lunar_date_for_calc`
  - `is_leap_month`
  - `bazi_pillars`
- 紫微引擎调用路径：`tools/ziwei_node/ziwei_calc.mjs`（官方 `iztro` npm 包）。
