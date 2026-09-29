import math


def dew_point_c(t_c: float, rh_pct: float) -> float:
    a, b = 17.62, 243.12
    rh = min(max(rh_pct, 0.1), 100.0)
    gamma = math.log(rh / 100.0) + (a * t_c) / (b + t_c)
    return (b * gamma) / (a - gamma)


def svp_kpa(t_c: float) -> float:
    return 0.6108 * math.exp((17.27 * t_c) / (t_c + 237.3))


def vpd_kpa(t_c: float, rh_pct: float) -> float:
    return svp_kpa(t_c) * (1.0 - rh_pct / 100.0)


def abs_humidity_gm3(t_c: float, rh_pct: float) -> float:
    return 216.7 * (svp_kpa(t_c) * 10.0 * rh_pct / 100.0) / (t_c + 273.15)


def condensation_margin_c(surface_t: float, air_t: float, rh: float) -> float:
    return surface_t - dew_point_c(air_t, rh)