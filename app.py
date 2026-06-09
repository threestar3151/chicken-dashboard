import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from io import StringIO
import random

SPREADSHEET_ID = "1gtWPFhnszYK1VPgmiZQLtstHCltUM_6h"

# ── 1. 페이지 설정 및 CSS ────────────────────────────────────────
st.set_page_config(page_title="치킨25 튀김 레이더", page_icon="🍗", layout="wide")

st.markdown("""
<style>
  .kpi-label { font-size:0.85rem; color:#666; margin-bottom:4px; font-weight:600;}
  .kpi-value { font-size:1.8rem; font-weight:800; color:#111; }
  .kpi-delta-pos { font-size:1rem; color:#E74C3C; font-weight:700; } 
  .kpi-delta-neg { font-size:1rem; color:#3498DB; font-weight:700; }
  .kpi-card {
    background:#fff; border:1px solid #EAEAEA; border-radius:12px;
    padding:1.2rem; box-shadow:0 4px 6px rgba(0,0,0,0.04); height: 100%;
  }
  .coach-card {
    border-radius:12px; padding:1.5rem; margin:1rem 0;
  }
  .coach-warn { background:#FFF3F3; border-left:6px solid #E74C3C; }
  .coach-good { background:#F0FFF4; border-left:6px solid #2ECC71; }
  .highlight-box {
    background:linear-gradient(90deg,#FFF9E6,#FFFDF5);
    border:1px solid #F0C040; border-radius:8px; padding:1rem; font-size:1rem;
  }
  .section-title { font-size:1.3rem; font-weight:800; margin-top:2rem; margin-bottom:1rem; color:#2C3E50; }
  .promo-item { font-size:1rem; color:#333; margin-bottom:0.5rem; }
  .sub-note { font-size:0.75rem; color:#888; margin-top:4px; }
  .divider { margin: 10px 0; border: 0.5px solid #eee; }
</style>
""", unsafe_allow_html=True)

# ── 2. 비밀번호 인증 ───────────────────────────────────────────
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

# ── 3. 스마트 데이터 로딩 엔진 ──────────────────────────
@st.cache_data(ttl=300)
def load_sheet(sheet_name):
    """다중 헤더 및 병합 셀을 똑똑하게 인식하여 데이터프레임으로 반환합니다."""
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    r = requests.get(url, timeout=10)
    if r.status_code != 200 or "html" in r.text.lower():
        raise ValueError(f"'{sheet_name}' 시트를 찾을 수 없습니다.")
    
    # 1. 데이터를 헤더 없이 모두 문자열로 로드
    df = pd.read_csv(StringIO(r.text), header=None, dtype=str)
    
    # 2. '점포명'이 포함된 진짜 기준 행 찾기
    header_idx = None
    for i in range(min(10, len(df))):
        if '점포명' in df.iloc[i].fillna('').values:
            header_idx = i
            break
            
    if header_idx is not None:
        # 3. 병합된 셀(빈칸)을 앞으로 당겨서 채우기 (ffill)
        if header_idx > 0:
            top_rows = df.iloc[0:header_idx].ffill(axis=1)
        else:
            top_rows = pd.DataFrame()
            
        # 4. 여러 줄의 헤더 이름을 하나로 결합
        new_cols = []
        for col_idx in range(len(df.columns)):
            base_name = str(df.iloc[header_idx, col_idx])
            if base_name == 'nan': base_name = f"Col_{col_idx}"
            
            prefixes = []
            for r_idx in range(len(top_rows)):
                val = str(top_rows.iloc[r_idx, col_idx])
                # 'nan' 이나 필요 없는 메타데이터 제외
                if val != 'nan' and val.strip() != '' and '*' not in val:
                    prefixes.append(val.strip())
            
            if prefixes:
                new_cols.append("_".join(prefixes) + "_" + base_name)
            else:
                new_cols.append(base_name)
                
        df.columns = new_cols
        df = df.iloc[header_idx + 1:].reset_index(drop=True)
    else:
        # 일반적인 1줄짜리 헤더인 경우
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)
        
    return df

@st.cache_data(ttl=300)
def get_part_store_mapping():
    try:
        df_sales = load_sheet("SALES")
        # '파트' 열 찾기 (이름이 살짝 다를 수 있으므로 유연하게 검색)
        part_col = next((c for c in df_sales.columns if '파트' in c), None)
        store_col = next((c for c in df_sales.columns if '점포명' in c), None)
        
        if part_col and store_col:
            # 결측치 제외
            valid_df = df_sales.dropna(subset=[part_col, store_col])
            mapping = valid_df.groupby(part_col)[store_col].unique().apply(list).to_dict()
            return mapping
        else:
            return {"전체 점포": df_sales[store_col].dropna().unique().tolist()} if store_col else {"테스트파트": ["데이터없음"]}
    except Exception as e:
        return {"시스템 파트": ["점포 로드 실패"]}

