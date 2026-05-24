# ===================================================
# STEP 1: BRING IN THE TOOLS
# ===================================================
# Import Streamlit, the framework that builds the web dashboard interface.
import streamlit as st 

# Import Pandas, the library used for building and manipulating data tables.
import pandas as pd 

# Import FRED API, the tool that directly connects to the Federal Reserve database.
from fredapi import Fred 

# Configure the web page to stretch across the full monitor and set the browser tab title.
st.set_page_config(page_title="MangsHessianAI | Yield Matrix", layout="wide")

# Render the main application title at the top of the dashboard.
st.title("MangsHessianAI: The Yield Matrix")

# Securely load the private FRED API password from the local secrets.toml file.
api_key = st.secrets["FRED_API_KEY"]

# Initialize the live database connection using the loaded API key.
fred = Fred(api_key=api_key)


# ===================================================
# STEP 2: THE QUANT DICTIONARIES
# ===================================================
# Map the friendly names of short-term T-Bills to their exact database ticker symbols.
tbill_options = {"1-Month": "DGS1MO", "3-Month": "DGS3MO", "6-Month": "DGS6MO", "1-Year": "DGS1"}

# Map the friendly names of medium-term T-Notes to their exact database ticker symbols.
tnote_options = {"2-Year": "DGS2", "3-Year": "DGS3", "5-Year": "DGS5", "7-Year": "DGS7", "10-Year": "DGS10"}

# Map the friendly names of long-term T-Bonds to their exact database ticker symbols.
tbond_options = {"10-Year": "DGS10", "20-Year": "DGS20", "30-Year": "DGS30"}


