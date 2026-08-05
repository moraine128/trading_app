# indicators_aggressive.py - VOLLSTÄNDIG KORRIGIERT
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator, SMAIndicator, EMAIndicator
from ta.volatility import BollingerBands

def add_indicators(df):
    if not isinstance(df, pd.DataFrame): raise ValueError("Input muss ein DataFrame sein")
    df = df.copy().ffill().bfill()
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        if col in df.columns: df[col] = df[col].astype(float)
    try:
        df['SMA_200'] = SMAIndicator(close=df['Close'], window=200).sma_indicator()
        df['RSI'] = RSIIndicator(close=df['Close'], window=14).rsi()
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['ADX'] = ADXIndicator(high=df['High'], low=df['Low'], close=df['Close'], window=14, fillna=True).adx()
        bb = BollingerBands(close=df['Close'], window=20, window_dev=2)
        df['BB_High'] = bb.bollinger_hband()
        df['BB_Low'] = bb.bollinger_lband()
        df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
                
        # ===== NEUE ERWEITERTE INDIKATOREN =====
        # Money Flow Index (MFI) - Volume-gewichteter RSI
        typical_price = (df['High'] + df['Low'] + df['Close']) / 3
        money_flow = typical_price * df['Volume']
        positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0)
        negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0)
        positive_mf = positive_flow.rolling(window=14).sum()
        negative_mf = negative_flow.rolling(window=14).sum()
        mfi_ratio = positive_mf / negative_mf
        df['MFI'] = 100 - (100 / (1 + mfi_ratio))
        
        # ATR für Position Sizing
        high_low = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close = (df['Low'] - df['Close'].shift()).abs()
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df['ATR'] = true_range.rolling(window=14).mean()
        
        # Volume-Analyse
        df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA']
        
        # Trendstärke mit SMA
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['Trend_Slope'] = (df['SMA_200'] - df['SMA_200'].shift(20)) / df['SMA_200'].shift(20)
        
        # Volatility-basierte Exits
        df['BB_Width'] = (df['BB_High'] - df['BB_Low']) / df['Close']
        df['Volatility_Regime'] = 'normal'
        df.loc[df['BB_Width'] > df['BB_Width'].rolling(50).quantile(0.75), 'Volatility_Regime'] = 'high'
        df.loc[df['BB_Width'] < df['BB_Width'].rolling(50).quantile(0.25), 'Volatility_Regime'] = 'low'
        df = df.replace([np.inf, -np.inf], np.nan).fillna(0)
    except Exception as e:
        print(f"⚠️ Indikator-Fehler: {e}")
    return df

def get_signal_details(df):
    if df is None or df.empty or len(df) < 200:
        return {"is_buy": False, "score": 0, "strength": "❌ Datenmangel", "signals": [], "bb_position": "N/A", "volume_ratio": 0.0}
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    score = 0
    signals = []
    
    # Logik
    trend_bullish = latest['Close'] > latest['SMA_200']
    if trend_bullish: score += 2; signals.append("📈 Trend Bullish")
    else: score -= 2; signals.append("📉 Trend Bearish")
    
    if latest['ADX'] > 20: score += 1
        
    # ===== NEUE FILTER =====
    # Volume Filter
    from settings_aggressive import MIN_AVG_VOLUME, VOLUME_SPIKE_THRESHOLD, USE_TREND_FILTER, TREND_SLOPE_MIN
    
    avg_volume = latest.get('Volume_SMA', 0)
    if avg_volume < MIN_AVG_VOLUME:
        return {"is_buy": False, "score": 0, "strength": "❌ Low Liquidity", "signals": [], "bb_position": "N/A", "volume_ok": False}
    
    volume_ratio = latest.get('Volume_Ratio', 0)
    if volume_ratio < VOLUME_SPIKE_THRESHOLD:
        score -= 1  # Reduziere Score bei schwachem Volumen
    else:
        score += 1
        signals.append("📈 Volume Spike")
    
    # Trendfilter
    if USE_TREND_FILTER:
        trend_slope = latest.get('Trend_Slope', 0)
        if trend_slope < TREND_SLOPE_MIN:
            return {"is_buy": False, "score": 0, "strength": "❌ Kein Aufwärtstrend", "signals": [], "bb_position": "N/A", "trend_ok": False}
        else:
            score += 1
            signals.append("📈 Starker Trend")
    
    # MFI Check (Money Flow Index)
    mfi = latest.get('MFI', 50)
    if mfi < 30:
        score += 2
        signals.append("💰 MFI Oversold")
    elif mfi > 70:
        score -= 2
        signals.append("⚠️ MFI Overbought")
    
    rsi = latest['RSI']
    if 30 <= rsi <= 50 and trend_bullish: score += 3; signals.append("💎 Dip")
    elif rsi < 30: score += 2; signals.append("🟢 RSI < 30")
    elif rsi > 70: score = 0; signals.append("⛔ RSI > 70")

    if prev['MACD'] < prev['MACD_Signal'] and latest['MACD'] > latest['MACD_Signal']:
        score += 2; signals.append("⚡ MACD Cross")

    # BB & Volume Berechnung für Anzeige
    bb_pos = "N/A"
    bb_range = latest['BB_High'] - latest['BB_Low']
    if bb_range > 0:
        bb_pos = f"{((latest['Close'] - latest['BB_Low']) / bb_range * 100):.0f}%"
    
    vol_ratio = float(latest['Volume'] / latest['Volume_SMA']) if latest['Volume_SMA'] > 0 else 0.0

    return {
        "is_buy": score >= 6,
        "score": int(score),
        "strength": "🚀 BUY" if score >= 6 else "HOLD",
        "signal_type": "BUY" if score >= 6 else "WAIT",
        "signals": signals,
        "reason": " | ".join(signals[:3]),
        "rsi": float(rsi),
        "macd_signal": f"{latest['MACD']:.2f}",
        "last_price": float(latest['Close']),
        "adx": float(latest['ADX']),
        "sma_200": float(latest['SMA_200']),
        "bb_position": bb_pos,
        "volume_ratio": vol_ratio
    }
