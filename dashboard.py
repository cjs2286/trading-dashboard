import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import gspread
from google.oauth2 import service_account

TZ = ZoneInfo("Asia/Seoul")

# ✅ Streamlit Cloud 환경 설정
GS_SHEET_ID = st.secrets["GS_SHEET_ID"]
GS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ===== Google Sheets 클라이언트 =====
@st.cache_resource
def get_gs_client():
    """Streamlit secrets에서 인증 정보 읽기"""
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=GS_SCOPES
    )
    return gspread.authorize(credentials)

# ===== 데이터 로드 함수들 =====
def load_portfolio():
    """portfolio 시트 읽기"""
    try:
        gc = get_gs_client()
        sh = gc.open_by_key(GS_SHEET_ID)
        ws = sh.worksheet("portfolio")
        
        # 10행부터 데이터 (1-9행은 요약 정보)
        data = ws.get_all_values()[9:]  # 10행부터
        
        if len(data) < 2:
            return pd.DataFrame()
        
        headers = data[0]  # 첫 행이 헤더
        df = pd.DataFrame(data[1:], columns=headers)
        
        # 숫자 변환
        for col in ["qty", "avg", "cost", "weight%"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # ticker를 symbol로 rename
        df = df.rename(columns={"ticker": "symbol", "qty": "quantity", "avg": "entry_price"})
        
        return df
    except Exception as e:
        st.error(f"포트폴리오 로드 실패: {e}")
        return pd.DataFrame()

def get_latest_sheet_name(prefix):
    """가장 최근 날짜의 시트 이름 찾기 (Alert_, Signal_, Order_)"""
    try:
        gc = get_gs_client()
        sh = gc.open_by_key(GS_SHEET_ID)
        
        # 모든 시트 이름 가져오기
        all_sheets = [ws.title for ws in sh.worksheets()]
        
        # prefix로 시작하는 시트들 필터링
        matching = [s for s in all_sheets if s.startswith(prefix)]
        
        if not matching:
            return None
        
        # 날짜 기준 정렬 (내림차순)
        matching.sort(reverse=True)
        return matching[0]
        
    except Exception as e:
        st.error(f"시트 이름 찾기 실패: {e}")
        return None

def load_orders():
    """Order_ 시트 읽기"""
    try:
        sheet_name = get_latest_sheet_name("Order_")
        if not sheet_name:
            return pd.DataFrame()
        
        gc = get_gs_client()
        sh = gc.open_by_key(GS_SHEET_ID)
        ws = sh.worksheet(sheet_name)
        
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty:
            for col in ["qty", "price"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            if "ts" in df.columns:
                df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
            
            # 컬럼명 통일
            df = df.rename(columns={"ticker": "symbol", "qty": "quantity"})
        
        return df
    except Exception as e:
        st.error(f"주문 내역 로드 실패: {e}")
        return pd.DataFrame()

def load_signals():
    """Signal_ 시트 읽기"""
    try:
        sheet_name = get_latest_sheet_name("Signal_")
        if not sheet_name:
            return pd.DataFrame()
        
        gc = get_gs_client()
        sh = gc.open_by_key(GS_SHEET_ID)
        ws = sh.worksheet(sheet_name)
        
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty:
            for col in ["close", "rsi", "trix", "trix_sig", "adx14", "ema20", "macd"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            if "ts" in df.columns:
                df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
            
            # 컬럼명 통일
            df = df.rename(columns={"ticker": "symbol", "close": "price"})
        
        return df
    except Exception as e:
        st.error(f"시그널 로드 실패: {e}")
        return pd.DataFrame()

def load_summary_info():
    """portfolio 시트 상단 요약 정보 읽기"""
    try:
        gc = get_gs_client()
        sh = gc.open_by_key(GS_SHEET_ID)
        ws = sh.worksheet("portfolio")
        
        # A1:B9 영역 읽기
        summary = ws.get("A1:B9")
        
        info = {}
        for row in summary:
            if len(row) >= 2:
                info[row[0]] = row[1]
        
        return info
    except Exception as e:
        st.error(f"요약 정보 로드 실패: {e}")
        return {}

# ===== 거래 내역 생성 (Order에서 계산) =====
def calculate_trades(orders_df):
    """Order 시트에서 거래 내역 계산"""
    if orders_df.empty:
        return pd.DataFrame()
    
    trades = []
    
    # 종목별로 그룹화
    for symbol in orders_df["symbol"].unique():
        symbol_orders = orders_df[orders_df["symbol"] == symbol].sort_values("ts")
        
        # BUY/SELL 매칭
        buys = symbol_orders[symbol_orders["side"] == "BUY"].copy()
        sells = symbol_orders[symbol_orders["side"] == "SELL"].copy()
        
        for _, sell in sells.iterrows():
            # 해당 SELL 이전의 BUY 찾기
            prior_buys = buys[buys["ts"] < sell["ts"]]
            
            if not prior_buys.empty:
                # 가장 최근 BUY
                buy = prior_buys.iloc[-1]
                
                profit_loss = (sell["price"] - buy["price"]) * sell["quantity"]
                profit_loss_pct = ((sell["price"] - buy["price"]) / buy["price"]) * 100
                
                trades.append({
                    "symbol": symbol,
                    "side": "SELL",
                    "quantity": sell["quantity"],
                    "entry_price": buy["price"],
                    "exit_price": sell["price"],
                    "profit_loss": profit_loss,
                    "profit_loss_pct": profit_loss_pct,
                    "entry_time": buy["ts"],
                    "exit_time": sell["ts"]
                })
    
    return pd.DataFrame(trades)

# ===== 메인 대시보드 =====
def main():
    st.set_page_config(page_title="트레이딩봇 대시보드", page_icon="📈", layout="wide")
    
    st.title("📈 암호화폐 트레이딩봇 대시보드")
    st.caption(f"최종 업데이트: {datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S KST')}")
    
    # 새로고침 버튼
    if st.button("🔄 새로고침"):
        st.cache_resource.clear()
        st.rerun()
    
    # 탭 구성
    tab1, tab2, tab3, tab4 = st.tabs(["📊 포트폴리오", "💰 요약 정보", "📉 거래 내역", "🎯 시그널"])
    
    # === 탭 1: 포트폴리오 ===
    with tab1:
        st.header("현재 포트폴리오")
        portfolio_df = load_portfolio()
        
        if not portfolio_df.empty:
            col1, col2, col3 = st.columns(3)
            
            total_cost = portfolio_df["cost"].sum() if "cost" in portfolio_df.columns else 0
            num_tickers = len(portfolio_df)
            
            col1.metric("총 투자금액", f"₩{total_cost:,.0f}")
            col2.metric("보유 종목 수", num_tickers)
            
            # 데이터 표시
            display_cols = ["symbol", "quantity", "entry_price", "cost"]
            if "weight%" in portfolio_df.columns:
                display_cols.append("weight%")
            
            st.dataframe(
                portfolio_df[display_cols],
                use_container_width=True
            )
        else:
            st.info("보유 중인 포지션이 없습니다.")
    
    # === 탭 2: 요약 정보 ===
    with tab2:
        st.header("계좌 요약")
        summary = load_summary_info()
        
        if summary:
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("💰 CAPITAL", f"₩{float(summary.get('CAPITAL', 0)):,.0f}")
                st.metric("📊 INVESTED_COST", f"₩{float(summary.get('INVESTED_COST', 0)):,.0f}")
                st.metric("💵 CASH", f"₩{float(summary.get('CASH', 0)):,.0f}")
                st.metric("📈 ALLOC_USED_%", f"{float(summary.get('ALLOC_USED_%', 0)):.2%}")
            
            with col2:
                st.metric("🎯 TICKERS", summary.get('TICKERS', '0'))
                st.metric("💵 REALIZED_PNL_TODAY", f"₩{float(summary.get('REALIZED_PNL_TODAY', 0)):,.0f}")
                st.metric("📊 UNREALIZED_PNL", f"₩{float(summary.get('UNREALIZED_PNL', 0)):,.0f}")
                
            if "LAST_UPDATE" in summary:
                st.info(f"마지막 업데이트: {summary['LAST_UPDATE']}")
        else:
            st.info("요약 정보가 없습니다.")
    
    # === 탭 3: 거래 내역 ===
    with tab3:
        st.header("거래 내역")
        orders_df = load_orders()
        
        if not orders_df.empty:
            # 거래 통계
            trades_df = calculate_trades(orders_df)
            
            if not trades_df.empty:
                col1, col2, col3, col4 = st.columns(4)
                
                total_trades = len(trades_df)
                win_trades = len(trades_df[trades_df["profit_loss"] > 0])
                win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0
                total_profit = trades_df["profit_loss"].sum()
                
                col1.metric("총 거래 수", total_trades)
                col2.metric("승률", f"{win_rate:.1f}%")
                col3.metric("총 손익", f"₩{total_profit:,.0f}")
                col4.metric("승/패", f"{win_trades}/{total_trades - win_trades}")
                
                st.subheader("완료된 거래")
                st.dataframe(
                    trades_df[[
                        "symbol", "quantity", "entry_price", "exit_price",
                        "profit_loss", "profit_loss_pct", "entry_time", "exit_time"
                    ]],
                    use_container_width=True
                )
            
            # 전체 주문 내역
            st.subheader("전체 주문 내역")
            st.dataframe(
                orders_df[["ts", "symbol", "side", "quantity", "price", "result"]],
                use_container_width=True
            )
        else:
            st.info("거래 내역이 없습니다.")
    
    # === 탭 4: 시그널 ===
    with tab4:
        st.header("최근 시그널")
        signals_df = load_signals()
        
        if not signals_df.empty:
            # 액션별 필터
            action_filter = st.multiselect(
                "액션 필터",
                options=signals_df["action"].unique(),
                default=signals_df["action"].unique()
            )
            
            filtered = signals_df[signals_df["action"].isin(action_filter)]
            
            # 종목별 탭
            symbols = filtered["symbol"].unique()
            
            if len(symbols) > 0:
                symbol_tabs = st.tabs([str(s) for s in symbols[:10]])  # 최대 10개
                
                for symbol, tab in zip(symbols[:10], symbol_tabs):
                    with tab:
                        symbol_data = filtered[filtered["symbol"] == symbol].copy()
                        
                        if not symbol_data.empty:
                            # 최신 데이터
                            latest = symbol_data.iloc[-1]
                            
                            col1, col2, col3 = st.columns(3)
                            col1.metric("가격", f"₩{latest['price']:,.0f}")
                            col2.metric("RSI", f"{latest['rsi']:.2f}")
                            col3.metric("액션", latest['action'])
                            
                            # RSI 차트
                            if "rsi" in symbol_data.columns:
                                fig_rsi = px.line(
                                    symbol_data,
                                    x="ts",
                                    y="rsi",
                                    title=f"{symbol} RSI"
                                )
                                fig_rsi.add_hline(y=70, line_dash="dash", line_color="red")
                                fig_rsi.add_hline(y=30, line_dash="dash", line_color="green")
                                st.plotly_chart(fig_rsi, use_container_width=True)
                            
                            # 상세 데이터
                            st.dataframe(symbol_data, use_container_width=True)
        else:
            st.info("시그널 데이터가 없습니다.")

if __name__ == "__main__":
    main()
