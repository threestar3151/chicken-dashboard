import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from io import StringIO

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
  .promo-item { font-size:1rem; color:#333; margin-bottom:0.5rem; line-height:1.4;}
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

# ── 3. 스마트 데이터 로딩 엔진 (이중 구조) ──────────────────────────

@st.cache_data(ttl=300)
def load_sales_sheet():
    """복잡한 병합셀 구조를 가진 SALES 탭 전용 파서"""
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=SALES"
    r = requests.get(url, timeout=10)
    df = pd.read_csv(StringIO(r.text), header=None, dtype=str)
    
    header_idx = next((i for i in range(10) if '점포명' in df.iloc[i].fillna('').values), 0)
    
    if header_idx > 0:
        top_rows = df.iloc[0:header_idx].ffill(axis=1)
        new_cols = []
        for col_idx in range(len(df.columns)):
            base_name = str(df.iloc[header_idx, col_idx])
            if base_name == 'nan': base_name = f"Col_{col_idx}"
            
            prefixes = [str(top_rows.iloc[r, col_idx]).strip() for r in range(len(top_rows)) 
                        if str(top_rows.iloc[r, col_idx]) != 'nan' and '*' not in str(top_rows.iloc[r, col_idx])]
            
            new_cols.append("_".join(prefixes) + "_" + base_name if prefixes else base_name)
            
        df.columns = new_cols
        df = df.iloc[header_idx + 1:].reset_index(drop=True)
    else:
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)
    return df

@st.cache_data(ttl=300)
def load_simple_sheet(sheet_name):
    """일반적인 1줄짜리 헤더를 가진 시트(time, units 등) 전용 파서"""
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    r = requests.get(url, timeout=10)
    df = pd.read_csv(StringIO(r.text), header=None, dtype=str)
    
    # '점포명'이 있는 진짜 1행 찾기
    header_idx = next((i for i in range(min(10, len(df))) if '점포명' in df.iloc[i].fillna('').values), 0)
    df.columns = df.iloc[header_idx]
    df = df.iloc[header_idx + 1:].dropna(how='all').reset_index(drop=True)
    return df

def clean_num(val):
    try: return float(str(val).replace(',', '').strip())
    except: return 0.0

@st.cache_data(ttl=300)
def get_part_store_mapping():
    try:
        df_sales = load_sales_sheet()
        part_col = next((c for c in df_sales.columns if '파트' in c), None)
        store_col = next((c for c in df_sales.columns if '점포명' in c), None)
        
        if part_col and store_col:
            valid_df = df_sales.dropna(subset=[part_col, store_col])
            return valid_df.groupby(part_col)[store_col].unique().apply(list).to_dict()
        else:
            return {"전체 점포": df_sales[store_col].dropna().unique().tolist()} if store_col else {"테스트": ["데이터없음"]}
    except:
        return {"시스템": ["오류발생"]}

