import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import streamlit as st
import pandas as pd
from streamlit_healthcheck.healthcheck import StreamlitPageMonitor, HealthCheckService, health_check


@StreamlitPageMonitor.monitor_page("detailed_analysis")
def detailed_analysis():

    # Set page config
    st.set_page_config(
        page_title="Detailed Analysis",
        page_icon="📊",
        layout="wide"
    )

    st.title("📊 Detailed Air Quality Analysis")
    st.markdown("### In-depth analysis of air quality parameters")

    # Read CSV file from data directory
    data_path = os.path.join("/home/saradindu/dev/streamlit-healthcheck/data")
    csv_files = [f for f in os.listdir(data_path) if f.endswith('.csv')]

    if not csv_files:
        st.error("No CSV files found in the data directory!")
    else:
        selected_file = st.selectbox(
            "Select monitoring station data file",
            csv_files,
            help="Choose the CSV file containing air pollution measurements"
        )

        try:
            # Read the CSV file
            df = pd.read_csv(os.path.join(data_path, selected_file))

            # Process timestamp
            time_columns = ['year', 'month', 'day', 'hour']
            if all(col in df.columns for col in time_columns):
                df['timestamp'] = pd.to_datetime(
                    df[['year', 'month', 'day', 'hour']].assign(minute=0),
                    format='%Y%m%d%H'
                )

                # Data processing
                df = df.drop(columns=time_columns)
                if df.columns[0] == 'No' or df.columns[0].isdigit():
                    df = df.drop(columns=[df.columns[0]], errors='ignore')

                numeric_columns = df.select_dtypes(include=['float64', 'int64']).columns

                # Analysis Options
                st.sidebar.header("Analysis Options")
                analysis_type = st.sidebar.selectbox(
                    "Select Analysis Type",
                    ["Time Series", "Correlation Analysis", "Distribution Analysis"]
                )

                if analysis_type == "Time Series":
                    # Multi-parameter comparison
                    st.markdown("### Multi-Parameter Comparison")
                    selected_params = st.multiselect(
                        "Select parameters to compare",
                        numeric_columns,
                        default=list(numeric_columns)[:2]
                    )

                    if selected_params:
                        fig = go.Figure()
                        for param in selected_params:
                            fig.add_trace(go.Scatter(
                                x=df['timestamp'],
                                y=df[param],
                                name=param,
                                mode='lines'
                            ))
                        fig.update_layout(
                            title="Parameter Comparison Over Time",
                            xaxis_title="Time",
                            yaxis_title="Concentration",
                            height=600
                        )
                        st.plotly_chart(fig, use_container_width=True)

                elif analysis_type == "Correlation Analysis":
                    st.markdown("### Parameter Correlations")
                    corr_matrix = df[numeric_columns].corr()
                    fig = px.imshow(
                        corr_matrix,
                        title="Correlation Matrix",
                        color_continuous_scale="RdBu",
                        aspect="auto"
                    )
                    st.plotly_chart(fig, use_container_width=True)

                elif analysis_type == "Distribution Analysis":
                    st.markdown("### Parameter Distributions")
                    selected_param = st.selectbox("Select parameter", numeric_columns)

                    fig = go.Figure()
                    fig.add_trace(go.Histogram(
                        x=df[selected_param],
                        name="Distribution",
                        nbinsx=30
                    ))
                    fig.update_layout(
                        title=f"Distribution of {selected_param}",
                        xaxis_title=selected_param,
                        yaxis_title="Frequency",
                        height=400
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # Add basic statistics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Mean", f"{df[selected_param].mean():.2f}")
                    with col2:
                        st.metric("Median", f"{df[selected_param].median():.2f}")
                    with col3:
                        st.metric("Std Dev", f"{df[selected_param].std():.2f}")
                    with col4:
                        st.metric("IQR", f"{df[selected_param].quantile(0.75) - df[selected_param].quantile(0.25):.2f}")

            else:
                st.error("Required time columns (year, month, day, hour) not found in the data!")

        except Exception as e:
            st.error(f"Error reading or processing the file: {str(e)}")

    # Add footer
    st.markdown("---")
    st.markdown("*Data source: Kaggle | Detailed Analysis Page*")
if __name__ == "__main__":
    detailed_analysis()