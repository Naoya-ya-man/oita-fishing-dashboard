import requests
import pandas as pd
from datetime import datetime, timedelta, date
from pathlib import Path

# =========================================================
# ファイルパス設定
# このPythonファイルと同じフォルダに spots.csv を置く
# fishing_weather.csv も同じフォルダに出力する
# =========================================================
BASE_DIR = Path(__file__).resolve().parent

SPOTS_CSV = BASE_DIR / "spots.csv"
OUTPUT_CSV = BASE_DIR / "fishing_weather.csv"


# =========================================================
# spots.csvを読み込む
# utf-8-sigで読めない場合はExcel系CSV向けのcp932で読む
# =========================================================
def read_spots_csv():
    try:
        return pd.read_csv(SPOTS_CSV, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(SPOTS_CSV, encoding="cp932")


# =========================================================
# Open-Meteo APIから天気情報を取得する
# API通信に失敗した場合は None を返す
# =========================================================
def fetch_weather(latitude, longitude):
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "weather_code,precipitation_probability,wind_speed_10m",
        "forecast_days": 2,
        "timezone": "Asia/Tokyo"
    }

    try:
        response = requests.get(url, params=params, timeout=10)

        # 400番台・500番台などのHTTPエラーを検知する
        response.raise_for_status()

        return response.json()

    except requests.exceptions.Timeout:
        print("API通信がタイムアウトしました。")

    except requests.exceptions.HTTPError as e:
        print(f"HTTPエラーが発生しました: {e}")

    except requests.exceptions.RequestException as e:
        print(f"API通信エラーが発生しました: {e}")

    except ValueError as e:
        print(f"APIレスポンスのJSON変換に失敗しました: {e}")

    return None


# =========================================================
# 天気コードを日本語に変換する
# =========================================================
def weather_code_to_text(code):
    weather_map = {
        0: "晴",
        1: "晴",
        2: "曇",
        3: "曇",
        45: "霧",
        48: "霧",
        51: "小雨",
        53: "小雨",
        55: "小雨",
        61: "雨",
        63: "雨",
        65: "強雨",
        80: "雨",
        81: "雨",
        82: "強雨",
        95: "雷雨",
    }
    return weather_map.get(code, "不明")


# =========================================================
# 点数からおすすめ度を決める
# Sが最もおすすめ、Eが最も低い
# =========================================================
def get_rank(score):
    if score >= 9:
        return "S"
    elif score >= 8:
        return "A"
    elif score >= 7:
        return "B"
    elif score >= 6:
        return "C"
    elif score >= 5:
        return "D"
    else:
        return "E"


# =========================================================
# 対象日の平均降水確率を計算する
# =========================================================
def get_average_rain(weather_json, target_date):
    times = weather_json["hourly"]["time"]
    rain_probs = weather_json["hourly"]["precipitation_probability"]

    target_rains = []

    for time, rain in zip(times, rain_probs):
        dt = datetime.fromisoformat(time)

        if dt.date() == target_date:
            target_rains.append(rain)

    if not target_rains:
        return 0

    return round(sum(target_rains) / len(target_rains), 1)


# =========================================================
# その日の中で一番釣りに向いていそうな時間を選ぶ
# =========================================================
def choose_best_hour(weather_json, target_date):
    times = weather_json["hourly"]["time"]
    weather_codes = weather_json["hourly"]["weather_code"]
    rain_probs = weather_json["hourly"]["precipitation_probability"]
    wind_speeds = weather_json["hourly"]["wind_speed_10m"]

    avg_rain = get_average_rain(weather_json, target_date)

    best = None
    best_score = -999

    for time, code, rain, wind in zip(times, weather_codes, rain_probs, wind_speeds):
        dt = datetime.fromisoformat(time)

        if dt.date() != target_date:
            continue

        hour = dt.hour
        score = 0
        reasons = []

        # 時間帯評価
        if 18 <= hour <= 22:
            score += 3
            reasons.append("夜釣り向き")
        elif 5 <= hour <= 7:
            score += 3
            reasons.append("朝まずめ")
        elif 16 <= hour <= 17:
            score += 2
            reasons.append("夕まずめ")

        # 平均降水確率評価
        if avg_rain <= 10:
            score += 3
            reasons.append("雨は降らないでしょう")
        elif avg_rain <= 20:
            score += 2
            reasons.append("平均降水確率やや低め")
        elif avg_rain <= 30:
            score += 1
            reasons.append("平均降水確率は低め")
        elif avg_rain <= 40:
            reasons.append("小雨可能性あり")
        elif avg_rain <= 50:
            score -= 1
            reasons.append("雨の可能性あり")
        elif avg_rain <= 60:
            score -= 1
            reasons.append("雨が降るでしょう")
        else:
            score -= 5
            reasons.append("雨が降ります")

        # 風速評価
        if wind <= 2:
            score += 3
            reasons.append("風がかなり弱い")
        elif wind <= 3:
            score += 1
            reasons.append("風は普通")
        elif wind <= 4:
            score -= 1
            reasons.append("風が少し気になる")
        elif wind <= 5:
            score -= 2
            reasons.append("風強め")
        else:
            score -= 5
            reasons.append("釣りどころではない風")

        if score > best_score:
            best_score = score
            best = {
                "time": time,
                "weather_code": code,
                "rain": rain,
                "avg_rain": avg_rain,
                "wind": wind,
                "rank": get_rank(score),
                "reason": "・".join(reasons)
            }

    return best


# =========================================================
# おすすめ時間帯を作る
# =========================================================
def make_recommend_time_range(best_time):
    best_dt = datetime.fromisoformat(best_time)
    start = best_dt - timedelta(hours=1)
    end = best_dt + timedelta(hours=1)

    return f"{start.strftime('%Y-%m-%d %H:%M:%S')} ～ {end.strftime('%Y-%m-%d %H:%M:%S')}"


# =========================================================
# メイン処理
# 1. spots.csvを読む
# 2. 今日・明日の対象日を作る
# 3. 漁港ごとにAPIから天気情報を取得
# 4. おすすめ時間帯を判定
# 5. fishing_weather.csv に出力
# =========================================================
def main():
    spots_df = read_spots_csv()
    rows = []

    target_dates = [
        date.today(),
        date.today() + timedelta(days=1)
    ]

    for _, spot in spots_df.iterrows():
        spot_name = spot["spot_name"]
        prefecture = spot["prefecture"]
        city = spot["city"]
        latitude = spot["latitude"]
        longitude = spot["longitude"]

        weather_json = fetch_weather(latitude, longitude)

        # API取得に失敗した場合は、その漁港だけスキップする
        if weather_json is None:
            print(f"{spot_name} の天気情報を取得できなかったため、スキップしました。")
            continue

        for target_date in target_dates:
            best = choose_best_hour(weather_json, target_date)

            if best is None:
                continue

            recommend_time = make_recommend_time_range(best["time"])

            rows.append({
                "取得日時": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "対象日": target_date.strftime("%Y-%m-%d"),
                "漁港名": spot_name,
                "天気": weather_code_to_text(best["weather_code"]),
                "平均降水確率": f"{best['avg_rain']}%",
                "おすすめ時間の降水確率": f"{best['rain']}%",
                "風速": f"{best['wind']}m/s",
                "おすすめ時間帯": recommend_time,
                "おすすめ理由": best["reason"],
                "ランク": best["rank"],
                "都道府県": prefecture,
                "市": city
            })

    output_df = pd.DataFrame(rows)

    output_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"{OUTPUT_CSV} を更新しました。")


if __name__ == "__main__":
    main()