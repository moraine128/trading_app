# settings_aggressive.py – Aggressive Trading-Konfiguration

# ===== PORTFOLIO SETTINGS =====
MAX_POSITION_SIZE = 100           # Max 100 Position pro Ticker
MAX_TOTAL_POSITIONS = 10  # Max 10 offene Positionen gesamt (mehr Trades)
MAX_PORTFOLIO_VALUE = 50000  # Max €10.000 Gesamt-Investition
MAX_POSITIONS_PCT = 0.9*MAX_PORTFOLIO_VALUE       # ausrechnen

# ===== SCAN SETTINGS =====
CHECK_INTERVAL_HOURS = 0.1  # Alle 4 Stunden (weniger Scans = weniger Trades)LOOKBACK_PERIOD = "30d"      # 30 Tage Historydaten
LOOKBACK_PERIOD = "90d"     # 90 Tage Historydaten (mehr Daten = stabilere Signale)
LOOKBACK_INTERVAL = "1h"    # 1-Stunden Kerzen (weniger Rauschen als 5min)
# ===== AUTO-TRADE SETTINGS =====
AUTO_TRADE_SCORE_THRESHOLD = 6  # Score >= 10 → AUTO-TRADE (höher = weniger, aber bessere Trades)# AUTO_TRADE_QUANTITY wird nicht verwendet - Quantity wird dynamisch basierend auf MAX_POSITION_PCT und Aktienkurs berechnet
# ===== EXIT SETTINGS (Take-Profit & Stop-Loss) =====
STOP_LOSS_PCT = 0.135 # -10% Stop-Loss (mehr Luft für Bewegung bei höheren Timeframes)
# ===== TRAILING STOP-LOSS =====
USE_TRAILING_STOP = True  # Trailing Stop aktivieren
TRAILING_STOP_ACTIVATION = 0.017  # Aktiviere Trailing erst ab +5% Gewinn (früher)
TRAILING_STOP_DISTANCE = 0.022  # Trail 4% unter Höchstkurs (enger)# ===== RISK MANAGEMENT =====
MAX_PORTFOLIO_RISK = 0.05  # Max 2% Risiko pro Trade
MAX_DRAWDOWN_LIMIT = 0.15  # Bot pausiert bei 15% Drawdown
MAX_PORTFOLIO_EXPOSURE = 0.90  # Max 90% des Kapitals investiert

# ===== VOLUME & LIQUIDITY FILTER =====
MIN_AVG_VOLUME = 100000  # Mindestens 100k durchschnittliches Volumen
VOLUME_SPIKE_THRESHOLD = 1.42  # Mindestens 1.4x durchschnittliches Volumen

# ===== TREND FILTER =====
USE_TREND_FILTER = False  # Nur Long-Trades im Aufwärtstrend
TREND_SMA_PERIOD = 14  # SMA-200 für Trendbestimmung
TREND_SLOPE_MIN = 0.001  # Minimale Steigung für Aufwärtstrend

# ===== COOLING PERIOD =====
COOLING_PERIOD_HOURS = 24  # Mindestens 24h zwischen Trades pro Symbol (verhindert Overtrading)

# ===== SIGNAL SCORE WEIGHTS (Aggressive) =====
# Diese Gewichte werden in indicators_aggressive.py verwendet
SIGNAL_WEIGHTS = {
    "rsi_extreme_down": 3,      # RSI < 20
    "rsi_strong_down": 3,       # RSI < 30
    "rsi_weak_down": 2,         # RSI < 40
    "macd_bullish_cross": 3,    # MACD Bullish Crossover
    "macd_bullish": 2,          # MACD > Signal
    "stoch_extreme_oversold": 3, # Stoch < 20
    "stoch_oversold": 3,        # Stoch < 30
    "stoch_bullish_cross": 2,   # Stoch Bullish Crossover
    "bb_oversold": 1,           # Price < Bollinger Low
    "ma_bullish": 1,            # EMA 9 > 21 > 50
    "candle_bullish": 1,        # Bullish Candle
    "volume_high": 1,           # High Volume
}

# ===== FILTER SETTINGS =====
MIN_SIGNAL_SCORE = 2  # Nur Signale mit Score >= 2 anzeigen
MIN_PRICE = 5.0       # Ignoriere Penny Stocks
MAX_SPREAD = 0.02     # Max 2% Bid-Ask Spread

