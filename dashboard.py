# ======================================================================
# Part 9.6) Streamlit 대시보드 메인 (오늘/누적 승률)
# ======================================================================

DASHBOARD_CODE = '''
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from zoneinfo import ZoneInfo
import os

TZ = ZoneInfo("Asia/Seoul")

os.environ.setdefault("GS_CREDS_JSON", "/content/drive/MyDrive/kis_config/service_account.json")
os.environ.setdefault("GS_SHEET_ID", "1BTkOmjj-nMxKgPxCNFeRe2OTjch0pE9shPzTGjGFntI")

st.set_page_config(page_title="트레이딩 대시보드", page_icon="📊", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; }
    .stMetric { background-color: #F8F9FA; padding: 15px; border-radius: 10px; border: 1px solid #E9ECEF; }
    .stMetric label { font-size: 16px !important; font-weight: 600; color: #495057; }
    .stMetric [data-testid="stMetricValue"] { font-size: 28px !important; font-weight: 700; }
    h1, h2, h3 { color: #212529; }
    hr { margin: 30px 0; border: none; border-top: 2px solid #DEE2E6; }
</style>
""", unsafe_allow_html=True)

st.title("📊 실시간 트레이딩 대시보드")

col_time, col_refresh = st.columns([4, 1])
with col_time:
    now_kst = datetime.now(TZ)
    st.caption(f"🕐 마지막 업데이트: {now_kst.strftime('%Y년 %m월 %d일 %H:%M:%S')}")
with col_refresh:
    if st.button("🔄 새로고침", use_container_width=True):
        st.rerun()

import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path

GS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def get_gs_client():
    creds_json = os.environ.get("GS_CREDS_JSON")
    p = Path(creds_json)
    creds = Credentials.from_service_account_file(str(p), scopes=GS_SCOPES)
    return gspread.authorize(creds)

# ✅ 종목명 매핑
STOCK_NAMES = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "051910": "LG화학",
    "035420": "NAVER",
    "009150": "삼성전기",
    "373220": "LG에너지솔루션",
    "005380": "현대차",
    "352820": "하이브",
    "068270": "셀트리온",
    "003490": "대한항공",
    "450080": "에코프로머티",
    "024110": "기업은행",
    "034020": "두산에너빌리티",
    "066570": "LG전자",
    "000990": "DB하이텍",
    "006400": "삼성SDI",
    "042660": "한화오션",
    "108490": "로보티즈",
    "028260": "삼성물산",
    "307950": "현대오토에버",
    "005490": "포스코홀딩스",
    "012450": "한화에어로스페이스",
    "009540": "HD한국조선해양",
    "015760": "한국전력",
    "003670": "포스코퓨처엠",
}

def load_portfolio_direct():
    try:
        sheet_id = os.environ.get("GS_SHEET_ID")
        client = get_gs_client()
        sheet = client.open_by_key(sheet_id)
        ws = sheet.worksheet("portfolio")

        summary = {}
        summary_data = ws.get("A1:B8")
        for row in summary_data:
            if len(row) >= 2:
                summary[row[0]] = row[1]

        table_data = ws.get("A10:E100")

        if not table_data or len(table_data) < 2:
            return summary, []

        positions = []
        for row in table_data[1:]:
            if not row or len(row) < 5:
                continue

            ticker = str(row[0]).strip()
            if not ticker:
                continue

            try:
                qty = int(float(str(row[1]).replace(',', '').strip()))
            except:
                qty = 0

            try:
                avg = float(str(row[2]).replace(',', '').strip())
            except:
                avg = 0

            try:
                cost = float(str(row[3]).replace(',', '').strip())
            except:
                cost = 0

            try:
                weight = float(str(row[4]).replace(',', '').strip())
            except:
                weight = 0

            positions.append({
                'ticker': ticker,
                'qty': qty,
                'avg': avg,
                'cost': cost,
                'weight%': weight
            })

        return summary, positions

    except Exception as e:
        return {}, []

def load_history():
    try:
        sheet_id = os.environ.get("GS_SHEET_ID")
        client = get_gs_client()
        sheet = client.open_by_key(sheet_id)
        ws = sheet.worksheet("history")
        data = ws.get_all_values()

        if len(data) <= 1:
            return pd.DataFrame()

        df = pd.DataFrame(data[1:], columns=data[0])
        df = df[df['date'].astype(str).str.strip() != '']
        if df.empty:
            return pd.DataFrame()

        df['date'] = pd.to_datetime(df['date'], format='%Y%m%d', errors='coerce')

        numeric_cols = ['capital', 'invested', 'cash', 'realized_pnl', 'unrealized_pnl', 'total_pnl', 'positions', 'wins', 'losses']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df = df.dropna(subset=['date'])
        return df.sort_values('date')
    except:
        return pd.DataFrame()

def load_orders_today():
    try:
        sheet_id = os.environ.get("GS_SHEET_ID")
        client = get_gs_client()
        sheet = client.open_by_key(sheet_id)

        today_key = datetime.now(TZ).strftime("%Y%m%d")
        ws = sheet.worksheet(f"Order_{today_key}")
        data = ws.get_all_values()

        if len(data) <= 1:
            return pd.DataFrame()

        df = pd.DataFrame(data[1:], columns=data[0])
        df = df[df['ticker'].astype(str).str.strip() != '']

        if 'qty' in df.columns:
            df['qty'] = pd.to_numeric(df['qty'], errors='coerce').fillna(0)
        if 'price' in df.columns:
            df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0)

        return df
    except:
        return pd.DataFrame()

def load_signals_today():
    try:
        sheet_id = os.environ.get("GS_SHEET_ID")
        client = get_gs_client()
        sheet = client.open_by_key(sheet_id)

        today_key = datetime.now(TZ).strftime("%Y%m%d")
        ws = sheet.worksheet(f"Signal_{today_key}")
        data = ws.get_all_values()

        if len(data) <= 1:
            return pd.DataFrame()

        df = pd.DataFrame(data[1:], columns=data[0])
        return df
    except:
        return pd.DataFrame()

def calculate_stats(history_df, orders_df):
    stats = {
        'cumulative_rpnl': 0.0,
        'trading_days': 0,
        'avg_daily_pnl': 0.0,
        'cumulative_return_pct': 0.0,
        'total_trades': 0,
        'buy_count': 0,
        'sell_count': 0,
        'win_rate_today': 0.0,
        'wins_today': 0,
        'losses_today': 0,
        'win_rate_cumulative': 0.0,
        'wins_cumulative': 0,
        'losses_cumulative': 0,
    }

    if not history_df.empty:
        stats['cumulative_rpnl'] = float(history_df['realized_pnl'].sum())
        stats['trading_days'] = int(len(history_df))

        if stats['trading_days'] > 0:
            stats['avg_daily_pnl'] = stats['cumulative_rpnl'] / stats['trading_days']
            first_capital = float(history_df.iloc[0]['capital'])
            if first_capital > 0:
                stats['cumulative_return_pct'] = (stats['cumulative_rpnl'] / first_capital) * 100

        # ✅ 누적 승률 (History에서)
        if 'wins' in history_df.columns and 'losses' in history_df.columns:
            total_wins = int(history_df['wins'].sum())
            total_losses = int(history_df['losses'].sum())
            total = total_wins + total_losses

            if total > 0:
                stats['win_rate_cumulative'] = (total_wins / total) * 100
                stats['wins_cumulative'] = total_wins
                stats['losses_cumulative'] = total_losses

    if not orders_df.empty:
        stats['total_trades'] = len(orders_df)
        stats['buy_count'] = len(orders_df[orders_df['side'] == 'BUY'])
        stats['sell_count'] = len(orders_df[orders_df['side'] == 'SELL'])

        # ✅ 오늘 승률
        sell_orders = orders_df[orders_df['side'] == 'SELL'].copy()
        if not sell_orders.empty:
            def parse_rpnl(result_str):
                try:
                    if 'rpnl=' in str(result_str):
                        rpnl_part = str(result_str).split('rpnl=')[1]
                        return float(rpnl_part.replace(',', '').strip().split()[0])
                except:
                    return None
                return None

            sell_orders['rpnl'] = sell_orders['result'].apply(parse_rpnl)
            sell_orders = sell_orders.dropna(subset=['rpnl'])

            if not sell_orders.empty:
                wins = int((sell_orders['rpnl'] > 0).sum())
                losses = int((sell_orders['rpnl'] <= 0).sum())
                total = wins + losses

                if total > 0:
                    stats['win_rate_today'] = (wins / total) * 100
                    stats['wins_today'] = wins
                    stats['losses_today'] = losses

    return stats

def get_market_status():
    now = datetime.now(TZ)
    if now.weekday() >= 5:
        return "🔴 휴장 (주말)"
    open_time = now.replace(hour=9, minute=0, second=0)
    close_time = now.replace(hour=15, minute=30, second=0)
    if now < open_time:
        return "🟡 장 시작 전"
    elif now <= close_time:
        return "🟢 장중"
    else:
        return "🔴 장 마감"

def load_all_data():
    summary, positions_list = load_portfolio_direct()
    history_df = load_history()
    orders_df = load_orders_today()
    signals_df = load_signals_today()
    stats = calculate_stats(history_df, orders_df)
    return summary, positions_list, history_df, orders_df, signals_df, stats

try:
    summary, positions_list, history_df, orders_df, signals_df, stats = load_all_data()

    st.header("💰 자본 현황")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        capital = int(float(summary.get('CAPITAL', 0)))
        st.metric("총 자본", f"{capital:,}원")

    with col2:
        invested = int(float(summary.get('INVESTED_COST', 0)))
        alloc_pct = (invested / capital * 100) if capital > 0 else 0
        st.metric("투자금액", f"{invested:,}원", f"{alloc_pct:.1f}%")

    with col3:
        cash = int(float(summary.get('CASH', 0)))
        cash_pct = (cash / capital * 100) if capital > 0 else 0
        st.metric("현금", f"{cash:,}원", f"{cash_pct:.1f}%")

    with col4:
        st.metric("시장 상태", get_market_status())

    st.divider()

    st.header("📈 오늘의 손익")
    col1, col2, col3 = st.columns(3)

    with col1:
        rpnl = int(float(summary.get('REALIZED_PNL_TODAY', 0)))
        rpnl_pct = (rpnl / capital * 100) if capital > 0 else 0
        st.metric("실현손익", f"{rpnl:+,}원", f"{rpnl_pct:+.2f}%", delta_color="normal" if rpnl >= 0 else "inverse")

    with col2:
        upnl = int(float(summary.get('UNREALIZED_PNL', 0)))
        upnl_pct = (upnl / capital * 100) if capital > 0 else 0
        st.metric("미실현손익", f"{upnl:+,}원", f"{upnl_pct:+.2f}%", delta_color="normal" if upnl >= 0 else "inverse")

    with col3:
        total_pnl = rpnl + upnl
        total_pct = (total_pnl / capital * 100) if capital > 0 else 0
        st.metric("총 손익", f"{total_pnl:+,}원", f"{total_pct:+.2f}%", delta_color="normal" if total_pnl >= 0 else "inverse")

    st.divider()

    st.header("🎯 누적 성과")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("누적 실현손익", f"{int(stats.get('cumulative_rpnl', 0)):+,}원")

    with col2:
        st.metric("누적 수익률", f"{stats.get('cumulative_return_pct', 0):+.2f}%")

    with col3:
        trading_days = stats.get('trading_days', 0)
        avg_daily = int(stats.get('avg_daily_pnl', 0))
        st.metric("거래일 / 일평균", f"{trading_days}일", f"{avg_daily:+,}원/일")

    with col4:
        wr_today = stats.get('win_rate_today', 0)
        w_today = stats.get('wins_today', 0)
        l_today = stats.get('losses_today', 0)
        st.metric("오늘 승률", f"{wr_today:.1f}%", f"{w_today}승 {l_today}패")

    with col5:
        wr_cum = stats.get('win_rate_cumulative', 0)
        w_cum = stats.get('wins_cumulative', 0)
        l_cum = stats.get('losses_cumulative', 0)
        st.metric("누적 승률", f"{wr_cum:.1f}%", f"{w_cum}승 {l_cum}패")

    st.divider()

    st.header("🔥 오늘의 활동")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("📊 총 거래", f"{stats.get('total_trades', 0)}건")

    with col2:
        buy_count = stats.get('buy_count', 0)
        buy_amount = 0
        if not orders_df.empty:
            buy_orders = orders_df[orders_df['side'] == 'BUY']
            if not buy_orders.empty:
                buy_amount = int((buy_orders['qty'] * buy_orders['price']).sum())
        st.metric("✅ 매수", f"{buy_count}건", f"{buy_amount:,}원")

    with col3:
        sell_count = stats.get('sell_count', 0)
        sell_amount = 0
        if not orders_df.empty:
            sell_orders = orders_df[orders_df['side'] == 'SELL']
            if not sell_orders.empty:
                sell_amount = int((sell_orders['qty'] * sell_orders['price']).sum())
        st.metric("❌ 매도", f"{sell_count}건", f"{sell_amount:,}원")

    with col4:
        st.metric("📍 보유 종목", f"{int(float(summary.get('TICKERS', 0)))}개")

    st.divider()

    st.header("📍 보유 포지션")

    if positions_list:
        display_data = []

        for pos in positions_list:
            weight = pos['weight%']
            status = "🔴" if weight > 0.15 else "🟡" if weight > 0.10 else "🟢"

            # ✅ 종목명 추가
            ticker = pos['ticker']
            stock_name = STOCK_NAMES.get(ticker, "")
            if stock_name:
                display_name = f"{stock_name} ({ticker})"
            else:
                display_name = ticker

            display_data.append({
                '상태': status,
                '종목': display_name,
                '수량': pos['qty'],
                '평균단가': f"{int(pos['avg']):,}원" if pos['avg'] > 0 else "-",
                '투자금액': f"{int(pos['cost']):,}원" if pos['cost'] > 0 else "-",
                '비중(%)': f"{weight*100:.2f}"
            })

        st.dataframe(pd.DataFrame(display_data), use_container_width=True, hide_index=True, height=300)

        costs = [p['cost'] for p in positions_list if p['cost'] > 0]
        tickers = [p['ticker'] for p in positions_list if p['cost'] > 0]

        if costs:
            # ✅ 차트도 종목명으로
            ticker_labels = []
            for t in tickers:
                name = STOCK_NAMES.get(t, t)
                ticker_labels.append(name)

            fig = px.pie(values=costs, names=ticker_labels, title='포지션 비중 분포', hole=0.4, color_discrete_sequence=px.colors.qualitative.Set3)
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("💤 보유 포지션이 없거나 장 시작 전입니다")

    st.divider()

    st.header("⚠️ 리스크 알림")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔴 긴급")
        alert_count = sum(1 for p in positions_list if p['weight%'] > 0.15)
        for p in positions_list:
            if p['weight%'] > 0.15:
                st.warning(f"**{p['ticker']}**: 비중 {p['weight%']*100:.1f}% (한도 15% 초과)")
        if alert_count == 0:
            st.success("✅ 이상 없음")

    with col2:
        st.subheader("🟡 주의")
        alloc_used = (invested / capital) if capital > 0 else 0
        if alloc_used > 0.75:
            st.warning(f"⚠️ 총 투자율: {alloc_used*100:.1f}% (권장 70% 이하)")
        else:
            st.success("✅ 이상 없음")

    st.divider()

    st.header("📊 성과 차트")

    if not history_df.empty and len(history_df) > 1:
        fig = go.Figure()
        colors = ['#00C853' if x > 0 else '#D50000' for x in history_df['realized_pnl']]

        fig.add_trace(go.Bar(x=history_df['date'], y=history_df['realized_pnl'], marker_color=colors, hovertemplate='날짜: %{x}<br>손익: %{y:,.0f}원<extra></extra>'))
        fig.update_layout(title='일별 실현손익', height=400, plot_bgcolor='white', paper_bgcolor='white')
        st.plotly_chart(fig, use_container_width=True)

        history_df_copy = history_df.copy()
        history_df_copy['cumulative'] = history_df_copy['realized_pnl'].cumsum()

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=history_df_copy['date'], y=history_df_copy['cumulative'], mode='lines+markers', line=dict(color='#2196F3', width=3), fill='tozeroy', fillcolor='rgba(33, 150, 243, 0.1)'))
        fig2.update_layout(title='누적 실현손익 곡선', height=400, plot_bgcolor='white')
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("📊 거래 히스토리가 2일 이상 쌓이면 차트가 표시됩니다")

    st.divider()

    st.header("📡 실시간 이벤트")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📝 최근 주문 (10개)")
        if not orders_df.empty:
            for _, row in orders_df.tail(10).iloc[::-1].iterrows():
                side_icon = "🟢" if row['side'] == 'BUY' else "🔴"
                st.text(f"{side_icon} {row['ts']}")
                st.text(f"   {row['side']} {row['ticker']} {int(row['qty'])}주 @ {int(row['price']):,}원")
                st.text("")
        else:
            st.info("💤 오늘 주문 내역이 없습니다")

    with col2:
        st.subheader("📊 최근 신호 (10개)")
        if not signals_df.empty:
            for _, row in signals_df.tail(10).iloc[::-1].iterrows():
                icon = "🔵" if str(row['action']) == 'BUY' else "🔴" if str(row['action']) == 'SELL' else "⚪"
                st.text(f"{icon} {row['ts']}")
                st.text(f"   {row['action']} {row['ticker']}")
                st.text("")
        else:
            st.info("💤 오늘 신호 내역이 없습니다")

except Exception as e:
    st.error(f"❌ 오류: {e}")
    st.exception(e)

st.caption("⏰ 60초 자동 새로고침")
'''

with open('/tmp/dashboard_app.py', 'w', encoding='utf-8') as f:
    f.write(DASHBOARD_CODE)

print("✅ 대시보드 코드 생성 완료 (오늘/누적 승률)")
