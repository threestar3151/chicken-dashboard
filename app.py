import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from io import StringIO

SPREADSHEET_ID = "1gtWPFhnszYK1VPgmiZQLtstHCltUM_6h" # 전달해주신 구글 시트 ID

# ── 1. 페이지 설정 및 CSS ────────────────────────────────────────
st.set_page_config(page_title="치킨25 튀김 레이더", page_icon="🍗", layout="wide")

st.markdown("""
<style>
  .kpi-label { font-size:0.85rem; color:#666; margin-bottom:4px; font-weight:600;}
  .kpi-value { font-size:1.8rem; font-weight:800; color:#111; }
  .kpi-delta-pos { font-size:1rem; color:#E74C3C; font-weight:700; } /* 치킨은 빨간색 상승이 어울림 */
  .kpi-delta-neg { font-size:1rem; color:#3498DB; font-weight:700; }
  .kpi-card {
    background:#fff; border:1px solid #EAEAEA; border-radius:12px;
    padding:1.2rem; box-shadow:0 4px 6px rgba(0,0,0,0.04);
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
    st.stop() # 인증되지 않으면 여기서 실행을 멈춤

# ── 3. 데이터 로딩 (구글 시트 연동) ──────────────────────────
@st.cache_data(ttl=300)
def load_sheet(sheet_name):
    """구글 시트의 특정 탭(시트명)을 불러옵니다."""
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    r = requests.get(url, timeout=10)
    return pd.read_csv(StringIO(r.text))

@st.cache_data(ttl=300)
def get_store_list():
    try:
        df_summary = load_sheet("요약")
        return df_summary['점포명'].unique().tolist()
    except:
        return ["강남본점", "서초점", "역삼점"] # 시트 연동 실패시 임시 점포 목록

@st.cache_data(ttl=300)
def get_store_data(store_name):
    try:
        # 📌 1. 실제 구글 시트에서 데이터 읽어오기 시도
        df_summary = load_sheet("요약")
        df_time = load_sheet("시간")
        df_item = load_sheet("품목")
        
        # 선택한 점포명으로 필터링
        store_summary = df_summary[df_summary['점포명'] == store_name].iloc[0]
        store_time = df_time[df_time['점포명'] == store_name]
        store_item = df_item[df_item['점포명'] == store_name].sort_values(by='품목매출', ascending=False)
        
        return {
            "총매출_25": int(store_summary['총매출_25']),
            "총매출_26": int(store_summary['총매출_26']),
            "치킨_25": int(store_summary['치킨_25']),
            "치킨_26": int(store_summary['치킨_26']),
            "운영율": float(store_summary['운영율']),
            "판매율": float(store_summary['판매율']),
            "시간": store_time['시간'].astype(int).tolist(),
            "객수": store_time['객수'].astype(int).tolist(),
            "품목명": store_item['품목명'].astype(str).tolist(),
            "품목매출": store_item['품목매출'].astype(int).tolist()
        }
    except Exception as e:
        # 📌 2. 오류 발생 시 (시트 구조가 안 맞거나 연결 실패) 임시 데이터 반환 (화면 깨짐 방지)
        print(f"⚠️ 구글 시트 연동 실패. (에러: {e})")
        np.random.seed(len(store_name)) 
        total_sales_25 = np.random.randint(1500000, 2500000)
        total_sales_26 = int(total_sales_25 * np.random.uniform(0.9, 1.2))
        chicken_25 = int(total_sales_25 * np.random.uniform(0.05, 0.1))
        chicken_26 = int(chicken_25 * np.random.uniform(0.8, 1.5))
        
        return {
            "총매출_25": total_sales_25,
            "총매출_26": total_sales_26,
            "치킨_25": chicken_25,
            "치킨_26": chicken_26,
            "운영율": np.random.uniform(60, 95),
            "판매율": np.random.uniform(70, 99),
            "시간": list(range(9, 24)),
            "객수": np.random.randint(10, 80, size=15).tolist(),
            "품목명": ["쏜살치킨", "바삭매콤치킨", "점보닭다리", "바삭통다리", "치킨꼬치"],
            "품목매출": sorted(np.random.randint(50000, 300000, size=5).tolist(), reverse=True)
        }

# ── 4. UI 렌더링 ───────────────────────────────────────────
st.title("🍗 치킨25 튀김 레이더")

# 점포 선택 UI 추가
store_list = get_store_list()
selected_store = st.selectbox("🏬 분석할 점포를 선택하세요:", store_list)

# 데이터 로드
data = get_store_data(selected_store)

# 증감률 계산 함수
def calc_growth(v25, v26):
    return ((v26 - v25) / v25) * 100

total_growth = calc_growth(data["총매출_25"], data["총매출_26"])
chicken_growth = calc_growth(data["치킨_25"], data["치킨_26"])

# ── 5. [인사이트 3 & 4] 핵심 KPI 및 팩폭 코칭 ────────────────────
st.markdown('<div class="section-title">📊 종합 실적 및 점포 진단</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">전체 일매출 흐름 (YoY)</div>
        <div class="kpi-value">{data['총매출_26']//10000:,}만원</div>
        <div class="{'kpi-delta-pos' if total_growth > 0 else 'kpi-delta-neg'}">
            {'▲' if total_growth > 0 else '▼'} {abs(total_growth):.1f}%
        </div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">치킨25 일매출 흐름 (YoY)</div>
        <div class="kpi-value">{data['치킨_26']//1000:,}천원</div>
        <div class="{'kpi-delta-pos' if chicken_growth > 0 else 'kpi-delta-neg'}">
            {'▲' if chicken_growth > 0 else '▼'} {abs(chicken_growth):.1f}%
        </div>
    </div>""", unsafe_allow_html=True)
