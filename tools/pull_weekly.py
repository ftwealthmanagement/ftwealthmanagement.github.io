# -*- coding: utf-8 -*-
"""Dump weekly closes (since 2025-09) for charting - compact format."""
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from futu import OpenQuoteContext, KLType, AuType, RET_OK

TICKERS = [
    ("US.SPY", "SPX"), ("US.IWM", "RUT"), ("SH.000300", "CSI300"),
    ("HK.800000", "HSI"), ("JP..N225", "N225"), ("US.FEZ", "SX5E"),
]

def main():
    ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
    out = {}
    for code, key in TICKERS:
        ret, data, _ = ctx.request_history_kline(
            code, start="2025-09-01", end="2026-10-14",
            ktype=KLType.K_WEEK, autype=AuType.QFQ, max_count=1000)
        if ret != RET_OK:
            out[key] = {"error": str(data)}
            continue
        rows = data.to_dict("records")
        out[key] = [[str(r["time_key"])[:10], round(float(r["close"]), 2)] for r in rows]
    ctx.close()
    print("###WEEKLY###")
    print(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