# ===== MODE SETTINGS =====
TRADING_MODE = "PAPER"  # "PAPER" | "LIVE" | "DEMO"
# PAPER = Simulierte Trades (kein echtes Geld)
# LIVE = Echte Trades (mit echtem Geld)
# DEMO = Nur Signale, keine Trades

# ===== RISK MANAGEMENT =====
DAILY_LOSS_LIMIT = -500  # Stop-Trading wenn Daily Loss > 500€
EQUITY_STOP_LOSS = 0.20  # Stop-Trading wenn 20% Equity verloren

# ===== NOTIFICATION SETTINGS =====
SEND_ALERTS = True
ALERT_ON_TRADE = True
ALERT_ON_EXIT = True
ALERT_ON_SCORE_5_PLUS = True

# ===== DATABASE SETTINGS =====
DATABASE_PATH = "trading_data.db"

# ===== LOGGING =====
VERBOSE_MODE = True  # Detaillierte Terminal-Ausgabe
LOG_FILE = "trading_bot.log"

# ===== QUICK CONFIGS =====
# Nutze diese für schnelle Konfiguration:

CONFIGS = {
    "STANDARD": {
        "CHECK_INTERVAL_HOURS": 0.25,   # 15 min
        "LOOKBACK_INTERVAL": "5m",
        "TAKE_PROFIT_PCT": 0.03,        # +3%
        "STOP_LOSS_PCT": 0.02,          # -2%
        "AUTO_TRADE_SCORE_THRESHOLD": 5,
        "universe": "ALL",  # DAX + SP500
    },
    "AGGRESSIVE": {
        "CHECK_INTERVAL_HOURS": 0.166,  # 10 min
        "LOOKBACK_INTERVAL": "5m",
        "TAKE_PROFIT_PCT": 0.05,        # +5%
        "STOP_LOSS_PCT": 0.01,          # -1%
        "AUTO_TRADE_SCORE_THRESHOLD": 4,
        "universe": "DAX",  # Nur DAX
    },
        "AGGRESSIVE_MM": {
        "CHECK_INTERVAL_HOURS": 0.166,  # 10 min
        "LOOKBACK_INTERVAL": "5m",
        "TAKE_PROFIT_PCT": 0.08,        # +8%
        "STOP_LOSS_PCT": 0.03,          # -3%
        "AUTO_TRADE_SCORE_THRESHOLD": 6,
        "universe": "ALL",  # alle
    },
    "CONSERVATIVE": {
        "CHECK_INTERVAL_HOURS": 0.5,    # 30 min
        "LOOKBACK_INTERVAL": "15m",
        "TAKE_PROFIT_PCT": 0.02,        # +2%
        "STOP_LOSS_PCT": 0.03,          # -3%
        "AUTO_TRADE_SCORE_THRESHOLD": 6,
        "universe": "SP500",  # Nur S&P500
    },
    "SCALPING": {
        "CHECK_INTERVAL_HOURS": 0.0833, # 5 min
        "LOOKBACK_INTERVAL": "1m",
        "TAKE_PROFIT_PCT": 0.01,        # +1%
        "STOP_LOSS_PCT": 0.005,         # -0.5%
        "AUTO_TRADE_SCORE_THRESHOLD": 5,
        "universe": "ALL",  # Alle
    },
     "SMART_TREND": {
        "CHECK_INTERVAL_HOURS": 0.5,     # 30 min (mehr Scans)
        "LOOKBACK_INTERVAL": "5m",
        "TAKE_PROFIT_PCT": 0.135,          # +13.5% (höherer Gewinn)
        "STOP_LOSS_PCT": 0.05,             # -5% (enger SL)
        "AUTO_TRADE_SCORE_THRESHOLD": 6,   # Niedrigerer Threshold (mehr Trades)
        "universe": "ALL",
        "USE_TREND_FILTER": True,          # Nur Long wenn Preis > EMA 200
        "MAX_RISK_PER_TRADE": 0.05,        # Max 2% Portfolio-Risiko pro Trade
    },
}

