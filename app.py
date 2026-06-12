import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from io import StringIO
import re

SPREADSHEET_ID = "1gtWPFhnszYK1VPgmiZQLtstHCltUM_6h"

# ── 1. 페이지 설정 & CSS ──────────────────────────────────────────
st.set_page_config(page_title="치킨25 튀김 레이더", page_icon="🍗", layout="wide")
st.markdown("""
<style>
  .kpi-label  { font-size:.85rem; color:#666; margin-bottom:4px; font-weight:600; }
  .kpi-value  { font-size:1.8rem; font-weight:800; color:#111; }
  .kpi-delta-pos { font-size:1rem; color:#E74C3C; font-weight:700; }
  .kpi-delta-neg { font-size:1rem; color:#3498DB; font-weight:700; }
  .kpi-card   { background:#fff; border:1px solid #EAEAEA; border-radius:12px;
                padding:1.2rem; box-shadow:0 4px 6px rgba(0,0,0,.04); height:100%; }
  .coach-card { border-radius:12px; padding:1.5rem; margin:1rem 0; }
  .coach-warn { background:#FFF3F3; border-left:6px solid #E74C3C; }
  .coach-good { background:#F0FFF4; border-left:6px solid #2ECC71; }
  .highlight-box { background:linear-gradient(90deg,#FFF9E6,#FFFDF5);
                   border:1px solid #F0C040; border-radius:8px;
                   padding:1rem; font-size:1rem; margin-top:.6rem; }
  .section-title { font-size:1.3rem; font-weight:800; margin-top:2rem;
                   margin-bottom:1rem; color:#2C3E50; }
  .rank-row  { display:flex; align-items:center; padding:7px 12px; margin-bottom:5px;
               background:#FFF9F0; border-radius:8px; border-left:4px solid #FF5733; }
  .rank-num  { font-size:1rem; font-weight:800; color:#FF5733; min-width:32px; }
  .rank-name { font-size:.95rem; font-weight:600; color:#222; flex:1; padding:0 8px;
               white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .rank-sales{ font-size:.9rem; color:#555; white-space:nowrap; }
  .promo-row { display:flex; align-items:center; padding:7px 12px; margin-bottom:5px;
               background:#F0FFF4; border-radius:8px; border-left:4px solid #27AE60; }
  .promo-name{ font-size:.9rem; font-weight:600; color:#222; flex:1; padding:0 6px;
               white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .promo-price{ font-size:.85rem; color:#555; white-space:nowrap; margin-right:8px; }
  .promo-sales{ font-size:.9rem; color:#27AE60; font-weight:700; white-space:nowrap; }
  .sim-row   { display:flex; align-items:center; padding:7px 12px; margin-bottom:5px;
               background:#EBF5FB; border-radius:8px; border-left:4px solid #3498DB; }
  .sim-num   { font-size:1rem; font-weight:800; color:#3498DB; min-width:32px; }
  .sim-name  { font-size:.95rem; font-weight:600; color:#222; flex:1; padding:0 8px;
               white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .sim-sales { font-size:.9rem; color:#2980B9; font-weight:700; white-space:nowrap; }
  .card-box  { background:#fff; border:1px solid #EAEAEA; border-radius:12px;
               padding:1.2rem; box-shadow:0 4px 6px rgba(0,0,0,.04); }
  .card-hd   { font-size:1.05rem; font-weight:800; color:#2C3E50; margin-bottom:3px; }
  .card-sub  { font-size:.75rem; color:#999; margin-bottom:12px; }
  .sub-note  { font-size:.75rem; color:#888; margin-top:4px; }
  .divider   { margin:10px 0; border:.5px solid #eee; }
</style>
""", unsafe_allow_html=True)

# ── 2. 비밀번호 인증 ──────────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if not st.session_state.authenticated:
    st.title("🔒 치킨25 튀김 레이더 시스템")
    pwd = st.text_input("비밀번호", type="password")
    if st.button("접속하기"):
        if pwd == "gs25":
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    st.stop()