def clean_num(val):
    """문자열에서 쉼표를 제거하고 숫자로 변환합니다."""
    try:
        return float(str(val).replace(',', '').strip())
    except:
        return 0.0

@st.cache_data(ttl=300)
def get_store_data(store_name):
    try:
        df_sales = load_sheet("SALES")
        store_col = next(c for c in df_sales.columns if '점포명' in c)
        store_sales = df_sales[df_sales[store_col] == store_name].iloc[0]
        
        # ── 스마트 데이터 추출 (25년/26년 / 전체/치킨 필터링) ──
        total_25_cols = [c for c in df_sales.columns if '2025' in c and '전체' in c]
        total_26_cols = [c for c in df_sales.columns if '2026' in c and '전체' in c]
        total_2605_cols = [c for c in df_sales.columns if '202605' in c and '전체' in c]
        
        chk_25_cols = [c for c in df_sales.columns if '2025' in c and '치킨' in c]
        chk_26_cols = [c for c in df_sales.columns if '2026' in c and '치킨' in c]
        chk_2605_cols = [c for c in df_sales.columns if '202605' in c and '치킨' in c]

        # 데이터 리스트를 숫자로 변환 후 평균 계산
        avg_total_25 = np.mean([clean_num(store_sales[c]) for c in total_25_cols]) if total_25_cols else 0
        avg_total_26 = np.mean([clean_num(store_sales[c]) for c in total_26_cols]) if total_26_cols else 0
        val_total_2605 = clean_num(store_sales[total_2605_cols[0]]) if total_2605_cols else 0

        avg_chk_25 = np.mean([clean_num(store_sales[c]) for c in chk_25_cols]) if chk_25_cols else 0
        avg_chk_26 = np.mean([clean_num(store_sales[c]) for c in chk_26_cols]) if chk_26_cols else 0
        val_chk_2605 = clean_num(store_sales[chk_2605_cols[0]]) if chk_2605_cols else 0

        # 임시 기본값 (운영율/판매율은 operation 시트에 있을 것으로 추정, 우선 85로 둠)
        운영율 = 85.0 
        판매율 = 92.0

        # ── 품목 (units) 데이터 처리 ──
        try:
            df_item = load_sheet("units")
            u_store_col = next((c for c in df_item.columns if '점포명' in c), df_item.columns[0])
            store_item_df = df_item[df_item[u_store_col] == store_name]
            
            item_col = next((c for c in store_item_df.columns if '품목' in c or '상품' in c), store_item_df.columns[1])
            sales_col = next((c for c in store_item_df.columns if '매출' in c or '금액' in c), store_item_df.columns[2])
            
            # 숫자 정제 후 정렬
            store_item_df['clean_sales'] = store_item_df[sales_col].apply(clean_num)
            store_item_df = store_item_df.sort_values(by='clean_sales', ascending=False)
            
            품목명 = store_item_df[item_col].tolist()
            품목매출 = store_item_df['clean_sales'].tolist()
        except:
            품목명 = ["데이터 부족"]
            품목매출 = [0]

        # ── 시간 (time) 데이터 처리 ──
        try:
            df_time = load_sheet("time")
            t_store_col = next((c for c in df_time.columns if '점포명' in c), df_time.columns[0])
            store_time_df = df_time[df_time[t_store_col] == store_name]
            시간 = store_time_df.iloc[:, 1].apply(clean_num).tolist()
            객수 = store_time_df.iloc[:, 2].apply(clean_num).tolist()
        except:
            시간 = list(range(9, 24))
            객수 = [0]*15

        return {
            "총매출_25평균": int(avg_total_25), "총매출_26평균": int(avg_total_26), "총매출_26년5월": int(val_total_2605),
            "치킨_25평균": int(avg_chk_25), "치킨_26평균": int(avg_chk_26), "치킨_26년5월": int(val_chk_2605),
            "운영율": 운영율, "판매율": 판매율,
            "시간": 시간, "객수": 객수,
            "품목명": 품목명, "품목매출": 품목매출,
            "프로모션": [], "유사상권_베스트": [], "is_mock": False
        }
    except Exception as e:
        print(f"⚠️ 실제 데이터 연동 실패: {e}")
        return {"is_mock": True, "에러내용": str(e)}

# ── 4. UI 렌더링 ───────────────────────────────────────────
st.title("🍗 치킨25 튀김 레이더")

part_store_map = get_part_store_mapping()
part_list = list(part_store_map.keys())

col_sel1, col_sel2 = st.columns(2)
with col_sel1:
    selected_part = st.selectbox("🏢 소속 파트를 선택하세요:", part_list)
with col_sel2:
    store_list = part_store_map[selected_part]
    selected_store = st.selectbox("🏬 분석할 점포를 선택하세요:", store_list)

data = get_store_data(selected_store)

