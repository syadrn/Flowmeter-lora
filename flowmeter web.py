import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

# Auto-refresh setiap 60 detik via cache ttl
DATA_URL = "https://script.google.com/macros/s/AKfycbyA9v5ZqUdatIoibb8bnO6SS7mbMdDvxTCI2-a4qIIO8CQ-5BvKDZXuhvT6vohxxcOB/exec"

@st.cache_data(ttl=60)
def fetch_data():
    try:
        res = requests.get(DATA_URL, timeout=15)
        if res.status_code == 200:
            data = res.json()
            # Asumsikan data adalah list of dict sesuai format yang diinginkan
            df = pd.DataFrame(data)
            # Rename/normalize columns if needed
            # Convert timestamp
            if "Server Timestamp" in df.columns:
                df["Server Timestamp"] = pd.to_datetime(df["Server Timestamp"], utc=True)
                df = df.sort_values("Server Timestamp")
            return df
        else:
            st.error(f"❌ Gagal ambil data. Status: {res.status_code}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error ambil data: {e}")
        return pd.DataFrame()

# === Layout ===
st.set_page_config(page_title="Monitoring Flowmeter", layout="wide")
st.title("📊 Monitoring Flowmeter")

# Auto-refresh setiap 60 detik
st_autorefresh(interval=40000, key="auto_refresh")


menu = st.sidebar.radio("Navigasi", ["Beranda", "Data Terkini", "Riwayat"])

df = fetch_data()
if df.empty:
    st.warning("⚠️ Tidak ada data yang bisa ditampilkan.")
    st.stop()

required_columns = [
    "Server Timestamp",
    "Avg Flow Rate (L/min)",
    "Std Flow Rate (L/min)",
    "Data Quality",
    "Device Type"
]
missing = [c for c in required_columns if c not in df.columns]
if missing:
    st.error("⚠️ Struktur data tidak sesuai. Kolom hilang: " + ", ".join(missing))
    st.write("Kolom yang ada:", df.columns.tolist())
    st.stop()

# Rename for easier access
df = df.rename(columns={
    "Server Timestamp": "Timestamp",
    "Avg Flow Rate (L/min)": "Avg_Flow_Rate",
    "Std Flow Rate (L/min)": "Std_Flow_Rate",
    "Data Quality": "Data_Quality",
    "Device Type": "Device_Type"
})
df["Timestamp"] = pd.to_datetime(df["Timestamp"], utc=True)
df = df.sort_values("Timestamp")

# === BERANDA ===
if menu == "Beranda":
    st.markdown("""
    Sistem ini menampilkan data flowmeter yang dikirim ke Google Sheets melalui Web Apps.  
    Data otomatis diperbarui setiap 60 detik (cache).  
    """)
    st.markdown("### Ringkasan Terakhir")
    latest = df.iloc[-1]
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Avg Flow Rate (L/min)", latest["Avg_Flow_Rate"])
    col2.metric("Std Flow Rate (L/min)", latest["Std_Flow_Rate"])
    col3.metric("Data Quality", latest["Data_Quality"])
    col4.metric("Device Type", latest["Device_Type"])
    col5.metric("Waktu Server", latest["Timestamp"].strftime("%Y-%m-%d %H:%M:%S UTC"))

# === DATA TERKINI ===
elif menu == "Data Terkini":
    latest = df.iloc[-1]
    st.subheader("📌 Data Flowmeter Terkini")
    st.markdown(f"**Waktu Server:** {latest['Timestamp'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Avg Flow Rate (L/min)", latest["Avg_Flow_Rate"])
    col2.metric("Std Flow Rate (L/min)", latest["Std_Flow_Rate"])
    col3.metric("Data Quality", latest["Data_Quality"])
    col4.metric("Device Type", latest["Device_Type"])

    st.markdown("### 📈 Grafik Sejarah Flow Rate")
    fig = make_subplots(rows=1, cols=2, subplot_titles=["Avg Flow Rate", "Std Flow Rate"])
    fig.add_trace(go.Scatter(x=df["Timestamp"], y=df["Avg_Flow_Rate"], name="Avg Flow Rate"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["Timestamp"], y=df["Std_Flow_Rate"], name="Std Flow Rate"), row=1, col=2)
    fig.update_layout(height=500, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# === RIWAYAT ===
elif menu == "Riwayat":
    st.subheader("📅 Lihat Data Berdasarkan Tanggal")
    tanggal = st.date_input("Pilih tanggal", datetime.utcnow().date())
    # Filter by date in UTC
    data_filter = df[df["Timestamp"].dt.date == tanggal]

    if data_filter.empty:
        st.warning("⚠️ Tidak ada data di tanggal tersebut.")
    else:
        st.dataframe(data_filter.reset_index(drop=True))
        st.markdown("### 📈 Grafik Flow Rate pada Tanggal Terpilih")
        fig = make_subplots(rows=1, cols=2, subplot_titles=["Avg Flow Rate", "Std Flow Rate"])
        fig.add_trace(go.Scatter(x=data_filter["Timestamp"], y=data_filter["Avg_Flow_Rate"], name="Avg Flow Rate"), row=1, col=1)
        fig.add_trace(go.Scatter(x=data_filter["Timestamp"], y=data_filter["Std_Flow_Rate"], name="Std Flow Rate"), row=1, col=2)
        fig.update_layout(height=500, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### 📊 Statistik Harian (Rata-rata)")
        daily_stats = data_filter.set_index("Timestamp").resample("D").agg({
            "Avg_Flow_Rate": "mean",
            "Std_Flow_Rate": "mean"
        }).reset_index()
        display = daily_stats.rename(columns={
            "Timestamp": "Tanggal",
            "Avg_Flow_Rate": "Rata-rata Avg Flow Rate (L/min)",
            "Std_Flow_Rate": "Rata-rata Std Flow Rate (L/min)"
        })
        st.dataframe(display)

        st.download_button(
            "⬇️ Unduh Data CSV",
            data=data_filter.to_csv(index=False),
            file_name="flowmeter_history.csv",
            mime="text/csv"
        )