# ── 3. 유틸리티 ──────────────────────────────────────────────────
def clean_num(val):
    try:
        return float(str(val).replace(",", "").strip())
    except:
        return 0.0

def find_col(columns, keywords):
    for kw in keywords:
        hit = [c for c in columns if kw in str(c)]
        if hit:
            return hit[0]
    return None

# ── 4. 만능 시트 파서 ─────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_sheet(sheet_name: str) -> pd.DataFrame:
    """'점포명' 행을 자동 탐색, 위쪽 메타행을 접두어로 합성"""
    url = (f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
           f"/gviz/tq?tqx=out:csv&sheet={sheet_name}")
    try:
        r = requests.get(url, timeout=15)
    except Exception as e:
        raise ConnectionError(f"'{sheet_name}' 요청 실패: {e}")

    raw = pd.read_csv(StringIO(r.text), header=None, dtype=str)

    header_idx = -1
    for i in range(min(15, len(raw))):
        if raw.iloc[i].fillna("").str.contains("점포명").any():
            header_idx = i
            break

    if header_idx == -1:
        df = pd.read_csv(StringIO(r.text), dtype=str)
        df.columns = [str(c).strip() for c in df.columns]
        return df

    top = raw.iloc[:header_idx].copy().ffill(axis=1) if header_idx > 0 else pd.DataFrame()

    new_cols = []
    for ci in range(len(raw.columns)):
        base = str(raw.iloc[header_idx, ci]).strip()
        if base in ("nan", ""):
            base = f"Col_{ci}"
        prefixes = [
            str(top.iloc[ri, ci]).strip()
            for ri in range(len(top))
            if str(top.iloc[ri, ci]).strip() not in ("nan", "") and "*" not in str(top.iloc[ri, ci])
        ]
        new_cols.append("_".join(prefixes + [base]) if prefixes else base)

    raw.columns = new_cols
    df = raw.iloc[header_idx + 1:].copy()
    df = df[~df.apply(lambda r: r.astype(str).str.strip().eq("").all(), axis=1)]
    return df.reset_index(drop=True)

# ── 5. 파트→점포 매핑 ─────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_part_store_mapping() -> dict:
    try:
        df = load_sheet("SALES")
        part_col  = find_col(df.columns, ["파트"])
        store_col = find_col(df.columns, ["점포명"])
        if not store_col:
            return {"전체": ["점포 없음"]}
        if part_col:
            valid = df.dropna(subset=[part_col, store_col])
            return valid.groupby(part_col)[store_col].unique().apply(list).to_dict()
        return {"전체": df[store_col].dropna().unique().tolist()}
    except Exception as e:
        return {"오류": [str(e)]}

