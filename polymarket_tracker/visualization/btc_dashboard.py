"""
BTC 5-Minute Trading Dashboard

Real-time dashboard for monitoring:
- Active BTC 5-min markets
- Live signals with confidence scores
- Whale activity and confluence
- Open positions and P&L
- Performance metrics
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import asyncio

st.set_page_config(
    page_title="BTC 5-Min Intelligence Bot",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        background: linear-gradient(90deg, #f7931a, #ffea00);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .signal-card {
        background-color: #1a1a2e;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        border-left: 4px solid;
    }
    .signal-long {
        border-color: #00d084;
    }
    .signal-short {
        border-color: #ff4757;
    }
    .metric-value {
        font-size: 1.5rem;
        font-weight: bold;
    }
    .positive {
        color: #00d084;
    }
    .negative {
        color: #ff4757;
    }
</style>
""", unsafe_allow_html=True)


def render_header():
    """Render dashboard header."""
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.markdown('<p class="main-header">₿ BTC 5-Min Intelligence Bot</p>', 
                   unsafe_allow_html=True)
    
    with col2:
        st.metric("Active Markets", "12", "+3")
    
    with col3:
        st.metric("Bot Status", "🟢 LIVE", "Scanning")


def render_portfolio_summary(position_manager):
    """Render portfolio summary cards."""
    st.subheader("💼 Portfolio Summary")
    
    summary = position_manager.get_portfolio_summary()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "Bankroll",
            f"${summary['bankroll']:,.0f}",
            f"${summary['daily_pnl']:+,.0f} today"
        )
    
    with col2:
        st.metric(
            "Open Positions",
            summary['open_positions'],
            f"{summary['exposure_pct']:.1%} exposed"
        )
    
    with col3:
        pnl_color = "normal"
        if summary['total_pnl'] > 0:
            pnl_color = "off"
        elif summary['total_pnl'] < 0:
            pnl_color = "inverse"
        
        st.metric(
            "Total P&L",
            f"${summary['total_pnl']:+,.0f}",
            f"{summary['current_drawdown']:.1%} DD"
        )
    
    with col4:
        st.metric(
            "Available",
            f"${summary['available_balance']:,.0f}",
            f"${summary['total_exposure']:,.0f} at risk"
        )
    
    with col5:
        win_rate = position_manager.get_trade_statistics().get('win_rate', 0)
        st.metric("Win Rate", f"{win_rate:.1%}", "Last 24h")


def render_active_signals(signal_generator):
    """Render active trading signals."""
    st.subheader("🎯 Active Signals")
    
    signals = signal_generator.get_active_signals()
    
    if not signals:
        st.info("No active signals. Waiting for high-probability setups...")
        return
    
    for signal in signals:
        direction_class = "signal-long" if signal.direction.value == 'long' else "signal-short"
        direction_emoji = "🟢" if signal.direction.value == 'long' else "🔴"
        
        with st.container():
            st.markdown(f'<div class="signal-card {direction_class}">', unsafe_allow_html=True)
            
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            
            with col1:
                st.markdown(f"**{direction_emoji} {signal.primary_pattern.value.replace('_', ' ').title()}**")
                st.caption(f"Market: {signal.market_question[:50]}...")
                st.caption(f"Time remaining: {signal.time_to_expiration:.0f}s")
            
            with col2:
                st.metric("Confidence", f"{signal.confidence_score:.1%}")
                st.caption(f"Win Prob: {signal.win_probability:.1%}")
            
            with col3:
                st.metric("Entry", f"${signal.entry_price:.4f}")
                st.caption(f"R:R = {signal.risk_reward:.2f}")
            
            with col4:
                st.metric("Target", f"${signal.target_price:.4f}")
                st.caption(f"Stop: ${signal.stop_loss:.4f}")
            
            # Reasoning
            with st.expander("Analysis"):
                st.markdown("**Supporting Evidence:**")
                for reason in signal.reasoning:
                    st.markdown(f"- {reason}")
                
                if signal.risk_factors:
                    st.markdown("**Risk Factors:**")
                    for risk in signal.risk_factors:
                        st.markdown(f"- ⚠️ {risk}")
                
                # Whale confluence
                if signal.whale_confluence.get('aligned_whales'):
                    st.markdown("**🐋 Whale Confluence:**")
                    st.json(signal.whale_confluence['aligned_whales'][:3])
            
            st.markdown('</div>', unsafe_allow_html=True)


def render_open_positions(position_manager):
    """Render open positions table."""
    st.subheader("📊 Open Positions")
    
    positions_df = position_manager.get_position_report()
    
    if positions_df.empty:
        st.info("No open positions")
        return
    
    # Color coding
    def color_pnl(val):
        if val > 0:
            return 'color: #00d084'
        elif val < 0:
            return 'color: #ff4757'
        return ''
    
    styled_df = positions_df.style.applymap(color_pnl, subset=['unrealized_pnl', 'unrealized_pct'])
    
    st.dataframe(styled_df, use_container_width=True)


def render_market_regime(market_scanner):
    """Render market regime analysis."""
    st.subheader("🌊 Market Regime Analysis")
    
    # Example data (would come from scanner)
    regimes = pd.DataFrame({
        'Market': ['BTC > 95K in 5m', 'BTC < 94K in 5m', 'BTC Vol Up', 'BTC Range Bound'],
        'Regime': ['TRENDING_UP', 'TRENDING_DOWN', 'HIGH_VOLATILITY', 'RANGING'],
        'Momentum': [0.035, -0.028, 0.015, -0.002],
        'Whale Imbalance': [0.65, -0.55, 0.12, 0.05],
        'Signal': ['LONG', 'SHORT', 'NEUTRAL', 'NEUTRAL']
    })
    
    st.dataframe(regimes, use_container_width=True)


