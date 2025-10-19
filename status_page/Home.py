import streamlit as st
import pandas as pd
import plotly.express as px
import os
from streamlit_healthcheck.healthcheck import StreamlitPageMonitor

"""
Place this at the top of your Streamlit app, before any error monitoring or decorator usage to ensure the sqlite
database is created properly at the specified path otherwise it will default to a temp directory. The temp directory
will be `~/local/share/streamlit-healthcheck/streamlit_page_errors.db`.

Example:

>>> StreamlitPageMonitor(db_path="/home/saradindu/dev/streamlit_page_errors.db")

"""
@StreamlitPageMonitor.monitor_page("air_pollution_dashboard")
def air_pollution_dashboard():
    # Set page config
    st.set_page_config(
        page_title="Air Pollution Dashboard",
        page_icon="🌬️",
        layout="wide"
    )

    # Add custom CSS
    st.markdown("""
        <style>
        .main {
            padding: 2rem;
        }
        .stPlotlyChart {
            background-color: #f0f2f6;
            border-radius: 10px;
            padding: 1rem;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("🌬️ Air Pollution Monitoring Dashboard")
    st.markdown("### Real-time visualization of air quality parameters")

    # Read CSV file from data directory
    data_path = os.path.join("/home/saradindu/dev/streamlit-healthcheck/data")
    csv_files = [f for f in os.listdir(data_path) if f.endswith('.csv')]

    if not csv_files:
        st.error("No CSV files found in the data directory!")
    else:
        # File selector with description
        selected_file = st.selectbox(
            "Select monitoring station data file",
            csv_files,
            help="Choose the CSV file containing air pollution measurements"
        )
        try:
            # Read the CSV file
            df = pd.read_csv(os.path.join(data_path, selected_file))
            
            # Combine year, month, day, hour columns into timestamp
            time_columns = ['year', 'month', 'day', 'hour']
            if all(col in df.columns for col in time_columns):
                df['timestamp'] = pd.to_datetime(
                    df[['year', 'month', 'day', 'hour']].assign(minute=0),
                    format='%Y%m%d%H'
                )
                
                # Drop individual time columns
                df = df.drop(columns=time_columns)
                # Remove the first column if it is an index or 'No'
                if df.columns[0] == 'No' or df.columns[0].isdigit():
                    df = df.drop(columns=[df.columns[0]], errors='ignore')
                # Set timestamp as the first column
                cols = ['timestamp'] + [col for col in df.columns if col != 'timestamp']
                df = df[cols]
                
                # Get numeric columns excluding the timestamp
                numeric_columns = df.select_dtypes(include=['float64', 'int64']).columns
                
                # Add date range selector
                col1, col2 = st.columns(2)
                with col1:
                    start_date = st.date_input("Start Date", df['timestamp'].min())
                with col2:
                    end_date = st.date_input("End Date", df['timestamp'].max())
                    
                # Filter data based on date range
                mask = (df['timestamp'].dt.date >= start_date) & (df['timestamp'].dt.date <= end_date)
                filtered_df = df.loc[mask]
                
                # Display basic statistics
                st.markdown("### 📊 Summary Statistics")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Time Period", f"{(end_date - start_date).days} days")
                with col2:
                    st.metric("Total Measurements", len(filtered_df))
                with col3:
                    st.metric("Parameters", len(numeric_columns))
                
                # Create plots for each pollutant
                st.markdown("### 📈 Pollution Parameters Over Time")
                for column in numeric_columns:
                    fig = px.line(
                        filtered_df, 
                        x='timestamp', 
                        y=column,
                        title=f"{column} Concentration Over Time",
                        template="plotly_white"
                    )
                    
                    # Update layout for better visualization
                    fig.update_layout(
                        xaxis_title="Time",
                        yaxis_title=f"Concentration ({column})",
                        hovermode='x unified',
                        showlegend=True,
                        height=400,
                        title_x=0.5,
                        title_font_size=16
                    )
                    
                    # Add range slider
                    fig.update_xaxes(rangeslider_visible=True)
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Display summary statistics for each parameter
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric(f"{column} Mean", f"{filtered_df[column].mean():.2f}")
                    with col2:
                        st.metric(f"{column} Max", f"{filtered_df[column].max():.2f}")
                    with col3:
                        st.metric(f"{column} Min", f"{filtered_df[column].min():.2f}")
                    with col4:
                        st.metric(f"{column} Std Dev", f"{filtered_df[column].std():.2f}")
            else:
                st.error("Required time columns (year, month, day, hour) not found in the data!")
                
        except Exception as e:
            st.error(f"Error reading or processing the file: {str(e)}")

    # Add footer
    st.markdown("---")
    st.markdown("*Data source: Kaggle*")
if __name__ == "__main__":
    air_pollution_dashboard()