# ── 6. 점포 데이터 로드 ──────────────────────────────────────────
@st.cache_data(ttl=300)
def get_store_data(store_name: str) -> dict:
    errors = []
    debug  = {}

    # ─ 6-1. SALES KPI ─────────────────────────────────────────────
    # 실제 컬럼: "202503 전체 일매출" / "202503 치킨25 일매출" 형식
    avg_total_25 = avg_total_26 = val_total_2605 = 0.0
    avg_chk_25   = avg_chk_26   = val_chk_2605   = 0.0
    try:
        df_s  = load_sheet("SALES")
        debug["SALES_cols"] = list(df_s.columns)
        sc    = find_col(df_s.columns, ["점포명"])
        row_s = df_s[df_s[sc] == store_name].iloc[0]

        def mean_kw(*kws):
            cols = [c for c in df_s.columns if all(k in c for k in kws)]
            vals = [clean_num(row_s[c]) for c in cols
                    if str(row_s[c]).strip() not in ("nan", "")]
            return (np.mean(vals) if vals else 0.0), cols

        avg_total_25, _ = mean_kw("2025", "전체", "일매출")
        avg_total_26, _ = mean_kw("2026", "전체", "일매출")
        _, t2605c = mean_kw("202605", "전체", "일매출")
        val_total_2605 = clean_num(row_s[t2605c[0]]) if t2605c else 0.0

        avg_chk_25, _ = mean_kw("2025", "치킨", "일매출")
        avg_chk_26, _ = mean_kw("2026", "치킨", "일매출")
        _, c2605c = mean_kw("202605", "치킨", "일매출")
        val_chk_2605 = clean_num(row_s[c2605c[0]]) if c2605c else 0.0

    except Exception as e:
        errors.append(f"SALES: {e}")

    # ─ 6-2. 운영율/판매율 (operation 탭) ──────────────────────────
    # 실제 컬럼: Col_8, Col_9 (헤더 없는 열), 날짜열(2026-05-XX_Col_N)
    op_rate = sell_rate = 0.0
    try:
        df_op  = load_sheet("operation")
        debug["operation_cols"] = list(df_op.columns)
        op_sc  = find_col(df_op.columns, ["점포명"])
        if op_sc:
            op_row = df_op[df_op[op_sc] == store_name].iloc[0]
            # 날짜별 컬럼(2026-05-XX)에서 운영 여부 합산
            date_cols = [c for c in df_op.columns if re.search(r"2026-\d{2}-\d{2}", c)]
            if date_cols:
                daily_vals = [clean_num(op_row[c]) for c in date_cols]
                op_rate = (sum(1 for v in daily_vals if v > 0) / len(daily_vals)) * 100
            # Col_8, Col_9 시도
            if "Col_8" in df_op.columns:
                v8 = clean_num(op_row["Col_8"])
                if 0 < v8 <= 100:
                    op_rate = v8
            if "Col_9" in df_op.columns:
                v9 = clean_num(op_row["Col_9"])
                if 0 < v9 <= 100:
                    sell_rate = v9
    except Exception as e:
        errors.append(f"operation: {e}")

    # ─ 6-3. 시간대별 객수 (time 탭, 가로형) ──────────────────────
    # 실제 컬럼: "00 총객수\n(3개월)" ~ "23 총객수\n(3개월)"
    시간_list: list = []
    객수_list: list = []
    try:
        df_t  = load_sheet("time")
        debug["time_cols"] = list(df_t.columns)
        t_sc  = find_col(df_t.columns, ["점포명"])
        sdf_t = df_t[df_t[t_sc] == store_name]
        if len(sdf_t) == 0:
            errors.append(f"time: '{store_name}' 행 없음")
        else:
            t_row = sdf_t.iloc[0]
            hour_buf = {}
            for col in df_t.columns:
                # "00 총객수..." 형식: 앞 두 자리 숫자
                m = re.match(r"^(\d{2})\s", str(col))
                if m:
                    h = int(m.group(1))
                    v = clean_num(t_row[col])
                    # 같은 시간대 중복 시 최대값
                    if h not in hour_buf or v > hour_buf[h]:
                        hour_buf[h] = v
            if hour_buf:
                for h in sorted(hour_buf):
                    시간_list.append(h)
                    객수_list.append(hour_buf[h])
            else:
                errors.append(f"time: 시간 컬럼 패턴 미매칭 → {list(df_t.columns)[8:12]}")
    except Exception as e:
        errors.append(f"time: {e}")

    # ─ 6-4. 베스트 상품 (units 탭, 가로형) ───────────────────────
    # 실제 컬럼: "치킨25)바삭통다리 일매출" 등 — 열=상품, 값=점포 일매출
    품목_list: list = []   # [{"상품명":…, "일매출":…}]
    df_u_cache = None
    try:
        df_u = load_sheet("units")
        debug["units_cols"] = list(df_u.columns)
        df_u_cache = df_u   # promotion 에서 재사용
        u_sc  = find_col(df_u.columns, ["점포명"])
        sdf_u = df_u[df_u[u_sc] == store_name]
        if len(sdf_u) == 0:
            errors.append(f"units: '{store_name}' 행 없음")
        else:
            u_row = sdf_u.iloc[0]
            for col in df_u.columns:
                if col.endswith(" 일매출") and not col.startswith("*"):
                    prod_nm = col[:-4].strip()   # " 일매출" 제거 (4글자)
                    val = clean_num(u_row[col])
                    if val > 0:
                        품목_list.append({"상품명": prod_nm, "일매출": val})
            품목_list.sort(key=lambda x: x["일매출"], reverse=True)
    except Exception as e:
        errors.append(f"units: {e}")

    # ─ 6-5. 프로모션 (promotion 탭) ──────────────────────────────
    # 실제 컬럼: 상품명, 행사가격, 정상가격, 행사타입(1), 기간
    # 점포 일매출 → units 탭에서 "상품명 + ' 일매출'" 으로 크로스 조인
    promo_list: list = []
    try:
        df_p = load_sheet("promotion")
        debug["promotion_cols"] = list(df_p.columns)

        # units 행으로 이 점포 일매출 dict 구성
        store_units_dict = {}
        if df_u_cache is not None:
            u_sc2 = find_col(df_u_cache.columns, ["점포명"])
            sdf_u2 = df_u_cache[df_u_cache[u_sc2] == store_name]
            if len(sdf_u2) > 0:
                u_row2 = sdf_u2.iloc[0]
                for col in df_u_cache.columns:
                    if col.endswith(" 일매출") and not col.startswith("*"):
                        prod_key = col[:-4].strip()
                        store_units_dict[prod_key] = clean_num(u_row2[col])

        prod_col  = "상품명"        # 실제 확인된 컬럼명
        price_col = "행사가격"
        reg_col   = "정상가격"
        period_col= "기간"

        for _, r in df_p.iterrows():
            prod_nm = str(r.get(prod_col, "")).strip()
            if prod_nm in ("nan", ""):
                continue
            p_price  = clean_num(r.get(price_col, 0))
            r_price  = clean_num(r.get(reg_col, 0))
            period   = str(r.get(period_col, "")).strip()
            # units에서 이 점포의 해당 상품 일매출 조회
            daily    = store_units_dict.get(prod_nm, 0.0)
            promo_list.append({
                "상품명":   prod_nm,
                "행사가격": p_price,
                "정상가격": r_price,
                "기간":     period,
                "일매출":   daily,
            })

        if not promo_list:
            promo_list = [{"상품명": "프로모션 데이터 없음",
                           "행사가격": 0, "정상가격": 0, "기간": "", "일매출": 0}]
    except Exception as e:
        errors.append(f"promotion: {e}")
        promo_list = [{"상품명": f"오류: {e}",
                       "행사가격": 0, "정상가격": 0, "기간": "", "일매출": 0}]

    # ─ 6-6. 유사상권 (O4O 탭) ────────────────────────────────────
    # 실제 컬럼: 점포명, 치킨25, 운영점, O4O 일매출
    # 구조상 상품별 breakdown 없음 → 집계 지표로 표시
    sim_list: list = []
    try:
        df_o = load_sheet("O4O")
        debug["O4O_cols"] = list(df_o.columns)
        o_sc  = find_col(df_o.columns, ["점포명"])
        o_sal = find_col(df_o.columns, ["O4O 일매출", "일매출"])
        sdf_o = df_o[df_o[o_sc] == store_name] if o_sc else pd.DataFrame()

        if len(sdf_o) > 0 and o_sal:
            o_row = sdf_o.iloc[0]
            o4o_val = clean_num(o_row[o_sal])
            # 운영점 수
            ops_col = find_col(df_o.columns, ["운영점"])
            ops_cnt = int(clean_num(o_row[ops_col])) if ops_col else 0
            sim_list = [{
                "상품명": f"유사상권 치킨25 평균 일매출",
                "일매출": o4o_val,
                "ops":    ops_cnt,
            }]
        else:
            sim_list = [{"상품명": "O4O 데이터 없음", "일매출": 0, "ops": 0}]
    except Exception as e:
        errors.append(f"O4O: {e}")
        sim_list = [{"상품명": f"오류: {e}", "일매출": 0, "ops": 0}]

    return {
        "총매출_25평균":  int(avg_total_25),
        "총매출_26평균":  int(avg_total_26),
        "총매출_26년5월": int(val_total_2605),
        "치킨_25평균":   int(avg_chk_25),
        "치킨_26평균":   int(avg_chk_26),
        "치킨_26년5월":  int(val_chk_2605),
        "운영율":  op_rate,
        "판매율":  sell_rate,
        "시간":    시간_list,
        "객수":    객수_list,
        "품목":    품목_list,          # [{"상품명":…,"일매출":…}]
        "프로모션": promo_list,        # [{"상품명","행사가격","정상가격","기간","일매출"}]
        "유사상권": sim_list,          # [{"상품명","일매출","ops"}]
        "errors":  errors,
        "debug":   debug,
    }

