import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
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
def load_portfolio_direct():
    try:
        gc = get_gs_client()
        sh = gc.open_by_key(GS_SHEET_ID)
        ws = sh.worksheet("portfolio")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty:
            for col in ["entry_price", "current_price", "quantity", "profit_loss", "profit_loss_pct"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            if "entry_time" in df.columns:
                df["entry_time"] = pd.to_datetime(df["entry_time"], errors="coerce")
        
        return df
    except Exception as e:
        st.error(f"포트폴리오 로드 실패: {e}")
        return pd.DataFrame()

def load_trades_direct():
    try:
        gc = get_gs_client()
        sh = gc.open_by_key(GS_SHEET_ID)
        ws = sh.worksheet("trades")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty:
            for col in ["entry_price", "exit_price", "quantity", "profit_loss", "profit_loss_pct"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            for col in ["entry_time", "exit_time"]:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
        
        return df
    except Exception as e:
        st.error(f"거래 내역 로드 실패: {e}")
        return pd.DataFrame()

def load_balances_direct():
    try:
        gc = get_gs_client()
        sh = gc.open_by_key(GS_SHEET_ID)
        ws = sh.worksheet("balances")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty:
            for col in ["krw", "total_krw", "total_value_krw"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        
        return df
    except Exception as e:
        st.error(f"잔고 내역 로드 실패: {e}")
        return pd.DataFrame()

def load_signals_direct():
    try:
        gc = get_gs_client()
        sh = gc.open_by_key(GS_SHEET_ID)
        ws = sh.worksheet("signals")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty:
            for col in ["price", "rsi", "macd", "signal", "histogram", "bb_upper", "bb_middle", "bb_lower"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        
        return df
    except Exception as e:
        st.error(f"시그널 로드 실패: {e}")
        return pd.DataFrame()

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
    tab1, tab2, tab3, tab4 = st.tabs(["📊 포트폴리오", "💰 잔고 추이", "📉 거래 내역", "🎯 시그널"])
    
    # === 탭 1: 포트폴리오 ===
    with tab1:
        st.header("현재 포트폴리오")
        portfolio_df = load_portfolio_direct()
        
        if not portfolio_df.empty:
            col1, col2, col3 = st.columns(3)
            
            total_value = (portfolio_df["current_price"] * portfolio_df["quantity"]).sum()
            total_pl = portfolio_df["profit_loss"].sum()
            total_pl_pct = (total_pl / (total_value - total_pl) * 100) if (total_value - total_pl) != 0 else 0
            
            col1.metric("총 평가액", f"₩{total_value:,.0f}")
            col2.metric("총 손익", f"₩{total_pl:,.0f}", f"{total_pl_pct:+.2f}%")
            col3.metric("보유 종목 수", len(portfolio_df))
            
            st.dataframe(
                portfolio_df[[
                    "symbol", "quantity", "entry_price", "current_price",
                    "profit_loss", "profit_loss_pct", "entry_time"
                ]],
                use_container_width=True
            )
        else:
            st.info("보유 중인 포지션이 없습니다.")
    
    # === 탭 2: 잔고 추이 ===
    with tab2:
        st.header("잔고 변화 추이")
        balances_df = load_balances_direct()
        
        if not balances_df.empty and "timestamp" in balances_df.columns:
            fig = px.line(
                balances_df,
                x="timestamp",
                y="total_value_krw",
                title="총 자산 가치 추이",
                labels={"total_value_krw": "총 자산 (KRW)", "timestamp": "시간"}
            )
            st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(balances_df[["timestamp", "krw", "total_value_krw"]], use_container_width=True)
        else:
            st.info("잔고 데이터가 없습니다.")
    
    # === 탭 3: 거래 내역 ===
    with tab3:
        st.header("거래 내역")
        trades_df = load_trades_direct()
        
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
            
            st.dataframe(
                trades_df[[
                    "symbol", "side", "quantity", "entry_price", "exit_price",
                    "profit_loss", "profit_loss_pct", "entry_time", "exit_time"
                ]],
                use_container_width=True
            )
        else:
            st.info("거래 내역이 없습니다.")
    
    # === 탭 4: 시그널 ===
    with tab4:
        st.header("최근 시그널")
        signals_df = load_signals_direct()
        
        if not signals_df.empty:
            # 종목별 탭
            symbols = signals_df["symbol"].unique()
            symbol_tabs = st.tabs(symbols)
            
            for symbol, tab in zip(symbols, symbol_tabs):
                with tab:
                    symbol_data = signals_df[signals_df["symbol"] == symbol].copy()
                    
                    if not symbol_data.empty and "timestamp" in symbol_data.columns:
                        # 가격 차트
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=symbol_data["timestamp"],
                            y=symbol_data["price"],
                            name="가격",
                            line=dict(color="blue")
                        ))
                        fig.update_layout(title=f"{symbol} 가격", xaxis_title="시간", yaxis_title="가격")
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # RSI 차트
                        if "rsi" in symbol_data.columns:
                            fig_rsi = px.line(
                                symbol_data,
                                x="timestamp",
                                y="rsi",
                                title=f"{symbol} RSI"
                            )
                            fig_rsi.add_hline(y=70, line_dash="dash", line_color="red")
                            fig_rsi.add_hline(y=30, line_dash="dash", line_color="green")
                            st.plotly_chart(fig_rsi, use_container_width=True)
        else:
            st.info("시그널 데이터가 없습니다.")

if __name__ == "__main__":
    main()
