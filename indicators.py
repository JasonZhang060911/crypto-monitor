# indicators.py

import pandas as pd
import numpy as np

def xrf_series(values: pd.Series, length: int) -> pd.Series:
    """
    Pine xrf: 从当前 bar 向前 length 根 bar 扫描，
    每次都更新 r_val，最后返回最老一根非 NaN 的值。
    """
    out = []
    for i in range(len(values)):
        r_val = np.nan
        for k in range(length + 1):
            j = i - k
            if j < 0:
                break
            v = values.iat[j]
            # 每次都更新，直到 k = length
            if np.isnan(r_val) or not np.isnan(v):
                r_val = v
        out.append(r_val)
    return pd.Series(out, index=values.index)

def xsa_series(src: pd.Series, length: int, weight: int) -> pd.Series:
    """
    Pine xsa: 带指数权重的移动平均（简化版）。
    """
    out = []
    prev = None
    for v in src:
        if prev is None:
            cur = v
        else:
            cur = (v * weight + prev * (length - weight)) / length
        out.append(cur)
        prev = cur
    return pd.Series(out, index=src.index)

def calculate_whale_pump_signal(lows: list[float], closes: list[float]) -> float:
    """
    完整对应你给的 PineScript calculate_whale_pump_signal，
    返回第二个黄色数字（var7）。
    """
    low   = pd.Series(lows)
    close = pd.Series(closes)

    # 1) var1 = xrf(low,1)  => 应当是上一根 bar 的 low
    var1 = xrf_series(low, 1)

    # 2) var2 = xsa(abs(low-var1),3,1) / xsa(max(low-var1,0),3,1) * 100
    diff1 = (low - var1).abs()
    diff2 = (low - var1).clip(lower=0)
    num   = xsa_series(diff1, 3, 1)
    den   = xsa_series(diff2, 3, 1).replace(0, np.nan)
    var2  = (num / den).fillna(0) * 100

    # 3) var3 = ema( var2 * 10 , 3 )  （Pine 中 close*1.2 始终为真）
    expr  = var2 * 10
    var3  = expr.ewm(span=3, adjust=False).mean()

    # 4) var4 = lowest(low,38), 5) var5 = highest(var3,38)
    var4 = low.rolling(38, min_periods=1).min()
    var5 = var3.rolling(38, min_periods=1).max()

    # 6) var6 = lowest(low,90) ? 1 : 0  => always 1 since price>0
    #    所以可以直接设为全 1
    # var6 = pd.Series(1, index=low.index)

    # 7) var7 = ema( low<=var4 ? (var3+var5*2)/2 : 0 ,3) / 618
    cond2 = low <= var4
    expr2 = pd.Series(np.where(cond2, (var3 + var5 * 2) / 2, 0),
                      index=low.index)
    var7  = expr2.ewm(span=3, adjust=False).mean() / 618

    # 返回最后一根 bar 的 var7
    return float(var7.iat[-1])