# ── 7. 헬퍼 ─────────────────────────────────────────────────────
def calc_growth(v25, v26):
    return 0.0 if v25 == 0 else (v26 - v25) / v25 * 100

def delta_html(g):
    cls = "kpi-delta-pos" if g >= 0 else "kpi-delta-neg"
    return f'<div class="{cls}">{"▲" if g >= 0 else "▼"} {abs(g):.1f}%</div>'

def won(v, unit=1, suffix="원"):
    """v를 unit으로 나눠 정수 포맷"""
    return f"{int(v / unit):,}{suffix}"

# ── 8. 대시보드 ──────────────────────────────────────────────────
st.title("🍗 치킨25 튀김 레이더")

show_debug = st.sidebar.checkbox("🔧 시트 컬럼 디버그", value=False)

part_map = get_part_store_mapping()
c1, c2 = st.columns(2)
with c1: sel_part  = st.selectbox("🏢 소속 파트를 선택하세요:", list(part_map.keys()))
with c2: sel_store = st.selectbox("🏬 분석할 점포를 선택하세요:", part_map[sel_part])

data = get_store_data(sel_store)

if show_debug:
    with st.expander("🔧 시트 컬럼 원본", expanded=True):
        for tab, cols in data["debug"].items():
            st.markdown(f"**{tab}**")
            st.code("\n".join(cols))
    if data["errors"]:
        with st.expander("⚠️ 오류 목록"):
            for e in data["errors"]: st.warning(e)

