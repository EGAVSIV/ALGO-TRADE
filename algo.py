# ==========================================================
# UPSTOX STREAMLIT ALGO TRADING APP (OPTIONS – F&O)
# ==========================================================

import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime

# ================= STREAMLIT CONFIG =================
st.set_page_config(
    page_title="Upstox Algo Trader",
    layout="wide",
    page_icon="⚡"
)

st.title("⚡ Upstox Options Algo Trading Dashboard")

# ================= CONFIG =================
UPSTOX_BASE = "https://api.upstox.com/v2"
TOKEN_FILE = "token.txt"

# ================= INSTRUMENT MAP =================
INSTRUMENT_MAP = {
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
    "RELIANCE": "NSE_EQ|RELIANCE",
    "INFY": "NSE_EQ|INFY",
    "TCS": "NSE_EQ|TCS"
}

# ================= TOKEN UTIL =================
def save_token(token):
    with open(TOKEN_FILE, "w") as f:
        f.write(token)

def load_token():
    try:
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    except:
        return ""

def headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

# ================= API TEST =================
def test_upstox(token):
    r = requests.get(f"{UPSTOX_BASE}/user/profile", headers=headers(token))
    return r.status_code == 200, r.json()

# ================= INDICATORS =================
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def bollinger(df, period=20):
    ma = df["close"].rolling(period).mean()
    std = df["close"].rolling(period).std()
    df["bb_upper"] = ma + 2 * std
    df["bb_lower"] = ma - 2 * std
    return df

# ================= SAFE CANDLE FETCH =================
def fetch_candles(token, instrument_key, interval="1minute", count=100):
    url = f"{UPSTOX_BASE}/historical-candle/intraday/{instrument_key}/{interval}"
    r = requests.get(url, headers=headers(token), timeout=10)

    if r.status_code != 200:
        raise Exception(f"HTTP {r.status_code}")

    j = r.json()

    if "data" not in j or "candles" not in j["data"]:
        raise Exception(f"No candle data returned")

    candles = j["data"]["candles"][-count:]

    df = pd.DataFrame(
        candles,
        columns=["time", "open", "high", "low", "close", "volume"]
    )
    df["time"] = pd.to_datetime(df["time"])
    return df

# ================= ALGO LOGIC =================
def algo_ema_pullback(htf, ltf):
    prev = ltf.iloc[-2]
    curr = ltf.iloc[-1]

    if htf["ema20"].iloc[-1] > htf["ema50"].iloc[-1]:
        if prev.close < prev.ema20 and curr.close > curr.ema20:
            return "BUY_CE"
        if prev.close < prev.ema50 and curr.close > curr.ema50:
            return "BUY_CE"

    if htf["ema20"].iloc[-1] < htf["ema50"].iloc[-1]:
        if prev.close > prev.ema20 and curr.close < curr.ema20:
            return "BUY_PE"
        if prev.close > prev.ema50 and curr.close < curr.ema50:
            return "BUY_PE"

    return None

def algo_bb_reversal(df):
    prev = df.iloc[-2]
    curr = df.iloc[-1]

    if prev.close < prev.bb_lower and curr.close > curr.bb_lower:
        return "BUY_CE"
    if prev.close > prev.bb_upper and curr.close < curr.bb_upper:
        return "BUY_PE"

    return None

# ================= SESSION STATE =================
if "run_algo" not in st.session_state:
    st.session_state.run_algo = False

# ================= TOKEN UI =================
token = st.text_input(
    "🔑 Upstox Access Token",
    value=load_token(),
    type="password"
)

col1, col2 = st.columns(2)

with col1:
    if st.button("💾 Save Token"):
        save_token(token)
        st.success("Token saved")

with col2:
    if st.button("🧪 Test API"):
        ok, data = test_upstox(token)
        if ok:
            st.success("API Connected Successfully")
        else:
            st.error("Invalid Token")

st.divider()

# ================= ALGO SETTINGS =================
st.header("⚙️ Algo Settings")

symbols = st.multiselect(
    "Select F&O Symbols",
    list(INSTRUMENT_MAP.keys()),
    default=["NIFTY"]
)

htf_tf = st.selectbox("Trend Timeframe", ["5minute", "15minute"])
ltf_tf = st.selectbox("Entry Timeframe", ["1minute", "3minute"])

use_ema = st.checkbox("Activate EMA Pullback Algo", True)
use_bb = st.checkbox("Activate Bollinger Reversal Algo", True)

qty = st.number_input("Lot Quantity", 1, 100, 1)

st.divider()

# ================= CONTROL BUTTONS =================
col1, col2 = st.columns(2)

with col1:
    if st.button("🚀 START ALGO"):
        st.session_state.run_algo = True

with col2:
    if st.button("🛑 STOP ALGO"):
        st.session_state.run_algo = False

# ================= RUN ALGO =================
if st.session_state.run_algo:
    st.info("Algo Running... (refreshes every 60 seconds)")

    for sym in symbols:
        try:
            spot_key = INSTRUMENT_MAP[sym]

            htf = fetch_candles(token, spot_key, htf_tf)
            ltf = fetch_candles(token, spot_key, ltf_tf)

            htf["ema20"] = ema(htf.close, 20)
            htf["ema50"] = ema(htf.close, 50)

            ltf["ema20"] = ema(ltf.close, 20)
            ltf["ema50"] = ema(ltf.close, 50)

            ltf = bollinger(ltf)

            signal = None

            if use_ema:
                signal = algo_ema_pullback(htf, ltf)

            if not signal and use_bb:
                signal = algo_bb_reversal(ltf)

            if signal:
                st.success(f"📌 {sym} SIGNAL → {signal}")
            else:
                st.write(f"{sym}: No Signal")

        except Exception as e:
            st.error(f"{sym} error: {e}")

    time.sleep(60)
    st.rerun()
