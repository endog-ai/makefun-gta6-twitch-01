"""Forecast GTA VI's launch-day Twitch viewers hour by hour (make.fun
gta6-twitch-ccu-forecast-01).

Method: launch-day SHAPE in log space, conditioned on the size of hour 1.

A launch day has a strong shape: viewers dip overnight (hours 2-7, UTC), then
rise to an evening peak (hours 19-22) as the world's time zones unlock and
streamers start. But the shape depends enormously on how big hour 1 already
is: a small launch (hour 1 in the hundreds) grows ~100x by the evening, while
a huge launch (hour 1 near a million) is already near its peak and stays flat.
Across the 37 past launches in the kit, the evening log-shape correlates about
-0.93 with log(hour 1) -- so one median shape fits nobody.

This forecaster therefore conditions on hour 1 with a local (k-nearest)
estimate: for each hour h, it takes the log-shape log(v_h / v_1) of every past
launch, weights each by a Gaussian kernel in log(hour 1) (bandwidth 0.6), and
reads off the weighted 5/25/50/75/95% quantiles. The five quantile curves are
then lightly smoothed over neighbouring hours (centre-weighted 1-2-1 moving
average in log space), which removes single-hour noise without blunting the
day/night shape. The forecast is the target's hour-1 print times the
exponentiated shape.

Pure standard library, deterministic (no randomness, no clock, no network):
two runs on the same case write byte-identical output.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# Standard-normal quantiles, used only by the fallback (persistence) forecast.
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
# Gaussian kernel bandwidth in log(hour-1) units for the local shape estimate.
BANDWIDTH = 0.6
# Smoothing half-window (hours) for the quantile curves: 1 = 3-hour moving average.
SMOOTH = 1


def parse_dt(s):
    """Parse an ISO-8601 UTC timestamp into an aware datetime."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def launch_day_hours(comp):
    """A comparable's release-day hourly viewers as {hour 1..24: viewers}.

    Returns None unless the comparable has a complete launch day (all 24 hours
    present and positive). This drops the GTA VI category's own pre-release
    history (no launch day yet) and any sparsely sampled launch.
    """
    day_start = parse_dt(comp["day_start"])
    hourly = {}
    for pt in comp.get("hourly") or []:
        viewers = pt.get("viewers")
        if viewers is None or viewers <= 0:
            continue
        try:
            t = parse_dt(pt["from"])
        except (KeyError, TypeError, ValueError):
            continue
        h = int((t - day_start).total_seconds() // 3600) + 1
        if 1 <= h <= 24:
            hourly[h] = viewers
    if len(hourly) != 24 or 1 not in hourly:
        return None
    return hourly


def weighted_quantile(points, weights, tau):
    """Weighted quantile of points (sorted ascending) at level tau."""
    order = sorted(range(len(points)), key=lambda i: points[i])
    total = sum(weights)
    if total <= 0:
        return points[order[len(order) // 2]]
    acc = 0.0
    for i in order:
        acc += weights[i]
        if acc >= tau * total:
            return points[i]
    return points[order[-1]]


def shape_quantiles(train, p1):
    """Per-hour weighted quantiles of log-shape, given the target's hour-1 print.

    train: list of (log_h1, {hour: viewers}) for past launches.
    Returns {hour: [q05, q25, q50, q75, q95]} in log-shape units.
    """
    lx = math.log(p1)
    out = {}
    for h in range(2, 25):
        pts = []
        wts = []
        for log_h1, hourly in train:
            pts.append(math.log(hourly[h] / hourly[1]))
            wts.append(math.exp(-((log_h1 - lx) ** 2) / (2.0 * BANDWIDTH * BANDWIDTH)))
        out[h] = [weighted_quantile(pts, wts, tau) for tau in LEVELS]
    return out


def smooth_quantiles(logq):
    """Centre-weighted smoothing of each quantile curve (log space).

    A 3-hour triangular moving average (weights 1-2-1): it removes single-hour
    noise from the weighted quantiles while preserving the day/night peak
    better than a flat average. At the ends (hours 2 and 24) only the hours
    that exist are averaged, with their weights renormalised.
    """
    out = {}
    for h in range(2, 25):
        row = []
        for qi in range(len(LEVELS)):
            num = 0.0
            den = 0.0
            for hh in range(max(2, h - SMOOTH), min(24, h + SMOOTH) + 1):
                w = 2.0 if hh == h else 1.0
                num += w * logq[hh][qi]
                den += w
            row.append(num / den)
        out[h] = row
    return out


def round2(x):
    """Round to 2 decimals, half up (matches the house baseline's rounding)."""
    scaled = x * 100.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100.0
    return int(value) if float(value).is_integer() else value


def fallback_forecast(p1):
    """Persistence with a widening spread (the house baseline's shape).

    Used only if a case carries no usable past launch at all.
    """
    hours = []
    for h in range(2, 25):
        qs = []
        prev = 0.0
        for z in Z:
            q = max(1.0, p1 * math.exp(z * 0.15 * math.sqrt(h - 1)))
            q = round2(q)
            q = max(q, prev)  # keep non-decreasing after rounding
            prev = q
            qs.append(q)
        hours.append({"hour": h, "q": qs})
    return {"hours": hours}


def forecast_case(case, name):
    """Forecast hours 2..24 of one case."""
    if case.get("levels") != LEVELS:
        raise ValueError(f"{name} asks for levels {case.get('levels')}, not {LEVELS}")
    first = next((k for k in case.get("known") or [] if k.get("hour") == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1.0, float(first["viewers"]))

    # Past launches with a complete launch-day curve, in name order (deterministic).
    train = []
    for comp in sorted(case.get("comparables") or [], key=lambda c: c.get("name", "")):
        hourly = launch_day_hours(comp)
        if hourly is not None:
            train.append((math.log(hourly[1]), hourly))
    if not train:
        return fallback_forecast(p1)

    logq = shape_quantiles(train, p1)
    logq = smooth_quantiles(logq)
    hours = []
    for h in range(2, 25):
        qs = []
        prev = 0.0
        for q in logq[h]:
            v = max(1.0, min(1e9, p1 * math.exp(q)))
            v = round2(v)
            v = max(v, prev)  # keep non-decreasing after rounding
            prev = v
            qs.append(v)
        hours.append({"hour": h, "q": qs})
    return {"hours": hours}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        out = json.dumps(forecast, separators=(",", ":")) + "\n"
        if len(out.encode("utf-8")) > 65536:
            raise ValueError(f"{path.name}: output over 65,536 bytes")
        (OUTPUT_DIR / f"{path.stem}.out").write_text(out, encoding="utf-8")


if __name__ == "__main__":
    main()