tg = calc_growth(data["총매출_25평균"], data["총매출_26평균"])
cg = calc_growth(data["치킨_25평균"],   data["치킨_26평균"])

# ── 8-1. KPI 4개 ─────────────────────────────────────────────────
st.markdown('<div class="section-title">📊 종합 실적 및 점포 진단</div>',
            unsafe_allow_html=True)
k1, k2, k3, k4 = st.columns(4)

with k1:
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">전체 일매출 흐름 (YoY)</div>
      <div class="kpi-value">{won(data['총매출_26평균'], 10000, '만원')}</div>
      {delta_html(tg)}
      <div class="divider"></div>
      <div style="font-size:.95rem"><b>'26년 5월:</b> {won(data['총매출_26년5월'], 10000, '만원')}</div>
      <div class="sub-note">* 25년 3~5월 평균 vs 26년 3~5월 평균</div>
    </div>""", unsafe_allow_html=True)

with k2:
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">치킨25 일매출 흐름 (YoY)</div>
      <div class="kpi-value">{won(data['치킨_26평균'], 1000, '천원')}</div>
      {delta_html(cg)}
      <div class="divider"></div>
      <div style="font-size:.95rem"><b>'26년 5월:</b> {won(data['치킨_26년5월'], 1000, '천원')}</div>
      <div class="sub-note">* 25년 3~5월 평균 vs 26년 3~5월 평균</div>
    </div>""", unsafe_allow_html=True)

