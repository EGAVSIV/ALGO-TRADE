# ==========================================================
# UPSTOX STREAMLIT ALGO TRADING APP (OPTIONS – F&O)
# ==========================================================

import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime, timedelta

# ================= CONFIG =================
UPSTOX_BASE = "https://api.upstox.com/v2"
TOKEN_FILE = "token.txt"

st.set_page_config("Upstox Algo Trader", layout="wide", page_icon="⚡")

# ================= UTILITIES =================
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

# ================= DATA FETCH =================
def fetch_candles(token, instrument_key, interval="1minute", count=100):
    url = f"{UPSTOX_BASE}/historical-candle/intraday/{instrument_key}/{interval}"
    r = requests.get(url, headers=headers(token))
    data = r.json()["data"]["candles"][-count:]

    df = pd.DataFrame(data, columns=["time","open","high","low","close","volume"])
    df["time"] = pd.to_datetime(df["time"])
    return df

# ================= OPTION SELECTION =================
def select_atm_option(option_chain, spot, side="CE"):
    option_chain["diff"] = abs(option_chain["strike"] - spot)
    atm = option_chain.sort_values("diff").iloc[0]
    return atm["instrument_key"]

# ================= ORDER PLACE =================
def place_order(token, instrument_key, qty):
    payload = {
        "instrument_key": instrument_key,
        "quantity": qty,
        "order_type": "MARKET",
        "transaction_type": "BUY",
        "product": "MIS",
        "validity": "DAY"
    }
    r = requests.post(f"{UPSTOX_BASE}/order/place", headers=headers(token), json=payload)
    return r.json()

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

# ================= UI =================
st.title("⚡ Upstox Options Algo Trading Dashboard")

token = st.text_input("🔑 Upstox Access Token", value=load_token(), type="password")

if st.button("💾 Save Token"):
    save_token(token)
    st.success("Token saved")

if st.button("🧪 Test API"):
    ok, data = test_upstox(token)
    if ok:
        st.success("API Connected Successfully")
        st.json(data)
    else:
        st.error("Invalid Token")

st.divider()

# ================= ALGO SETTINGS =================
st.header("⚙️ Algo Settings")

symbols = st.multiselect(
    "Select F&O Stocks",
    ["NIFTY","BANKNIFTY","FINNIFTY","RELIANCE","INFY","TCS"],
    default=["NIFTY"]
)

htf_tf = st.selectbox("Trend Timeframe", ["5minute","15minute"])
ltf_tf = st.selectbox("Entry Timeframe", ["1minute","3minute"])

use_ema = st.checkbox("Activate EMA Pullback Algo", True)
use_bb = st.checkbox("Activate Bollinger Reversal Algo", True)

qty = st.number_input("Lot Quantity", 1, 100, 1)

st.divider()

# ================= RUN ALGO =================
if st.button("🚀 RUN ALGO (LIVE)"):
    st.info("Algo Started...")

    while True:
        for sym in symbols:
            try:
                spot_key = f"NSE_EQ|{sym}"

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
                    st.success(f"{sym} SIGNAL: {signal}")
                    # Option chain + ATM selection logic goes here
                    # place_order(token, atm_option_key, qty)

            except Exception as e:
                st.error(f"{sym} error: {e}")

        time.sleep(60)
