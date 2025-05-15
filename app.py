# app.py （保持最新版，无需改动）
import threading, time, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, jsonify
from binance_client import get_all_usdt_spot_symbols, fetch_klines
from indicators import calculate_whale_pump_signal
from binance.exceptions import BinanceAPIException

app = Flask(__name__)

INTERVALS = ["5m","15m","30m","1h","4h","1d","1w"]
MAX_SYMBOLS = 50

SYMBOLS, cache = [], {}

def init_symbols_and_cache():
    global SYMBOLS, cache
    all_syms = get_all_usdt_spot_symbols()
    SYMBOLS = all_syms[:MAX_SYMBOLS]
    cache = { sym: {} for sym in SYMBOLS }

def fetch_and_calc(sym, tf):
    # ... 同之前，限流重试逻辑 ...
    while True:
        try:
            lows, closes = fetch_klines(sym, tf)
            return sym, tf, calculate_whale_pump_signal(lows, closes)
        except BinanceAPIException as e:
            msg = str(e)
            if "Too much request weight" in msg:
                time.sleep(60); continue
            m = re.search(r"IP banned until (\d+)", msg)
            if m:
                banned_ms = int(m.group(1))
                sleep_s = banned_ms/1000 - time.time() +1
                time.sleep(max(sleep_s,1)); continue
            return sym, tf, None
        except:
            return sym, tf, None

def update_loop():
    init_symbols_and_cache()
    total = len(SYMBOLS)*len(INTERVALS)
    while True:
        # 清缓存
        for s in SYMBOLS: cache[s]={}
        # 并发刷新
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(fetch_and_calc,s,tf)
                       for s in SYMBOLS for tf in INTERVALS]
            for fut in as_completed(futures):
                s,tf,v = fut.result()
                cache[s][tf] = v
                time.sleep(0.05)
        # 立即下一轮，无需 sleep
        print("⏱️ 等待 5 秒，然后进入下一轮")
        time.sleep(5)

@app.route('/')
def index():
    return render_template('index.html',
                           intervals=INTERVALS,
                           symbols=SYMBOLS)

@app.route('/api/data')
def api_data():
    return jsonify(cache)

@app.route('/symbol/<symbol>')
def symbol_page(symbol):
    return render_template('symbol.html',
                           symbol=symbol.upper(),
                           intervals=INTERVALS)

threading.Thread(target=update_loop, daemon=True).start()

if __name__=='__main__':
    app.run('0.0.0.0',5000,debug=True,use_reloader=False)