with k3:
    op_txt = f"{data['운영율']:.1f}%" if data['운영율'] > 0 else "—"
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">튀김기 운영율</div>
      <div class="kpi-value">{op_txt}</div>
      <div class="sub-note">* 목표 85% 이상 | operation 탭 기준</div>
    </div>""", unsafe_allow_html=True)

with k4:
    sl_txt = f"{data['판매율']:.1f}%" if data['판매율'] > 0 else "—"
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">치킨 판매율 (수율)</div>
      <div class="kpi-value">{sl_txt}</div>
      <div class="sub-note">* 튀긴 수량 대비 실판매 | operation 탭 기준</div>
    </div>""", unsafe_allow_html=True)

# ── 8-2. 코칭 메시지 ──────────────────────────────────────────────
if   tg > 0 and cg < 0:
    msg = (f"🚨 <b>기회 로스!</b> 전체 손님 <b>{tg:.1f}%▲</b> 증가에도 치킨 매출 <b>{abs(cg):.1f}%▼</b>. "
           "매대 진열 즉시 강화하세요!")
    cls = "coach-warn"
elif tg < 0 and cg > 0:
    msg = (f"💡 <b>치킨이 효자!</b> 전체 하락 속 치킨 <b>{cg:.1f}%▲</b>. "
           "베스트 상품 복수 진열로 객단가를 더 올리세요.")
    cls = "coach-good"
elif tg < 0 and cg < 0:
    msg = "⚠️ <b>전면 리프레시 필요!</b> 매출 동반 하락. 피크타임 선조리로 냄새 마케팅을 강화하세요."
    cls = "coach-warn"
else:
    msg = "🔥 <b>완벽한 상승!</b> 전체·치킨 모두 상승 중. 신상품 추가 도입으로 추가 매출을 노리세요."
    cls = "coach-good"
st.markdown(f'<div class="coach-card {cls}">{msg}</div>', unsafe_allow_html=True)
st.markdown("<hr style='border:1px dashed #DDD; margin:0;'>", unsafe_allow_html=True)

# ── 8-3. 시간대 차트 + 베스트 상품 ──────────────────────────────
left, right = st.columns([1.3, 1])

with left:
    st.markdown('<div class="section-title">⏱️ 시간대별 방문객 및 조리 타이밍</div>',
                unsafe_allow_html=True)
    if data["객수"] and max(data["객수"]) > 0:
        max_i  = int(np.argmax(data["객수"]))
        peak_h = int(data["시간"][max_i])
        colors = ["#FFC300" if i == max_i else "#BDC3C7"
                  for i in range(len(data["시간"]))]
        fig_t = go.Figure()
        fig_t.add_trace(go.Bar(
            x=[f"{int(h):02d}시" for h in data["시간"]],
            y=data["객수"],
            marker_color=colors,
            text=[f"{int(v):,}" for v in data["객수"]],
            textposition="outside",
            textfont=dict(size=10),
        ))
        fig_t.update_layout(
            plot_bgcolor="white", height=340,
            margin=dict(t=15, b=5, l=0, r=0),
            xaxis=dict(showgrid=False, tickfont=dict(size=10)),
            yaxis=dict(showgrid=True, gridcolor="#EEE",
                       title="3개월 누적 객수"),
        )
        st.plotly_chart(fig_t, use_container_width=True)
        st.markdown(
            f'<div class="highlight-box">👨‍🍳 <b>AI 조리 지시서:</b> '
            f'<b>{peak_h:02d}시</b>가 피크타임입니다. '
            f'<b>{peak_h - 1:02d}시 30분</b>부터 베스트 상품을 선조리해 '
            f'매대를 꽉 채우고 고소한 냄새로 구매 욕구를 자극하세요!</div>',
            unsafe_allow_html=True)
    else:
        st.info("time 시트에서 시간대 데이터를 찾지 못했습니다.\n"
                "사이드바 디버그 모드에서 time_cols를 확인해 주세요.")

