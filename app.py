import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Smart DCA Dashboard", page_icon="📈")

# --- CUSTOM CSS FOR STYLING ---
st.markdown("""
    <style>
    .stMetric {
        background-color: #0E1117;
        padding: 10px;
        border-radius: 5px;
    }
    .badge-standard { background-color: #262730; color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
    .badge-smart { background-color: #1C4E38; color: #2EE583; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
    .badge-deep { background-color: #143528; color: #00FFA3; padding: 4px 8px; border-radius: 4px; font-size: 12px; border: 1px solid #00FFA3; }
    .badge-trim { background-color: #4A1A1A; color: #FF4B4B; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
    </style>
""", unsafe_allow_html=True)

# --- CONFIGURATION & INPUTS ---
# List of assets to track (Matches your screenshot)
TICKERS = ['SPY', 'VT', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 'NFLX', 'NVDA', 'PLTR', 'META', 'GOOGL']

# --- DATA FETCHING FUNCTION ---
@st.cache_data(ttl=3600)  # Cache data for 1 hour to prevent spamming APIs
def get_market_data(tickers):
    data = []
    
    # Download batch data for speed
    hist_data = yf.download(tickers, period="2y", group_by='ticker', auto_adjust=True)
    
    for ticker in tickers:
        try:
            # Handle slight difference in yfinance structure for single vs multiple tickers
            if len(tickers) == 1:
                df = hist_data
            else:
                df = hist_data[ticker]
            
            # clean missing data
            df = df.dropna()
            
            if df.empty:
                continue

            current_price = df['Close'].iloc[-1]
            
            # Calculate 200 Day Moving Average
            dma_200 = df['Close'].rolling(window=200).mean().iloc[-1]
            
            # Calculate Drawdown from 52-week High
            year_high = df['Close'].tail(252).max()
            drawdown = (current_price - year_high) / year_high
            
            # Determine Status & Multiplier based on Dashboard Rules
            # Rules: 
            # 1. > 200 DMA & > 20% over 200 DMA -> Trim/Hold (0.0x)
            # 2. < 200 DMA & Drawdown > 20% -> Deep Value (2.0x)
            # 3. < 200 DMA -> Smart Buy (1.5x)
            # 4. > 200 DMA -> Standard (1.0x)
            
            dma_diff_pct = (current_price - dma_200) / dma_200
            
            status = "Standard"
            multiplier = 1.0
            badge_class = "badge-standard"
            
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
            st.error(f"Error fetching {ticker}: {e}")
            
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

    # Top Metrics (Hardcoded Fear & Greed for demo, as it requires scraping)
    # In a real app, you'd scrape CNN Fear & Greed or use an API
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.markdown("**Fear & Greed:** <span style='color:orange'>49 Neutral</span>", unsafe_allow_html=True)
    with col_m2:
        st.markdown("**Shiller PE:** <span style='color:red'>39.85 Overvalued</span>", unsafe_allow_html=True)
    
    st.markdown("---")

    # Control Panel
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns(5)
        
        with c1:
            base_contribution = st.number_input("Base Monthly Contribution ($)", value=1000, step=100)
        
        # Calculate Logic
        df = get_market_data(TICKERS)
        
        if df.empty:
            st.warning("No data available. Please check ticker symbols.")
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
    st.caption("Legend: < 200DMA (1.5x) | Deep Value < 200DMA & >20% DD (2.0x) | Standard (1.0x) | Overextended > 20% over 200DMA (0.0x)")

    # --- TABS FOR FILTERING ---
    tab1, tab2, tab3, tab4 = st.tabs(["All Assets", "Opportunities", "Standard", "Hold/Trim"])

    def render_grid(dataframe):
        # Create a grid layout (4 columns)
        cols = st.columns(4)
        for index, row in dataframe.iterrows():
            with cols[index % 4]:
                # Card Container
                with st.container(border=True):
                    # Header: Ticker + Badge
                    h1, h2 = st.columns([1, 2])
                    with h1:
                        st.subheader(row['Ticker'])
                    with h2:
                        st.markdown(f"<div style='text-align:right'><span class='{row['Badge']}'>{row['Status']}</span></div>", unsafe_allow_html=True)
                    
                    # Price Data
                    st.metric("Price", f"${row['Price']:.2f}", f"{(row['Price'] - row['200_DMA']):.2f} vs 200DMA")
                    
                    # Progress Bar logic (Visual flair for valuation)
                    # Normalize simple deviation for a progress bar (0.5 is fair value)
                    progress_val = 0.5 + (row['DMA_Diff'] / 0.4) # rough scaling
                    progress_val = max(0.0, min(1.0, progress_val))
                    st.progress(progress_val, text="Undervalued ⟵ ⟶ Overvalued")

                    # Drawdown & Multiplier
                    d1, d2 = st.columns(2)
                    with d1:
                        st.text("Drawdown")
                        st.markdown(f"<span style='color: #FF4B4B'>{row['Drawdown']:.1%}</span>", unsafe_allow_html=True)
                    with d2:
                        st.text("Rec. Mult.")
                        st.write(f"**x{row['Multiplier']}**")
                    
                    # Investment Action Button
                    if row['Multiplier'] > 0:
                        st.button(f"Invest ${row['Invest_Amount']:.2f}", key=f"btn_{row['Ticker']}", use_container_width=True, type="primary")
                    else:
                        st.button("Trim / Hold", key=f"btn_{row['Ticker']}", use_container_width=True, disabled=True)

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