@st.cache_data(ttl=300)
def get_store_data(store_name):
    try:
        # --- 1. SALES 데이터 (KPI용) ---
        df_sales = load_sales_sheet()
        store_col = next(c for c in df_sales.columns if '점포명' in c)
        store_sales = df_sales[df_sales[store_col] == store_name].iloc[0]
        
        t25_cols = [c for c in df_sales.columns if '2025' in c and '전체' in c]
        t26_cols = [c for c in df_sales.columns if '2026' in c and '전체' in c]
        t2605_cols = [c for c in df_sales.columns if '202605' in c and '전체' in c]
        
        c25_cols = [c for c in df_sales.columns if '2025' in c and '치킨' in c]
        c26_cols = [c for c in df_sales.columns if '2026' in c and '치킨' in c]
        c2605_cols = [c for c in df_sales.columns if '202605' in c and '치킨' in c]

        avg_total_25 = np.mean([clean_num(store_sales[c]) for c in t25_cols]) if t25_cols else 0
        avg_total_26 = np.mean([clean_num(store_sales[c]) for c in t26_cols]) if t26_cols else 0
        val_total_2605 = clean_num(store_sales[t2605_cols[0]]) if t2605_cols else 0

        avg_chk_25 = np.mean([clean_num(store_sales[c]) for c in c25_cols]) if c25_cols else 0
        avg_chk_26 = np.mean([clean_num(store_sales[c]) for c in c26_cols]) if c26_cols else 0
        val_chk_2605 = clean_num(store_sales[c2605_cols[0]]) if c2605_cols else 0

        # --- 2. 시간 (time) 가로/세로 양식 호환 엔진 ---
        try:
            df_time = load_simple_sheet("time")
            store_time_df = df_time[df_time['점포명'] == store_name]
            
            # 가로 양식인지 (01시, 02시... 가 컬럼에 있는지) 확인
            time_cols_horizontal = [c for c in store_time_df.columns if '시' in str(c) and str(c).replace('시','').strip().isdigit()]
            
            if time_cols_horizontal:
                시간 = [int(str(c).replace('시','').strip()) for c in time_cols_horizontal]
                객수 = [clean_num(store_time_df.iloc[0][c]) for c in time_cols_horizontal]
            else:
                # 세로 양식 처리 (기존 방식)
                t_col = next((c for c in store_time_df.columns if '시간' in c or '시각' in c), None)
                c_col = next((c for c in store_time_df.columns if '객수' in c or '방문' in c), None)
                시간 = store_time_df[t_col].apply(clean_num).tolist() if t_col else []
                객수 = store_time_df[c_col].apply(clean_num).tolist() if c_col else []
        except:
            시간, 객수 = [], []

        # --- 3. 베스트 품목 (units) 무적 찾기 엔진 ---
        try:
            df_item = load_simple_sheet("units")
            store_item_df = df_item[df_item['점포명'] == store_name].copy()
            
            i_col = next((c for c in store_item_df.columns if any(x in str(c) for x in ['품목','상품','메뉴'])), None)
            s_col = next((c for c in store_item_df.columns if any(x in str(c) for x in ['매출','금액','수량'])), None)
            
            # 단어로 못 찾으면 무조건 점포명 옆 1칸, 2칸을 가져옵니다.
            if not i_col or not s_col:
                idx = store_item_df.columns.get_loc('점포명')
                i_col = store_item_df.columns[idx+1]
                s_col = store_item_df.columns[idx+2]

            store_item_df['clean_sales'] = store_item_df[s_col].apply(clean_num)
            store_item_df = store_item_df.sort_values(by='clean_sales', ascending=False)
            품목명 = store_item_df[i_col].astype(str).tolist()
            품목매출 = store_item_df['clean_sales'].tolist()
        except:
            품목명, 품목매출 = [], []

        # --- 4. 프로모션 & 유사상권 데이터 복구 ---
        프로모션_리스트 = []
        try:
            df_promo = load_simple_sheet("promotion")
            store_promo_df = df_promo[df_promo['점포명'] == store_name]
            for _, row in store_promo_df.iterrows():
                # 행사명/내용 이라는 열이 없어도 순서대로 가져옴
                행사명 = row.get('행사명', row.iloc[1] if len(row.index)>1 else '제목 없음')
                내용 = row.get('내용', row.iloc[2] if len(row.index)>2 else '')
                프로모션_리스트.append({"행사명": 행사명, "내용": 내용})
            if not 프로모션_리스트:
                프로모션_리스트 = [{"행사명": "진행중인 특화 프로모션 없음", "내용": ""}]
        except:
            프로모션_리스트 = [{"행사명": "promotion 시트 연결 필요", "내용": ""}]

        유사상권_리스트 = []
        try:
            df_sim = load_simple_sheet("O4O")
            store_sim_df = df_sim[df_sim['점포명'] == store_name]
            sim_col = next((c for c in store_sim_df.columns if '상품' in str(c) or '품목' in str(c)), store_sim_df.columns[1])
            유사상권_리스트 = store_sim_df[sim_col].astype(str).tolist()[:3]
        except:
            유사상권_리스트 = ["O4O 시트 연결 필요"]

        return {
            "총매출_25평균": int(avg_total_25), "총매출_26평균": int(avg_total_26), "총매출_26년5월": int(val_total_2605),
            "치킨_25평균": int(avg_chk_25), "치킨_26평균": int(avg_chk_26), "치킨_26년5월": int(val_chk_2605),
            "운영율": 85.0, "판매율": 92.0,
            "시간": 시간, "객수": 객수,
            "품목명": 품목명, "품목매출": 품목매출,
            "프로모션": 프로모션_리스트, 
            "유사상권_베스트": 유사상권_리스트, 
            "is_mock": False
        }
    except Exception as e:
        print(f"⚠️ 에러 발생: {e}")
        return {"is_mock": True, "에러내용": str(e)}

