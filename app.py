import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Smart DCA Dashboard", page_icon="📈")

# --- CUSTOM CSS FOR BADGES ONLY ---
# We removed the metric background styling to fix the "Unreadable Text" issue.
st.markdown("""
    <style>
    .badge-standard { background-color: #555; color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
    .badge-smart { background-color: #1C4E38; color: #2EE583; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
    .badge-deep { background-color: #143528; color: #00FFA3; padding: 4px 8px; border-radius: 4px; font-size: 12px; border: 1px solid #00FFA3; }
    .badge-trim { background-color: #4A1A1A; color: #FF4B4B; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
    </style>
""", unsafe_allow_html=True)

# --- CONFIGURATION & INPUTS ---
TICKERS = ['SPY', 'VT', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 'NFLX', 'NVDA', 'PLTR', 'META', 'GOOGL']

# --- DATA FETCHING FUNCTION ---
@st.cache_data(ttl=3600)
def get_market_data(tickers):
    data = []
    
    # We fetch tickers one by one to avoid yfinance MultiIndex errors
    # This is slightly slower but much more stable for a dashboard
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            # Fetch 2 years of history
            df = stock.history(period="2y")
            
            if df.empty:
                continue

            current_price = df['Close'].iloc[-1]
            
            # Calculate 200 Day Moving Average
            if len(df) >= 200:
                dma_200 = df['Close'].rolling(window=200).mean().iloc[-1]
            else:
                dma_200 = df['Close'].mean() # Fallback if new stock
            
            # Calculate Drawdown from 52-week High (approx 252 trading days)
            year_high = df['Close'].tail(252).max()
            drawdown = (current_price - year_high) / year_high
            
            # Determine Status & Multiplier based on Dashboard Rules
            dma_diff_pct = (current_price - dma_200) / dma_200
            
            status = "Standard"
            multiplier = 1.0
            badge_class = "badge-standard"
            
            # Logic:
            # 1. > 20% over 200 DMA -> Trim/Hold
            # 2. < 200 DMA & Drawdown > 20% -> Deep Value
            # 3. < 200 DMA -> Smart Buy
            # 4. Otherwise -> Standard
            
            if current_price > dma_200 and dma_diff_pct > 0.20:
                status = "Overextended"
                multiplier = 0.0
                badge_class = "badge-trim"
            elif current_price < dma_200 and drawdown < -0.20:
                status = "Deep Value Buy"
                multiplier = 2.0
                badge_class = "badge-deep"
            elif current_price < dma_200:
                status = "Smart Buy"
                multiplier = 1.5
                badge_class = "badge-smart"
            
            data.append({
                "Ticker": ticker,
                "Price": current_price,
                "200_DMA": dma_200,
                "DMA_Diff": dma_diff_pct,
                "Drawdown": drawdown,
                "Multiplier": multiplier,
                "Status": status,
                "Badge": badge_class
            })
            
        except Exception as e:
            # Silently skip errors to prevent app crashing
            print(f"Error fetching {ticker}: {e}")
            continue
            
    return pd.DataFrame(data)

# --- MAIN APP ---
def main():
    # Header Section
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("Smart DCA Dashboard")
        st.caption("Live Market Data via Yahoo Finance")
    with col2:
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()

    # Top Metrics
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.markdown("**Fear & Greed:** <span style='color:orange'>49 Neutral</span>", unsafe_allow_html=True)
    with col_m2:
        st.markdown("**Shiller PE:** <span style='color:red'>39.85 Overvalued</span>", unsafe_allow_html=True)
    
    st.divider()

    # Control Panel
    # Using container with border ensuring visibility in light/dark mode
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns(5)
        
        with c1:
            base_contribution = st.number_input("Base Monthly Contribution ($)", value=1000, step=100)
        
        # Calculate Logic
        with st.spinner("Fetching market data..."):
            df = get_market_data(TICKERS)
        
        if df.empty:
            st.error("Could not fetch data. Please check your internet connection or try again later.")
            return

        # Base allocation per asset (Equal Weight Base)
        base_per_asset = base_contribution / len(df)
        
        # Calculate individual investments
        df['Invest_Amount'] = base_per_asset * df['Multiplier']
        
        total_smart_dca = df['Invest_Amount'].sum()
        active_multiplier = total_smart_dca / base_contribution if base_contribution > 0 else 0
        opportunities = len(df[df['Multiplier'] > 1.0])

        with c2:
            st.metric("Base Invest", f"${base_contribution:,.2f}")
        with c3:
            delta_color = "normal" if total_smart_dca <= base_contribution else "inverse"
            st.metric("Smart DCA Total", f"${total_smart_dca:,.2f}", delta=f"{active_multiplier:.2f}x", delta_color=delta_color)
        with c4:
            st.metric("Active Multiplier", f"{active_multiplier:.2f}x")
        with c5:
            st.metric("Opportunities", opportunities)

    # Legend
    st.info("Strategy Legend: < 200DMA (1.5x) | Deep Value < 200DMA & >20% DD (2.0x) | Standard (1.0x) | Overextended > 20% over 200DMA (0.0x)", icon="ℹ️")

    # --- TABS FOR FILTERING ---
    tab1, tab2, tab3, tab4 = st.tabs(["All Assets", "Opportunities", "Standard", "Hold/Trim"])

    def render_grid(dataframe):
        if dataframe.empty:
            st.write("No assets in this category.")
            return

        # Create a grid layout
        # We calculate rows to ensure layout stays clean
        cols_per_row = 4
        rows = [dataframe.iloc[i:i + cols_per_row] for i in range(0, len(dataframe), cols_per_row)]

        for row_data in rows:
            cols = st.columns(cols_per_row)
            for idx, (index, asset) in enumerate(row_data.iterrows()):
                with cols[idx]:
                    # Card Container
                    with st.container(border=True):
                        # Header: Ticker + Badge
                        h1, h2 = st.columns([1, 2])
                        with h1:
                            st.subheader(asset['Ticker'])
                        with h2:
                            st.markdown(f"<div style='text-align:right'><span class='{asset['Badge']}'>{asset['Status']}</span></div>", unsafe_allow_html=True)
                        
                        # Price Data
                        st.metric("Price", f"${asset['Price']:.2f}", f"{(asset['Price'] - asset['200_DMA']):.2f} vs 200DMA")
                        
                        # Progress Bar logic
                        progress_val = 0.5 + (asset['DMA_Diff'] / 0.4) 
                        progress_val = max(0.0, min(1.0, progress_val))
                        st.progress(progress_val, text="Undervalued ⟵ ⟶ Overvalued")

                        # Drawdown & Multiplier
                        d1, d2 = st.columns(2)
                        with d1:
                            st.text("Drawdown")
                            st.markdown(f"**{asset['Drawdown']:.1%}**")
                        with d2:
                            st.text("Multiplier")
                            st.markdown(f"**x{asset['Multiplier']}**")
                        
                        # Investment Action
                        if asset['Multiplier'] > 0:
                            st.success(f"Invest ${asset['Invest_Amount']:.2f}")
                        else:
                            st.warning("Trim / Hold")

    with tab1:
        render_grid(df)
    with tab2:
        render_grid(df[df['Multiplier'] > 1.0])
    with tab3:
        render_grid(df[df['Multiplier'] == 1.0])
    with tab4:
        render_grid(df[df['Multiplier'] == 0.0])

if __name__ == "__main__":
    main()
