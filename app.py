import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from io import StringIO
import re

SPREADSHEET_ID = "1gtWPFhnszYK1VPgmiZQLtstHCltUM_6h"

# ── 1. 페이지 설정 및 CSS ─────────────────────────────────────────
st.set_page_config(page_title="치킨25 튀김 레이더", page_icon="🍗", layout="wide")

st.markdown("""
<style>
  .kpi-label { font-size:0.85rem; color:#666; margin-bottom:4px; font-weight:600; }
  .kpi-value { font-size:1.8rem; font-weight:800; color:#111; }
  .kpi-delta-pos { font-size:1rem; color:#E74C3C; font-weight:700; }
  .kpi-delta-neg { font-size:1rem; color:#3498DB; font-weight:700; }
  .kpi-card {
    background:#fff; border:1px solid #EAEAEA; border-radius:12px;
    padding:1.2rem; box-shadow:0 4px 6px rgba(0,0,0,0.04); height:100%;
  }
  .coach-card { border-radius:12px; padding:1.5rem; margin:1rem 0; }
  .coach-warn { background:#FFF3F3; border-left:6px solid #E74C3C; }
  .coach-good { background:#F0FFF4; border-left:6px solid #2ECC71; }
  .highlight-box {
    background:linear-gradient(90deg,#FFF9E6,#FFFDF5);
    border:1px solid #F0C040; border-radius:8px; padding:1rem; font-size:1rem;
  }
  .section-title {
    font-size:1.3rem; font-weight:800; margin-top:2rem; margin-bottom:1rem; color:#2C3E50;
  }
  .promo-item { font-size:1rem; color:#333; margin-bottom:0.6rem; line-height:1.5; }
  .sub-note { font-size:0.75rem; color:#888; margin-top:4px; }
  .divider { margin:10px 0; border:0.5px solid #eee; }
</style>
""", unsafe_allow_html=True)


# ── 2. 비밀번호 인증 ──────────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 치킨25 튀김 레이더 시스템")
    st.markdown("보안을 위해 비밀번호를 입력해주세요.")
    pwd = st.text_input("비밀번호", type="password")
    if st.button("접속하기"):
        if pwd == "gs25":
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    st.stop()


# ── 3. 공통 유틸리티 ─────────────────────────────────────────────
def clean_num(val):
    """쉼표 포함 문자열을 숫자로 변환"""
    try:
        return float(str(val).replace(",", "").strip())
    except:
        return 0.0


def find_col(columns, keywords):
    """컬럼 목록에서 키워드가 포함된 첫 번째 컬럼명 반환"""
    for kw in keywords:
        result = [c for c in columns if kw in str(c)]
        if result:
            return result[0]
    return None


