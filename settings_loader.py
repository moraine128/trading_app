# settings_loader.py
import json
import os

def load_settings(profile_name=None):
    """Lädt Settings aus settings.json"""
    
    with open('settings.json', 'r') as f:
        config = json.load(f)
    
    # Nutze active_profile wenn kein spezifisches Profil angegeben
    if profile_name is None:
        profile_name = config['active_profile']
    
    profile = config['profiles'][profile_name]
    
    # Konvertiere zu flacher Struktur für Backward-Compatibility
    settings = {}
    
    # Direkt aus Profile
    for key, value in profile.items():
        if isinstance(value, dict):
            for subkey, subvalue in value.items():
                settings[subkey] = subvalue
        else:
            settings[key] = value
    
    # Optimization Ranges hinzufügen
    settings['optimization_ranges'] = config.get('optimization_ranges', {})
    
    return settings

# Für alten Code: Exportiere alle Settings als Module-Level Variablen
_settings = load_settings()
globals().update(_settings)

# ===== Zusätzliche Kompatibilitäts-Variablen und Defaults =====

# Portfolio Settings (falls nicht in JSON)
MAX_POSITION_SIZE = _settings.get('MAX_POSITION_SIZE', 100)
MAX_TOTAL_POSITIONS = _settings.get('MAX_TOTAL_POSITIONS', 10)
MAX_PORTFOLIO_VALUE = _settings.get('MAX_PORTFOLIO_VALUE', 50000)
MAX_POSITIONS_PCT = _settings.get('MAX_POSITIONS_PCT', 0.9 * MAX_PORTFOLIO_VALUE)

# Scan Settings
CHECK_INTERVAL_HOURS = _settings.get('CHECK_INTERVAL_HOURS', 0.1)
LOOKBACK_PERIOD = _settings.get('LOOKBACK_PERIOD', '90d')
LOOKBACK_INTERVAL = _settings.get('LOOKBACK_INTERVAL', '1h')

# Auto-Trade Settings
AUTO_TRADE_SCORE_THRESHOLD = _settings.get('AUTO_TRADE_SCORE_THRESHOLD', 6)

# Exit Settings
TAKE_PROFIT_PCT = _settings.get('TAKE_PROFIT_PCT', 0.135)
STOP_LOSS_PCT = _settings.get('STOP_LOSS_PCT', 0.05)

# Trailing Stop
USE_TRAILING_STOP = _settings.get('USE_TRAILING_STOP', True)
TRAILING_STOP_ACTIVATION = _settings.get('TRAILING_STOP_ACTIVATION', 0.017)
TRAILING_STOP_DISTANCE = _settings.get('TRAILING_STOP_DISTANCE', 0.022)

# Risk Management
MAX_PORTFOLIO_RISK = _settings.get('MAX_PORTFOLIO_RISK', 0.05)
MAX_DRAWDOWN_LIMIT = _settings.get('MAX_DRAWDOWN_LIMIT', 0.15)
MAX_PORTFOLIO_EXPOSURE = _settings.get('MAX_PORTFOLIO_EXPOSURE', 0.90)
MAX_RISK_PER_TRADE = _settings.get('MAX_RISK_PER_TRADE', 0.02)

# Volume & Liquidity Filter
MIN_AVG_VOLUME = _settings.get('MIN_AVG_VOLUME', 100000)
VOLUME_SPIKE_THRESHOLD = _settings.get('VOLUME_SPIKE_THRESHOLD', 1.42)

# Trend Filter
USE_TREND_FILTER = _settings.get('USE_TREND_FILTER', False)
TREND_SMA_PERIOD = _settings.get('TREND_SMA_PERIOD', 14)
TREND_SLOPE_MIN = _settings.get('TREND_SLOPE_MIN', 0.001)

# Cooling Period
COOLING_PERIOD_HOURS = _settings.get('COOLING_PERIOD_HOURS', 24)

# Signal Score Weights
SIGNAL_WEIGHTS = _settings.get('SIGNAL_WEIGHTS', {
    "rsi_extreme_down": 3,
    "rsi_strong_down": 3,
    "rsi_weak_down": 2,
    "macd_bullish_cross": 3,
    "macd_bullish": 2,
    "stoch_extreme_oversold": 3,
    "stoch_oversold": 3,
    "stoch_bullish_cross": 2,
    "bb_oversold": 1,
    "ma_bullish": 1,
    "candle_bullish": 1,
    "volume_high": 1,
})

