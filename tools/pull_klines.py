# -*- coding: utf-8 -*-
"""Pull 13-month daily K-lines for 6 indices/ETF proxies and compute summary metrics."""
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from futu import OpenQuoteContext, KLType, AuType, RET_OK

TICKERS = [
    ("US.SPY", "标普500", "SPX"),
    ("US.IWM", "罗素2000", "RUT"),
    ("SH.000300", "沪深300", "CSI300"),
    ("HK.800000", "恒生指数", "HSI"),
    ("JP..N225", "日经225", "N225"),
    ("US.FEZ", "斯托克50", "SX5E"),
]

def pct(a, b):
    return round((a / b - 1) * 100, 2) if b else None

def main():
    ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
    out = {}
    for code, cname, key in TICKERS:
        ret, data, _ = ctx.request_history_kline(
            code, start="2025-09-01", end="2026-10-14",
            ktype=KLType.K_DAY, autype=AuType.QFQ, max_count=1000)
        if ret != RET_OK:
            print(json.dumps({"error": code + ": " + str(data)}, ensure_ascii=False))
            continue
        rows = data.to_dict("records")
        closes = [(str(r["time_key"])[:10], float(r["close"])) for r in rows]
        if not closes:
            continue
        dates = [c[0] for c in closes]
        vals = [c[1] for c in closes]
        last_d, last = closes[-1]

        # helpers to find close on or before a date
        def close_at_or_before(dstr):
            best = None
            for d, v in closes:
                if d <= dstr:
                    best = v
                else:
                    break
            return best

        # YTD: last close of 2025
        y2025 = [v for d, v in closes if d.startswith("2025")]
        ytd_base = y2025[-1] if y2025 else vals[0]

        # 52-week window (approx 252 trading days back from end)
        w52 = vals[-252:] if len(vals) >= 252 else vals
        hi52, lo52 = max(w52), min(w52)

        # annualized vol from daily returns (last 60 sessions)
        rets = [(vals[i] / vals[i - 1] - 1) for i in range(max(1, len(vals) - 60), len(vals))]
        if rets:
            m = sum(rets) / len(rets)
            var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1) if len(rets) > 1 else 0
            vol = (var ** 0.5) * (252 ** 0.5) * 100
        else:
            vol = None

        # max drawdown over 52w
        peak = w52[0]
        mdd = 0.0
        for v in w52:
            peak = max(peak, v)
            mdd = min(mdd, v / peak - 1)

        out[key] = {
            "name": cname, "code": code, "last_date": last_d, "last": last,
            "chg_today": pct(last, vals[-2]) if len(vals) >= 2 else None,
            "ytd": pct(last, ytd_base),
            "ret_1m": pct(last, close_at_or_before("2026-09-14")),
            "ret_3m": pct(last, close_at_or_before("2026-07-14")),
            "ret_6m": pct(last, close_at_or_before("2026-04-14")),
            "ret_1y": pct(last, close_at_or_before("2025-10-14")),
            "hi_52w": round(hi52, 2), "lo_52w": round(lo52, 2),
            "off_high": pct(last, hi52), "above_low": pct(last, lo52),
            "vol_60d_ann": round(vol, 2) if vol is not None else None,
            "mdd_52w": round(mdd * 100, 2),
            "n_days": len(closes),
        }
    ctx.close()
    print("###METRICS###")
    print(json.dumps(out, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