# ── 4. 만능 시트 파서 ─────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_sheet(sheet_name: str) -> pd.DataFrame:
    """
    병합셀/다중 헤더 행을 자동 감지하여 데이터프레임으로 반환.
    - '점포명' 단어가 있는 행을 헤더로 인식
    - 헤더 위 행들은 ffill → 헤더 이름과 '_'로 합성
    """
    url = (
        f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
        f"/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    )
    try:
        r = requests.get(url, timeout=15)
    except Exception as e:
        raise ConnectionError(f"'{sheet_name}' 시트 요청 실패: {e}")

    raw = pd.read_csv(StringIO(r.text), header=None, dtype=str)

    # '점포명' 이 있는 행 위치 탐색
    header_idx = -1
    for i in range(min(15, len(raw))):
        if raw.iloc[i].fillna("").str.contains("점포명").any():
            header_idx = i
            break

    if header_idx == -1:
        # 헤더 감지 실패 → 1행을 헤더로 처리
        df = pd.read_csv(StringIO(r.text), dtype=str)
        df.columns = [str(c).strip() for c in df.columns]
        return df

    # 위쪽 메타 행 전처리: 빈 셀을 왼쪽 값으로 채우기
    if header_idx > 0:
        top = raw.iloc[:header_idx].copy()
        top = top.ffill(axis=1)
    else:
        top = pd.DataFrame()

    # 각 컬럼의 최종 이름 = (메타 행들 접두어) + '_' + 헤더 행 이름
    new_cols = []
    for ci in range(len(raw.columns)):
        base = str(raw.iloc[header_idx, ci]).strip()
        if base in ("nan", ""):
            base = f"Col_{ci}"

        prefixes = []
        for ri in range(len(top)):
            v = str(top.iloc[ri, ci]).strip()
            if v not in ("nan", "") and "*" not in v:
                prefixes.append(v)

        col_name = "_".join(prefixes + [base]) if prefixes else base
        new_cols.append(col_name)

    raw.columns = new_cols
    df = raw.iloc[header_idx + 1:].copy()
    df = df[~df.apply(lambda row: row.astype(str).str.strip().eq("").all(), axis=1)]
    df = df.reset_index(drop=True)
    return df


# ── 5. 파트 → 점포 매핑 ──────────────────────────────────────────
@st.cache_data(ttl=300)
def get_part_store_mapping() -> dict:
    try:
        df = load_sheet("SALES")
        part_col = find_col(df.columns, ["파트"])
        store_col = find_col(df.columns, ["점포명"])
        if not store_col:
            return {"전체": ["점포 데이터 없음"]}
        if part_col:
            df = df.dropna(subset=[part_col, store_col])
            return df.groupby(part_col)[store_col].unique().apply(list).to_dict()
        return {"전체": df[store_col].dropna().unique().tolist()}
    except Exception as e:
        st.error(f"파트/점포 목록 로드 실패: {e}")
        return {"오류": ["데이터 없음"]}


# ── 6. 점포별 데이터 로드 ─────────────────────────────────────────
@st.cache_data(ttl=300)
def get_store_data(store_name: str) -> dict:

    errors = []

    # ── 6-1. SALES KPI ──
    try:
        df_sales = load_sheet("SALES")
        s_col = find_col(df_sales.columns, ["점포명"])
        row = df_sales[df_sales[s_col] == store_name].iloc[0]

        def avg_cols(keywords_include, keywords_exclude=None):
            cols = [
                c for c in df_sales.columns
                if all(k in c for k in keywords_include)
                and (not keywords_exclude or not any(k in c for k in keywords_exclude))
            ]
            vals = [clean_num(row[c]) for c in cols]
            return np.mean(vals) if vals else 0.0, cols

        avg_total_25, _ = avg_cols(["2025", "전체"])
        avg_total_26, _ = avg_cols(["2026", "전체"])
        _, t2605 = avg_cols(["202605", "전체"])
        val_total_2605 = clean_num(row[t2605[0]]) if t2605 else 0.0

        avg_chk_25, _ = avg_cols(["2025", "치킨"])
        avg_chk_26, _ = avg_cols(["2026", "치킨"])
        _, c2605 = avg_cols(["202605", "치킨"])
        val_chk_2605 = clean_num(row[c2605[0]]) if c2605 else 0.0

        # operation 시트에서 운영율/판매율 시도
        op_rate, sell_rate = 85.0, 92.0
        try:
            df_op = load_sheet("operation")
            op_store_col = find_col(df_op.columns, ["점포명"])
            if op_store_col:
                op_row = df_op[df_op[op_store_col] == store_name].iloc[0]
                op_col = find_col(df_op.columns, ["운영율", "운영률", "가동"])
                sl_col = find_col(df_op.columns, ["판매율", "판매률", "수율"])
                if op_col:
                    op_rate = clean_num(op_row[op_col])
                if sl_col:
                    sell_rate = clean_num(op_row[sl_col])
        except:
            pass

    except Exception as e:
        errors.append(f"SALES: {e}")
        avg_total_25 = avg_total_26 = val_total_2605 = 0.0
        avg_chk_25 = avg_chk_26 = val_chk_2605 = 0.0
        op_rate, sell_rate = 85.0, 92.0

    # ── 6-2. 시간대별 객수 (time 탭, 가로 형식) ──
    시간, 객수 = [], []
    try:
        df_time = load_sheet("time")
        t_store_col = find_col(df_time.columns, ["점포명"])
        store_row = df_time[df_time[t_store_col] == store_name].iloc[0]

        # '시' 포함 + 숫자 포함 컬럼 찾기 (가로 형식)
        time_cols = [c for c in df_time.columns if "시" in str(c) and re.search(r"\d", str(c))]
        for c in time_cols:
            m = re.search(r"(\d{1,2})시", str(c))
            if m:
                시간.append(int(m.group(1)))
                객수.append(clean_num(store_row[c]))

        # 세로 형식 fallback
        if not 시간:
            h_col = find_col(df_time.columns, ["시간", "시각"])
            c_col = find_col(df_time.columns, ["객수", "방문"])
            store_time_df = df_time[df_time[t_store_col] == store_name]
            if h_col and c_col:
                시간 = store_time_df[h_col].apply(clean_num).tolist()
                객수 = store_time_df[c_col].apply(clean_num).tolist()

    except Exception as e:
        errors.append(f"time: {e}")

    # ── 6-3. 베스트 상품 (units 탭) ──
    품목명, 품목매출 = [], []
    try:
        df_item = load_sheet("units")
        u_store_col = find_col(df_item.columns, ["점포명"])
        store_item_df = df_item[df_item[u_store_col] == store_name].copy()

        i_col = find_col(store_item_df.columns, ["품목명", "상품명", "메뉴명", "품목", "상품", "메뉴"])
        s_col = find_col(store_item_df.columns, ["매출", "금액", "판매액"])

        # 키워드로 못 찾으면 점포명 바로 다음 두 열 사용
        if not i_col or not s_col:
            idx = list(store_item_df.columns).index(u_store_col)
            if len(store_item_df.columns) > idx + 2:
                i_col = store_item_df.columns[idx + 1]
                s_col = store_item_df.columns[idx + 2]

        if i_col and s_col:
            store_item_df["_sales"] = store_item_df[s_col].apply(clean_num)
            store_item_df = store_item_df[store_item_df["_sales"] > 0]
            store_item_df = store_item_df.sort_values("_sales", ascending=False)
            품목명 = store_item_df[i_col].astype(str).tolist()
            품목매출 = store_item_df["_sales"].tolist()

    except Exception as e:
        errors.append(f"units: {e}")

    # ── 6-4. 프로모션 (promotion 탭) ──
    프로모션 = []
    try:
        df_promo = load_sheet("promotion")
        p_store_col = find_col(df_promo.columns, ["점포명"])
        store_promo_df = df_promo[df_promo[p_store_col] == store_name]

        name_col = find_col(store_promo_df.columns, ["행사명", "프로모션", "제목", "행사"])
        desc_col = find_col(store_promo_df.columns, ["내용", "설명", "비고"])

        if not name_col:
            idx = list(store_promo_df.columns).index(p_store_col)
            name_col = store_promo_df.columns[idx + 1] if len(store_promo_df.columns) > idx + 1 else None
        if not desc_col:
            idx = list(store_promo_df.columns).index(p_store_col)
            desc_col = store_promo_df.columns[idx + 2] if len(store_promo_df.columns) > idx + 2 else None

        for _, r in store_promo_df.iterrows():
            nm = str(r[name_col]).strip() if name_col else "행사명 없음"
            dc = str(r[desc_col]).strip() if desc_col else ""
            if nm not in ("nan", ""):
                프로모션.append({"행사명": nm, "내용": dc})

        if not 프로모션:
            프로모션 = [{"행사명": "이 점포에 적용 중인 특화 프로모션이 없습니다.", "내용": ""}]

    except Exception as e:
        errors.append(f"promotion: {e}")
        프로모션 = [{"행사명": "promotion 시트 연결 필요", "내용": str(e)}]

    # ── 6-5. 유사상권 베스트 (O4O 탭) ──
    유사상권 = []
    try:
        df_o4o = load_sheet("O4O")
        o_store_col = find_col(df_o4o.columns, ["점포명"])
        store_o4o_df = df_o4o[df_o4o[o_store_col] == store_name]

        sim_col = find_col(store_o4o_df.columns, ["상품명", "품목명", "상품", "품목", "베스트"])
        if not sim_col:
            idx = list(store_o4o_df.columns).index(o_store_col)
            sim_col = store_o4o_df.columns[idx + 1] if len(store_o4o_df.columns) > idx + 1 else None

        if sim_col:
            유사상권 = [
                v for v in store_o4o_df[sim_col].astype(str).tolist()
                if v.strip() not in ("nan", "")
            ][:3]

        if not 유사상권:
            유사상권 = ["O4O 시트에 해당 점포 데이터 없음"]

    except Exception as e:
        errors.append(f"O4O: {e}")
        유사상권 = ["O4O 시트 연결 필요"]

    return {
        "총매출_25평균": int(avg_total_25),
        "총매출_26평균": int(avg_total_26),
        "총매출_26년5월": int(val_total_2605),
        "치킨_25평균": int(avg_chk_25),
        "치킨_26평균": int(avg_chk_26),
        "치킨_26년5월": int(val_chk_2605),
        "운영율": op_rate,
        "판매율": sell_rate,
        "시간": 시간,
        "객수": 객수,
        "품목명": 품목명,
        "품목매출": 품목매출,
        "프로모션": 프로모션,
        "유사상권_베스트": 유사상권,
        "errors": errors,
    }


# ── 7. 성장률 계산 ────────────────────────────────────────────────
def calc_growth(v25, v26):
    if v25 == 0:
        return 0.0
    return (v26 - v25) / v25 * 100


# ── 8. 대시보드 렌더링 ────────────────────────────────────────────
st.title("🍗 치킨25 튀김 레이더")

# 파트 / 점포 선택
part_map = get_part_store_mapping()
col_s1, col_s2 = st.columns(2)
with col_s1:
    sel_part = st.selectbox("🏢 소속 파트를 선택하세요:", list(part_map.keys()))
with col_s2:
    sel_store = st.selectbox("🏬 분석할 점포를 선택하세요:", part_map[sel_part])

data = get_store_data(sel_store)

# 시트 연동 오류 디버그 출력 (관리자용 expander)
if data["errors"]:
    with st.expander("⚙️ 시트 연동 상태 (클릭하여 확인)"):
        for e in data["errors"]:
            st.warning(e)

total_growth = calc_growth(data["총매출_25평균"], data["총매출_26평균"])
chk_growth = calc_growth(data["치킨_25평균"], data["치킨_26평균"])

# ── 8-1. KPI 카드 4개 ──
st.markdown('<div class="section-title">📊 종합 실적 및 점포 진단</div>', unsafe_allow_html=True)
k1, k2, k3, k4 = st.columns(4)

def delta_html(growth):
    cls = "kpi-delta-pos" if growth >= 0 else "kpi-delta-neg"
    arrow = "▲" if growth >= 0 else "▼"
    return f'<div class="{cls}">{arrow} {abs(growth):.1f}%</div>'

with k1:
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">전체 일매출 흐름 (YoY)</div>
      <div class="kpi-value">{data['총매출_26평균']//10000:,}만원</div>
      {delta_html(total_growth)}
      <div class="divider"></div>
      <div style="font-size:0.95rem;"><b>'26년 5월:</b> {data['총매출_26년5월']//10000:,}만원</div>
      <div class="sub-note">* 25년 월평균 vs 26년 월평균 비교</div>
    </div>""", unsafe_allow_html=True)

with k2:
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">치킨25 일매출 흐름 (YoY)</div>
      <div class="kpi-value">{data['치킨_26평균']//1000:,}천원</div>
      {delta_html(chk_growth)}
      <div class="divider"></div>
      <div style="font-size:0.95rem;"><b>'26년 5월:</b> {data['치킨_26년5월']//1000:,}천원</div>
      <div class="sub-note">* 25년 월평균 vs 26년 월평균 비교</div>
    </div>""", unsafe_allow_html=True)

with k3:
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">튀김기 운영율 (가동률)</div>
      <div class="kpi-value">{data['운영율']:.1f}%</div>
      <div class="sub-note">* 목표: 85% 이상 | operation 탭 기준</div>
    </div>""", unsafe_allow_html=True)

with k4:
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">치킨 판매율 (수율)</div>
      <div class="kpi-value">{data['판매율']:.1f}%</div>
      <div class="sub-note">* 튀긴 수량 대비 실판매량 | operation 탭 기준</div>
    </div>""", unsafe_allow_html=True)