# ===== LOAD A CONFIG =====
from settings_aggressive import CONFIGS
config = CONFIGS["SMART_TREND"]

# Globale Variablen aktualisieren
TAKE_PROFIT_PCT = config["TAKE_PROFIT_PCT"]
STOP_LOSS_PCT = config["STOP_LOSS_PCT"]
AUTO_TRADE_SCORE_THRESHOLD = config["AUTO_TRADE_SCORE_THRESHOLD"]
CHECK_INTERVAL_HOURS = config["CHECK_INTERVAL_HOURS"]
MAX_RISK_PER_TRADE = config["MAX_RISK_PER_TRADE"]
USE_TREND_FILTER = config["USE_TREND_FILTER"]
                                
# Globale Settings überschreiben
# USE_TREND_FILTER = config.get("USE_TREND_FILTER", True)
#MAX_RISK_PER_TRADE = config.get("MAX_RISK_PER_TRADE", 0.05) # 5% Risiko pro Trade



# ===== UNIVERSE SETTINGS =====
# DAX Top-Aktien
DAX_TICKERS = {
    "SAP.DE": "SAP",
    "SIE.DE": "Siemens",
    "ALV.DE": "Allianz",
    "MUV2.DE": "Munich Re",
    "IFX.DE": "Infineon",
    "VOW3.DE": "Volkswagen",
    "BMW.DE": "BMW",
    "DB1.DE": "Deutsche Börse",
    "DBK.DE": "Deutsche Bank",
    "LHA.DE": "Lufthansa",
    "HEN3.DE": "Henkel",
    "MRK.DE": "Merck",
    "RWE.DE": "RWE",
    "BAYN.DE": "Bayer",
    "CON.DE": "Continental",
}

# S&P 500 Top 100 (US Stocks)
SP500_TOP100 = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "GOOGL": "Alphabet",
    "AMZN": "Amazon",
    "NVDA": "NVIDIA",
    "TSLA": "Tesla",
    "META": "Meta",
    "NFLX": "Netflix",
    "ADBE": "Adobe",
    "CRM": "Salesforce",
    "AVGO": "Broadcom",
    "PYPL": "PayPal",
    "INTC": "Intel",
    "AMD": "Advanced Micro",
    "QCOM": "Qualcomm",
    "TXN": "Texas Instruments",
    "CSCO": "Cisco",
    "ORCL": "Oracle",
    "IBM": "IBM",
    "VRTX": "Vertex",
    "SNPS": "Synopsys",
    "CDNS": "Cadence",
    "ASML": "ASML",
    "MCHP": "Microchip",
    "LRCX": "Lam Research",
    "AMAT": "Applied Materials",
    "JKHY": "Jack Henry",
    "GILD": "Gilead",
    "AMGN": "Amgen",
    "REGN": "Regeneron",
    "BIIB": "Biogen",
    "SQ": "Square",
    "ROKU": "Roku",
    "TTM": "Tencent Music",
    "PINS": "Pinterest",
    "SNAP": "Snap",
    "DKNG": "DraftKings",
    "DASH": "DoorDash",
    "LYFT": "Lyft",
    "UBER": "Uber",
    "SPOT": "Spotify",
    "DOCU": "DocuSign",
    "ZM": "Zoom",
    "OKTA": "Okta",
    "SNOW": "Snowflake",
    "DBX": "Dropbox",
    "NET": "Cloudflare",
    "CRWD": "CrowdStrike",
    "ZS": "Zscaler",
    "DDOG": "Datadog",
    "PSTG": "PostgreSQL",
    "MDB": "MongoDB",
    "ESTC": "Elastic",
    "SPLK": "Splunk",
    "SUMO": "Sumo Logic",
    "ENVX": "Enveyo",
    "PLUG": "Plug Power",
    "FCEL": "FuelCell",
    "RUN": "Sunrun",
    "SEDG": "SolarEdge",
    "ENPH": "Enphase",
    "XPEV": "XPeng",
    "LI": "Li Auto",
    "NIO": "NIO",
    "FSR": "Fisker",
    "LCID": "Lucid",
    "RIVN": "Rivian",
    "SOFI": "SoFi",
    "UPST": "Upstart",
    "COIN": "Coinbase",
    "MSTR": "MicroStrategy",

}

