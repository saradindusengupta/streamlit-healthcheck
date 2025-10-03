import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_squared_error
import numpy as np
from streamlit_healthcheck.healthcheck import StreamlitPageMonitor, HealthCheckService, health_check


@StreamlitPageMonitor.monitor_page("regression_analysis")
def regression_analysis():
    # Set page config
    st.set_page_config(
        page_title="Regression Analysis",
        page_icon="📈",
        layout="wide"
    )

    st.title("📈 Air Quality Regression Analysis")
    st.markdown("### Analyze relationships between parameters using regression")

    # Read CSV file from data directory
    data_path = os.path.join("/home/saradindu/dev/streamlit-healthcheck/data")
    csv_files = [f for f in os.listdir(data_path) if f.endswith('.csv')]

    if not csv_files:
        st.error("No CSV files found in the data directory!")
        return

    selected_file = st.selectbox(
        "Select monitoring station data file",
        csv_files,
        help="Choose the CSV file containing air pollution measurements"
    )

    try:
        # Read and process the data
        df = pd.read_csv(os.path.join(data_path, selected_file))

        # Handle missing values
        initial_rows = len(df)

        # Show missing value information
        missing_info = df.isnull().sum()
        if missing_info.any():
            st.sidebar.markdown("### Missing Values")
            st.sidebar.dataframe(missing_info[missing_info > 0])

            handling_method = st.sidebar.radio(
                "Handle missing values by:",
                ["Drop rows", "Fill with mean", "Fill with median"],
                help="Choose how to handle missing values in the dataset"
            )

            if handling_method == "Drop rows":
                df = df.dropna()
            elif handling_method == "Fill with mean":
                df = df.fillna(df.mean())
            else:  # Fill with median
                df = df.fillna(df.median())

            rows_affected = initial_rows - len(df)
            if rows_affected > 0:
                st.warning(f"Handled {rows_affected} rows with missing values ({(rows_affected/initial_rows)*100:.1f}% of data)")

        # Process timestamp
        time_columns = ['year', 'month', 'day', 'hour']
        if all(col in df.columns for col in time_columns):
            df['timestamp'] = pd.to_datetime(
                df[['year', 'month', 'day', 'hourss']].assign(minute=0),
                format='%Y%m%d%H'
            )

            # Data processing
            df = df.drop(columns=time_columns)
            if df.columns[0] == 'No' or df.columns[0].isdigit():
                df = df.drop(columns=[df.columns[0]], errors='ignore')

            numeric_columns = df.select_dtypes(include=['float64', 'int64']).columns

            # Regression Analysis Options
            st.sidebar.header("Regression Options")
            regression_type = st.sidebar.selectbox(
                "Select Regression Type",
                ["Simple Regression", "Multiple Regression"]
            )

            if regression_type == "Simple Regression":
                st.markdown("### Simple Linear Regression")

                col1, col2 = st.columns(2)
                with col1:
                    dependent_var = st.selectbox("Select Dependent Variable (Y)", numeric_columns)
                with col2:
                    independent_var = st.selectbox("Select Independent Variable (X)", 
                                                 [col for col in numeric_columns if col != dependent_var])

                # Perform regression
                X = df[independent_var].values.reshape(-1, 1)
                y = df[dependent_var].values

                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

                model = LinearRegression()
                model.fit(X_train, y_train)

                # Create scatter plot with regression line
                fig = px.scatter(df, x=independent_var, y=dependent_var, 
                               title=f'Regression Analysis: {dependent_var} vs {independent_var}')

                # Add regression line
                x_range = np.linspace(X.min(), X.max(), 100).reshape(-1, 1)
                y_pred = model.predict(x_range)

                fig.add_trace(go.Scatter(x=x_range.flatten(), y=y_pred, 
                                       mode='lines', name='Regression Line',
                                       line=dict(color='red')))

                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)

                # Display regression statistics
                y_pred_test = model.predict(X_test)
                r2 = r2_score(y_test, y_pred_test)
                rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("R² Score", f"{r2:.3f}")
                with col2:
                    st.metric("RMSE", f"{rmse:.3f}")
                with col3:
                    st.metric("Coefficient", f"{model.coef_[0]:.3f}")

            else:  # Multiple Regression
                st.markdown("### Multiple Linear Regression")

                dependent_var = st.selectbox("Select Dependent Variable (Y)", numeric_columns)
                independent_vars = st.multiselect(
                    "Select Independent Variables (X)",
                    [col for col in numeric_columns if col != dependent_var],
                    default=[col for col in numeric_columns if col != dependent_var][:2]
                )

                if len(independent_vars) > 0:
                    # Perform regression
                    X = df[independent_vars]
                    y = df[dependent_var]

                    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

                    model = LinearRegression()
                    model.fit(X_train, y_train)

                    # Display regression statistics
                    y_pred_test = model.predict(X_test)
                    r2 = r2_score(y_test, y_pred_test)
                    rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))

                    # Show results
                    st.markdown("#### Regression Results")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("R² Score", f"{r2:.3f}")
                    with col2:
                        st.metric("RMSE", f"{rmse:.3f}")

                    # Display coefficients
                    st.markdown("#### Model Coefficients")
                    coef_df = pd.DataFrame({
                        'Variable': independent_vars,
                        'Coefficient': model.coef_
                    })
                    st.dataframe(coef_df)

                    # Actual vs Predicted Plot
                    fig = px.scatter(x=y_test, y=model.predict(X_test),
                                   labels={'x': 'Actual Values', 'y': 'Predicted Values'},
                                   title='Actual vs Predicted Values')

                    # Add 45-degree line
                    fig.add_trace(go.Scatter(
                        x=[y_test.min(), y_test.max()],
                        y=[y_test.min(), y_test.max()],
                        mode='lines',
                        name='Perfect Prediction',
                        line=dict(color='red', dash='dash')
                    ))

                    fig.update_layout(height=500)
                    st.plotly_chart(fig, use_container_width=True)

        else:
            st.error("Required time columns (year, month, day, hour) not found in the data!")

    except Exception as e:
        st.error(f"Error reading or processing the file: {str(e)}")
        raise
    # Add footer
    st.markdown("---")
    st.markdown("*Data source: Kaggle | Regression Analysis Page*")
    
if __name__ == "__main__":
    regression_analysis()