# ── 8-2. AI 코칭 메시지 ──
if total_growth > 0 and chk_growth < 0:
    msg = (f"🚨 <b>기회 로스 발생!</b> 점포 전체 손님은 <b>{total_growth:.1f}% 늘었는데</b>,"
           f" 치킨 매출은 오히려 <b>{abs(chk_growth):.1f}% 감소</b>했습니다."
           " 매대에 치킨이 비어 판매 기회를 놓치고 있습니다. 튀김기 가동률을 높이고 진열을 강화하세요!")
    cls = "coach-warn"
elif total_growth < 0 and chk_growth > 0:
    msg = (f"💡 <b>치킨이 효자입니다!</b> 점포 전체 매출이 하락하는 상황에서도"
           f" 치킨 매출이 <b>{chk_growth:.1f}% 상승</b>하며 방어 중입니다."
           " 잘 나가는 치킨 품목의 복수 진열을 늘려 객단가를 끌어올리세요.")
    cls = "coach-good"
elif total_growth < 0 and chk_growth < 0:
    msg = ("⚠️ <b>전면적인 리프레시 필요!</b> 전체 매출과 치킨 매출이 동반 하락 중입니다."
           " 아래 피크타임 데이터를 참고해, 손님이 가장 많이 몰리는 시간 직전에"
           " 냄새 마케팅(선조리)으로 발길을 잡으세요.")
    cls = "coach-warn"
