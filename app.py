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
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    r = requests.get(url, timeout=10)
    if r.status_code != 200 or "html" in r.text.lower():
        raise ValueError(f"'{sheet_name}' 시트를 찾을 수 없습니다.")
    
    df = pd.read_csv(StringIO(r.text), header=None, dtype=str)
    
    header_idx = None
    for i in range(min(10, len(df))):
        if '점포명' in df.iloc[i].fillna('').values:
            header_idx = i
            break
            
    if header_idx is not None:
        if header_idx > 0:
            top_rows = df.iloc[0:header_idx].ffill(axis=1)
        else:
            top_rows = pd.DataFrame()
            
        new_cols = []
        for col_idx in range(len(df.columns)):
            base_name = str(df.iloc[header_idx, col_idx])
            if base_name == 'nan': base_name = f"Col_{col_idx}"
            
            prefixes = []
            for r_idx in range(len(top_rows)):
                val = str(top_rows.iloc[r_idx, col_idx])
                if val != 'nan' and val.strip() != '' and '*' not in val:
                    prefixes.append(val.strip())
            
            if prefixes:
                new_cols.append("_".join(prefixes) + "_" + base_name)
            else:
                new_cols.append(base_name)
                
        df.columns = new_cols
        df = df.iloc[header_idx + 1:].reset_index(drop=True)
    else:
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)
        
    return df

@st.cache_data(ttl=300)
def get_part_store_mapping():
    try:
        df_sales = load_sheet("SALES")
        part_col = next((c for c in df_sales.columns if '파트' in c), None)
        store_col = next((c for c in df_sales.columns if '점포명' in c), None)
        
        if part_col and store_col:
            valid_df = df_sales.dropna(subset=[part_col, store_col])
            mapping = valid_df.groupby(part_col)[store_col].unique().apply(list).to_dict()
            return mapping
        else:
            return {"전체 점포": df_sales[store_col].dropna().unique().tolist()} if store_col else {"테스트파트": ["데이터없음"]}
    except Exception as e:
        return {"시스템 파트": ["점포 로드 실패"]}

def clean_num(val):
    try:
        return float(str(val).replace(',', '').strip())
    except:
        return 0.0

@st.cache_data(ttl=300)
def get_store_data(store_name):
    try:
        # 1. SALES 데이터 처리
        df_sales = load_sheet("SALES")
        store_col = next(c for c in df_sales.columns if '점포명' in c)
        store_sales = df_sales[df_sales[store_col] == store_name].iloc[0]
        
        total_25_cols = [c for c in df_sales.columns if '2025' in c and '전체' in c]
        total_26_cols = [c for c in df_sales.columns if '2026' in c and '전체' in c]
        total_2605_cols = [c for c in df_sales.columns if '202605' in c and '전체' in c]
        
        chk_25_cols = [c for c in df_sales.columns if '2025' in c and '치킨' in c]
        chk_26_cols = [c for c in df_sales.columns if '2026' in c and '치킨' in c]
        chk_2605_cols = [c for c in df_sales.columns if '202605' in c and '치킨' in c]

        avg_total_25 = np.mean([clean_num(store_sales[c]) for c in total_25_cols]) if total_25_cols else 0
        avg_total_26 = np.mean([clean_num(store_sales[c]) for c in total_26_cols]) if total_26_cols else 0
        val_total_2605 = clean_num(store_sales[total_2605_cols[0]]) if total_2605_cols else 0

        avg_chk_25 = np.mean([clean_num(store_sales[c]) for c in chk_25_cols]) if chk_25_cols else 0
        avg_chk_26 = np.mean([clean_num(store_sales[c]) for c in chk_26_cols]) if chk_26_cols else 0
        val_chk_2605 = clean_num(store_sales[chk_2605_cols[0]]) if chk_2605_cols else 0

        운영율 = 85.0 
        판매율 = 92.0

        # 2. 품목(units) 데이터 처리 (위치 대신 이름으로 스마트 검색)
        try:
            df_item = load_sheet("units")
            u_store_col = next((c for c in df_item.columns if '점포명' in c), None)
            if u_store_col:
                store_item_df = df_item[df_item[u_store_col] == store_name]
                
                # '품목'이나 '상품' 단어가 들어간 열 찾기
                item_cols = [c for c in store_item_df.columns if '품목' in c or '상품' in c or '메뉴' in c]
                # '매출'이나 '금액' 단어가 들어간 열 찾기
                sales_cols = [c for c in store_item_df.columns if '매출' in c or '금액' in c or '수량' in c]
                
                if item_cols and sales_cols:
                    item_col = item_cols[0]
                    sales_col = sales_cols[0]
                    
                    store_item_df['clean_sales'] = store_item_df[sales_col].apply(clean_num)
                    store_item_df = store_item_df.sort_values(by='clean_sales', ascending=False)
                    품목명 = store_item_df[item_col].tolist()
                    품목매출 = store_item_df['clean_sales'].tolist()
                else:
                    품목명 = ["'품목명' 열을 시트에서 찾지 못했습니다"]
                    품목매출 = [0]
            else:
                품목명 = ["점포명 불일치"]
                품목매출 = [0]
        except:
            품목명 = ["데이터 부족"]
            품목매출 = [0]

        # 3. 시간(time) 데이터 처리 (위치 대신 이름으로 스마트 검색)
        try:
            df_time = load_sheet("time")
            t_store_col = next((c for c in df_time.columns if '점포명' in c), None)
            if t_store_col:
                store_time_df = df_time[df_time[t_store_col] == store_name]
                
                # '시간' 단어가 들어간 열 찾기
                time_cols = [c for c in store_time_df.columns if '시간' in c or '시각' in c]
                # '객수' 단어가 들어간 열 찾기
                customer_cols = [c for c in store_time_df.columns if '객수' in c or '방문' in c]
                
                if time_cols and customer_cols:
                    시간 = store_time_df[time_cols[0]].apply(clean_num).tolist()
                    객수 = store_time_df[customer_cols[0]].apply(clean_num).tolist()
                else:
                    시간 = []
                    객수 = []
            else:
                시간 = []
                객수 = []
        except:
            시간 = []
            객수 = []

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
        <div style="font-size:0.95rem;"><b>