# ===================================================
# STEP 3: THE MASTER CHART ENGINE
# ===================================================
# Define a single reusable function to handle all data pulling and math for every tab.
def generate_spread_chart(leg_1_name, leg_2_name, ticker_dict, instrument_info):
    
    # Wrap the entire process in a try-except block to prevent the app from crashing on network errors.
    try:
        # Retrieve the exact FRED ticker symbol for the user's first dropdown selection.
        leg_1_tkr = ticker_dict[leg_1_name]
        
        # Retrieve the exact FRED ticker symbol for the user's second dropdown selection.
        leg_2_tkr = ticker_dict[leg_2_name]
        
        # Download the complete historical daily yield data for Leg 1.
        leg_1_data = fred.get_series(leg_1_tkr)
        
        # Download the complete historical daily yield data for Leg 2.
        leg_2_data = fred.get_series(leg_2_tkr)
        
        # Merge both historical data series into a single Pandas DataFrame (like an Excel table).
        df = pd.DataFrame({
            f"{leg_1_name} (%)": leg_1_data,
            f"{leg_2_name} (%)": leg_2_data
        })
        
        # Dynamically generate a title for the new spread calculation column.
        spread_name = f"Spread ({leg_1_name} - {leg_2_name})"
        
        # Calculate the spread by subtracting the shorter-term yield from the longer-term yield row by row.
        df[spread_name] = df[f"{leg_1_name} (%)"] - df[f"{leg_2_name} (%)"]
        
        # Remove any rows containing empty data (e.g., weekends and market holidays).
        df = df.dropna()
        
        # Convert the row index into a strict datetime format so Python can filter it accurately.
        df.index = pd.to_datetime(df.index)
        
        # Isolate the data to only include dates from January 1, 2023, up to the present day.
        df_chart = df[df.index >= "2023-01-01"].copy()

        # ===================================================
        # NEW FIX: EXTRACT EXACT TIMEFRAME DATES
        # ===================================================
        # Find the absolute minimum (oldest) date in our filtered dataset and format it as 'Jan 01, 2023'.
        start_date = df_chart.index.min().strftime('%b %d, %Y')
        
        # Find the absolute maximum (newest) date in our filtered dataset and format it.
        end_date = df_chart.index.max().strftime('%b %d, %Y')
        
        # Combine them into a clean string to inject into our UI messages.
        timeframe_string = f"between **{start_date}** and **{end_date}**"
        
        # ===================================================
        # STEP 3A: REGIME SHIFT ALGORITHM
        # ===================================================
        # Tag each day as "Normal (Red)" if the spread is > 0, or "Inverted (Green)" if the spread is <= 0.
        df_chart["Regime"] = df_chart[spread_name].apply(lambda x: "Normal (Red)" if x > 0 else "Inverted (Green)")
        
        # Shift the regime column down by exactly 1 day to compare the current day's status against yesterday's status.
        df_chart["Previous_Regime"] = df_chart["Regime"].shift(1)
        
        # Filter the dataset to find ONLY the specific days where the regime status flipped completely.
        shifts = df_chart[(df_chart["Regime"] != df_chart["Previous_Regime"]) & (df_chart["Previous_Regime"].notnull())].copy()
        
        # Count the total number of times the regime flipped since 2023.
        shift_count = len(shifts)

        # Use float('nan') instead of None. This forces Streamlit to recognize empty columns as Math, not Text.
        df_chart["Normal (Red)"] = df_chart[spread_name].apply(lambda x: float(x) if x > 0 else float('nan'))
        df_chart["Inverted (Green)"] = df_chart[spread_name].apply(lambda x: float(x) if x <= 0 else float('nan'))

        # Render the interactive scatter chart on the dashboard using designated Hex colors.
        st.scatter_chart(
            df_chart[["Normal (Red)", "Inverted (Green)"]],
            color=["#FF0000", "#00FF00"] 
        )

        # ===================================================
        # STEP 3B: MANGSHESSIAN SHIFT ANALYSIS & TOP 10
        # ===================================================
        # Render a subheader for the AI-driven market analysis section.
        st.subheader("🧠 MangsHessianAI: Regime Shift Analysis")
        
        # Execute this block if the market never inverted during the selected timeframe.
        if shift_count == 0:
            
            # Display a blue informational notification that includes our new exact date range string.
            st.info(f"**0 Regime Shifts Detected.** The {leg_1_name} vs {leg_2_name} spread has never crossed the zero line {timeframe_string}. The market has remained in a single constant state for this segment.")
            
        # Execute this block if the market DID invert at least once.
        else:
            
            # Isolate the crucial columns showing the exact dates and yields when the flips happened.
            display_shifts = shifts[[f"{leg_1_name} (%)", f"{leg_2_name} (%)", spread_name, "Previous_Regime", "Regime"]].copy()
            
            # Strip the redundant 00:00:00 timestamp off the index to clean up the display.
            display_shifts.index = display_shifts.index.date
            
            # Rename the index header explicitly to "Date of Shift".
            display_shifts.index.name = "Date of Shift"
            
            # UI UPGRADE: If there are more than 10 shifts, slice the table to show only the 10 most recent.
            if shift_count > 10:
                # Print the warning including the exact date range, noting that we are filtering the table.
                st.warning(f"**{shift_count} Regime Shifts Detected** {timeframe_string}. Filtering table to display only the **10 most recent** shifts.")
                display_shifts = display_shifts.tail(10)
            else:
                # Print the standard warning with the exact date range for 10 or fewer shifts.
                st.warning(f"**{shift_count} Regime Shifts Detected** {timeframe_string}. The market crossed the zero line {shift_count} times during this period.")
            
            # Render the historical shift data as an interactive table.
            st.dataframe(display_shifts)

        # Create a collapsible expander box to house the deep institutional macro logic.
        with st.expander("Why do these Red/Green shifts happen? (Read Macro Logic)"):
            
            # Render the universal explanation of yield curve inversion mechanics.
            st.markdown("""
            **🔴 Flipping to RED (Normalizing/De-Inversion):** This happens when long-term yields rise above short-term yields. It usually means the immediate panic is over, and the market expects a return to normal economic growth. Paradoxically, if the curve has been deeply inverted for a long time, the sudden "flip to red" is historically the exact moment a recession actually begins, because the Federal Reserve is violently cutting short-term rates to save the economy.
            
            **🟢 Flipping to GREEN (Inversion/Panic):**
            This happens when short-term yields spike above long-term yields. It is driven by severe, immediate panic (inflation shocks, wars, banking collapses). Institutional money demands massive short-term payouts for immediate risk, while fleeing to long-term bonds for future safety (driving long yields down). It is the ultimate warning siren of market stress.
            
            ---
            **Understanding the Instruments in this Chart:**
            """)
            
            # Dynamically render the specific definition (Bills, Notes, or Bonds) passed down by the current tab.
            st.markdown(instrument_info)

    # Intercept any API or calculation errors and display them safely in a red box instead of crashing.
    except Exception as e:
        st.error(f"Error calculating spread: {e}")


