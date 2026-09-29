def classify_source(pv_w: float | None, battery_soc: float | None, grid_present: bool, load_w: float | None) -> str:
    pv_w, battery_soc, load_w = pv_w or 0.0, battery_soc or 0.0, load_w or 0.0
    if grid_present:
        return "GRID"
    if pv_w > load_w * 0.9:
        return "SOLAR"
    if battery_soc > 2.0:
        return "BATTERY"
    return "NONE"


def autonomy_hours(battery_soc: float | None, capacity_kwh: float, load_w: float | None, reserve_pct: float = 15.0) -> float:
    load_w = load_w or 0.0
    if load_w <= 1:
        return 999.0
    usable_kwh = max(0.0, ((battery_soc or 0.0) - reserve_pct) / 100.0) * capacity_kwh
    return usable_kwh * 1000.0 / load_w