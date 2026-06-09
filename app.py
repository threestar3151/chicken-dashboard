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
        raise ValueError(f"시트 '{sheet_name}'를 찾을 수 없거나 접근 권한이 없습니다.")
    return pd.read_csv(StringIO(r.text))

@st.cache_data(ttl=300)
def get_part_store_mapping():
    try:
        df_summary = load_sheet("요약")
        mapping = df_summary.groupby('파트')['점포명'].unique().apply(list).to_dict()
        return mapping
    except Exception:
        return {
            "강남파트": ["강남본점", "서초점", "역삼점"],
            "강북파트": ["홍대본점", "신촌점", "합정점"],
            "부산파트": ["서면점", "해운대점", "광안리점"]
        }

@st.cache_data(ttl=300)
def get_store_data(store_name):
    try:
        # 📌 1. 기존 필수 데이터 로드 시도
        df_summary = load_sheet("요약")
        df_time = load_sheet("시간")
        df_item = load_sheet("품목")
        
        # 📌 2. 신규 데이터 로드 (프로모션 및 유사상권)
        # 시트가 없을 경우를 대비해 예외처리 추가
        try:
            df_promo = load_sheet("promotion")
            # 선택된 점포에 맞는 프로모션만 필터링 후 딕셔너리로 변환
            store_promo = df_promo[df_promo['점포명'] == store_name].to_dict('records')
            if not store_promo:
                store_promo = [{"행사명": "전사 공통 프로모션", "내용": "현재 점포에 특화된 데이터가 없습니다."}]
        except:
            store_promo = [{"행사명": "치킨+콜라 콤보 (임시)", "내용": "구글 시트에 'promotion' 탭을 만들어주세요."}]
            
        try:
            df_similar = load_sheet("유사상권")
            similar_items = df_similar[df_similar['점포명'] == store_name]['상품명'].tolist()[:3]
            if not similar_items:
                similar_items = ["데이터 1", "데이터 2", "데이터 3"]
        except:
            similar_items = ["바삭통다리 (임시)", "치킨꼬치 (임시)", "소떡소떡 (임시)"]

        # 📌 3. 점포별 데이터 필터링
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
            "품목매출": store_item['품목매출'].astype(int).tolist(),
            "프로모션": store_promo,
            "유사상권_베스트": similar_items,
            "is_mock": False
        }
    except Exception as e:
        print(f"⚠️ 구글 시트 연동 실패. (에러: {e})")
        # 📌 4. 오류 발생 시 임시 데이터 생성 (UI 깨짐 방지용)
        all_items = ["쏜살치킨", "바삭매콤치킨", "점보닭다리", "바삭통다리", "치킨꼬치", "매콤순살꼬치", "바삭치즈볼", "한마리치킨(팩)", "안심텐더", "소떡소떡"]
        random.seed(store_name) 
        mock_items = random.sample(all_items, 5)
        similar_items_mock = random.sample(all_items, 3)
        
        np.random.seed(len(store_name)) 
        total_sales_25 = np.random.randint(1500000, 2500000)
        total_sales_26 = int(total_sales_25 * np.random.uniform(0.9, 1.2))
        chicken_25 = int(total_sales_25 * np.random.uniform(0.05, 0.1))
        chicken_26 = int(chicken_25 * np.random.uniform(0.8, 1.5))
        
        mock_promos = [
            {"행사명": "주말 쏜살치킨 1+1", "내용": "유사상권 대비 점포 매출 상승 효과 기대"},
            {"행사명": "맥주 4캔 + 튀김 세트할인", "내용": "객단가 15% 상승 타겟 목표"}
        ]
        
        return {
            "총매출_25": total_sales_25,
            "총매출_26": total_sales_26,
            "치킨_25": chicken_25,
            "치킨_26": chicken_26,
            "운영율": np.random.uniform(60, 95),
            "판매율": np.random.uniform(70, 99),
            "시간": list(range(9, 24)),
            "객수": np.random.randint(10, 80, size=15).tolist(),
            "품목명": mock_items,
            "품목매출": sorted(np.random.randint(50000, 300000, size=5).tolist(), reverse=True),
            "프로모션": mock_promos,
            "유사상권_베스트": similar_items_mock,
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
    st.warning("⚠️ 구글 시트 연동 구조 문제로 임시 테스트 데이터를 보여주고 있습니다. 시트 탭에 `요약`, `시간`, `품목`, `promotion`, `유사상권`이 잘 있는지 확인해주세요.")

def calc_growth(v25, v26):
    return ((v26 - v25) / v25) * 100

total_growth = calc_growth(data["총매출_25"], data["총매출_26"])
chicken_growth = calc_growth(data["치킨_25"], data["치킨_26"])

# ── 5. 핵심 KPI 및 팩폭 코칭 ─────────────────────────────────
st.markdown('<div class="section-title">📊 종합 실적 및 점포 진단</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"""<div class="kpi-card"><div class="kpi-label">전체 일매출 흐름 (YoY)</div>
    <div class="kpi-value">{data['총매출_26']//10000:,}만원</div>
    <div class="{'kpi-delta-pos' if total_growth > 0 else 'kpi-delta-neg'}">{'▲' if total_growth > 0 else '▼'} {abs(total_growth):.1f}%</div></div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div class="kpi-card"><div class="kpi-label">치킨25 일매출 (YoY)</div>
    <div class="kpi-value">{data['치킨_26']//1000:,}천원</div>
    <div class="{'kpi-delta-pos' if chicken_growth > 0 else 'kpi-delta-neg'}">{'▲' if chicken_growth > 0 else '▼'} {abs(chicken_growth):.1f}%</div></div>""", unsafe_allow_html=True)
with c3:
    st.markdown(f"""<div class="kpi-card"><div class="kpi-label">튀김기 운영율</div>
    <div class="kpi-value">{data['운영율']:.1f}%</div>
    <div style="font-size:0.85rem; color:#888; margin-top:4px;">목표: 85% 이상</div></div>""", unsafe_allow_html=True)
with c4:
    st.markdown(f"""<div class="kpi-card"><div class="kpi-label">치킨 판매율</div>
    <div class="kpi-value">{data['판매율']:.1f}%</div>
    <div style="font-size:0.85rem; color:#888; margin-top:4px;">튀긴 수량 대비 판매량</div></div>""", unsafe_allow_html=True)

if total_growth > 0 and chicken_growth < 0:
    coach_msg = f"🚨 <b>기회 로스 발생!</b> 점포 손님은 <b>{total_growth:.1f}% 늘었는데</b>, 치킨 매출은 <b>{abs(chicken_growth):.1f}% 감소</b>. 매대 진열량을 늘리세요!"
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

# ── 7. 신규 추가: 프로모션 & 유사상권 인사이트 ─────────────────────
st.markdown('<div class="section-title">✨ 점포 맞춤형 프로모션 & 유사상권 인사이트</div>', unsafe_allow_html=True)
col_promo, col_sim = st.columns(2)

with col_promo:
    st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
    st.markdown("#### 🎁 현재 적용 가능한 프로모션")
    st.markdown("<div style='color:#666; font-size:0.9rem; margin-bottom:10px;'>구글 시트 'promotion' 탭 연동 데이터</div>", unsafe_allow_html=True)
    
    for p in data["프로모션"]:
        행사명 = p.get('행사명', '행사명 없음')
        내용 = p.get('내용', '')
        st.markdown(f"<div class='promo-item'>✔️ <b>{행사명}</b> <br><span style='color:#555; font-size:0.9rem;'>{내용}</span></div>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col_sim:
    st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
    st.markdown("#### 🏪 유사상권 베스트 상품 Top 3")
    st.markdown("<div style='color:#666; font-size:0.9rem; margin-bottom:10px;'>비슷한 상권에서 잘 팔리는 상품 (미취급 시 발주 요망)</div>", unsafe_allow_html=True)
    
    for idx, item in enumerate(data["유사상권_베스트"]):
        st.markdown(f"<div class='promo-item'><b>{idx+1}위.</b> {item}</div>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
