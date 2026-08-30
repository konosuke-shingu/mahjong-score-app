
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="麻雀成績集計 v8.10",
    page_icon="🀄",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# -----------------------------
# スマホ向けCSS
# -----------------------------
st.markdown("""
<style>
    .block-container {
        max-width: 760px;
        padding-top: 1.2rem;
        padding-bottom: 5rem;
        padding-left: 0.9rem;
        padding-right: 0.9rem;
    }

    h1 {
        font-size: 2rem !important;
        line-height: 1.2 !important;
        margin-bottom: 0.2rem !important;
    }

    h2 {
        font-size: 1.45rem !important;
        margin-top: 1.2rem !important;
    }

    h3 {
        font-size: 1.2rem !important;
    }

    /* 入力欄をスマホで押しやすく */
    div[data-baseweb="input"] input {
        font-size: 1.05rem !important;
        min-height: 46px !important;
    }

    div[data-testid="stNumberInput"] button {
        min-width: 46px !important;
        min-height: 46px !important;
    }

    div[data-testid="stCheckbox"] label {
        font-size: 1rem !important;
    }

    .stButton > button,
    .stDownloadButton > button {
        width: 100%;
        min-height: 50px;
        font-size: 1.05rem;
        font-weight: 700;
        border-radius: 12px;
    }

    div[data-testid="stExpander"] {
        border-radius: 14px;
        margin-bottom: 0.6rem;
    }

    div[data-testid="stMetric"] {
        border: 1px solid rgba(128,128,128,0.25);
        padding: 0.8rem;
        border-radius: 14px;
        background: rgba(128,128,128,0.04);
    }

    .result-card {
        border: 1px solid rgba(128,128,128,0.25);
        border-radius: 14px;
        padding: 0.9rem 1rem;
        margin-bottom: 0.7rem;
        background: rgba(128,128,128,0.04);
    }

    .result-rank {
        font-size: 0.95rem;
        opacity: 0.75;
    }

    .result-name {
        font-size: 1.15rem;
        font-weight: 700;
        margin-top: 0.1rem;
    }

    .result-point {
        font-size: 1.7rem;
        font-weight: 800;
        margin-top: 0.15rem;
    }

    .result-detail {
        font-size: 0.9rem;
        opacity: 0.8;
        margin-top: 0.2rem;
    }




    /* 最終得点横の±ボタン */
    div[class*="st-key-toggle_sign_"] button {
        min-height: 46px !important;
        height: 46px !important;
        padding: 0 !important;
        font-size: 1.25rem !important;
        font-weight: 700 !important;
        border-radius: 10px !important;
    }

    @media (max-width: 600px) {
        .block-container {
            padding-left: 0.7rem;
            padding-right: 0.7rem;
            padding-top: 0.8rem;
        }

        h1 {
            font-size: 1.65rem !important;
        }

        div[data-testid="stDataFrame"] {
            font-size: 0.85rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# 設定
# -----------------------------
RETURN_SCORE = 30000
UMA_BY_POSITION = {1: 20.0, 2: 10.0, 3: -10.0, 4: -20.0}
TOBI_PENALTY = -10.0
TOBASHI_BONUS_PER_PERSON = 10.0
YAKITORI_PENALTY = -10.0
DEFAULT_PLAYERS = ["プレイヤー1", "プレイヤー2", "プレイヤー3", "プレイヤー4"]


# -----------------------------
# 計算ロジック
# -----------------------------
def round_score_5_6(score: int) -> int:
    """
    百の位を5捨6入して1,000点単位にする。
    31,500 -> 31,000
    31,600 -> 32,000
    20,500 -> 20,000
    -9,500 -> -9,000
    -9,600 -> -10,000
    """
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

    # v6から継続する重要ルール:
    # 1位の最終P = 1位以外の最終P合計の符号反転
    # 同率1位の場合は、1位グループ全体で残差を均等分配
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


# -----------------------------
# セッション
# -----------------------------
if "history" not in st.session_state:
    st.session_state.history = []
if "player_names" not in st.session_state:
    st.session_state.player_names = DEFAULT_PLAYERS.copy()
if "settlement_step" not in st.session_state:
    st.session_state.settlement_step = 0
if "settlement_rate" not in st.session_state:
    st.session_state.settlement_rate = 30
if "chip_counts" not in st.session_state:
    st.session_state.chip_counts = {}
if "chip_rate" not in st.session_state:
    st.session_state.chip_rate = 100



# -----------------------------
# 入力補助
# -----------------------------
def reset_all_scores():
    # 対局入力を次の半荘用の初期状態へ戻す
    # 名前と履歴は維持する
    for i in range(4):
        st.session_state[f"score_{i}"] = 25000
        st.session_state[f"tobashi_{i}"] = 0
        st.session_state[f"yakitori_{i}"] = False


def toggle_score_sign(i):
    """最終得点の符号を反転する。例: 9600 <-> -9600"""
    key = f"score_{i}"
    current = st.session_state.get(key, 25000)
    if current is not None:
        st.session_state[key] = -int(current)


# -----------------------------
# ヘッダー
# -----------------------------
st.title("🀄 麻雀成績集計 v8.10")
st.caption("スマホ操作向け / 25,000点持ち・30,000点返し / ウマ10-20 / オカなし")

with st.expander("計算ルールを確認"):
    st.markdown("""
- 得点は**百の位を5捨6入**してから素点計算
- 20,500 → 20,000 → **-10P**
- 31,600 → 32,000 → **+2P**
- -9,500 → -9,000 → **-39P**
- -9,600 → -10,000 → **-40P**
- ウマ：1位 +20 / 2位 +10 / 3位 -10 / 4位 -20
- 同点は同順位。占有する順位枠のウマを均等分配
- 飛び：最終得点がマイナスなら自動 **-10P**
- 飛ばし：1人につき **+10P**
- 焼き鳥：**-10P**
- **1位の最終P = 1位以外の最終P合計を符号反転**
""")

# -----------------------------
# 入力
# -----------------------------
st.subheader("対局結果入力")
st.caption("スマホでは上から1人ずつ入力できます。")

players = []
scores = []
tobashi_counts = []
yakitori_flags = []
score_missing = False

for i in range(4):
    default_name = st.session_state.player_names[i]
    with st.expander(f"{i + 1}人目　{default_name}", expanded=True):

        name = st.text_input(
            "名前",
            value=default_name,
            key=f"name_{i}",
            placeholder=f"プレイヤー{i+1}",
        )

        score_col, sign_col = st.columns([0.84, 0.16], vertical_alignment="bottom")
        with score_col:
            with st.container(key=f"score_mobile_{i}"):
                score = st.number_input(
                    "最終得点",
                    min_value=-200000,
                    max_value=300000,
                    value=25000,
                    step=100,
                    key=f"score_{i}",
                    help="スマホでは数字キーボードを優先表示します。負数は右の±ボタンで切り替えます",
                    format="%d",
                )

        with sign_col:
            st.button(
                "±",
                key=f"toggle_sign_{i}",
                help="最終得点のプラス/マイナスを切り替える",
                use_container_width=True,
                on_click=toggle_score_sign,
                args=(i,),
            )

        c1, c2 = st.columns(2)
        with c1:
            tobashi_count = st.number_input(
                "飛ばした人数",
                min_value=0,
                max_value=3,
                value=0,
                step=1,
                key=f"tobashi_{i}",
            )
        with c2:
            yakitori = st.checkbox(
                "焼き鳥",
                value=False,
                key=f"yakitori_{i}",
            )

        players.append(name.strip() or f"プレイヤー{i + 1}")

        if score is None:
            score_missing = True
            scores.append(0)
        else:
            scores.append(int(score))

        tobashi_counts.append(int(tobashi_count))
        yakitori_flags.append(bool(yakitori))


# スマホで最終得点欄をタップした際、数字キーボードを優先表示する。
# Streamlitの number_input は元々数値型だが、inputmode を明示して
# iPhone / Android のブラウザで数字入力UIが出やすいよう補強する。
components.html(
    """
    <script>
    (function () {
        let lastApply = 0;

        function tuneInput(input) {
            if (!input) return;

            // 数字キーボードを優先しつつ、負数は±ボタンで切替可能。
            input.setAttribute('type', 'number');
            input.setAttribute('inputmode', 'numeric');
            input.setAttribute('pattern', '[0-9]*');
            input.setAttribute('enterkeyhint', 'done');
            input.setAttribute('autocomplete', 'off');

            // Streamlit再描画後にも確実に再適用するため、
            // focus/touch時にも属性を入れ直す。
            if (!input.dataset.numericKeyboardBound) {
                const reapply = () => {
                    input.setAttribute('type', 'number');
                    input.setAttribute('inputmode', 'numeric');
                    input.setAttribute('pattern', '[0-9]*');
                    input.setAttribute('enterkeyhint', 'done');
                    input.setAttribute('autocomplete', 'off');
                };
                input.addEventListener('focus', reapply, {passive: true});
                input.addEventListener('touchstart', reapply, {passive: true});
                input.addEventListener('click', reapply, {passive: true});
                input.dataset.numericKeyboardBound = '1';
            }
        }

        function applyNumericKeyboard() {
            try {
                const now = Date.now();
                if (now - lastApply < 50) return;
                lastApply = now;

                const doc = window.parent.document;

                // まずv8.9の専用ラッパーを優先して検索
                const wrappers = doc.querySelectorAll('[class*="st-key-score_mobile_"]');
                wrappers.forEach((wrapper) => {
                    tuneInput(wrapper.querySelector('input'));
                });

                // 念のためキー名 score_0～score_3 の number input も直接補強
                for (let i = 0; i < 4; i++) {
                    const keyWrap = doc.querySelector('[class*="st-key-score_' + i + '"]');
                    if (keyWrap) {
                        tuneInput(keyWrap.querySelector('input'));
                    }
                }
            } catch (e) {
                console.log("numeric keyboard helper:", e);
            }
        }

        // 初期表示直後・描画後・少し遅れてから複数回適用
        applyNumericKeyboard();
        [100, 300, 700, 1200, 2000, 3500].forEach((ms) => {
            setTimeout(applyNumericKeyboard, ms);
        });

        // StreamlitのDOM再描画を監視し続けて再適用
        try {
            const doc = window.parent.document;
            const observer = new MutationObserver(() => {
                applyNumericKeyboard();
            });
            observer.observe(doc.body, {
                childList: true,
                subtree: true,
                attributes: false
            });

            // 長時間開きっぱなしでも、一定時間は監視を維持
            setTimeout(() => observer.disconnect(), 30000);
        } catch (e) {}
    })();
    </script>
    """,
    height=0,
    width=0,
)

st.session_state.player_names = players

if len(set(players)) != 4:
    st.warning("プレイヤー名が重複しています。履歴集計のため別々の名前がおすすめです。")

if score_missing:
    st.warning("最終得点が空欄のプレイヤーがいます。数値を入力してください。")

# -----------------------------
# 計算結果
# -----------------------------
if score_missing:
    result = None
else:
    result = calculate_match(players, scores, tobashi_counts, yakitori_flags)

if result is not None:
    st.subheader("今回の結果")

    # スマホ用カード表示
    for _, row in result.sort_values(["順位", "得点"], ascending=[True, False]).iterrows():
        st.markdown(
            f"""
            <div class="result-card">
                <div class="result-rank">{int(row['順位'])}位</div>
                <div class="result-name">{row['プレイヤー']}</div>
                <div class="result-point">{fmt_point(row['最終P'])}</div>
                <div class="result-detail">
                    {int(row['得点']):,}点 → 5捨6入後 {int(row['5捨6入後']):,}点
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if abs(float(result["最終P"].sum())) < 1e-9:
        st.success("最終ポイント合計：0P")
    else:
        st.error(f"最終ポイント合計：{result['最終P'].sum():+.1f}P")

    with st.expander("ポイント内訳を見る"):
        detail = result.copy()
        for c in ["素点", "順位点", "飛び", "飛ばし", "焼き鳥", "最終P"]:
            detail[c] = detail[c].map(fmt_point)
        detail["順位"] = detail["順位"].map(lambda x: f"{int(x)}位")
        st.dataframe(
            detail[
                ["プレイヤー", "得点", "5捨6入後", "順位", "素点", "順位点", "飛び", "飛ばし", "焼き鳥", "最終P"]
            ],
            use_container_width=True,
            hide_index=True,
        )

else:
    st.info("4人全員の最終得点を入力すると、計算結果が表示されます。")

# -----------------------------
# 履歴操作
# -----------------------------
st.subheader("履歴")

if st.button(
    "＋ この半荘を履歴に追加",
    type="primary",
    use_container_width=True,
    disabled=(result is None),
):
    existing_matches = {x["半荘"] for x in st.session_state.history}
    match_no = max(existing_matches) + 1 if existing_matches else 1
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

    # 履歴追加後、自動で次の半荘用に入力欄を初期化
    reset_all_scores()
    st.rerun()

if st.session_state.history:
    history_df = pd.DataFrame(st.session_state.history)

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

    st.markdown("#### 累計順位")
    for _, row in summary.iterrows():
        st.markdown(
            f"""
            <div class="result-card">
                <div class="result-rank">累計 {int(row['順位'])}位</div>
                <div class="result-name">{row['プレイヤー']}</div>
                <div class="result-point">{fmt_point(row['累計P'])}</div>
                <div class="result-detail">
                    {int(row['半荘数'])}半荘 / 1位 {int(row['1位回数'])}回 / 平均 {fmt_point(row['平均P'])}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.expander("対局履歴を見る"):
        shown_history = history_df.copy()
        shown_history["最終P"] = shown_history["最終P"].map(fmt_point)
        shown_history["順位"] = shown_history["順位"].map(lambda x: f"{x}位")
        st.dataframe(shown_history, use_container_width=True, hide_index=True)

    csv = history_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "履歴CSVをダウンロード",
        data=csv,
        file_name="mahjong_history_v8_10.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.divider()

    # -----------------------------
    # 精算
    # -----------------------------
    if st.session_state.settlement_step == 0:
        if st.button("💴 精算する", type="primary", use_container_width=True):
            st.session_state.settlement_step = 1
            st.rerun()

    elif st.session_state.settlement_step == 1:
        st.markdown("### 精算 1/3：レート選択")
        rate_label = st.radio(
            "麻雀のレートを選択してください",
            options=["1000点 × 30", "1000点 × 50", "1000点 × 100"],
            index=[30, 50, 100].index(st.session_state.settlement_rate),
            key="settlement_rate_radio",
        )
        selected_rate = {
            "1000点 × 30": 30,
            "1000点 × 50": 50,
            "1000点 × 100": 100,
        }[rate_label]

        c1, c2 = st.columns(2)
        with c1:
            if st.button("キャンセル", use_container_width=True):
                st.session_state.settlement_step = 0
                st.rerun()
        with c2:
            if st.button("次へ：チップ入力", type="primary", use_container_width=True):
                st.session_state.settlement_rate = selected_rate
                st.session_state.settlement_step = 2
                st.rerun()

    elif st.session_state.settlement_step == 2:
        st.markdown("### 精算 2/3：チップ枚数入力")
        st.caption("受け取りはプラス、支払いはマイナスで入力してください。4人の合計が0枚になるようにします。")

        current_players = summary["プレイヤー"].tolist()
        entered_chips = {}

        for player in current_players:
            default_value = int(st.session_state.chip_counts.get(player, 0))
            entered_chips[player] = int(
                st.number_input(
                    f"{player} のチップ枚数",
                    min_value=-999,
                    max_value=999,
                    value=default_value,
                    step=1,
                    key=f"chip_count_{player}",
                )
            )

        chip_total = sum(entered_chips.values())
        if chip_total == 0:
            st.success("チップ合計：0枚")
        else:
            st.warning(f"チップ合計：{chip_total:+d}枚（合計0枚になるように入力してください）")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("← レート選択へ戻る", use_container_width=True):
                st.session_state.chip_counts = entered_chips
                st.session_state.settlement_step = 1
                st.rerun()
        with c2:
            if st.button(
                "次へ：チップレート",
                type="primary",
                use_container_width=True,
                disabled=(chip_total != 0),
            ):
                st.session_state.chip_counts = entered_chips
                st.session_state.settlement_step = 3
                st.rerun()

    elif st.session_state.settlement_step == 3:
        st.markdown("### 精算 3/3：チップレート選択")
        chip_rate_label = st.radio(
            "チップ1枚のレートを選択してください",
            options=["1枚 100円", "1枚 300円", "1枚 500円", "1枚 1000円"],
            index=[100, 300, 500, 1000].index(st.session_state.chip_rate),
            key="chip_rate_radio",
        )
        selected_chip_rate = {
            "1枚 100円": 100,
            "1枚 300円": 300,
            "1枚 500円": 500,
            "1枚 1000円": 1000,
        }[chip_rate_label]

        c1, c2 = st.columns(2)
        with c1:
            if st.button("← チップ入力へ戻る", use_container_width=True):
                st.session_state.settlement_step = 2
                st.rerun()
        with c2:
            if st.button("精算結果を表示", type="primary", use_container_width=True):
                st.session_state.chip_rate = selected_chip_rate
                st.session_state.settlement_step = 4
                st.rerun()

    elif st.session_state.settlement_step == 4:
        st.markdown("### 💴 精算結果")

        rate = st.session_state.settlement_rate
        chip_rate = st.session_state.chip_rate
        chip_counts = st.session_state.chip_counts

        settlement_rows = []
        for _, row in summary.iterrows():
            player = row["プレイヤー"]
            total_p = float(row["累計P"])
            chips = int(chip_counts.get(player, 0))
            point_amount = total_p * rate
            chip_amount = chips * chip_rate
            final_amount = point_amount + chip_amount

            settlement_rows.append({
                "プレイヤー": player,
                "累計P": total_p,
                "麻雀分": point_amount,
                "チップ": chips,
                "チップ分": chip_amount,
                "精算額": final_amount,
            })

        settlement_df = pd.DataFrame(settlement_rows).sort_values("精算額", ascending=False)

        st.caption(
            f"麻雀レート：1000点 × {rate} ／ "
            f"チップ：1枚 {chip_rate:,}円"
        )

        for _, row in settlement_df.iterrows():
            amount = row["精算額"]
            sign_label = "受取" if amount > 0 else ("支払" if amount < 0 else "±0")
            st.markdown(
                f"""
                <div class="result-card">
                    <div class="result-rank">{sign_label}</div>
                    <div class="result-name">{row['プレイヤー']}</div>
                    <div class="result-point">{amount:+,.0f}円</div>
                    <div class="result-detail">
                        麻雀 {row['累計P']:+.1f}P × {rate} = {row['麻雀分']:+,.0f}円<br>
                        チップ {int(row['チップ']):+d}枚 × {chip_rate:,}円 = {row['チップ分']:+,.0f}円
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        total_money = float(settlement_df["精算額"].sum())
        if abs(total_money) < 0.001:
            st.success("精算額の合計：0円")
        else:
            st.warning(f"精算額の合計：{total_money:+,.0f}円")

        with st.expander("精算表を見る"):
            shown = settlement_df.copy()
            shown["累計P"] = shown["累計P"].map(fmt_point)
            shown["麻雀分"] = shown["麻雀分"].map(lambda x: f"{x:+,.0f}円")
            shown["チップ"] = shown["チップ"].map(lambda x: f"{int(x):+d}枚")
            shown["チップ分"] = shown["チップ分"].map(lambda x: f"{x:+,.0f}円")
            shown["精算額"] = shown["精算額"].map(lambda x: f"{x:+,.0f}円")
            st.dataframe(shown, use_container_width=True, hide_index=True)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("← 精算条件を変更", use_container_width=True):
                st.session_state.settlement_step = 1
                st.rerun()
        with c2:
            if st.button("✅ 精算完了・履歴クリア", type="primary", use_container_width=True):
                st.session_state.history = []
                st.session_state.settlement_step = 0
                st.session_state.chip_counts = {}
                st.rerun()
else:
    st.info("まだ履歴はありません。")
