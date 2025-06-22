import streamlit as st
import pandas as pd
import plotly.express as px
import json
from sqlalchemy import create_engine
import urllib.parse


# ----------------------------
# Load DB credentials securely
# ----------------------------

def load_db_config(path="config/db_config.json"):
    with open(path, "r") as file:
        return json.load(file)

# ----------------------------
# Create SQLAlchemy engine
# ----------------------------

def create_db_engine():
    config = load_db_config()
    user = config["user"]
    encoded_password = urllib.parse.quote_plus(config['password'])
    host = config["host"]
    database = config["database"]
    return create_engine(f"mysql+pymysql://{user}:{encoded_password}@{host}/{database}")
# ----------------------------
# Load data from database
# ----------------------------
def load_data():
    engine = create_db_engine()
    sales_df = pd.read_sql("SELECT * FROM sales", engine)
    customers_df = pd.read_sql("SELECT * FROM customers", engine)
    inventory_df = pd.read_sql("SELECT * FROM inventory", engine)
    return sales_df, customers_df, inventory_df

# ----------------------------
# Streamlit App Layout
# ----------------------------
st.set_page_config(layout="wide", page_title="Retail Sales Dashboard")
st.title("🛍️ Retail Analytics Dashboard")

sales, customers, inventory = load_data()

# Sidebar Filters
st.sidebar.header("🔍 Filter Options")
category_filter = st.sidebar.multiselect(
    "Select Product Category:",
    options=inventory["category"].unique(),
    default=inventory["category"].unique(),
)

# Merge sales with inventory
merged = pd.merge(sales, inventory, on="productid")
merged = pd.merge(merged, customers, on="customerid")
merged = merged[merged["category"].isin(category_filter)]

# KPI Section
st.subheader("Key Metrics")
total_revenue = (merged["quantitypurchased"] * merged["price_x"]).sum()
total_orders = merged["transactionid"].nunique()
total_customers = merged["customerid"].nunique()
col1, col2, col3 = st.columns(3)
col1.metric("Total Revenue", f"${total_revenue:,.2f}")
col2.metric("Total Orders", total_orders)
col3.metric("Unique Customers", total_customers)

# Product Performance
st.subheader("Top & Bottom Performing Products")
product_perf = merged.groupby("productname").agg(
    total_units_sold=("quantitypurchased", "sum"),
    total_revenue=("price_x", lambda x: (x * merged.loc[x.index, "quantitypurchased"]).sum())
).reset_index()

col1, col2 = st.columns(2)
col1.plotly_chart(px.bar(product_perf.sort_values("total_units_sold", ascending=False).head(10),
                         x="productname", y="total_units_sold", title="Top 10 Products by Units Sold"))

col2.plotly_chart(px.bar(product_perf.sort_values("total_units_sold").head(10),
                         x="productname", y="total_units_sold", title="Bottom 10 Products by Units Sold"))

# Customer Segmentation
st.subheader("Customer Segmentation")
cust_seg = merged.groupby("customerid").agg(
    total_orders=("transactionid", "count"),
    total_spent=("price_x", lambda x: (x * merged.loc[x.index, "quantitypurchased"]).sum()),
    age=("age", "first"),
    gender=("gender", "first"),
    location=("location", "first")
).reset_index()


st.plotly_chart(px.scatter(cust_seg, x="total_orders", y="total_spent", color="gender",
                           hover_data=["location"], title="Customer Spend vs Order Frequency"))

st.subheader("📌 Customer Segments by Frequency")

# Segmenting customers based on number of orders
customer_segments = sales.groupby("customerid").agg(
    total_orders=('transactionid', 'count')
).reset_index()

customer_segments["customer_segment"] = customer_segments["total_orders"].apply(
    lambda x: "Inactive" if x == 0 else
              "Low" if x <= 5 else
              "Medium" if x <= 7  else "High"
)

# Show in Streamlit
#st.dataframe(customer_segments)

# Visual
# Bar chart for distribution
segment_counts = customer_segments["customer_segment"].value_counts().reset_index()
segment_counts.columns = ["Segment", "Count"]

fig = px.bar(segment_counts, x="Segment", y="Count", color="Segment",
             title="Customer Segments by Frequency", text="Count")

st.plotly_chart(fig)


repeat_customers = sales.groupby("customerid").agg(
    active_days=('transactiondate', lambda x: x.dt.date.nunique())
).reset_index()

repeat_customers = repeat_customers[repeat_customers["active_days"] > 1]

# Show table
#st.dataframe(repeat_customers.sort_values(by="active_days", ascending=False))

# Visual
fig_repeat = px.histogram(repeat_customers, x="active_days", nbins=20,
                          title="Distribution of Active Purchase Days")
st.plotly_chart(fig_repeat)


# Loyalty View
st.subheader("🎯 Customer Loyalty")
loyalty_df = sales.copy()
loyalty_df["transactiondate"] = pd.to_datetime(loyalty_df["transactiondate"])
repeat = loyalty_df.groupby("customerid").agg(
    days_active=("transactiondate", lambda x: x.dt.date.nunique()),
    total_orders=("transactionid", "count")
).reset_index()

st.plotly_chart(px.scatter(repeat, x="days_active", y="total_orders",
                           title="Customer Loyalty: Active Days vs Orders", trendline="ols"))

# Monthly Revenue Trend
st.subheader("📅 Monthly Revenue Trend")

# Ensure date is in datetime format
sales["transactiondate"] = pd.to_datetime(sales["transactiondate"])

# Create month column as string
sales["month"] = sales["transactiondate"].dt.to_period("M").astype(str)

# Calculate monthly revenue
monthly = sales.groupby("month").apply(
    lambda x: (x["quantitypurchased"] * x["price"]).sum()
).reset_index(name="monthly_revenue")

# Plot
st.plotly_chart(
    px.line(monthly, x="month", y="monthly_revenue", markers=True,
            title="Monthly Revenue Trend")
)
