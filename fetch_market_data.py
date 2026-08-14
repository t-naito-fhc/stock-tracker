"""
===================================================================
9757（船井総研ホールディングス）前日終値 ＋ 日経平均前日終値
取引終了後の夕方にGitHub Actionsで自動実行 → リポジトリ内のJSONファイルに書き出す
===================================================================

【仕組み】
・yfinance（Yahoo!ファイナンスの非公式Pythonライブラリ、登録不要）で
  9757.T と ^N225 の値を取得する
・このスクリプトは「取引終了後の夕方（16:00頃）」に実行する前提。
  その時点ではその日の取引がもう終わっているので、取得できるのは
  「その日の確定した終値」になる
・取得したデータは data/latest.json に書き出す
・このJSONファイルをGAS側が定期的に読みに行く（pull方式）

【設計方針】
時価総額の計算はこのスクリプトではやらない。株価と発行済株式数から
時価総額を出す計算は、スプレッドシート側の数式（例：=B2*100000000/1000000）
でやるようにしている。担当者が異動しても、誰でもスプレッドシートを
見ればすぐに計算方法が分かるようにするため。
===================================================================
"""

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import yfinance as yf

OUTPUT_PATH = os.path.join("data", "latest.json")


def _get_last_completed_bar(hist):
    """
    取引時間中（15:30の取引終了より前）に実行された場合、最新行が
    「まだ確定してない当日の途中経過」になっていることがある。
    その場合のみ、その行を除外して1つ前（＝直近の確定済み終値）を使う。

    逆に、15:30を過ぎてから実行された場合は、最新行の日付が今日であっても
    それはもう「今日の確定した終値」なので、そのまま使う。

    戻り値は (取引日, 終値) のタプル。土日・祝日にこのスクリプトが実行された
    場合、取引日は「直近の営業日（例：金曜日）」になる。日付を実行日
    （例：土曜日）にしてしまうと、前営業日比が意図せず0になってしまうため、
    必ず「実際の取引日」を使うようにしている。
    """
    now_jst = datetime.now(ZoneInfo("Asia/Tokyo"))
    market_close_today = now_jst.replace(hour=15, minute=30, second=0, microsecond=0)

    last_date = hist.index[-1].date()
    is_last_bar_today = last_date == now_jst.date()
    before_market_close = now_jst < market_close_today

    if is_last_bar_today and before_market_close and len(hist) >= 2:
        return hist.index[-2].date(), hist["Close"].iloc[-2]

    return hist.index[-1].date(), hist["Close"].iloc[-1]


def get_previous_close(ticker_symbol: str):
    """指定ティッカーの前日終値（または当日確定終値）と、その取引日を取得する"""
    ticker = yf.Ticker(ticker_symbol)
    hist = ticker.history(period="5d")

    if hist.empty:
        raise RuntimeError(f"{ticker_symbol} の株価データが取得できませんでした")

    trading_date, price = _get_last_completed_bar(hist)
    return trading_date, round(float(price))


def get_index_previous_close(ticker_symbol: str):
    """指数（日経平均など）の前日終値（または当日確定終値）と、その取引日を取得する"""
    ticker = yf.Ticker(ticker_symbol)
    hist = ticker.history(period="5d")

    if hist.empty:
        raise RuntimeError(f"{ticker_symbol} のデータが取得できませんでした")

    trading_date, price = _get_last_completed_bar(hist)
    return trading_date, round(float(price), 2)


def main():
    stock_date, stock_price = get_previous_close("9757.T")
    _, nikkei_close = get_index_previous_close("^N225")

    # 記録する日付は「実行日」ではなく「実際の取引日」を使う。
    # 土日・祝日にこのスクリプトが動いても、記録される日付は
    # 直近の営業日（例：金曜日）になるので、GAS側で重複チェックできる。
    date_str = stock_date.strftime("%Y/%m/%d")

    data = {
        "date": date_str,
        "stockPrice": stock_price,
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