with right:
    st.markdown('<div class="section-title">🏆 우리 점포 치킨 베스트 Top 5</div>',
                unsafe_allow_html=True)
    top5 = data["품목"][:5]
    if top5:
        # 순위 카드
        for i, p in enumerate(top5):
            nm = p["상품명"].replace("치킨25)", "")   # 접두어 제거로 가독성↑
            sv = p["일매출"]
            st.markdown(
                f'<div class="rank-row">'
                f'<span class="rank-num">{i+1}위</span>'
                f'<span class="rank-name" title="{p["상품명"]}">{nm}</span>'
                f'<span class="rank-sales">일매출 {int(sv):,}원</span>'
                f'</div>',
                unsafe_allow_html=True)

        # 가로 막대
        names  = [p["상품명"].replace("치킨25)", "")[:12] for p in top5]
        values = [p["일매출"] for p in top5]
        fig_i  = go.Figure()
        fig_i.add_trace(go.Bar(
            y=names[::-1],
            x=values[::-1],
            orientation="h",
            marker=dict(color="#FF5733", opacity=0.85),
            text=[f"{int(v):,}원" for v in values[::-1]],
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color="white", size=11),
        ))
        fig_i.update_layout(
            plot_bgcolor="white", height=240,
            margin=dict(t=5, b=5, l=0, r=10),
            xaxis=dict(showgrid=False, visible=False),
            yaxis=dict(showgrid=False, tickfont=dict(size=11)),
        )
        st.plotly_chart(fig_i, use_container_width=True)
        st.markdown(
            f'<div class="sub-note" style="padding-left:4px;">'
            f'* units 탭 | 26년 3~5월 평균 일매출 기준</div>',
            unsafe_allow_html=True)
    else:
        st.info("units 시트에서 품목 데이터를 찾지 못했습니다.")

# ── 8-4. 프로모션 & 유사상권 ─────────────────────────────────────
st.markdown('<div class="section-title">✨ 프로모션 행사 & 유사상권 인사이트</div>',
            unsafe_allow_html=True)
cp, co = st.columns(2)

