
import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="麻雀成績集計 v6", page_icon="🀄", layout="wide")

RETURN_SCORE = 30000
UMA_BY_POSITION = {1: 20.0, 2: 10.0, 3: -10.0, 4: -20.0}
TOBI_PENALTY = -10.0
TOBASHI_BONUS_PER_PERSON = 10.0
YAKITORI_PENALTY = -10.0
DEFAULT_PLAYERS = ["プレイヤー1", "プレイヤー2", "プレイヤー3", "プレイヤー4"]


def round_score_5_6(score: int) -> int:
    """百の位を5捨6入して1,000点単位にする。"""
    sign = -1 if score < 0 else 1
    value = abs(int(score))
    thousands, remainder = divmod(value, 1000)
    if remainder >= 600:
        thousands += 1
    return sign * thousands * 1000


def base_point(score: int) -> float:
    return (round_score_5_6(score) - RETURN_SCORE) / 1000.0


def rank_and_uma(scores):
    """
    同点は同順位。
    同点者が占有する順位枠のウマ合計を均等分配。
    例: 1位2人なら (+20 + +10) / 2 = +15Pずつ。
    """
    order = sorted(range(4), key=lambda i: scores[i], reverse=True)
    ranks = [None] * 4
    umas = [0.0] * 4

    pos = 1
    idx = 0
    while idx < 4:
        same = [order[idx]]
        j = idx + 1
        while j < 4 and scores[order[j]] == scores[order[idx]]:
            same.append(order[j])
            j += 1

        occupied = list(range(pos, pos + len(same)))
        shared_uma = sum(UMA_BY_POSITION[p] for p in occupied) / len(same)

        for player_idx in same:
            ranks[player_idx] = pos
            umas[player_idx] = shared_uma

        pos += len(same)
        idx = j

    return ranks, umas


def calculate_match(players, scores, tobashi_counts, yakitori_flags):
    ranks, umas = rank_and_uma(scores)
    rounded_scores = [round_score_5_6(s) for s in scores]
    bases = [base_point(s) for s in scores]
    tobi = [TOBI_PENALTY if s < 0 else 0.0 for s in scores]
    tobashi = [c * TOBASHI_BONUS_PER_PERSON for c in tobashi_counts]
    yakitori = [YAKITORI_PENALTY if f else 0.0 for f in yakitori_flags]

    prelim = [
        bases[i] + umas[i] + tobi[i] + tobashi[i] + yakitori[i]
        for i in range(4)
    ]

    # v6ルール:
    # 1位の最終Pは、1位以外の最終P合計を符号反転した値。
    # 同率1位は、1位グループ全体に必要な残差を均等分配する。
    first_indices = [i for i, r in enumerate(ranks) if r == 1]
    non_first_indices = [i for i, r in enumerate(ranks) if r != 1]
    final_points = prelim[:]

    amount_for_first_group = -sum(final_points[i] for i in non_first_indices)
    shared_first = amount_for_first_group / len(first_indices)
    for i in first_indices:
        final_points[i] = shared_first

    rows = []
    for i in range(4):
        rows.append({
            "プレイヤー": players[i],
            "得点": scores[i],
            "5捨6入後": rounded_scores[i],
            "順位": ranks[i],
            "素点": bases[i],
            "順位点": umas[i],
            "飛び": tobi[i],
            "飛ばし": tobashi[i],
            "焼き鳥": yakitori[i],
            "最終P": final_points[i],
        })
    return pd.DataFrame(rows)


def fmt_point(v):
    if abs(v - round(v)) < 1e-9:
        return f"{int(round(v)):+d}P"
    return f"{v:+.1f}P"


if "history" not in st.session_state:
    st.session_state.history = []
if "player_names" not in st.session_state:
    st.session_state.player_names = DEFAULT_PLAYERS.copy()


st.title("🀄 麻雀成績集計アプリ v6")
st.caption("25,000点持ち / 30,000点返し / ウマ10-20 / オカなし")

with st.expander("v6 の計算ルール", expanded=False):
    st.markdown("""
- 得点は**百の位を5捨6入**してから素点計算
  - 20,500 → 20,000 → -10P
  - 31,500 → 31,000 → +1P
  - 31,600 → 32,000 → +2P
  - -9,500 → -9,000 → -39P
  - -9,600 → -10,000 → -40P
- ウマ：1位 +20 / 2位 +10 / 3位 -10 / 4位 -20
- 同点は同順位。占有する順位枠のウマを均等分配
- 飛び：最終得点がマイナスなら自動で -10P
- 飛ばし：1人飛ばすごとに +10P
- 焼き鳥：-10P
- **1位の最終P = 1位以外の最終P合計を符号反転**
- 同率1位の場合は1位グループで均等分配
""")

st.subheader("対局結果入力")

cols = st.columns(4)
players, scores, tobashi_counts, yakitori_flags = [], [], [], []