# ===================================================
# STEP 4: THE TABS UI & CONTEXTUAL EXPLANATIONS
# ===================================================
# Generate three distinct, clickable tabs at the top of the interface.
tab1, tab2, tab3 = st.tabs(["📉 Panic Pulse (T-Bills)", "📊 Recession Pulse (T-Notes)", "🏛️ Structural Pulse (T-Bonds)"])

# Execute the following UI layout ONLY when the user is viewing Tab 1.
with tab1:
    
    # Render the section header.
    st.subheader("Ultra-Short Liquidity (1M to 1Y)")
    
    # Define the specific educational context for this tab to pass to the engine.
    tbill_desc = "**T-Bills (Treasury Bills):** Ultra-short-term debt maturing in 1 year or less (e.g., 1-Month, 3-Month). Because they are almost like cash, they measure immediate market liquidity and sudden panic."
    
    # Split the screen horizontally into two equal columns for the dropdown menus.
    col1, col2 = st.columns(2)
    
    with col1:
        # Render the Leg 1 dropdown using the T-Bill dictionary. Set default to index 1 (3-Month).
        b_leg1 = st.selectbox("Leg 1 (Longer):", list(tbill_options.keys()), index=1, key="b1") 
        
    with col2:
        # Render the Leg 2 dropdown using the T-Bill dictionary. Set default to index 0 (1-Month).
        b_leg2 = st.selectbox("Leg 2 (Shorter):", list(tbill_options.keys()), index=0, key="b2") 
        
    # Trigger the Master Chart Engine using the selected T-Bill variables and description.
    generate_spread_chart(b_leg1, b_leg2, tbill_options, tbill_desc)

# Execute the following UI layout ONLY when the user is viewing Tab 2.
with tab2:
    
    # Render the section header.
    st.subheader("Medium-Term Economic Outlook (2Y to 10Y)")
    
    # Define the specific educational context for this tab to pass to the engine.
    tnote_desc = "**T-Notes (Treasury Notes):** Medium-term debt maturing between 2 and 10 years. These form the benchmark for mortgages and corporate loans, tracking the main business cycle and recession fears."
    
    # Split the screen horizontally into two equal columns.
    col1, col2 = st.columns(2)
    
    with col1:
        # Render the Leg 1 dropdown using the T-Note dictionary. Set default to index 4 (10-Year).
        n_leg1 = st.selectbox("Leg 1 (Longer):", list(tnote_options.keys()), index=4, key="n1") 
        
    with col2:
        # Render the Leg 2 dropdown using the T-Note dictionary. Set default to index 0 (2-Year).
        n_leg2 = st.selectbox("Leg 2 (Shorter):", list(tnote_options.keys()), index=0, key="n2") 
        
    # Trigger the Master Chart Engine using the selected T-Note variables and description.
    generate_spread_chart(n_leg1, n_leg2, tnote_options, tnote_desc)

# Execute the following UI layout ONLY when the user is viewing Tab 3.
with tab3:
    
    # Render the section header.
    st.subheader("Long-Term Structural Debt (10Y to 30Y)")
    
    # Define the specific educational context for this tab to pass to the engine.
    tbond_desc = "**T-Bonds (Treasury Bonds):** Long-term debt maturing in 20 to 30 years. These measure Wall Street's deep, structural expectations for long-term inflation and economic growth."
    
    # Split the screen horizontally into two equal columns.
    col1, col2 = st.columns(2)
    
    with col1:
        # Render the Leg 1 dropdown using the T-Bond dictionary. Set default to index 2 (30-Year).
        bd_leg1 = st.selectbox("Leg 1 (Longer):", list(tbond_options.keys()), index=2, key="bd1") 
        
    with col2:
        # Render the Leg 2 dropdown using the T-Bond dictionary. Set default to index 0 (10-Year).
        bd_leg2 = st.selectbox("Leg 2 (Shorter):", list(tbond_options.keys()), index=0, key="bd2") 
        
    # Trigger the Master Chart Engine using the selected T-Bond variables and description.
    generate_spread_chart(bd_leg1, bd_leg2, tbond_options, tbond_desc)