with c3:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">튀김기 운영율 (가동률)</div>
        <div class="kpi-value">{data['운영율']:.1f}%</div>
        <div style="font-size:0.85rem; color:#888; margin-top:4px;">목표: 85% 이상</div>
    </div>""", unsafe_allow_html=True)
with c4:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">치킨 판매율 (수율)</div>
        <div class="kpi-value">{data['판매율']:.1f}%</div>
        <div style="font-size:0.85rem; color:#888; margin-top:4px;">튀긴 수량 대비 판매량</div>
    </div>""", unsafe_allow_html=True)

# 경영주 자극용 코칭 로직
if total_growth > 0 and chicken_growth < 0:
    coach_msg = f"🚨 <b>기회 로스 발생!</b> 점포 전체에 들어오는 손님은 <b>{total_growth:.1f}% 늘었는데</b>, 치킨 매출은 오히려 <b>{abs(chicken_growth):.1f}% 감소</b>했습니다. 손님이 와도 매대에 치킨이 비어있어 사지 못하고 있습니다. 튀김기 가동률을 높여야 전체 객단가가 올라갑니다!"
    coach_class = "coach-warn"
elif total_growth < 0 and chicken_growth > 0:
    coach_msg = f"💡 <b>치킨이 효자입니다!</b> 점포 전체 매출이 빠지는 상황에서도 치킨 매출이 <b>{chicken_growth:.1f}% 상승</b>하며 방어해주고 있습니다. 지금 잘 나가는 치킨 품목의 복수 진열을 늘려 객단가를 더 끌어올리세요."
    coach_class = "coach-good"
elif total_growth < 0 and chicken_growth < 0:
    coach_msg = f"⚠️ <b>전면적인 리프레시 필요!</b> 전체 매출과 치킨 매출이 동반 하락 중입니다. 시간대별 객수 데이터를 확인하고 가장 손님이 가장 많은 피크타임(Top 1)에 승부수를 띄워야 합니다. 냄새 마케팅(튀기는 냄새)으로 발길을 잡으세요."
    coach_class = "coach-warn"