# Filter Settings
MIN_SIGNAL_SCORE = _settings.get('MIN_SIGNAL_SCORE', 2)
MIN_PRICE = _settings.get('MIN_PRICE', 5.0)
MAX_PRICE = _settings.get('MAX_PRICE', 1000.0)
MAX_SPREAD = _settings.get('MAX_SPREAD', 0.02)

# Mode Settings
TRADING_MODE = _settings.get('TRADING_MODE', 'PAPER')

# Risk Management Limits
DAILY_LOSS_LIMIT = _settings.get('DAILY_LOSS_LIMIT', -500)
EQUITY_STOP_LOSS = _settings.get('EQUITY_STOP_LOSS', 0.20)

# Notification Settings
SEND_ALERTS = _settings.get('SEND_ALERTS', True)
ALERT_ON_TRADE = _settings.get('ALERT_ON_TRADE', True)
ALERT_ON_EXIT = _settings.get('ALERT_ON_EXIT', True)
ALERT_ON_SCORE_5_PLUS = _settings.get('ALERT_ON_SCORE_5_PLUS', True)

# Database Settings
DATABASE_PATH = _settings.get('DATABASE_PATH', 'trading_data.db')

# Logging
VERBOSE_MODE = _settings.get('VERBOSE_MODE', True)
LOG_FILE = _settings.get('LOG_FILE', 'trading_bot.log')

# ===== QUICK CONFIGS =====
CONFIGS = {
    "STANDARD": {
        "CHECK_INTERVAL_HOURS": 0.25,
        "LOOKBACK_INTERVAL": "5m",
        "TAKE_PROFIT_PCT": 0.03,
        "STOP_LOSS_PCT": 0.02,
        "AUTO_TRADE_SCORE_THRESHOLD": 5,
        "universe": "ALL",
    },
    "AGGRESSIVE": {
        "CHECK_INTERVAL_HOURS": 0.166,
        "LOOKBACK_INTERVAL": "5m",
        "TAKE_PROFIT_PCT": 0.05,
        "STOP_LOSS_PCT": 0.01,
        "AUTO_TRADE_SCORE_THRESHOLD": 4,
        "universe": "DAX",
    },
    "AGGRESSIVE_MM": {
        "CHECK_INTERVAL_HOURS": 0.166,
        "LOOKBACK_INTERVAL": "5m",
        "TAKE_PROFIT_PCT": 0.08,
        "STOP_LOSS_PCT": 0.03,
        "AUTO_TRADE_SCORE_THRESHOLD": 6,
        "universe": "ALL",
    },
    "CONSERVATIVE": {
        "CHECK_INTERVAL_HOURS": 0.5,
        "LOOKBACK_INTERVAL": "15m",
        "TAKE_PROFIT_PCT": 0.02,
        "STOP_LOSS_PCT": 0.03,
        "AUTO_TRADE_SCORE_THRESHOLD": 6,
        "universe": "SP500",
    },
    "SCALPING": {
        "CHECK_INTERVAL_HOURS": 0.0833,
        "LOOKBACK_INTERVAL": "1m",
        "TAKE_PROFIT_PCT": 0.01,
        "STOP_LOSS_PCT": 0.005,
        "AUTO_TRADE_SCORE_THRESHOLD": 5,
        "universe": "ALL",
    },
    "SMART_TREND": {
        "CHECK_INTERVAL_HOURS": 0.5,
        "LOOKBACK_INTERVAL": "5m",
        "TAKE_PROFIT_PCT": 0.135,
        "STOP_LOSS_PCT": 0.05,
        "AUTO_TRADE_SCORE_THRESHOLD": 6,
        "universe": "ALL",
        "USE_TREND_FILTER": True,
        "MAX_RISK_PER_TRADE": 0.05,
    },
}

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
    "ROKU": "Roku",
    "63T.F": "Tencent Music Group FRA",
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
    "MDB": "MongoDB",
    "ESTC": "Elastic",
    "ENVX": "Enveyo",
    "PLUG": "Plug Power",
    "FCEL": "FuelCell",
    "RUN": "Sunrun",
    "SEDG": "SolarEdge",
    "ENPH": "Enphase",
    "XPEV": "XPeng",
    "LI": "Li Auto",
    "NIO": "NIO",
    "LCID": "Lucid",
    "RIVN": "Rivian",
    "SOFI": "SoFi",
    "UPST": "Upstart",
    "COIN": "Coinbase",
    "MSTR": "MicroStrategy",
}
