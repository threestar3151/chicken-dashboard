import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from io import StringIO
import random

SPREADSHEET_ID = "1gtWPFhnszYK1VPgmiZQLtstHCltUM_6h" # 전달해주신 구글 시트 ID

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

# ── 2. 비밀번호 인증 로직 ───────────────────────────────────────────
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

# ── 3. 데이터 로딩 (구글 시트 연동) ──────────────────────────
@st.cache_data(ttl=300)
def load_sheet(sheet_name):
    """구글 시트의 특정 탭(시트명)을 불러옵니다."""
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    r = requests.get(url, timeout=10)
    if r.status_code != 200 or "html" in r.text.lower():
        raise ValueError(f"시트 '{sheet_name}'를 찾을 수 없거나 권한이 없습니다.")
    df = pd.read_csv(StringIO(r.text))
    df.columns = df.columns.str.strip() # 헤더의 불필요한 공백 제거 (에러 방지)
    return df

@st.cache_data(ttl=300)
def get_part_store_mapping():
    try:
        df_summary = load_sheet("SALES") # 요약 -> SALES 탭으로 변경
        # 파트 데이터가 없다면 임시로 점포명 기준 생성
        if '파트' in df_summary.columns:
            mapping = df_summary.groupby('파트')['점포명'].unique().apply(list).to_dict()
        else:
            mapping = {"전체 점포": df_summary['점포명'].dropna().unique().tolist()}
        return mapping
    except Exception:
        return {"테스트파트": ["강남본점", "홍대점"]}

@st.cache_data(ttl=300)
def get_store_data(store_name):
    try:
        # 실제 탭 이름으로 로드
        df_sales = load_sheet("SALES")
        df_time = load_sheet("time")
        df_item = load_sheet("units")
        
        # 추가 데이터 로드 (시트가 없을 경우 예외처리)
        try:
            df_promo = load_sheet("promotion")
            store_promo = df_promo[df_promo['점포명'] == store_name].to_dict('records')
            if not store_promo:
                store_promo = [{"행사명": "점포 특화 프로모션", "내용": "데이터가 없습니다."}]
        except:
            store_promo = [{"행사명": "임시 행사", "내용": "promotion 시트를 확인해주세요."}]
            
        try:
            df_similar = load_sheet("O4O") # 유사상권 -> O4O 탭
            # 상품명 또는 유사한 열 찾기
            item_col = '상품명' if '상품명' in df_similar.columns else df_similar.columns[1]
            similar_items = df_similar[df_similar['점포명'] == store_name][item_col].tolist()[:3]
            if not similar_items:
                similar_items = ["데이터 없음"]
        except:
            similar_items = ["임시 상품 1", "임시 상품 2", "임시 상품 3"]

        # 점포 필터링
        store_sales = df_sales[df_sales['점포명'] == store_name].iloc[0]
        
        # ── 스마트 데이터 추출 (평균 계산) ──
        # '전체' 매출 컬럼 찾기
        total_25_cols = [c for c in df_sales.columns if '2025' in c and '전체' in c]
        total_26_cols = [c for c in df_sales.columns if '2026' in c and '전체' in c]
        total_2605_col = [c for c in df_sales.columns if '202605' in c and '전체' in c]
        
        # '치킨' 매출 컬럼 찾기
        chk_25_cols = [c for c in df_sales.columns if '2025' in c and '치킨' in c]
        chk_26_cols = [c for c in df_sales.columns if '2026' in c and '치킨' in c]
        chk_2605_col = [c for c in df_sales.columns if '202605' in c and '치킨' in c]

        # 데이터가 있으면 계산, 없으면 임의의 값(오류 방지용)
        avg_total_25 = store_sales[total_25_cols].mean() if total_25_cols else 2000000
        avg_total_26 = store_sales[total_26_cols].mean() if total_26_cols else 2200000
        val_total_2605 = store_sales[total_2605_col[0]] if total_2605_col else avg_total_26

        avg_chk_25 = store_sales[chk_25_cols].mean() if chk_25_cols else 150000
        avg_chk_26 = store_sales[chk_26_cols].mean() if chk_26_cols else 160000
        val_chk_2605 = store_sales[chk_2605_col[0]] if chk_2605_col else avg_chk_26

        # 운영율/판매율 열 처리
        op_col = [c for c in df_sales.columns if '운영' in c]
        sales_col = [c for c in df_sales.columns if '판매' in c]
        운영율 = float(store_sales[op_col[0]]) if op_col else 85.0
        판매율 = float(store_sales[sales_col[0]]) if sales_col else 90.0

        # 시간/품목 데이터 필터링 (컬럼명이 다를 수 있어 유연하게 처리)
        time_data = df_time[df_time['점포명'] == store_name] if not df_time.empty else pd.DataFrame()
        item_data = df_item[df_item['점포명'] == store_name] if not df_item.empty else pd.DataFrame()
        
        return {
            "총매출_25평균": int(avg_total_25),
            "총매출_26평균": int(avg_total_26),
            "총매출_26년5월": int(val_total_2605),
            "치킨_25평균": int(avg_chk_25),
            "치킨_26평균": int(avg_chk_26),
            "치킨_26년5월": int(val_chk_2605),
            "운영율": 운영율,
            "판매율": 판매율,
            "시간": time_data.iloc[:, 1].astype(int).tolist() if len(time_data.columns)>1 else list(range(9,24)),
            "객수": time_data.iloc[:, 2].astype(int).tolist() if len(time_data.columns)>2 else np.random.randint(10,80,15).tolist(),
            "품목명": item_data.iloc[:, 1].astype(str).tolist() if len(item_data.columns)>1 else ["데이터 부족"],
            "품목매출": item_data.iloc[:, 2].astype(int).tolist() if len(item_data.columns)>2 else [10000],
            "프로모션": store_promo,
            "유사상권_베스트": similar_items,
            "is_mock": False
        }
    except Exception as e:
        print(f"⚠️ 구글 시트 연동 실패. (에러: {e})")
        # 📌 오류 발생 시 화면 구성을 보여주기 위한 임시 데이터
        random.seed(store_name) 
        mock_items = random.sample(["쏜살치킨", "바삭매콤", "점보닭다리", "바삭통다리", "치킨꼬치"], 5)
        return {
            "총매출_25평균": 2000000,
            "총매출_26평균": 2200000,
            "총매출_26년5월": 2300000,
            "치킨_25평균": 150000,
            "치킨_26평균": 180000,
            "치킨_26년5월": 190000,
            "운영율": 82.5,
            "판매율": 91.0,
            "시간": list(range(9, 24)),
            "객수": np.random.randint(10, 80, size=15).tolist(),
            "품목명": mock_items,
            "품목매출": sorted(np.random.randint(50000, 300000, size=5).tolist(), reverse=True),
            "프로모션": [{"행사명": "테스트 행사", "내용": "시트 오류로 임시 표시됨"}],
            "유사상권_베스트": ["치킨꼬치", "소떡소떡", "바삭통다리"],
            "is_mock": True
        }

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
    st.warning("⚠️ 시트 양식 매핑 오류로 테스트 데이터가 표시중입니다. 백그라운드 터미널 창의 에러 메시지를 확인해주세요.")

