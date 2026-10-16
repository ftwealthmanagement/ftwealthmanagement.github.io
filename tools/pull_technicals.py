# -*- coding: utf-8 -*-
"""拉六大指数 160 根日K，本地计算技术指标：RSI14 / MACD / KDJ / BOLL / 均线排列 / 量能。
输出 compact JSON 供页面嵌入。量能统一用成交额（恒指指数成交量恒为0）。"""
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from futu import OpenQuoteContext, KLType, AuType, RET_OK

TICKERS = [
    ("US.SPY", "SPX"), ("US.IWM", "RUT"), ("SH.000300", "CSI300"),
    ("HK.800000", "HSI"), ("JP..N225", "N225"), ("US.FEZ", "SX5E"),
]

def ema(vals, n):
    out = [None] * len(vals)
    if not vals:
        return out
    k = 2.0 / (n + 1)
    prev = None
    for i, v in enumerate(vals):
        prev = v if prev is None else v * k + prev * (1 - k)
        out[i] = prev
    return out

def rsi(closes, n=14):
    if len(closes) < n + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    ag = sum(gains[:n]) / n
    al = sum(losses[:n]) / n
    for i in range(n, len(gains)):
        ag = (ag * (n - 1) + gains[i]) / n
        al = (al * (n - 1) + losses[i]) / n
    if al == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + ag / al)

def macd(closes):
    e12, e26 = ema(closes, 12), ema(closes, 26)
    dif = [a - b if (a is not None and b is not None) else None for a, b in zip(e12, e26)]
    dif_v = [d for d in dif if d is not None]
    dea_v = ema(dif_v, 9)
    return dif, dea_v

def kdj(rows, n=9):
    k, d = 50.0, 50.0
    ks, ds, js = [], [], []
    for i in range(len(rows)):
        lo = min(r["low"] for r in rows[max(0, i - n + 1):i + 1])
        hi = max(r["high"] for r in rows[max(0, i - n + 1):i + 1])
        c = rows[i]["close"]
        rsv = 50.0 if hi == lo else (c - lo) / (hi - lo) * 100
        k = 2.0 / 3 * k + 1.0 / 3 * rsv
        d = 2.0 / 3 * d + 1.0 / 3 * k
        ks.append(k); ds.append(d); js.append(3 * k - 2 * d)
    return ks, ds, js

def sma(vals, n):
    out = []
    for i in range(len(vals)):
        if i + 1 < n:
            out.append(None)
        else:
            out.append(sum(vals[i + 1 - n:i + 1]) / n)
    return out

def main():
    ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
    out = {}
    for code, key in TICKERS:
        ret, data, _ = ctx.request_history_kline(
            code, start="2026-01-01", end="2026-10-14",
            ktype=KLType.K_DAY, autype=AuType.QFQ, max_count=1000)
        if ret != RET_OK:
            out[key] = {"error": str(data)}
            continue
        rows = data.to_dict("records")
        rows = [{"close": float(r["close"]), "high": float(r["high"]),
                 "low": float(r["low"]), "amt": float(r.get("turnover") or 0)} for r in rows]
        if len(rows) < 80:
            out[key] = {"error": "insufficient rows: %d" % len(rows)}
            continue
        closes = [r["close"] for r in rows]
        last = closes[-1]

        # RSI14
        r = rsi(closes)

        # MACD（近5日是否金叉/死叉）
        dif, dea_v = macd(closes)
        dif_v = [d for d in dif if d is not None]
        # 对齐：dif_v/dea_v 均为 dif 起点起算
        dif_last, dea_last = dif_v[-1], dea_v[-1]
        hist = dif_last - dea_last
        cross = "none"
        for i in range(max(1, len(dif_v) - 5), len(dif_v)):
            prev = dif_v[i - 1] - dea_v[i - 1]
            cur = dif_v[i] - dea_v[i]
            if prev <= 0 < cur:
                cross = "golden"
            elif prev >= 0 > cur:
                cross = "dead"

        # KDJ
        ks, ds, js = kdj(rows)
        k_last, d_last, j_last = ks[-1], ds[-1], js[-1]
        k_cross = "none"
        for i in range(max(1, len(ks) - 3), len(ks)):
            if ks[i - 1] <= ds[i - 1] and ks[i] > ds[i]:
                k_cross = "golden"
            elif ks[i - 1] >= ds[i - 1] and ks[i] < ds[i]:
                k_cross = "dead"

        # BOLL(20,2)
        b_mid = sma(closes, 20)[-1]
        last20 = closes[-20:]
        m = sum(last20) / 20
        var = sum((c - m) ** 2 for c in last20) / 20
        sd = var ** 0.5
        b_hi, b_lo = m + 2 * sd, m - 2 * sd
        b_pos = (last - b_lo) / (b_hi - b_lo) if b_hi > b_lo else 0.5

        # 均线
        ma5 = sma(closes, 5)[-1]
        ma20 = sma(closes, 20)[-1]
        ma60 = sma(closes, 60)[-1] if len(closes) >= 60 else None
        if ma60:
            if last > ma5 > ma20 > ma60:
                trend = "多头排列"
            elif last < ma5 < ma20 < ma60:
                trend = "空头排列"
            elif last > ma20:
                trend = "站上20日线"
            else:
                trend = "跌破20日线"
        else:
            trend = "数据不足"

        # 量能（成交额 5日/20日 均比）
        amts = [r["amt"] for r in rows]
        a5 = sum(amts[-5:]) / 5
        a20 = sum(amts[-20:]) / 20
        vol_ratio = a5 / a20 if a20 else None

        # 近5日涨跌（量价配合）
        chg5 = closes[-1] / closes[-6] - 1 if len(closes) >= 6 else None

        out[key] = {
            "rsi": round(r, 1) if r is not None else None,
            "macd_hist": round(hist / last * 100, 3),  # 归一化（相对点位百分比）
            "macd_cross": cross,
            "kdj_k": round(k_last, 1), "kdj_d": round(d_last, 1), "kdj_j": round(j_last, 1),
            "kdj_cross": k_cross,
            "boll_pos": round(b_pos, 2),
            "boll_hi": round(b_hi, 2), "boll_mid": round(b_mid, 2), "boll_lo": round(b_lo, 2),
            "trend": trend,
            "vol_ratio": round(vol_ratio, 2) if vol_ratio else None,
            "chg5": round(chg5 * 100, 2) if chg5 is not None else None,
            "n": len(rows), "last_date": None,
        }
    ctx.close()
    print("###TECH###")
    print(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