# ── 5. UI 렌더링 ───────────────────────────────────────────
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
    st.error(f"⚠️ 시스템 오류가 발생했습니다. 담당자에게 문의하세요. ({data.get('에러내용')})")
    st.stop()

def calc_growth(v25, v26):
    if v25 == 0: return 0
    return ((v26 - v25) / v25) * 100

total_growth = calc_growth(data["총매출_25평균"], data["총매출_26평균"])
chicken_growth = calc_growth(data["치킨_25평균"], data["치킨_26평균"])

# ── 6. 대시보드 ─────────────────────────────────
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
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">치킨25 일매출 흐름 (YoY)</div>
        <div class="kpi-value">{data['치킨_26평균']//1000:,}천원</div>
        <div class="{'kpi-delta-pos' if chicken_growth > 0 else 'kpi-delta-neg'}">{'▲' if chicken_growth > 0 else '▼'} {abs(chicken_growth):.1f}%</div>
        <div class="divider"></div>
        <div style="font-size:0.95rem;"><b>'26년 5월:</b> {data['치킨_26년5월']//1000:,}천원</div>
        <div class="sub-note">*산정기준: 25년/26년 월별 평균 비교</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""<div class="kpi-card"><div class="kpi-label">튀김기 운영율</div>
    <div class="kpi-value">{data['운영율']:.1f}%</div>
    <div class="sub-note">목표: 85% 이상 유지</div></div>""", unsafe_allow_html=True)

with c4:
    st.markdown(f"""<div class="kpi-card"><div class="kpi-label">치킨 판매율</div>
    <div class="kpi-value">{data['판매율']:.1f}%</div>
    <div class="sub-note">기준: 튀긴 수량 대비 판매량</div></div>""", unsafe_allow_html=True)

col_left, col_right = st.columns([1.2, 1])

with col_left:
    st.markdown('<div class="section-title">⏱️ 시간대별 방문객 및 조리 타이밍</div>', unsafe_allow_html=True)
    if data["객수"] and sum(data["객수"]) > 0:
        max_idx = np.argmax(data["객수"])
        peak_hour_1 = int(data["시간"][max_idx])
        
        fig_time = go.Figure()
        colors = ['#FFC300' if i == max_idx else '#EAEAEA' for i in range(len(data["시간"]))]
        fig_time.add_trace(go.Bar(x=[f"{int(h):02d}시" for h in data["시간"]], y=data["객수"], marker_color=colors, text=data["객수"], textposition='outside'))
        fig_time.update_layout(plot_bgcolor='white', height=300, margin=dict(t=10, b=20, l=10, r=10), xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#F5F5F5'))
        st.plotly_chart(fig_time, use_container_width=True)
        st.markdown(f'<div class="highlight-box">👨‍🍳 <b>AI 조리 지시서:</b> {peak_hour_1}시에 가장 붐빕니다. {peak_hour_1 - 1}시 30분부터 선조리를 시작하세요!</div>', unsafe_allow_html=True)
    else:
        st.warning("데이터가 없습니다. `time` 시트를 확인해주세요.")

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
        st.warning("데이터가 없습니다. `units` 시트를 확인해주세요.")

st.markdown('<div class="section-title">✨ 점포 맞춤형 프로모션 & 유사상권 인사이트</div>', unsafe_allow_html=True)
col_promo, col_sim = st.columns(2)

with col_promo:
    st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
    st.markdown("#### 🎁 현재 적용 가능한 프로모션")
    st.markdown("<div class='sub-note' style='margin-bottom:10px;'>구글 시트 promotion 탭 연동</div>", unsafe_allow_html=True)
    
    for p in data["프로모션"]:
        st.markdown(f"<div class='promo-item'>✔️ <b>{p['행사명']}</b> <br><span style='color:#555; font-size:0.9rem;'>{p['내용']}</span></div>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col_sim:
    st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
    st.markdown("#### 🏪 유사상권 베스트 상품 Top 3")
    st.markdown("<div class='sub-note' style='margin-bottom:10px;'>구글 시트 O4O 탭 연동</div>", unsafe_allow_html=True)
    
    for idx, item in enumerate(data["유사상권_베스트"]):
        st.markdown(f"<div class='promo-item'><b>{idx+1}위.</b> {item}</div>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
