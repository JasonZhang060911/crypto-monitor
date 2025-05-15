import os
import time
import re
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException

# —— 自动加载 .env ——  
load_dotenv()
API_KEY    = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
PROXY      = os.getenv("BINANCE_PROXY")

# 配置代理或空字典
if PROXY:
    os.environ["HTTP_PROXY"]  = PROXY
    os.environ["HTTPS_PROXY"] = PROXY
    REQUESTS_PARAMS = {"proxies": {"http": PROXY, "https": PROXY}}
else:
    REQUESTS_PARAMS = {}

# 全局客户端引用（首次使用时创建）
_client = None

def get_client() -> Client:
    global _client
    if _client is None:
        # 延迟创建并捕获初始化时的限流
        while True:
            try:
                _client = Client(API_KEY, API_SECRET, requests_params=REQUESTS_PARAMS)
                break
            except BinanceAPIException as e:
                msg = str(e)
                m = re.search(r"IP banned until (\d+)", msg)
                if m:
                    banned_ms = int(m.group(1))
                    sleep_sec = banned_ms/1000 - time.time() + 1
                    print(f"🔒 Binance client init banned, sleeping {sleep_sec:.1f}s")
                    time.sleep(max(sleep_sec, 1))
                    continue
                else:
                    print("⚠️ Binance client init error, retrying in 5s:", e)
                    time.sleep(5)
                    continue
    return _client

def get_all_usdt_spot_symbols() -> list[str]:
    """
    返回所有 USDT 现货交易对列表，自动重试直到成功。
    """
    client = get_client()
    while True:
        try:
            info   = client.get_exchange_info()
            symbols= info.get("symbols", [])
            result = [
                s["symbol"]
                for s in symbols
                if s.get("quoteAsset")=="USDT"
                and s.get("status")=="TRADING"
                and s.get("isSpotTradingAllowed", False)
            ]
            print(f"🔹 Found {len(result)} USDT spot symbols")
            return result
        except BinanceAPIException as e:
            msg = str(e)
            m = re.search(r"IP banned until (\d+)", msg)
            if m:
                banned_ms = int(m.group(1))
                sleep_sec = banned_ms/1000 - time.time() + 1
                print(f"🔒 get_exchange_info banned, sleeping {sleep_sec:.1f}s")
                time.sleep(max(sleep_sec,1))
                continue
            else:
                print("⚠️ get_exchange_info error, retrying in 5s:", e)
                time.sleep(5)
                continue

def fetch_klines(symbol: str, interval: str, limit: int = 200):
    """
    返回 lows, closes 列表，自动处理限流 Ban 并重试。
    """
    client = get_client()
    while True:
        try:
            kl = client.get_klines(symbol=symbol, interval=interval, limit=limit)
            lows   = [float(c[3]) for c in kl]
            closes = [float(c[4]) for c in kl]
            return lows, closes
        except BinanceAPIException as e:
            msg = str(e)
            m = re.search(r"IP banned until (\d+)", msg)
            if m:
                banned_ms = int(m.group(1))
                sleep_sec = banned_ms/1000 - time.time() + 1
                print(f"🔒 {symbol} {interval} banned, sleeping {sleep_sec:.1f}s")
                time.sleep(max(sleep_sec,1))
                continue
            else:
                print(f"⚠️ Error fetching {symbol} {interval}, retrying in 5s:", e)
                time.sleep(5)
                continue
        except Exception as e:
            # 网络等其他问题，短暂重试
            print(f"⚠️ Unexpected error {symbol} {interval}, retrying in 5s:", e)
            time.sleep(5)
            continue