with cp:
    st.markdown(
        '<div class="card-box">'
        '<div class="card-hd">🎁 현재 행사 상품 & 이 점포 일매출</div>'
        '<div class="card-sub">promotion 탭 × units 탭 크로스 조인 | 행사가격 · 점포 일매출</div>',
        unsafe_allow_html=True)

    # 판매 실적 있는 것 / 없는 것 분리 표시
    selling = [p for p in data["프로모션"] if p["일매출"] > 0]
    not_sell = [p for p in data["프로모션"] if p["일매출"] == 0]

    if selling:
        st.markdown("**▶ 판매 중인 행사 상품**", unsafe_allow_html=False)
        for p in selling:
            nm   = p["상품명"].replace("치킨25)", "")
            hp   = int(p["행사가격"]) if p["행사가격"] > 0 else "-"
            sv   = int(p["일매출"])
            period = f" ({p['기간']})" if p["기간"] not in ("nan","") else ""
            st.markdown(
                f'<div class="promo-row">'
                f'<span class="promo-name" title="{p["상품명"]}">{nm}{period}</span>'
                f'<span class="promo-price">행사가 {hp}원</span>'
                f'<span class="promo-sales">일매출 {sv:,}원</span>'
                f'</div>',
                unsafe_allow_html=True)

    if not_sell:
        with st.expander(f"미취급 행사 상품 ({len(not_sell)}개) — 클릭해서 보기"):
            for p in not_sell:
                nm = p["상품명"].replace("치킨25)","")
                hp = int(p["행사가격"]) if p["행사가격"] > 0 else "-"
                st.markdown(
                    f'<div style="padding:5px 10px; margin-bottom:4px;'
                    f'background:#F8F8F8; border-radius:6px; font-size:.9rem;">'
                    f'⬜ {nm} &nbsp; <span style="color:#999;">행사가 {hp}원 | 이 점포 미취급</span>'
                    f'</div>',
                    unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with co:
    st.markdown(
        '<div class="card-box">'
        '<div class="card-hd">🏪 유사상권 치킨25 현황</div>'
        '<div class="card-sub">O4O 탭 연동 | 유사상권 평균 일매출 벤치마크</div>',
        unsafe_allow_html=True)

    store_chk = data["치킨_26평균"]   # 이 점포 치킨 일매출
    o4o_val   = data["유사상권"][0]["일매출"] if data["유사상권"] else 0
    ops_cnt   = data["유사상권"][0].get("ops", 0) if data["유사상권"] else 0

    diff = store_chk - o4o_val
    diff_pct = (diff / o4o_val * 100) if o4o_val > 0 else 0
    color = "#E74C3C" if diff >= 0 else "#3498DB"
    arrow = "▲" if diff >= 0 else "▼"

    st.markdown(f"""
    <div style="background:#EBF5FB; border-radius:10px; padding:14px; margin-bottom:10px;">
      <div style="font-size:.85rem; color:#555; margin-bottom:4px;">유사상권 치킨25 평균 일매출</div>
      <div style="font-size:1.6rem; font-weight:800; color:#2980B9;">{int(o4o_val):,}원</div>
      <div style="font-size:.8rem; color:#777;">* 유사 점포 {ops_cnt}개 평균 | O4O 탭 기준</div>
    </div>
    <div style="background:#FFF; border:1px solid #DDD; border-radius:10px; padding:14px;">
      <div style="font-size:.85rem; color:#555; margin-bottom:4px;">우리 점포 vs 유사상권</div>
      <div style="font-size:1.3rem; font-weight:800; color:{color};">
        {arrow} {abs(int(diff)):,}원 ({abs(diff_pct):.1f}%)
      </div>
      <div style="font-size:.8rem; color:#777; margin-top:4px;">
        우리 점포: {int(store_chk):,}원 / 유사상권: {int(o4o_val):,}원
      </div>
    </div>
    """, unsafe_allow_html=True)

    # 유사상권 베스트 참고 — units 탭 전체 기준 상위 상품 표시
    st.markdown(
        "<div style='margin-top:14px; font-size:.9rem; font-weight:700; color:#2C3E50;'>"
        "📌 전체 점포 치킨25 베스트 Top 3 (참고용)</div>",
        unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:.75rem; color:#999; margin-bottom:8px;'>"
        "* units 탭 전 점포 일매출 합계 기준</div>",
        unsafe_allow_html=True)
    try:
        df_u_all = load_sheet("units")
        u_sc_all = find_col(df_u_all.columns, ["점포명"])
        agg = {}
        for col in df_u_all.columns:
            if col.endswith(" 일매출") and not col.startswith("*"):
                prod_nm = col[:-4].strip()
                total   = df_u_all[col].apply(clean_num).sum()
                if total > 0:
                    agg[prod_nm] = total
        top3_all = sorted(agg.items(), key=lambda x: x[1], reverse=True)[:3]
        for i, (nm, tot) in enumerate(top3_all):
            nm_short = nm.replace("치킨25)","")
            st.markdown(
                f'<div class="sim-row">'
                f'<span class="sim-num">{i+1}위</span>'
                f'<span class="sim-name" title="{nm}">{nm_short}</span>'
                f'<span class="sim-sales">합계 {int(tot):,}원</span>'
                f'</div>',
                unsafe_allow_html=True)
    except Exception as e:
        st.info(f"전체 집계 조회 실패: {e}")

    st.markdown("</div>", unsafe_allow_html=True)
