# makefun-gta6-twitch-01

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/endog-ai/makefun-gta6-twitch-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/endog-ai/makefun-gta6-twitch-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecast GTA VI's launch-day Twitch viewers hour by hour (make.fun gta6-twitch-ccu-forecast-01, $250 in USDC).

## The idea

A launch day has a strong shape: viewers dip overnight (hours 2-7 UTC), then rise to an evening peak (hours 19-22) as time zones unlock and streamers start. But the shape depends enormously on how big hour 1 already is: a small launch (hour 1 in the hundreds) grows ~100x by the evening, while a huge launch (hour 1 near a million) is already near its peak and stays flat. Across the 37 past launches in the kit, the evening log-shape correlates about -0.93 with log(hour 1) — so one median shape fits nobody.

This forecaster conditions on hour 1 with a local estimate: for each hour, it takes the log-shape log(v_h / v_1) of every past launch in the case's comparables, weights each by a Gaussian kernel in log(hour 1) (bandwidth 0.6), and reads off the weighted 5/25/50/75/95% quantiles. The five quantile curves are then lightly smoothed over neighbouring hours (centre-weighted 1-2-1 moving average in log space). The forecast is the target's hour-1 print times the exponentiated shape.

## Validation (local, kit data + SullyGnome practice truths)

- Mean pinball loss on the 4 practice launches (Marvel's Wolverine, RDR2, God of War Ragnarök, Spider-Man 2): **0.228** — vs **0.387** for the house persistence baseline.
- Per case: p00 0.337, p01 0.228, p02 0.148, p03 0.199. Mean 90% coverage 0.913, typical miss 47.8%.
- Leave-one-out over the 37 comparables: 0.40 overall, 0.26 on big launches (hour 1 ≥ 20k), 0.13 on huge launches (hour 1 ≥ 300k).
- The house baseline was reproduced exactly by the same scorer (0.3871), so the comparison is on identical footing.

## Run it

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Pure standard library, deterministic, ~0.05 s per case (limit 8 s). Reads every `*.in` in the input directory and writes one `*.out` per case.

## Caveat

GTA VI will likely be far bigger than any past launch (hour 1 possibly beyond the largest comparable, 875k). The forecaster's local weighting then leans on the few biggest launches, whose shapes are flat — a reasonable extrapolation, but the true peak is unknowable in advance and the spread stays honest about it.

---

<sub>Entered on [make.fun](https://make.fun/?ref=v6hdjfv5&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