for i, col in enumerate(cols):
    with col:
        st.markdown(f"#### {i + 1}人目")
        name = st.text_input("名前", value=st.session_state.player_names[i], key=f"name_{i}")
        score = st.number_input(
            "最終得点",
            min_value=-200000,
            max_value=300000,
            value=25000,
            step=100,
            key=f"score_{i}",
        )
        tobashi_count = st.number_input(
            "飛ばした人数",
            min_value=0,
            max_value=3,
            value=0,
            step=1,
            key=f"tobashi_{i}",
            help="1人飛ばすごとに +10P",
        )
        yakitori = st.checkbox(
            "焼き鳥",
            value=False,
            key=f"yakitori_{i}",
            help="半荘中に一度も和了していない場合",
        )

        players.append(name.strip() or f"プレイヤー{i + 1}")
        scores.append(int(score))
        tobashi_counts.append(int(tobashi_count))
        yakitori_flags.append(bool(yakitori))

st.session_state.player_names = players

if len(set(players)) != 4:
    st.warning("プレイヤー名が重複しています。履歴集計のため別々の名前を推奨します。")

result = calculate_match(players, scores, tobashi_counts, yakitori_flags)

st.divider()
st.subheader("今回の計算結果")

display_df = result.copy()
for c in ["素点", "順位点", "飛び", "飛ばし", "焼き鳥", "最終P"]:
    display_df[c] = display_df[c].map(fmt_point)
display_df["順位"] = display_df["順位"].map(lambda x: f"{x}位")

st.dataframe(
    display_df[["プレイヤー", "得点", "5捨6入後", "順位", "素点", "順位点", "飛び", "飛ばし", "焼き鳥", "最終P"]],
    use_container_width=True,
    hide_index=True,
)

metric_cols = st.columns(4)
for i, col in enumerate(metric_cols):
    row = result.iloc[i]
    with col:
        st.metric(
            label=f"{int(row['順位'])}位  {row['プレイヤー']}",
            value=fmt_point(row["最終P"]),
            delta=f"{int(row['5捨6入後']):,}点",
            delta_color="off",
        )

total_final = float(result["最終P"].sum())
if abs(total_final) < 1e-9:
    st.success("最終ポイント合計：0P")
else:
    st.error(f"最終ポイント合計が0Pではありません：{total_final:+.1f}P")

with st.expander("5捨6入の動作確認", expanded=False):
    checks = [
        (20500, 20000, -10),
        (31500, 31000, 1),
        (31600, 32000, 2),
        (-9500, -9000, -39),
        (-9600, -10000, -40),
    ]
    rows = []
    for raw, expected_rounded, expected_base in checks:
        actual_rounded = round_score_5_6(raw)
        actual_base = base_point(raw)
        rows.append({
            "入力": raw,
            "5捨6入後": actual_rounded,
            "素点": fmt_point(actual_base),
            "期待値": f"{expected_rounded:,}点 / {expected_base:+d}P",
            "判定": "OK" if actual_rounded == expected_rounded and actual_base == expected_base else "NG",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

st.divider()
left, right = st.columns(2)

with left:
    if st.button("この半荘を履歴に追加", type="primary", use_container_width=True):
        match_no = len({x["半荘"] for x in st.session_state.history}) + 1 if st.session_state.history else 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for _, row in result.iterrows():
            st.session_state.history.append({
                "半荘": match_no,
                "日時": timestamp,
                "プレイヤー": row["プレイヤー"],
                "得点": int(row["得点"]),
                "順位": int(row["順位"]),
                "最終P": float(row["最終P"]),
            })
        st.success(f"第{match_no}半荘を追加しました。")

with right:
    if st.button("履歴をすべてクリア", use_container_width=True):
        st.session_state.history = []
        st.rerun()

if st.session_state.history:
    history_df = pd.DataFrame(st.session_state.history)

    st.subheader("累計")
    summary = (
        history_df.groupby("プレイヤー", as_index=False)
        .agg(**{
            "半荘数": ("半荘", "nunique"),
            "累計P": ("最終P", "sum"),
            "平均P": ("最終P", "mean"),
            "1位回数": ("順位", lambda s: int((s == 1).sum())),
        })
        .sort_values(["累計P", "1位回数"], ascending=[False, False])
        .reset_index(drop=True)
    )
    summary.insert(0, "順位", range(1, len(summary) + 1))

    shown_summary = summary.copy()
    shown_summary["累計P"] = shown_summary["累計P"].map(fmt_point)
    shown_summary["平均P"] = shown_summary["平均P"].map(fmt_point)
    st.dataframe(shown_summary, use_container_width=True, hide_index=True)

    st.subheader("対局履歴")
    shown_history = history_df.copy()
    shown_history["最終P"] = shown_history["最終P"].map(fmt_point)
    shown_history["順位"] = shown_history["順位"].map(lambda x: f"{x}位")
    st.dataframe(shown_history, use_container_width=True, hide_index=True)

    csv = history_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "履歴CSVをダウンロード",
        data=csv,
        file_name="mahjong_history_v6.csv",
        mime="text/csv",
        use_container_width=True,
    )
else:
    st.info("まだ履歴はありません。計算結果を確認して「この半荘を履歴に追加」を押してください。")