else:
    msg = ("🔥 <b>완벽한 상승 기류!</b> 전체 매출과 치킨 매출이 모두 상승 중입니다."
           " 현재 조리 스케줄을 유지하면서 신상품을 추가 도입해 추가 매출을 노려보세요.")
    cls = "coach-good"

st.markdown(f'<div class="coach-card {cls}">{msg}</div>', unsafe_allow_html=True)
st.markdown("<hr style='border:1px dashed #DDD;'>", unsafe_allow_html=True)

# ── 8-3. 시간대별 차트 + 베스트 상품 ──
col_left, col_right = st.columns([1.2, 1])

with col_left:
    st.markdown('<div class="section-title">⏱️ 시간대별 방문객 및 조리 타이밍</div>', unsafe_allow_html=True)

    if data["객수"] and sum(data["객수"]) > 0:
        max_idx = int(np.argmax(data["객수"]))
        peak_h = int(data["시간"][max_idx])

        colors = ["#FFC300" if i == max_idx else "#EAEAEA" for i in range(len(data["시간"]))]
        fig_t = go.Figure()
        fig_t.add_trace(go.Bar(
            x=[f"{int(h):02d}시" for h in data["시간"]],
            y=data["객수"],
            marker_color=colors,
            text=[int(v) for v in data["객수"]],
            textposition="outside",
        ))
        fig_t.update_layout(
            plot_bgcolor="white", height=300,
            margin=dict(t=10, b=20, l=10, r=10),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="#F5F5F5"),
        )
        st.plotly_chart(fig_t, use_container_width=True)

        st.markdown(
            f'<div class="highlight-box">👨‍🍳 <b>AI 조리 지시서:</b> '
            f'<b>{peak_h}시</b>에 손님이 가장 많습니다. '
            f'<b>{peak_h - 1}시 30분</b>부터 베스트 상품을 선조리하여 매대를 꽉 채우고,'
            f' 고소한 냄새로 구매 욕구를 자극하세요!</div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("💡 `time` 시트에 이 점포의 시간대별 데이터가 없습니다.")

with col_right:
    st.markdown('<div class="section-title">🏆 우리 점포 치킨 베스트 Top 5</div>', unsafe_allow_html=True)

    top_items = data["품목명"][:5]
    top_sales = data["품목매출"][:5]

    if top_sales and sum(top_sales) > 0:
        fig_i = go.Figure()
        fig_i.add_trace(go.Bar(
            y=top_items[::-1],
            x=top_sales[::-1],
            orientation="h",
            marker=dict(color="#FF5733", opacity=0.85),
            text=[f"일매출 {int(v):,}원" for v in top_sales[::-1]],
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color="white", size=12),
        ))
        fig_i.update_layout(
            plot_bgcolor="white", height=300,
            margin=dict(t=10, b=20, l=10, r=10),
            xaxis=dict(showgrid=False, visible=False),
            yaxis=dict(showgrid=False, tickfont=dict(size=13)),
        )
        st.plotly_chart(fig_i, use_container_width=True)

        if top_items:
            st.markdown(
                f'<div style="font-size:0.95rem; color:#555; padding-left:6px;">'
                f'💡 1위 <b>{top_items[0]}</b>은 절대 결품 없도록 발주량을 늘리고,'
                f' 피크타임 전 전진 진열하세요.</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("💡 `units` 시트에 이 점포의 품목별 매출 데이터가 없습니다.")

# ── 8-4. 프로모션 & 유사상권 ──
st.markdown(
    '<div class="section-title">✨ 점포 맞춤형 프로모션 & 유사상권 인사이트</div>',
    unsafe_allow_html=True,
)
col_p, col_o = st.columns(2)

with col_p:
    st.markdown(
        '<div class="kpi-card">'
        '<h4 style="margin-bottom:4px;">🎁 현재 적용 가능한 프로모션</h4>'
        '<div class="sub-note" style="margin-bottom:12px;">구글 시트 promotion 탭 연동</div>',
        unsafe_allow_html=True,
    )
    for p in data["프로모션"]:
        nm = p.get("행사명", "")
        dc = p.get("내용", "")
        desc_html = f"<br><span style='color:#555; font-size:0.9rem;'>{dc}</span>" if dc else ""
        st.markdown(
            f"<div class='promo-item'>✔️ <b>{nm}</b>{desc_html}</div>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

with col_o:
    st.markdown(
        '<div class="kpi-card">'
        '<h4 style="margin-bottom:4px;">🏪 유사상권 베스트 상품 Top 3</h4>'
        '<div class="sub-note" style="margin-bottom:12px;">비슷한 상권에서 잘 팔리는 상품 | O4O 탭 연동</div>',
        unsafe_allow_html=True,
    )
    for idx, item in enumerate(data["유사상권_베스트"]):
        st.markdown(
            f"<div class='promo-item'><b>{idx + 1}위.</b> {item}</div>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)
