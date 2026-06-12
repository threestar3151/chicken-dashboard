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
  .rank-row {
    display:flex; justify-content:space-between; align-items:center;
    padding:8px 12px; margin-bottom:6px;
    background:#FFF9F0; border-radius:8px; border-left:4px solid #FF5733;
  }
  .rank-num { font-size:1.1rem; font-weight:800; color:#FF5733; min-width:28px; }
  .rank-name { font-size:1rem; font-weight:600; color:#222; flex:1; padding:0 8px; }
  .rank-sales { font-size:0.9rem; color:#555; white-space:nowrap; }
  .promo-row {
    display:flex; justify-content:space-between; align-items:center;
    padding:8px 12px; margin-bottom:6px;
    background:#F0FFF4; border-radius:8px; border-left:4px solid #2ECC71;
  }
  .promo-name { font-size:0.95rem; font-weight:600; color:#222; flex:1; }
  .promo-sales { font-size:0.9rem; color:#27AE60; font-weight:700; white-space:nowrap; }
  .sim-row {
    display:flex; justify-content:space-between; align-items:center;
    padding:8px 12px; margin-bottom:6px;
    background:#EBF5FB; border-radius:8px; border-left:4px solid #3498DB;
  }
  .sim-num { font-size:1.1rem; font-weight:800; color:#3498DB; min-width:28px; }
  .sim-name { font-size:0.95rem; font-weight:600; color:#222; flex:1; padding:0 8px; }
  .sim-sales { font-size:0.9rem; color:#2980B9; font-weight:700; white-space:nowrap; }
  .sub-note { font-size:0.75rem; color:#888; margin-top:4px; }
  .divider { margin:10px 0; border:0.5px solid #eee; }
  .card-header { font-size:1.05rem; font-weight:800; color:#2C3E50; margin-bottom:4px; }
  .card-subnote { font-size:0.75rem; color:#999; margin-bottom:12px; }
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


# ── 3. 유틸리티 ──────────────────────────────────────────────────
def clean_num(val):
    try:
        return float(str(val).replace(",", "").strip())
    except:
        return 0.0


def find_col(columns, keywords):
    """키워드 리스트 순서대로 첫 번째 매칭 컬럼 반환"""
    for kw in keywords:
        matched = [c for c in columns if kw in str(c)]
        if matched:
            return matched[0]
    return None


# ── 4. 만능 시트 파서 ─────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_sheet(sheet_name: str) -> pd.DataFrame:
    """병합셀/다중헤더를 자동 감지. '점포명' 행을 헤더로 사용."""
    url = (
        f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
        f"/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    )
    try:
        r = requests.get(url, timeout=15)
    except Exception as e:
        raise ConnectionError(f"'{sheet_name}' 요청 실패: {e}")

    raw = pd.read_csv(StringIO(r.text), header=None, dtype=str)

    # '점포명' 행 탐색
    header_idx = -1
    for i in range(min(15, len(raw))):
        if raw.iloc[i].fillna("").str.contains("점포명").any():
            header_idx = i
            break

    if header_idx == -1:
        df = pd.read_csv(StringIO(r.text), dtype=str)
        df.columns = [str(c).strip() for c in df.columns]
        return df

    # 헤더 위 메타행 → ffill 후 접두어로 합성
    if header_idx > 0:
        top = raw.iloc[:header_idx].copy().ffill(axis=1)
    else:
        top = pd.DataFrame()

    new_cols = []
    for ci in range(len(raw.columns)):
        base = str(raw.iloc[header_idx, ci]).strip()
        if base in ("nan", ""):
            base = f"Col_{ci}"
        prefixes = [
            str(top.iloc[ri, ci]).strip()
            for ri in range(len(top))
            if str(top.iloc[ri, ci]).strip() not in ("nan", "")
            and "*" not in str(top.iloc[ri, ci])
        ]
        new_cols.append("_".join(prefixes + [base]) if prefixes else base)

    raw.columns = new_cols
    df = raw.iloc[header_idx + 1:].copy()
    df = df[~df.apply(lambda r: r.astype(str).str.strip().eq("").all(), axis=1)]
    return df.reset_index(drop=True)


# ── 5. 파트→점포 매핑 ────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_part_store_mapping() -> dict:
    try:
        df = load_sheet("SALES")
        part_col = find_col(df.columns, ["파트"])
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
    debug_info = {}   # 각 시트 컬럼명 저장 (디버그용)
    errors = []

    # ─ 6-1. SALES KPI ─
    avg_total_25 = avg_total_26 = val_total_2605 = 0.0
    avg_chk_25 = avg_chk_26 = val_chk_2605 = 0.0
    op_rate = sell_rate = 0.0
    try:
        df_s = load_sheet("SALES")
        debug_info["SALES_cols"] = list(df_s.columns)
        sc = find_col(df_s.columns, ["점포명"])
        row = df_s[df_s[sc] == store_name].iloc[0]

        def mean_kw(*kws):
            cols = [c for c in df_s.columns if all(k in c for k in kws)]
            vals = [clean_num(row[c]) for c in cols if str(row[c]).strip() not in ("nan","")]
            return (np.mean(vals) if vals else 0.0), cols

        avg_total_25, _ = mean_kw("2025", "전체")
        avg_total_26, _ = mean_kw("2026", "전체")
        _, t2605c      = mean_kw("202605", "전체")
        val_total_2605 = clean_num(row[t2605c[0]]) if t2605c else 0.0

        avg_chk_25, _ = mean_kw("2025", "치킨")
        avg_chk_26, _ = mean_kw("2026", "치킨")
        _, c2605c      = mean_kw("202605", "치킨")
        val_chk_2605   = clean_num(row[c2605c[0]]) if c2605c else 0.0

        # operation 탭 시도
        try:
            df_op = load_sheet("operation")
            debug_info["operation_cols"] = list(df_op.columns)
            osc = find_col(df_op.columns, ["점포명"])
            if osc:
                op_r = df_op[df_op[osc] == store_name].iloc[0]
                oc = find_col(df_op.columns, ["운영율","운영률","가동률","가동율"])
                slc = find_col(df_op.columns, ["판매율","판매률","수율"])
                if oc:  op_rate   = clean_num(op_r[oc])
                if slc: sell_rate = clean_num(op_r[slc])
        except:
            op_rate = sell_rate = 0.0

    except Exception as e:
        errors.append(f"SALES 오류: {e}")

    # ─ 6-2. 시간대별 객수 (time 탭) ─
    시간_list, 객수_list = [], []
    try:
        df_t = load_sheet("time")
        debug_info["time_cols"] = list(df_t.columns)
        tsc = find_col(df_t.columns, ["점포명"])
        store_rows = df_t[df_t[tsc] == store_name]

        if len(store_rows) == 0:
            errors.append(f"time 시트에 '{store_name}' 데이터 없음")
        else:
            store_row = store_rows.iloc[0]

            # 방법A: 가로 형식 — 컬럼명에 숫자+시 패턴 존재
            hour_cols = []
            for c in df_t.columns:
                m = re.search(r"(\d{1,2})시$", str(c))   # 끝이 XX시인 컬럼
                if m:
                    h = int(m.group(1))
                    v = clean_num(store_row[c])
                    if v >= 0:
                        hour_cols.append((h, v, c))

            if hour_cols:
                # 중복 시간 제거 (같은 시간대가 여러 열이면 최대값 사용)
                hour_dict = {}
                for h, v, c in hour_cols:
                    if h not in hour_dict or v > hour_dict[h]:
                        hour_dict[h] = v
                for h in sorted(hour_dict):
                    시간_list.append(h)
                    객수_list.append(hour_dict[h])
            else:
                # 방법B: 세로 형식
                hc = find_col(df_t.columns, ["시간","시각","hour"])
                cc = find_col(df_t.columns, ["객수","방문객","방문수"])
                if hc and cc:
                    sdf = df_t[df_t[tsc] == store_name].sort_values(hc)
                    시간_list = sdf[hc].apply(clean_num).tolist()
                    객수_list = sdf[cc].apply(clean_num).tolist()
                else:
                    errors.append(f"time 탭: 시간/객수 열을 찾지 못함. 컬럼={list(df_t.columns)[:10]}")

    except Exception as e:
        errors.append(f"time 오류: {e}")

    # ─ 6-3. 베스트 상품 (units 탭) ─
    품목명_list, 품목매출_list = [], []
    try:
        df_u = load_sheet("units")
        debug_info["units_cols"] = list(df_u.columns)
        usc = find_col(df_u.columns, ["점포명"])
        sdf_u = df_u[df_u[usc] == store_name].copy()

        # 상품명 열 탐색
        ic = find_col(sdf_u.columns, ["품목명","상품명","메뉴명","품목","상품","메뉴","item"])
        # 매출 열 탐색 — '일매출', '매출액', '매출', '금액' 순
        sc2 = find_col(sdf_u.columns, ["일매출","매출액","매출금액","매출","금액","판매액","sales"])

        # 자동 탐색 실패 시 — 점포명 열 기준 우측 첫 번째/두 번째 열
        if not ic or not sc2:
            cols_list = list(sdf_u.columns)
            try:
                base_i = cols_list.index(usc)
                if not ic and len(cols_list) > base_i + 1:
                    ic = cols_list[base_i + 1]
                if not sc2 and len(cols_list) > base_i + 2:
                    sc2 = cols_list[base_i + 2]
            except ValueError:
                pass

        if ic and sc2:
            sdf_u["_s"] = sdf_u[sc2].apply(clean_num)
            sdf_u = sdf_u[sdf_u["_s"] > 0].sort_values("_s", ascending=False)
            품목명_list  = sdf_u[ic].astype(str).tolist()
            품목매출_list = sdf_u["_s"].tolist()
        else:
            errors.append(f"units 탭: 상품명/매출 열 미발견. 컬럼={list(df_u.columns)[:15]}")

    except Exception as e:
        errors.append(f"units 오류: {e}")

    # ─ 6-4. 프로모션 (promotion 탭) ─
    promo_list = []   # [{"행사명":..., "상품명":..., "일매출":...}]
    try:
        df_p = load_sheet("promotion")
        debug_info["promotion_cols"] = list(df_p.columns)
        psc = find_col(df_p.columns, ["점포명"])

        if psc:
            sdf_p = df_p[df_p[psc] == store_name].copy()
        else:
            # 점포명 열이 없으면 전체 행사 표시
            sdf_p = df_p.copy()
            errors.append("promotion 탭: 점포명 열 없음 → 전체 행사 표시")

        # 열 이름 탐색
        pname_c  = find_col(sdf_p.columns, ["행사명","프로모션명","행사","프로모션","제목"])
        pitem_c  = find_col(sdf_p.columns, ["상품명","품목명","상품","품목","item"])
        psalse_c = find_col(sdf_p.columns, ["일매출","매출액","매출","금액","sales"])

        if not pname_c:
            # 점포명 옆 열을 행사명으로
            cols_list = list(sdf_p.columns)
            try:
                bi = cols_list.index(psc) if psc else 0
                pname_c = cols_list[bi + 1] if len(cols_list) > bi + 1 else None
            except (ValueError, IndexError):
                pname_c = cols_list[1] if len(cols_list) > 1 else None

        for _, r in sdf_p.iterrows():
            nm = str(r[pname_c]).strip() if pname_c else "행사 정보 없음"
            item = str(r[pitem_c]).strip() if pitem_c else ""
            sales = clean_num(r[psalse_c]) if psalse_c else 0.0
            if nm not in ("nan", ""):
                promo_list.append({"행사명": nm, "상품명": item, "일매출": sales})

        if not promo_list:
            promo_list = [{"행사명": "현재 적용 중인 특화 프로모션 없음", "상품명": "", "일매출": 0}]

    except Exception as e:
        errors.append(f"promotion 오류: {e}")
        promo_list = [{"행사명": f"promotion 시트 오류: {e}", "상품명": "", "일매출": 0}]

    # ─ 6-5. 유사상권 베스트 (O4O 탭) ─
    sim_list = []   # [{"상품명":..., "일매출":...}]
    try:
        df_o = load_sheet("O4O")
        debug_info["O4O_cols"] = list(df_o.columns)
        osc2 = find_col(df_o.columns, ["점포명"])

        if osc2:
            sdf_o = df_o[df_o[osc2] == store_name].copy()
        else:
            sdf_o = df_o.copy()
            errors.append("O4O 탭: 점포명 열 없음 → 전체 표시")

        # 상품명/매출 열 탐색
        sim_ic  = find_col(sdf_o.columns, ["상품명","품목명","상품","품목","item","베스트"])
        sim_sc  = find_col(sdf_o.columns, ["일매출","매출액","매출","금액","sales"])

        if not sim_ic and osc2:
            cols_list = list(sdf_o.columns)
            try:
                bi = cols_list.index(osc2)
                sim_ic = cols_list[bi + 1] if len(cols_list) > bi + 1 else None
                if not sim_sc and len(cols_list) > bi + 2:
                    sim_sc = cols_list[bi + 2]
            except (ValueError, IndexError):
                pass

        for _, r in sdf_o.iterrows():
            nm = str(r[sim_ic]).strip() if sim_ic else "?"
            sales = clean_num(r[sim_sc]) if sim_sc else 0.0
            if nm not in ("nan", ""):
                sim_list.append({"상품명": nm, "일매출": sales})

        # 매출 기준 정렬 후 Top 3
        sim_list = sorted(sim_list, key=lambda x: x["일매출"], reverse=True)[:3]
        if not sim_list:
            sim_list = [{"상품명": "O4O 시트에 해당 점포 데이터 없음", "일매출": 0}]

    except Exception as e:
        errors.append(f"O4O 오류: {e}")
        sim_list = [{"상품명": f"O4O 시트 오류: {e}", "일매출": 0}]

    return {
        "총매출_25평균": int(avg_total_25),
        "총매출_26평균": int(avg_total_26),
        "총매출_26년5월": int(val_total_2605),
        "치킨_25평균": int(avg_chk_25),
        "치킨_26평균": int(avg_chk_26),
        "치킨_26년5월": int(val_chk_2605),
        "운영율": op_rate,
        "판매율": sell_rate,
        "시간": 시간_list,
        "객수": 객수_list,
        "품목명": 품목명_list,
        "품목매출": 품목매출_list,
        "프로모션": promo_list,
        "유사상권": sim_list,
        "errors": errors,
        "debug": debug_info,
    }


# ── 7. 헬퍼 ─────────────────────────────────────────────────────
def calc_growth(v25, v26):
    if v25 == 0:
        return 0.0
    return (v26 - v25) / v25 * 100


def delta_html(growth):
    cls   = "kpi-delta-pos" if growth >= 0 else "kpi-delta-neg"
    arrow = "▲" if growth >= 0 else "▼"
    return f'<div class="{cls}">{arrow} {abs(growth):.1f}%</div>'


# ── 8. 대시보드 ──────────────────────────────────────────────────
st.title("🍗 치킨25 튀김 레이더")

# 사이드바 디버그 토글
show_debug = st.sidebar.checkbox("🔧 시트 컬럼 디버그 보기", value=False)

part_map = get_part_store_mapping()
col_s1, col_s2 = st.columns(2)
with col_s1:
    sel_part  = st.selectbox("🏢 소속 파트를 선택하세요:", list(part_map.keys()))
with col_s2:
    sel_store = st.selectbox("🏬 분석할 점포를 선택하세요:", part_map[sel_part])

data = get_store_data(sel_store)

# 디버그 패널
if show_debug:
    with st.expander("🔧 시트 컬럼명 원본 (문제 진단용)", expanded=True):
        for tab, cols in data["debug"].items():
            st.markdown(f"**{tab}**")
            st.code("\n".join(cols))
    if data["errors"]:
        with st.expander("⚠️ 오류 목록"):
            for e in data["errors"]:
                st.warning(e)

total_growth = calc_growth(data["총매출_25평균"], data["총매출_26평균"])
chk_growth   = calc_growth(data["치킨_25평균"],   data["치킨_26평균"])

# ── 8-1. KPI 카드 ──────────────────────────────────────────────
st.markdown('<div class="section-title">📊 종합 실적 및 점포 진단</div>', unsafe_allow_html=True)
k1, k2, k3, k4 = st.columns(4)

with k1:
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">전체 일매출 흐름 (YoY)</div>
      <div class="kpi-value">{data['총매출_26평균']//10000:,}만원</div>
      {delta_html(total_growth)}
      <div class="divider"></div>
      <div style="font-size:0.95rem;"><b>'26년 5월:</b> {data['총매출_26년5월']//10000:,}만원</div>
      <div class="sub-note">* 25년 월평균 vs 26년 월평균</div>
    </div>""", unsafe_allow_html=True)

with k2:
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">치킨25 일매출 흐름 (YoY)</div>
      <div class="kpi-value">{data['치킨_26평균']//1000:,}천원</div>
      {delta_html(chk_growth)}
      <div class="divider"></div>
      <div style="font-size:0.95rem;"><b>'26년 5월:</b> {data['치킨_26년5월']//1000:,}천원</div>
      <div class="sub-note">* 25년 월평균 vs 26년 월평균</div>
    </div>""", unsafe_allow_html=True)

with k3:
    op_disp = f"{data['운영율']:.1f}%" if data['운영율'] > 0 else "데이터 없음"
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">튀김기 운영율 (가동률)</div>
      <div class="kpi-value">{op_disp}</div>
      <div class="sub-note">* 목표: 85% 이상 | operation 탭 기준</div>
    </div>""", unsafe_allow_html=True)

with k4:
    sl_disp = f"{data['판매율']:.1f}%" if data['판매율'] > 0 else "데이터 없음"
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">치킨 판매율 (수율)</div>
      <div class="kpi-value">{sl_disp}</div>
      <div class="sub-note">* 튀긴 수량 대비 실판매량 | operation 탭 기준</div>
    </div>""", unsafe_allow_html=True)

# ── 8-2. AI 코칭 메시지 ──────────────────────────────────────
if total_growth > 0 and chk_growth < 0:
    msg = (f"🚨 <b>기회 로스 발생!</b> 전체 손님은 <b>{total_growth:.1f}%▲</b> 늘었는데, "
           f"치킨 매출은 <b>{abs(chk_growth):.1f}%▼ 감소</b>. 매대 진열을 즉시 강화하세요!")
    cls = "coach-warn"
elif total_growth < 0 and chk_growth > 0:
    msg = (f"💡 <b>치킨이 효자!</b> 전체 매출 하락 속에서도 치킨은 <b>{chk_growth:.1f}%▲</b>. "
           "베스트 상품 복수 진열로 객단가를 더 끌어올리세요.")
    cls = "coach-good"
elif total_growth < 0 and chk_growth < 0:
    msg = ("⚠️ <b>전면 리프레시 필요!</b> 매출 동반 하락. "
           "피크타임 직전 선조리로 냄새 마케팅을 강화하세요.")
    cls = "coach-warn"
else:
    msg = ("🔥 <b>완벽한 상승 기류!</b> 전체·치킨 모두 상승 중. "
           "신상품 추가 도입으로 추가 매출을 노리세요.")
    cls = "coach-good"

st.markdown(f'<div class="coach-card {cls}">{msg}</div>', unsafe_allow_html=True)
st.markdown("<hr style='border:1px dashed #DDD; margin:0;'>", unsafe_allow_html=True)

# ── 8-3. 시간대별 차트 + 베스트 상품 ────────────────────────
col_left, col_right = st.columns([1.3, 1])

with col_left:
    st.markdown('<div class="section-title">⏱️ 시간대별 방문객 및 조리 타이밍</div>',
                unsafe_allow_html=True)

    if data["객수"] and sum(data["객수"]) > 0:
        max_idx = int(np.argmax(data["객수"]))
        peak_h  = int(data["시간"][max_idx])

        colors = ["#FFC300" if i == max_idx else "#BFCFDD"
                  for i in range(len(data["시간"]))]
        fig_t = go.Figure()
        fig_t.add_trace(go.Bar(
            x=[f"{int(h):02d}시" for h in data["시간"]],
            y=data["객수"],
            marker_color=colors,
            text=[f"{int(v)}" for v in data["객수"]],
            textposition="outside",
            textfont=dict(size=11),
        ))
        fig_t.update_layout(
            plot_bgcolor="white", height=320,
            margin=dict(t=15, b=10, l=0, r=0),
            xaxis=dict(showgrid=False, tickfont=dict(size=11)),
            yaxis=dict(showgrid=True, gridcolor="#F0F0F0"),
        )
        st.plotly_chart(fig_t, use_container_width=True)
        st.markdown(
            f'<div class="highlight-box">👨‍🍳 <b>AI 조리 지시서:</b> '
            f'<b>{peak_h:02d}시</b>에 손님이 가장 많습니다. '
            f'<b>{peak_h - 1:02d}시 30분</b>부터 베스트 상품을 선조리해 '
            f'매대를 꽉 채우고 고소한 냄새로 구매 욕구를 자극하세요!</div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("💡 time 시트에서 이 점포의 시간대별 데이터를 찾지 못했습니다.\n"
                "좌측 사이드바에서 '디버그 보기'를 켜서 time 컬럼명을 확인해 주세요.")

with col_right:
    st.markdown('<div class="section-title">🏆 우리 점포 치킨 베스트 Top 5</div>',
                unsafe_allow_html=True)

    items  = data["품목명"][:5]
    sales  = data["품목매출"][:5]

    if items and sum(sales) > 0:
        # 순위 카드 형태로 표시
        for i, (nm, sv) in enumerate(zip(items, sales)):
            sv_str = f"{int(sv):,}원" if sv > 0 else "-"
            st.markdown(
                f'<div class="rank-row">'
                f'<span class="rank-num">{i+1}위</span>'
                f'<span class="rank-name">{nm}</span>'
                f'<span class="rank-sales">일매출 {sv_str}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # 가로 막대 차트도 함께
        fig_i = go.Figure()
        fig_i.add_trace(go.Bar(
            y=items[::-1],
            x=sales[::-1],
            orientation="h",
            marker=dict(color="#FF5733", opacity=0.82),
            text=[f"{int(v):,}원" for v in sales[::-1]],
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color="white", size=11),
        ))
        fig_i.update_layout(
            plot_bgcolor="white", height=220,
            margin=dict(t=5, b=5, l=0, r=10),
            xaxis=dict(showgrid=False, visible=False),
            yaxis=dict(showgrid=False, tickfont=dict(size=11)),
        )
        st.plotly_chart(fig_i, use_container_width=True)
        st.markdown(
            f'<div class="sub-note" style="padding-left:4px;">* units 탭 기준 | 일평균 매출 기준 정렬</div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("💡 units 시트에서 이 점포의 품목 데이터를 찾지 못했습니다.\n"
                "사이드바 디버그 모드에서 units 컬럼명을 확인해 주세요.")

# ── 8-4. 프로모션 & 유사상권 ─────────────────────────────────
st.markdown('<div class="section-title">✨ 프로모션 행사 & 유사상권 인사이트</div>',
            unsafe_allow_html=True)
col_p, col_o = st.columns(2)

with col_p:
    st.markdown(
        '<div class="kpi-card">'
        '<div class="card-header">🎁 점포 적용 프로모션 행사 상품</div>'
        '<div class="card-subnote">promotion 탭 연동 | 해당 점포 행사 상품 일매출</div>',
        unsafe_allow_html=True,
    )
    for p in data["프로모션"]:
        nm    = p.get("행사명", "")
        item  = p.get("상품명", "")
        sv    = p.get("일매출", 0)
        sv_str = f"{int(sv):,}원" if sv > 0 else "-"
        label = f"{nm}" + (f" · {item}" if item and item != "nan" else "")
        st.markdown(
            f'<div class="promo-row">'
            f'<span class="promo-name">✔️ {label}</span>'
            f'<span class="promo-sales">일매출 {sv_str}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

with col_o:
    st.markdown(
        '<div class="kpi-card">'
        '<div class="card-header">🏪 유사상권 베스트 상품 Top 3</div>'
        '<div class="card-subnote">O4O 탭 연동 | 비슷한 상권 점포 베스트 상품 일매출</div>',
        unsafe_allow_html=True,
    )
    for i, s in enumerate(data["유사상권"]):
        nm    = s.get("상품명", "")
        sv    = s.get("일매출", 0)
        sv_str = f"{int(sv):,}원" if sv > 0 else "-"
        st.markdown(
            f'<div class="sim-row">'
            f'<span class="sim-num">{i+1}위</span>'
            f'<span class="sim-name">{nm}</span>'
            f'<span class="sim-sales">일매출 {sv_str}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)