def render_whale_leaderboard(whale_tracker):
    """Render top whale performers."""
    st.subheader("🐋 Top BTC 5-Min Traders")
    
    leaderboard = whale_tracker.get_top_performers(min_sessions=5)
    
    if leaderboard.empty:
        st.info("No whale data available")
        return
    
    # Display top 10
    display_df = leaderboard.head(10)[[
        'name', 'win_rate', 'profit_factor', 'recent_pnl', 'is_hot', 'is_dangerous'
    ]].copy()
    
    display_df.columns = ['Trader', 'Win Rate', 'Profit Factor', 'Recent P&L', 'Hot', 'Smart']
    
    st.dataframe(display_df, use_container_width=True)


def render_performance_charts(signal_generator, position_manager):
    """Render performance charts."""
    st.subheader("📈 Performance Analytics")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Pattern performance
        pattern_stats = signal_generator.pattern_engine.get_pattern_statistics()
        
        if not pattern_stats.empty:
            fig = px.bar(
                pattern_stats,
                x='pattern',
                y='count',
                color='avg_confidence',
                title='Pattern Detection Frequency',
                labels={'count': 'Detections', 'pattern': 'Pattern Type'}
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No pattern data yet")
    
    with col2:
        # P&L over time
        stats = position_manager.get_trade_statistics()
        
        if 'message' not in stats:
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=stats['win_rate'] * 100,
                title={'text': "Win Rate %"},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': "#00d084" if stats['win_rate'] > 0.5 else "#ff4757"},
                    'steps': [
                        {'range': [0, 50], 'color': "#ffe0e0"},
                        {'range': [50, 100], 'color': "#e0ffe0"}
                    ],
                    'threshold': {
                        'line': {'color': "black", 'width': 4},
                        'thickness': 0.75,
                        'value': 50
                    }
                }
            ))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(stats['message'])


def render_signal_log(signal_generator):
    """Render signal history log."""
    st.subheader("📝 Signal Log")
    
    log_df = signal_generator.get_signal_summary()
    
    if not log_df.empty:
        st.dataframe(log_df.tail(20), use_container_width=True)
    else:
        st.info("No signals generated yet")


def render_settings():
    """Render settings sidebar."""
    with st.sidebar:
        st.header("⚙️ Bot Settings")
        
        # Risk settings
        st.subheader("Risk Management")
        risk_level = st.select_slider(
            "Risk Level",
            options=["Conservative", "Moderate", "Aggressive"],
            value="Moderate"
        )
        
        max_risk = st.slider("Max Risk per Trade", 0.5, 5.0, 2.0, 0.5) / 100
        kelly_frac = st.slider("Kelly Fraction", 0.1, 1.0, 0.5, 0.1)
        
        # Signal settings
        st.subheader("Signal Filters")
        min_confidence = st.slider("Min Confidence", 50, 95, 65, 5) / 100
        min_rr = st.slider("Min Risk/Reward", 1.0, 3.0, 1.5, 0.1)
        
        # Bot controls
        st.subheader("Bot Controls")
        
        col1, col2 = st.columns(2)
        with col1:
            st.button("▶️ Start", use_container_width=True)
        with col2:
            st.button("⏸️ Pause", use_container_width=True)
        
        st.divider()
        
        # Display current config
        st.caption(f"Current Config:")
        st.caption(f"- Risk: {risk_level}")
        st.caption(f"- Max Risk/Trade: {max_risk:.1%}")
        st.caption(f"- Kelly: {kelly_frac:.0%}")
        st.caption(f"- Min Confidence: {min_confidence:.0%}")


def main():
    """Main dashboard."""
    # Initialize components (placeholder - would be real in production)
    from ..data.btc_market_scanner import BTCMarketScanner
    from ..data.micro_whale_tracker import MicroWhaleTracker
    from ..analysis.signal_generator import SignalGenerator
    from ..risk.position_manager import PositionManager, RiskParameters
    from ..utils.config import Config
    
    config = Config.from_env()
    
    # Header
    render_header()
    
    # Sidebar settings
    render_settings()
    
    # Main content
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 Trading Floor",
        "🐋 Whale Intelligence",
        "📊 Analytics",
        "⚙️ System"
    ])
    
    with tab1:
        # Placeholder for demo
        st.info("Connect live data to see real-time signals")
        
        # Example signal
        st.subheader("Example Signal Format")
        st.json({
            "signal_id": "btc_5m_143022",
            "pattern": "MOMENTUM_LONG",
            "confidence": 0.78,
            "direction": "LONG",
            "entry": 0.65,
            "target": 0.68,
            "stop": 0.63,
            "risk_reward": 1.5,
            "whale_confluence": 0.72,
            "time_remaining": 180
        })
    
    with tab2:
        st.info("Whale tracking requires wallet data")
        
        st.subheader("Tracked Wallets")
        st.text_input("Add Whale Wallet", placeholder="0x...")
    
    with tab3:
        st.info("Performance analytics will appear after trading")
    
    with tab4:
        st.subheader("System Status")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("WebSocket", "🟢 Connected")
        with col2:
            st.metric("API Latency", "45ms")
        with col3:
            st.metric("Last Update", "2s ago")
        
        st.subheader("Logs")
        st.code("""
[14:30:22] Scanner initialized
[14:30:23] Connected to WebSocket
[14:30:24] Found 12 active BTC 5-min markets
[14:30:25] Waiting for signals...
        """)
    
    # Footer
    st.divider()
    st.markdown(
        "<center><small>⚠️ For educational purposes only. "
        "Crypto trading involves substantial risk.</small></center>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