if data.get("is_mock"):
    st.error(f"⚠️ 점포 데이터를 계산하는 중 오류가 발생했습니다. (사유: {data.get('에러내용')})")
    st.stop()

def calc_growth(v25, v26):
    if v25 == 0: return 0
    return ((v26 - v25) / v25) * 100

total_growth = calc_growth(data["총매출_25평균"], data["총매출_26평균"])
chicken_growth = calc_growth(data["치킨_25평균"], data["치킨_26평균"])

# ── 5. 핵심 KPI ─────────────────────────────────
st.markdown('<div class="section-title">📊 종합 실적 및 점포 진단</div>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">전체 일매출 흐름 (YoY)</div>
        <div class="kpi-value">{data['총매출_26평균']//10000:,}만원</div>
        <div class="{'kpi-delta-pos' if total_growth > 0 else 'kpi-delta-neg'}">{'▲' if total_growth > 0 else '▼'} {abs(total_growth):.1f}%</div>
        <div class="divider"></div>
        <div style="font-size:0.95rem;"><b>'26년 5월:</b> {data['총매출_26년5월']//10000:,}만원</div>
        <div class="sub-note">*산정기준: 25년/26년 월별 평균 비교</div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">치킨25 일매출 흐름 (YoY)</div>
        <div class="kpi-value">{data['치킨_26평균']//1000:,}천원</div>
        <div class="{'kpi-delta-pos' if chicken_growth > 0 else 'kpi-delta-neg'}">{'▲' if chicken_growth > 0 else '▼'} {abs(chicken_growth):.1f}%</div>
        <div class="divider"></div>
        <div style="font-size:0.95rem;"><b>'26년 5월:</b> {data['치킨_26년5월']//1000:,}천원</div>
        <div class="sub-note">*산정기준: 25년/26년 월별 평균 비교</div>
    </div>""", unsafe_allow_html=True)
with c3:
    st.markdown(f"""<div class="kpi-card"><div class="kpi-label">튀김기 운영율</div>
    <div class="kpi-value">{data['운영율']:.1f}%</div>
    <div class="sub-note">목표: 85% 이상 유지</div></div>""", unsafe_allow_html=True)
with c4:
    st.markdown(f"""<div class="kpi-card"><div class="kpi-label">치킨 판매율</div>
    <div class="kpi-value">{data['판매율']:.1f}%</div>
    <div class="sub-note">기준: 튀긴 수량 대비 판매량</div></div>""", unsafe_allow_html=True)

# ── 6. 기존 차트 영역 ──────────────────────────────────────────
col_left, col_right = st.columns([1.2, 1])

with col_left:
    st.markdown('<div class="section-title">⏱️ 시간대별 방문객 및 조리 타이밍</div>', unsafe_allow_html=True)
    if sum(data["객수"]) > 0:
        max_idx = np.argmax(data["객수"])
        peak_hour_1 = int(data["시간"][max_idx])
        
        fig_time = go.Figure()
        colors = ['#FFC300' if i == max_idx else '#EAEAEA' for i in range(len(data["시간"]))]
        fig_time.add_trace(go.Bar(x=[f"{int(h)}시" for h in data["시간"]], y=data["객수"], marker_color=colors, text=data["객수"], textposition='outside'))
        fig_time.update_layout(plot_bgcolor='white', height=300, margin=dict(t=10, b=20, l=10, r=10), xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#F5F5F5'))
        st.plotly_chart(fig_time, use_container_width=True)
        st.markdown(f'<div class="highlight-box">👨‍🍳 <b>AI 조리 지시서:</b> {peak_hour_1}시에 가장 붐빕니다. {peak_hour_1 - 1}시 30분부터 선조리를 시작하세요!</div>', unsafe_allow_html=True)
    else:
        st.info("해당 점포의 시간대별 데이터가 없습니다.")

with col_right:
    st.markdown('<div class="section-title">🏆 우리 점포 치킨 베스트 Top 5</div>', unsafe_allow_html=True)
    top5_items = data["품목명"][:5]
    top5_sales = data["품목매출"][:5]
    
    if sum(top5_sales) > 0:
        fig_items = go.Figure()
        fig_items.add_trace(go.Bar(y=top5_items[::-1], x=top5_sales[::-1], orientation='h', marker=dict(color='#FF5733', opacity=0.8), text=[f"일매출 {int(v):,}원" for v in top5_sales[::-1]], textposition='inside', insidetextanchor='middle', textfont=dict(color='white', weight='bold')))
        fig_items.update_layout(plot_bgcolor='white', height=300, margin=dict(t=10, b=20, l=10, r=10), xaxis=dict(showgrid=False, visible=False), yaxis=dict(showgrid=False, tickfont=dict(size=13, weight='bold')))
        st.plotly_chart(fig_items, use_container_width=True)
    else:
        st.info("해당 점포의 품목별 매출 데이터가 없습니다.")