def calc_growth(v25, v26):
    if v25 == 0: return 0
    return ((v26 - v25) / v25) * 100

total_growth = calc_growth(data["총매출_25평균"], data["총매출_26평균"])
chicken_growth = calc_growth(data["치킨_25평균"], data["치킨_26평균"])

# ── 5. 핵심 KPI 및 팩폭 코칭 ─────────────────────────────────
st.markdown('<div class="section-title">📊 종합 실적 및 점포 진단</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">전체 일매출 흐름 (YoY)</div>
        <div class="kpi-value">{data['총매출_26평균']//10000:,}만원</div>
        <div class="{'kpi-delta-pos' if total_growth > 0 else 'kpi-delta-neg'}">{'▲' if total_growth > 0 else '▼'} {abs(total_growth):.1f}%</div>
        <div class="divider"></div>
        <div style="font-size:0.95rem; color:#333;"><b>'26년 5월:</b> {data['총매출_26년5월']//10000:,}만원</div>
        <div class="sub-note">*산정기준: 25년/26년 월별 평균 비교</div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">치킨25 일매출 흐름 (YoY)</div>
        <div class="kpi-value">{data['치킨_26평균']//1000:,}천원</div>
        <div class="{'kpi-delta-pos' if chicken_growth > 0 else 'kpi-delta-neg'}">{'▲' if chicken_growth > 0 else '▼'} {abs(chicken_growth):.1f}%</div>
        <div class="divider"></div>
        <div style="font-size:0.95rem; color:#333;"><b>'26년 5월:</b> {data['치킨_26년5월']//1000:,}천원</div>
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

if total_growth > 0 and chicken_growth < 0:
    coach_msg = f"🚨 <b>기회 로스 발생!</b> 전체 평균 매출은 <b>{total_growth:.1f}% 늘었는데</b>, 치킨 매출은 <b>{abs(chicken_growth):.1f}% 감소</b>. 매대 진열량을 늘리세요!"
    coach_class = "coach-warn"
elif total_growth < 0 and chicken_growth > 0:
    coach_msg = f"💡 <b>치킨이 효자입니다!</b> 전체 하락에도 치킨이 <b>{chicken_growth:.1f}% 상승</b>하며 방어 중입니다. 복수 진열을 강화하세요."
    coach_class = "coach-good"
elif total_growth < 0 and chicken_growth < 0:
    coach_msg = f"⚠️ <b>전면적인 리프레시 필요!</b> 매출 동반 하락 중입니다. 피크타임 냄새 마케팅으로 발길을 확실히 잡으세요."
    coach_class = "coach-warn"
else:
    coach_msg = f"🔥 <b>완벽한 상승 기류!</b> 매출 동반 상승 중입니다. 신상품을 도입해 추가 매출을 노려보세요."
    coach_class = "coach-good"

st.markdown(f'<div class="coach-card {coach_class}">{coach_msg}</div>', unsafe_allow_html=True)
st.markdown("<hr style='border: 1px dashed #DDD;'>", unsafe_allow_html=True)

# ── 6. 기존 차트 영역 ──────────────────────────────────────────
col_left, col_right = st.columns([1.2, 1])

with col_left:
    st.markdown('<div class="section-title">⏱️ 시간대별 조리 타이밍</div>', unsafe_allow_html=True)
    max_idx = np.argmax(data["객수"])
    peak_hour_1 = data["시간"][max_idx]
    
    fig_time = go.Figure()
    colors = ['#FFC300' if i == max_idx else '#EAEAEA' for i in range(len(data["시간"]))]
    fig_time.add_trace(go.Bar(x=[f"{h}시" for h in data["시간"]], y=data["객수"], marker_color=colors, text=data["객수"], textposition='outside'))
    fig_time.update_layout(plot_bgcolor='white', height=300, margin=dict(t=10, b=20, l=10, r=10), xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#F5F5F5'))
    st.plotly_chart(fig_time, use_container_width=True)
    
    st.markdown(f'<div class="highlight-box">👨‍🍳 <b>AI 조리 지시서:</b> {peak_hour_1}시에 가장 붐빕니다. {peak_hour_1 - 1}시 30분부터 선조리를 시작하세요!</div>', unsafe_allow_html=True)

with col_right:
    st.markdown('<div class="section-title">🏆 점포 치킨 베스트 Top 5</div>', unsafe_allow_html=True)
    top5_items = data["품목명"][:5]
    top5_sales = data["품목매출"][:5]
    
    fig_items = go.Figure()
    fig_items.add_trace(go.Bar(y=top5_items[::-1], x=top5_sales[::-1], orientation='h', marker=dict(color='#FF5733', opacity=0.8), text=[f"일매출 {v:,}원" for v in top5_sales[::-1]], textposition='inside', insidetextanchor='middle', textfont=dict(color='white', weight='bold')))
    fig_items.update_layout(plot_bgcolor='white', height=300, margin=dict(t=10, b=20, l=10, r=10), xaxis=dict(showgrid=False, visible=False), yaxis=dict(showgrid=False, tickfont=dict(size=13, weight='bold')))
    st.plotly_chart(fig_items, use_container_width=True)

# ── 7. 프로모션 & 유사상권 인사이트 ─────────────────────
st.markdown('<div class="section-title">✨ 점포 맞춤형 프로모션 & 유사상권 인사이트</div>', unsafe_allow_html=True)
col_promo, col_sim = st.columns(2)

with col_promo:
    st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
    st.markdown("#### 🎁 현재 적용 가능한 프로모션")
    st.markdown("<div class='sub-note' style='margin-bottom:10px;'>구글 시트 'promotion' 탭 연동 데이터</div>", unsafe_allow_html=True)
    
    for p in data["프로모션"]:
        행사명 = p.get('행사명', '행사명 없음')
        내용 = p.get('내용', '')
        st.markdown(f"<div class='promo-item'>✔️ <b>{행사명}</b> <br><span style='color:#555; font-size:0.9rem;'>{내용}</span></div>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col_sim:
    st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
    st.markdown("#### 🏪 유사상권 베스트 상품 Top 3")
    st.markdown("<div class='sub-note' style='margin-bottom:10px;'>비슷한 상권에서 잘 팔리는 상품 (O4O 탭 연동)</div>", unsafe_allow_html=True)
    
    for idx, item in enumerate(data["유사상권_베스트"]):
        st.markdown(f"<div class='promo-item'><b>{idx+1}위.</b> {item}</div>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
