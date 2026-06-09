import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from io import StringIO
import re

SPREADSHEET_ID = "1gtWPFhnszYK1VPgmiZQLtstHCltUM_6h"

# ── 1. 페이지 설정 및 CSS ────────────────────────────────────────
st.set_page_config(page_title="치킨25 튀김 레이더", page_icon="🍗", layout="wide")

st.markdown("""
<style>
  .kpi-label { font-size:0.85rem; color:#666; margin-bottom:4px; font-weight:600;}
  .kpi-value { font-size:1.8rem; font-weight:800; color:#111; }
  .kpi-delta-pos { font-size:1rem; color:#E74C3C; font-weight:700; } 
  .kpi-delta-neg { font-size:1rem; color:#3498DB; font-weight:700; }
  .kpi-card { background:#fff; border:1px solid #EAEAEA; border-radius:12px; padding:1.2rem; box-shadow:0 4px 6px rgba(0,0,0,0.04); height: 100%; }
  .coach-card { border-radius:12px; padding:1.5rem; margin:1rem 0; }
  .coach-warn { background:#FFF3F3; border-left:6px solid #E74C3C; }
  .coach-good { background:#F0FFF4; border-left:6px solid #2ECC71; }
  .highlight-box { background:linear-gradient(90deg,#FFF9E6,#FFFDF5); border:1px solid #F0C040; border-radius:8px; padding:1rem; font-size:1rem; }
  .section-title { font-size:1.3rem; font-weight:800; margin-top:2rem; margin-bottom:1rem; color:#2C3E50; }
  .promo-item { font-size:1rem; color:#333; margin-bottom:0.5rem; line-height:1.4;}
  .sub-note { font-size:0.75rem; color:#888; margin-top:4px; }
  .divider { margin: 10px 0; border: 0.5px solid #eee; }
</style>
""", unsafe_allow_html=True)

# ── 2. 비밀번호 인증 ───────────────────────────────────────────
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if not st.session_state.authenticated:
    st.title("🔒 치킨25 튀김 레이더 시스템")
    st.markdown("보안을 위해 비밀번호를 입력해주세요.")
    pwd = st.text_input("비밀번호", type="password")
    if st.button("접속하기"):
        if pwd == "gs25": st.session_state.authenticated = True; st.rerun()
        else: st.error("비밀번호가 틀렸습니다.")
    st.stop()

# ── 3. 만능 시트 로딩 엔진 (모든 탭에 적용) ──────────────────────────
@st.cache_data(ttl=300)
def load_universal_sheet(sheet_name):
    """모든 시트의 복잡한 병합셀과 헤더를 똑똑하게 하나로 합쳐주는 만능 엔진"""
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    r = requests.get(url, timeout=10)
    df = pd.read_csv(StringIO(r.text), header=None, dtype=str)
    
    # '점포명'이 있는 진짜 기준 행 찾기
    header_idx = next((i for i in range(min(15, len(df))) if '점포명' in df.iloc[i].fillna('').values), -1)
    
    if header_idx != -1:
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
        else:
            df.columns = df.iloc[0]
        df = df.iloc[header_idx + 1:].dropna(how='all').reset_index(drop=True)
    return df

def clean_num(val):
    try: return float(str(val).replace(',', '').strip())
    except: return 0.0

@st.cache_data(ttl=300)
def get_part_store_mapping():
    df_sales = load_universal_sheet("SALES")
    part_col = next((c for c in df_sales.columns if '파트' in c), None)
    store_col = next((c for c in df_sales.columns if '점포명' in c), None)
    if part_col and store_col:
        valid_df = df_sales.dropna(subset=[part_col, store_col])
        return valid_df.groupby(part_col)[store_col].unique().apply(list).to_dict()
    return {"전체": ["데이터없음"]}

@st.cache_data(ttl=300)
def get_store_data(store_name):
    # --- 1. SALES ---
    df_sales = load_universal_sheet("SALES")
    store_col = next(c for c in df_sales.columns if '점포명' in c)
    store_sales = df_sales[df_sales[store_col] == store_name].iloc[0]
    
    t25_cols = [c for c in df_sales.columns if '2025' in c and '전체'
