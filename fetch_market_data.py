"""
===================================================================
9757（船井総研ホールディングス）前日終値・時価総額 ＋ 日経平均前日終値
毎朝GitHub Actionsで自動実行 → リポジトリ内のJSONファイルに書き出す
===================================================================

【仕組み】
・yfinance（Yahoo!ファイナンスの非公式Pythonライブラリ、登録不要）で
  9757.T と ^N225 の値を取得する
・このスクリプトは「取引開始前の朝」に実行する前提。その時点でのデータは
  必ず「前営業日の確定した終値」になるので、結果としてこれが「前日終値」になる
・取得したデータは data/latest.json に書き出す（Webhook送信はしない）
・このJSONファイルをGAS側が定期的に読みに行く（pull方式）
===================================================================
"""

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import yfinance as yf

# 発行済株式数のフォールバック値（yfinanceから取得できなかった場合に使う）
# 頻繁に変わる数字ではないので、年1回くらい見直せばOK
SHARES_OUTSTANDING_FALLBACK = 100_000_000  # 2026年8月時点の参考値

OUTPUT_PATH = os.path.join("data", "latest.json")


def get_previous_close_and_shares(ticker_symbol: str):
    """指定ティッカーの前日終値と発行済株式数を取得する"""
    ticker = yf.Ticker(ticker_symbol)
    hist = ticker.history(period="5d")

    if hist.empty:
        raise RuntimeError(f"{ticker_symbol} の株価データが取得できませんでした")

    # 朝イチ実行前提：最新行がすでに前営業日の確定終値になっている
    previous_close = round(float(hist["Close"].iloc[-1]))

    shares_outstanding = None
    try:
        info = ticker.info
        shares_outstanding = info.get("sharesOutstanding")
    except Exception as e:
        print(f"発行済株式数の取得に失敗（yfinance info）: {e}")

    if not shares_outstanding:
        shares_outstanding = SHARES_OUTSTANDING_FALLBACK
        print(f"発行済株式数はフォールバック値を使用: {shares_outstanding}")

    return previous_close, shares_outstanding


def get_index_previous_close(ticker_symbol: str) -> float:
    """指数（日経平均など）の前日終値を取得する"""
    ticker = yf.Ticker(ticker_symbol)
    hist = ticker.history(period="5d")

    if hist.empty:
        raise RuntimeError(f"{ticker_symbol} のデータが取得できませんでした")

    return round(float(hist["Close"].iloc[-1]), 2)


def main():
    today_str = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y/%m/%d")

    stock_price, shares_outstanding = get_previous_close_and_shares("9757.T")
    market_cap_million_yen = round(stock_price * shares_outstanding / 1_000_000)

    nikkei_close = get_index_previous_close("^N225")

    data = {
        "date": today_str,
        "stockPrice": stock_price,
        "marketCap": market_cap_million_yen,
        "nikkeiClose": nikkei_close,
        "generatedAtUtc": datetime.utcnow().isoformat(),
    }

    print("書き出す内容:", data)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"{OUTPUT_PATH} に書き出したで")


if __name__ == "__main__":
    main()