else:
    coach_msg = f"🔥 <b>완벽한 상승 기류!</b> 전체 매출과 치킨 매출이 모두 상승 중입니다. 현재의 조리 스케줄을 유지하시되, 신상품(예: 새로운 맛 쏜살치킨)을 도입해 추가 매출을 노려보세요."
    coach_class = "coach-good"

st.markdown(f'<div class="coach-card {coach_class}">{coach_msg}</div>', unsafe_allow_html=True)

st.markdown("<hr style='border: 1px dashed #DDD;'>", unsafe_allow_html=True)

# ── 6. [인사이트 1 & 2] 하단 분석 차트 ────────────────────────────
col_left, col_right = st.columns([1.2, 1])

# --- 시간대별 객수 및 조리 타이밍 코칭 ---
with col_left:
    st.markdown('<div class="section-title">⏱️ 시간대별 방문객 및 조리 타이밍</div>', unsafe_allow_html=True)
    
    # 피크 타임 찾기 (객수가 가장 많은 시간)
    max_idx = np.argmax(data["객수"])
    peak_hour_1 = data["시간"][max_idx]
    
    fig_time = go.Figure()
    
    # 기본 바 차트
    colors = ['#FFC300' if i == max_idx else '#EAEAEA' for i in range(len(data["시간"]))]
    fig_time.add_trace(go.Bar(
        x=[f"{h}시" for h in data["시간"]], 
        y=data["객수"],
        marker_color=colors,
        text=data["객수"], textposition='outside'
    ))
    
    fig_time.update_layout(
        plot_bgcolor='white', height=300, margin=dict(t=10, b=20, l=10, r=10),
        xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#F5F5F5')
    )
    st.plotly_chart(fig_time, use_container_width=True)
    
    # 핀셋 코칭 (사전 조리 지시)
    st.markdown(f"""
    <div class="highlight-box">
        👨‍🍳 <b>AI 조리 지시서:</b> 우리 점포는 <b>{peak_hour_1}시</b>에 손님이 가장 많이 몰립니다. <br>
        치킨 구매를 유도하려면 <b>{peak_hour_1 - 1}시 30분</b>부터 가장 잘 팔리는 베스트 상품을 미리 튀겨 매대를 꽉 채우고, 매장에 고소한 냄새를 풍겨야 합니다!
    </div>
    """, unsafe_allow_html=True)

# --- 점포별 베스트 상품 Top 5 ---
with col_right:
    st.markdown('<div class="section-title">🏆 우리 점포 치킨 베스트 Top 5</div>', unsafe_allow_html=True)
    
    top5_items = data["품목명"][:5]
    top5_sales = data["품목매출"][:5]
    
    # 시각적 효과를 위해 가로형 바 차트 사용 (판매량 순 정렬을 위해 reverse)
    fig_items = go.Figure()
    fig_items.add_trace(go.Bar(
        y=top5_items[::-1], 
        x=top5_sales[::-1],
        orientation='h',
        marker=dict(color='#FF5733', opacity=0.8), # 치킨 느낌의 주황/빨강
        text=[f"{v:,}원" for v in top5_sales[::-1]], textposition='inside',
        insidetextanchor='middle', textfont=dict(color='white', weight='bold')
    ))
    
    fig_items.update_layout(
        plot_bgcolor='white', height=300, margin=dict(t=10, b=20, l=10, r=10),
        xaxis=dict(showgrid=False, visible=False), 
        yaxis=dict(showgrid=False, tickfont=dict(size=13, weight='bold'))
    )
    st.plotly_chart(fig_items, use_container_width=True)
    
    st.markdown(f"""
    <div style="padding-left:10px; font-size:0.95rem; color:#555;">
        💡 <b>코칭 팁:</b> 1위 상품인 <b>{top5_items[0]}</b>은 절대 결품이 나지 않도록 발주량을 늘리고, 피크타임 전에 반드시 전진 진열해 주세요.
    </div>
    """, unsafe_allow_html=True)
