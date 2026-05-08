"""
Streamlit Dashboard for Polymarket Whale Tracker.

Provides real-time visualization of:
- Whale leaderboard
- Strategy breakdown
- Consensus meter
- Risk alerts
- Zombie watch
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from ..data.whale_tracker import WhaleTracker
from ..analysis.archetype_classifier import ArchetypeClassifier
from ..utils.config import Config

st.set_page_config(
    page_title="Polymarket Whale Tracker",
    page_icon="🐋",
    layout="wide",
)


def main():
    """Main dashboard."""
    st.title("🐋 Polymarket Whale Tracker")
    st.markdown("*Educational analytics for prediction market whale behavior*")
    
    # Initialize
    config = Config.from_env()
    tracker = WhaleTracker(config)
    classifier = ArchetypeClassifier()
    
    # Sidebar
    with st.sidebar:
        st.header("Track Wallets")
        wallet = st.text_input("Add Wallet Address", placeholder="0x...")
        
        if st.button("Analyze"):
            with st.spinner("Analyzing..."):
                st.info("Analysis feature - integrate with tracker.analyze_wallet()")
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Leaderboard", "🎯 Strategies", "📈 Consensus", "👻 Zombie Watch"
    ])
    
    with tab1:
        st.header("Whale Leaderboard")
        
        # Example data
        example_df = pd.DataFrame({
            'Wallet': ['SeriouslySirius', 'DrPufferfish', 'simonbanza', 'Swisstony'],
            'True WR %': [53.0, 50.9, 57.6, 51.0],
            'Displayed WR %': [73.0, 83.5, 57.6, 52.0],
            'Vanity Gap %': [20.0, 32.6, 0.0, 1.0],
            'Total PnL': [150000, 89000, 45000, 125000],
        })
        
        st.dataframe(example_df, use_container_width=True)
        
        # Chart
        fig = go.Figure()
        fig.add_trace(go.Bar(name='True WR', x=example_df['Wallet'], y=example_df['True WR %']))
        fig.add_trace(go.Bar(name='Displayed WR', x=example_df['Wallet'], y=example_df['Displayed WR %']))
        fig.update_layout(barmode='group', title='Win Rate Comparison')
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.header("Strategy Archetypes")
        
        st.markdown("""
        ### The Six Archetypes
        
        1. **🛡️ Hedger** - Bets on 3+ directions per event
        2. **🎲 Probability Transformer** - 10+ low-probability bets
        3. **⚡ Speed Trader** - High-frequency algorithmic
        4. **📊 Swing Trader** - Treats probability as charts
        5. **🎯 Micro-Arbitrageur** - YES+NO < $1.00 edge
        6. **🔮 Domain Expert** - Category specialist
        """)
        
        # Classifier demo
        st.subheader("Classify Wallet")
        trades = st.slider("Trades per day", 0.0, 50.0, 5.0)
        hedge = st.slider("Hedge ratio", 0.0, 1.0, 0.1)
        
        if hedge > 0.5:
            st.success("Archetype: Hedger or Probability Transformer")
        elif trades > 10:
            st.success("Archetype: Speed Trader or Micro-Arbitrageur")
        else:
            st.success("Archetype: Swing Trader or Domain Expert")
    
    with tab3:
        st.header("Whale Consensus")
        
        market_id = st.text_input("Market ID", placeholder="Enter condition ID...")
        
        if st.button("Check Consensus"):
            st.info("Consensus calculation - integrate with consensus engine")
            
            # Example gauge
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=0.7,
                title={'text': "Whale Confidence"},
                gauge={'axis': {'range': [0, 1]}, 'bar': {'color': "green"}}
            ))
            st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
        st.header("Zombie Watch")
        
        st.markdown("""
        **Zombie Orders** = Positions open > 30 days with unrealized losses.
        These artificially inflate displayed win rates.
        """)
        
        st.metric("Total Zombie Orders", 47)
        st.metric("Avg Vanity Gap", "18.5%")
    
    # Footer
    st.divider()
    st.markdown(
        "<center><small>⚠️ For educational purposes only. "
        "Past performance ≠ future results.</small></center>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
