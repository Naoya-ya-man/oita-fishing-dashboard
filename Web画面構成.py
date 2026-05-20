import streamlit as st
import pandas as pd
from pathlib import Path

# =========================================================
# CSVファイルのパス設定
# このPythonファイルと同じフォルダに fishing_weather.csv を置く
# =========================================================
BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "fishing_weather.csv"


# =========================================================
# CSVを読み込む関数
# utf-8-sigで読むことでExcel向けCSVも文字化けしにくくする
# =========================================================
def load_data():
    if not CSV_PATH.exists():
        st.error("fishing_weather.csv が見つかりません。")
        st.stop()

    try:
        df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(CSV_PATH, encoding="cp932")

    required_columns = [
        "対象日",
        "漁港名",
        "天気",
        "平均降水確率",
        "おすすめ時間の降水確率",
        "風速",
        "おすすめ時間帯",
        "おすすめ理由",
        "ランク",
        "都道府県",
        "市"
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        st.error(f"CSVに必要な列がありません: {missing_columns}")
        st.stop()

    return df


# =========================================================
# 最高ランクを取得する関数
# S → A → B → C → D → E の順で判定する
# =========================================================
def get_best_rank(df):
    rank_order = ["S", "A", "B", "C", "D", "E"]

    for rank in rank_order:
        if rank in df["ランク"].values:
            return rank

    return "-"


# =========================================================
# Streamlit画面の基本設定
# =========================================================
st.set_page_config(
    page_title="大分釣り日和情報",
    page_icon="🎣",
    layout="wide"
)

st.title("🎣 大分釣り日和情報")
st.write("天気・風速・降水確率をもとに、漁港ごとの釣りやすさを表示します。")

# =========================================================
# データ読み込み
# =========================================================
df = load_data()

# =========================================================
# サイドバーの絞り込み条件
# =========================================================
st.sidebar.header("絞り込み")

target_date = st.sidebar.selectbox(
    "対象日",
    sorted(df["対象日"].dropna().unique())
)

rank_filter = st.sidebar.multiselect(
    "おすすめ度",
    sorted(df["ランク"].dropna().unique()),
    default=sorted(df["ランク"].dropna().unique())
)

# =========================================================
# 絞り込み処理
# =========================================================
filtered_df = df[
    (df["対象日"] == target_date) &
    (df["ランク"].isin(rank_filter))
]

# =========================================================
# 概要表示
# =========================================================
st.subheader("📌 本日の概要")

col1, col2, col3 = st.columns(3)

col1.metric("表示件数", len(filtered_df))

if len(filtered_df) > 0:
    best_rank = get_best_rank(filtered_df)
    col2.metric("最高ランク", best_rank)
    col3.metric("対象日", target_date)
else:
    col2.metric("最高ランク", "-")
    col3.metric("対象日", target_date)

# =========================================================
# 釣り情報一覧
# =========================================================
st.subheader("釣り情報一覧")

display_columns = [
    "対象日",
    "漁港名",
    "天気",
    "平均降水確率",
    "おすすめ時間の降水確率",
    "風速",
    "おすすめ時間帯",
    "おすすめ理由",
    "ランク",
    "都道府県",
    "市"
]

st.dataframe(
    filtered_df[display_columns],
    use_container_width=True
)

# =========================================================
# Sランクだけ別表示
# =========================================================
st.subheader("🔥 特におすすめの漁港")

s_rank_df = filtered_df[filtered_df["ランク"] == "S"]

if len(s_rank_df) > 0:
    for _, row in s_rank_df.iterrows():
        st.success(
            f"{row['漁港名']}｜{row['おすすめ時間帯']}｜{row['おすすめ理由']}"
        )
else:
    st.info("現在、Sランクの漁港はありません。")