import sqlite3
import yfinance as yf

# User-Agent setzen um Blockierung zu vermeiden
import requests
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})
yf.set_tz_cache_location = None  # Timezone-Cache deaktivieren


import os
from datetime import datetime
from typing import Dict, List
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
import settings_loader as settings
import json
import yfinance as yf
import threading

import warnings
# Unterdrücke FutureWarnings von Bibliotheken (wie ta/pandas)
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action='ignore', category=RuntimeWarning)

# User-Agent setzen um Blockierung zu vermeiden
import requests
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})
yf.set_tz_cache_location = None  # Timezone-Cache deaktivieren

from indicators_aggressive import add_indicators, get_signal_details
from settings_loader import (
    CONFIGS,
    DAX_TICKERS,
    SP500_TOP100,
    DATABASE_PATH,
    AUTO_TRADE_SCORE_THRESHOLD,
    TRADING_MODE,
    MAX_POSITION_SIZE,      # NEU
    MAX_TOTAL_POSITIONS,    # NEU
    MAX_PORTFOLIO_VALUE,    # NEU
    MAX_POSITIONS_PCT,       # NEU
)

current_config = CONFIGS["SMART_TREND"]
config = CONFIGS["SMART_TREND"]
TAKE_PROFIT_PCT = config["TAKE_PROFIT_PCT"]
STOP_LOSS_PCT = config["STOP_LOSS_PCT"]
AUTO_TRADE_SCORE_THRESHOLD = config["AUTO_TRADE_SCORE_THRESHOLD"]
CHECK_INTERVAL_HOURS = config["CHECK_INTERVAL_HOURS"]
LOOKBACK_INTERVAL = config["LOOKBACK_INTERVAL"]
universe = config["universe"]


def get_all_tickers():
    """Gibt alle verfügbaren Ticker zurück (DAX + S&P500)"""
    all_tickers = list(DAX_TICKERS.keys()) + list(SP500_TOP100.keys())
    return all_tickers


from trading_engine import TradingEngine
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verwaltet Startup und Shutdown"""
    global scheduler

    # Startup
    print("🚀 Trading Bot starting up...")
    
    # ✅ INITIAL SCAN IN BACKGROUND THREAD (blockiert nicht Server-Start)
    print("🔍 Starte initialen Scan im Hintergrund...")
    scan_thread = threading.Thread(target=run_scan, daemon=True)
    scan_thread.start()
    
    # Scheduler für regelmäßige Scans
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_scan, "interval", minutes=int(round(float(CHECK_INTERVAL_HOURS) * 60)), id="universe_scan")
    scheduler.add_job(run_exit_checks, "interval", minutes=1, id="exit_checks")
    scheduler.start()
    print("✅ Scheduler gestartet")

    yield  # App läuft hier

    # Shutdown
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        print("✅ Scheduler shutdown")

# FastAPI mit Lifespan
app = FastAPI(title="Trading Bot Dashboard", lifespan=lifespan)

# Static Files Setup
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# Template-Verzeichnis
if os.path.exists("templates"):
    templates = Jinja2Templates(directory="templates")

    # Custom Filter für datetime formatting
    def strftime_filter(value, format='%Y-%m-%d %H:%M:%S'):
        """Custom Jinja2 filter für datetime formatting"""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except:
                try:
                    value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                except:
                    return value
        if isinstance(value, datetime):
            return value.strftime(format)
        return value

    templates.env.filters['strftime'] = strftime_filter
else:
    templates = None

# ===== Runtime Config =====
current_config = {
    "mode": TRADING_MODE,  # PAPER / LIVE / DEMO
    "universe": "ALL",
    "scan_interval_minutes": int(round(float(CHECK_INTERVAL_HOURS) * 60)),
    "auto_trade_score": int(AUTO_TRADE_SCORE_THRESHOLD),
    "takeprofit_pct": float(TAKE_PROFIT_PCT),
    "stoploss_pct": float(STOP_LOSS_PCT),
    "max_position_pct": MAX_PORTFOLIO_VALUE * MAX_POSITIONS_PCT,  # FIX: Fehlender Key
}

BLACKLIST = {"PYPL", "INTC"}
engine = TradingEngine(dbpath=DATABASE_PATH)
scheduler = BackgroundScheduler()
current_signals: Dict[str, Dict] = {}


# ===== Helper Functions =====

def is_trading_day():
    """Check if today is a trading day (Mon-Fri)"""
    from datetime import datetime
    now = datetime.utcnow()
    return now.weekday() < 5


def universe_tickers(universe: str) -> List[str]:
    """Hole Tickers basierend auf Universe-Auswahl"""
    if universe == "DAX":
        return list(DAX_TICKERS.keys()) if isinstance(DAX_TICKERS, dict) else list(DAX_TICKERS)
    if universe == "SP500":
        return list(SP500_TOP100.keys()) if isinstance(SP500_TOP100, dict) else list(SP500_TOP100)
    if universe == "ALL":
        dax = list(DAX_TICKERS.keys()) if isinstance(DAX_TICKERS, dict) else list(DAX_TICKERS)
        sp = list(SP500_TOP100.keys()) if isinstance(SP500_TOP100, dict) else list(SP500_TOP100)
        return dax + sp
    return []

def get_ticker_name(ticker: str) -> str:
    """
    Holt den vollständigen Unternehmensnamen für einen Ticker von yfinance.
    """
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        # Versuche verschiedene Felder für den Namen
        return info.get('longName') or info.get('shortName') or ticker
    except:
        return ticker



def download_daily_60d(ticker: str):
    """
    Optimierter Download: Holt 300 Tage für SMA 200 Berechnung!
    60 Tage reichen nicht für langfristige Trendfilter.
    """
    import pandas as pd
    from datetime import datetime, timedelta

    try:
        # Wir brauchen ca 1 Jahr Daten für SMA 200 sicher
        start_date = datetime.now() - timedelta(days=400)

        ticker_obj = yf.Ticker(ticker)
        df = ticker_obj.history(start=start_date, interval="1d")

        if df is None or df.empty:
            return None

        # Standardisierung (wie in deiner korrigierten Version)
        df = df.reset_index()
        df.columns = [c.capitalize() if c.lower() in ['date','open','high','low','close','volume'] else c for c in df.columns]

        # Timezone fix
        if 'Date' in df.columns and df['Date'].dtype.name.startswith('datetime64[ns,'):
             df['Date'] = df['Date'].dt.tz_localize(None)

        return df

    except Exception as e:
        print(f"❌ Error {ticker}: {e}")
        return None


def check_risk_limits(ticker: str, entry_price: float, quantity: int) -> tuple[bool, str]:
    """
    Prüfe ob Trade die Risk-Limits einhält
    Returns: (allowed: bool, reason: str)
    """

    # 1. Prüfe: Max Positionen gesamt
    open_orders = engine.get_open_orders()
    if len(open_orders) >= MAX_TOTAL_POSITIONS:
        return False, f"MAX_TOTAL_POSITIONS erreicht ({MAX_TOTAL_POSITIONS})"

    # 2. Prüfe: Bereits Position für diesen Ticker?
    existing_positions = [o for o in open_orders if o['ticker'] == ticker]
    if len(existing_positions) >= MAX_POSITION_SIZE:
        return False, f"MAX_POSITION_SIZE für {ticker} erreicht ({MAX_POSITION_SIZE})"

    # 3. Prüfe: Portfolio-Value Limit
    portfolio = engine.get_portfolio()
    total_invested = sum(p.get('totalcost', 0) for p in portfolio)

    new_position_cost = entry_price * quantity

    if total_invested + new_position_cost > MAX_PORTFOLIO_VALUE:
        return False, f"MAX_PORTFOLIO_VALUE überschritten (€{total_invested:.0f} + €{new_position_cost:.0f} > €{MAX_PORTFOLIO_VALUE})"

    # 4. Prüfe: Max % pro Position
    if MAX_PORTFOLIO_VALUE > 0:
        position_pct = new_position_cost / MAX_PORTFOLIO_VALUE
        if position_pct > MAX_POSITIONS_PCT:
            return False, f"Position zu groß ({position_pct*100:.1f}% > {MAX_POSITIONS_PCT*100:.1f}%)"

    # Alle Checks bestanden
    return True, "OK"


# ===== Scanning Functions =====
def run_scan() -> None:
    """Hauptscan-Funktion mit Signal-Generierung"""
    import time
    global current_signals

    out: Dict[str, Dict] = {}
    tickers = universe_tickers(current_config["universe"])

    print(f"\n🔍 Scanning {len(tickers)} tickers...")
    print("=" * 60)

    success_count = 0
    failed_count = 0
    trades_executed = 0
    trades_blocked = 0

    for i, ticker in enumerate(tickers, 1):
        if ticker in BLACKLIST:
            continue

        # Rate Limiting
        if i > 1:
            time.sleep(1.0)

        print(f"[{i}/{len(tickers)}] {ticker}...", end=" ")

        df = download_daily_60d(ticker)
        if df is None or len(df) < 50:
            print("❌ Keine Daten")
            failed_count += 1
            continue

        try:
            df = add_indicators(df)
            signal = get_signal_details(df)
            out[ticker] = signal
            success_count += 1

            # Auto-Trade Logic mit Risk-Checks
            if current_config["mode"] in {"PAPER", "LIVE"}:
                score = int(signal.get("score", 0))
                threshold = int(current_config["auto_trade_score"])

                if score >= threshold:
                    last_close = float(df.iloc[-1]["Close"])
                    quantity = max(1, int(current_config["max_position_pct"] / last_close))
                    # ✅ RISK-CHECK VOR TRADE
                    allowed, reason = check_risk_limits(ticker, last_close, quantity)

                    if allowed:
                        engine.create_buy_order(
                            ticker=ticker,
                            quantity=quantity,
                            entryprice=last_close,
                            signalscore=score,
                            takeprofitpct=float(current_config["takeprofit_pct"]),
                            stoplosspct=float(current_config["stoploss_pct"]),
                        )
                        print(f"✅ TRADE (Score: {score})")
                        trades_executed += 1
                    else:
                        print(f"⚠️ BLOCKED: {reason}")
                        trades_blocked += 1
                else:
                    print(f"✅ Signal: {score}")

        except Exception as e:
            print(f"❌ Fehler: {str(e)[:50]}")
            failed_count += 1
            continue

    current_signals = out
    print("=" * 60)
    print(f"✅ Scan abgeschlossen:")
    print(f"   Erfolgreich: {success_count}")
    print(f"   Fehlgeschlagen: {failed_count}")
    print(f"   Signale generiert: {len(current_signals)}")
    print(f"   Trades ausgeführt: {trades_executed}")
    print(f"   Trades blockiert: {trades_blocked}")
    print("=" * 60)


def run_exit_checks() -> Dict:
    """Prüfe offene Orders auf TP/SL und schließe sie"""
    closed = 0
    checked = 0
    open_orders = engine.get_open_orders()

    for order in open_orders:
        checked += 1
        last = engine.get_last_price(order["ticker"])
        if last is None or last <= 0:
            continue
        reason = engine.check_exit_condition_for_order(order, float(last))
        if reason:
            try:
                engine.close_position(order["ticker"], order["id"], float(last), exitreason=reason)
                closed += 1
                print(f"Closed {order['ticker']} - {reason}")
            except Exception as e:
                print(f"Error closing {order['ticker']}: {e}")

    return {
        "checked": checked,
        "closed": closed,
        "timestamp": datetime.now().isoformat()
    }


def apply_named_config(config_name: str) -> None:
    """Wende vordefinierte Konfiguration an"""
    cfg = CONFIGS.get(config_name)
    if not cfg:
        return
    current_config["universe"] = cfg.get("universe", current_config["universe"])
    if "CHECK_INTERVAL_HOURS" in cfg:
        current_config["scan_interval_minutes"] = int(round(float(cfg["CHECK_INTERVAL_HOURS"]) * 60))
    if "AUTO_TRADE_SCORE_THRESHOLD" in cfg:
        current_config["auto_trade_score"] = int(cfg["AUTO_TRADE_SCORE_THRESHOLD"])
    if "TAKE_PROFIT_PCT" in cfg:
        current_config["takeprofit_pct"] = float(cfg["TAKE_PROFIT_PCT"])
    if "STOP_LOSS_PCT" in cfg:
        current_config["stoploss_pct"] = float(cfg["STOP_LOSS_PCT"])


def start_jobs() -> None:
    """Starte Scheduler-Jobs"""
    scheduler.add_job(
        run_scan,
        "interval",
        minutes=int(current_config["scan_interval_minutes"]),
        id="universe_scan",
        replace_existing=True,
    )
    scheduler.add_job(
        run_exit_checks,
        "interval",
        minutes=1,
        id="exit_checks",
        replace_existing=True,
    )
    if not scheduler.running:
        scheduler.start()
    print("Scheduler started")



# ===== Routes =====
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trading Bot Dashboard</title>
    <link rel="stylesheet" href="/static/css/style.css">
    <link rel="favicon" href="/static/css/favicon.ico" type="image/x-icon">
</head>
<body>
    <div class="nav">
            <a href="/">🏠 Dashboard</a>
            <a href="/portfolio">📊 Portfolio</a>
            <a href="/trades">📈 Closed Trades</a>
            <a href="/signals">🎯 Signals</a>
            <a href="/stats">📉 Statistics</a>
            <!-- <a href="/api/signals">API: Signals (JSON)</a> -->
            <!-- <a href="/api/stats">API: Stats (JSON)</a> -->
            <a href="/Doku/index.html">📚 Dokumentation</a>
    </div>
    <div class="container">
        <h1>🚀 Trading Bot Dashboard</h1>
        <div class="info">
            <!-- Hole Settings direkt aus settings_loader -->
            <p><strong>Mode:</strong> {current_config['mode']}</p>
            <p><strong>Universe:</strong> {current_config['universe']}</p>
            <p><strong>Scan Interval:</strong> {current_config['scan_interval_minutes']} Minuten</p>
            <p><strong>🎯 Score Threshold:</strong> <span class="score-threshold">{settings.AUTO_TRADE_SCORE_THRESHOLD}</span> (Optimiert)</p>
            <p><strong>📈 Take Profit:</strong> <span class="take-profit">{settings.TAKE_PROFIT_PCT*100:.1f}%</span> | <strong>🚨 Stop Loss:</strong> <span class="stop-loss">{settings.STOP_LOSS_PCT*100:.1f}%</span></p>
            <p><strong>🛡️ Trailing Stop:</strong> {'✅ Aktiv' if settings.USE_TRAILING_STOP else '❌ Inaktiv'} {f'(+{settings.TRAILING_STOP_ACTIVATION*100:.0f}% → -{settings.TRAILING_STOP_DISTANCE*100:.0f}%)' if settings.USE_TRAILING_STOP else ''}</p>
            <p><strong>📊 Risk Management:</strong> Max Risk {settings.MAX_PORTFOLIO_RISK*100:.0f}% | Drawdown Limit {settings.MAX_DRAWDOWN_LIMIT*100:.0f}% | Exposure {settings.MAX_PORTFOLIO_EXPOSURE*100:.0f}%</p>
            <p><strong>📊 Filter:</strong> Volume {settings.MIN_AVG_VOLUME/1000000:.1f}M | Trend {'✅' if settings.USE_TREND_FILTER else '❌'}</p>
        </div>       
    </div>
        <div class="stats">
            <div class="stat-box">
                <h3>Aktive Signale</h3>
                <p class="stat-value">{len(current_signals)}</p>
            </div>
            <div class="stat-box">
                <h3>Open Orders</h3>
                <p class="stat-value">{len(engine.get_open_orders())}</p>
            </div>
            <div class="stat-box">
                <h3>Total Trades</h3>
                <p class="stat-value">{engine.get_stats()['totaltrades']}</p>
            </div>
            <div class="stat-box">
                <h3>Total P&L</h3>
                <p class="stat-value {'positive' if engine.get_stats()['totalpnl'] >= 0 else 'negative'}">{engine.get_stats()['totalpnl']:.2f}€</p>
            </div>
        </div>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html, media_type="text/html; charset=utf-8")

@app.get("/portfolio", response_class=HTMLResponse)
async def portfolio_page(request: Request):
    """Portfolio Seite mit aktuellen Scores"""
    import time
    
    portfolio = engine.get_portfolio()
    stats = engine.get_stats()
    
    # Portfolio-Stats berechnen
    total_invested = sum(p.get('totalcost', 0) for p in portfolio)
    total_current_value = sum(p.get('currentvalue', 0) for p in portfolio)
    unrealized_pnl = total_current_value - total_invested
    unrealized_pnl_percent = (unrealized_pnl / total_invested * 100) if total_invested > 0 else 0
    
    stats['total_invested'] = total_invested
    stats['total_current_value'] = total_current_value
    stats['unrealizedpnl_percent'] = unrealized_pnl_percent
    
    # ✅ BERECHNE SCORES ON-DEMAND (GARANTIERT!)
    print(f"\n🔍 Berechne Scores für {len(portfolio)} Positionen...")
    print(f"📊 current_signals hat {len(current_signals)} Ticker")
    
    for i, pos in enumerate(portfolio, 1):
        ticker = pos['ticker']
        print(f"[{i}/{len(portfolio)}] Verarbeite {ticker}...", end=" ")
        
        # Versuche zuerst aus current_signals
        if ticker in current_signals:
            pos['current_score'] = current_signals[ticker].get('score', 0)
            pos['current_signal'] = current_signals[ticker].get('signal', 'HOLD')
            print(f"✅ aus Cache (Score: {pos['current_score']})")
        else:
            # On-Demand Berechnung
            print(f"⏳ berechne...", end=" ")
            df = download_daily_60d(ticker)
            
            if df is not None and len(df) >= 50:
                try:
                    df = add_indicators(df)
                    signal = get_signal_details(df)
                    pos['current_score'] = signal.get('score', 0)
                    pos['current_signal'] = signal.get('signal', 'HOLD')
                    print(f"✅ Score: {pos['current_score']}")
                except Exception as e:
                    print(f"❌ Fehler: {str(e)[:50]}")
                    pos['current_score'] = 0
                    pos['current_signal'] = 'ERROR'
            else:
                print(f"❌ Keine Daten")
                pos['current_score'] = 0
                pos['current_signal'] = 'NO_DATA'
            
            # Rate Limiting
            if i < len(portfolio):
                time.sleep(0.5)
    
    # Ticker-Namen holen
    all_tickers = {p['ticker'] for p in portfolio}
    ticker_names = {ticker: get_ticker_name(ticker) for ticker in all_tickers}
    
    print(f"✅ Portfolio-Seite geladen mit Scores\n")
    
    if templates:
        return templates.TemplateResponse(
            "portfolio.html",
            {
                "request": request,
                "portfolio": portfolio,
                "stats": stats,
                "ticker_names": ticker_names
            }
        )
    else:
        return HTMLResponse("<h1>Portfolio</h1><p>Template nicht gefunden</p>")


@app.post("/api/close_position")
async def api_close_position(ticker: str, reason: str = "MANUAL_CLOSE"):
    """API: Manuell Position schließen"""
    try:
        # Hole alle offenen Orders für diesen Ticker
        open_orders = engine.get_open_orders()
        orders_to_close = [o for o in open_orders if o['ticker'] == ticker]
        
        if not orders_to_close:
            return {
                "status": "error",
                "message": f"Keine offenen Positionen für {ticker} gefunden"
            }
        
        # Hole aktuellen Preis
        current_price = engine.get_last_price(ticker)
        if current_price is None or current_price <= 0:
            return {
                "status": "error",
                "message": f"Konnte aktuellen Preis für {ticker} nicht abrufen"
            }
        
        # Schließe alle Positionen für diesen Ticker
        closed_count = 0
        total_pnl = 0
        
        for order in orders_to_close:
            try:
                result = engine.close_position(
                    ticker=ticker,
                    order_id=order['id'],
                    exitprice=current_price,
                    exitreason=reason
                )
                closed_count += 1
                total_pnl += result.pnl if result.pnl else 0
            except Exception as e:
                print(f"❌ Fehler beim Schließen von Order {order['id']}: {e}")
                continue
        
        return {
            "status": "success",
            "message": f"{closed_count} Position(en) für {ticker} geschlossen",
            "ticker": ticker,
            "closed_orders": closed_count,
            "exit_price": current_price,
            "total_pnl": total_pnl,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Fehler beim Schließen: {str(e)}"
        }


@app.get("/trades", response_class=HTMLResponse)
async def trades_page(request: Request):
    """Closed Trades Seite"""
    trades = engine.get_closed_orders(limit=200)
    stats = engine.get_stats()
        # Hole Unternehmensnamen für alle Ticker in Trades
    all_tickers = set()
    for trade in trades:
        all_tickers.add(trade['ticker'])
    ticker_names = {ticker: get_ticker_name(ticker) for ticker in all_tickers}
    

    if templates:
        return templates.TemplateResponse(
            "trades.html",
            {
                "request": request,
                "trades": trades,
                "stats": stats,
                                "ticker_names": ticker_names
            }
        )
    else:
        return HTMLResponse("<h1>Trades</h1><p>Template nicht gefunden</p>")



@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    """Statistics Seite"""
    # Update prices before showing stats
    stats = engine.get_stats()
    # Add color values for conditional styling
    stats['totalpnl_color'] = '#28a745' if stats.get('totalpnl', 0) >= 0 else '#dc3545'
    stats['realizedpnl_color'] = '#28a745' if stats.get('realizedpnl', 0) >= 0 else '#dc3545'
    stats['unrealizedpnl_color'] = '#28a745' if stats.get('unrealizedpnl', 0) >= 0 else '#dc3545'
    if templates:
        return templates.TemplateResponse(
            "stats.html",
            {
                "request": request,
                "stats": stats
            }
        )
    else:
        return HTMLResponse("<h1>Statistics</h1><p>Template nicht gefunden</p>")
@app.get("/signals", response_class=HTMLResponse)
async def signals_page(request: Request):
    """Signals Seite - zeigt ALLE Ticker mit ihren Signalen"""
    if templates:
        # Hole ALLE Ticker aus dem aktuellen Universe
        all_tickers = universe_tickers(current_config["universe"])
        
        # Generiere Signale für ALLE Ticker
        signals_with_defaults = {}
        ticker_names = {}
        
        for ticker in all_tickers:
            if ticker in BLACKLIST:
                continue
                
            # Versuche zuerst aus current_signals zu holen
            if ticker in current_signals:
                signal = current_signals[ticker]
            else:
                # Wenn nicht vorhanden, generiere Signal on-the-fly
                df = download_daily_60d(ticker)
                if df is not None and len(df) >= 50:
                    try:
                        df = add_indicators(df)
                        signal = get_signal_details(df)
                    except:
                        signal = {}
                else:
                    signal = {}
            
            # Bereite Signal mit Defaults auf
            enriched_signal = dict(signal) if isinstance(signal, dict) else {}
            enriched_signal.setdefault('rsi', 50)
            enriched_signal.setdefault('score', 0)
            enriched_signal.setdefault('ticker', ticker)
            
            signals_with_defaults[ticker] = enriched_signal
            ticker_names[ticker] = get_ticker_name(ticker)
        
        return templates.TemplateResponse(
            "signals.html",
            {
                "request": request,
                "signals": current_signals or {},
                "config": current_config,
                "ticker_names": ticker_names
            }
        )
    else:
        return HTMLResponse("<h1>Signals</h1><p>Template nicht gefunden</p>")


@app.get("/api/stats")
async def api_stats():
    """API: Trading Stats"""
    return {
        "config": current_config,
        "portfolio": engine.get_portfolio(),
        "open_orders": engine.get_open_orders(),
        "stats": engine.get_stats(),
    }


@app.get("/api/signals")
async def api_signals():
    """API: Current Signals"""
    return current_signals


@app.get("/api/trades")
async def api_trades(limit: int = 200):
    """API: Closed Trades"""
    return engine.get_closed_orders(limit=limit)


# GET-Version für Browser-Aufruf
@app.get("/api/trigger_scan")
async def api_trigger_scan_get():
    """API: Trigger Manual Scan (GET)"""
    return await api_trigger_scan()

# Bestehende POST-Route bleibt
@app.post("/api/trigger_scan")
async def api_trigger_scan():
    """API: Trigger Manual Scan"""
    scan_thread = threading.Thread(target=run_scan, daemon=True)
    scan_thread.start()
    return {
        "status": "started",
        "message": "Scan läuft im Hintergrund",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/exit-check")
async def api_trigger_exit_check():
    """API: Trigger Manual Exit Check"""
    return run_exit_checks()


@app.get("/api/risk-status")
async def api_risk_status():
    """API: Aktueller Risk-Status"""
    open_orders = engine.get_open_orders()
    portfolio = engine.get_portfolio()

    total_invested = sum(p.get('totalcost', 0) for p in portfolio)

    # Zähle Positionen pro Ticker
    positions_per_ticker = {}
    for order in open_orders:
        ticker = order['ticker']
        positions_per_ticker[ticker] = positions_per_ticker.get(ticker, 0) + 1

    return {
        "open_positions": len(open_orders),
        "max_positions": MAX_TOTAL_POSITIONS,
        "positions_available": MAX_TOTAL_POSITIONS - len(open_orders),
        "total_invested": total_invested,
        "max_portfolio_value": MAX_PORTFOLIO_VALUE,
        "portfolio_utilization_pct": (total_invested / MAX_PORTFOLIO_VALUE * 100) if MAX_PORTFOLIO_VALUE > 0 else 0,
        "positions_per_ticker": positions_per_ticker,
        "max_position_size": MAX_POSITION_SIZE,
        "max_position_pct": MAX_POSITIONS_PCT * 100,
    }
# ============================================================
# LIVE STREAMING API ENDPOINTS
# ============================================================
from fastapi.responses import StreamingResponse
import asyncio

@app.get("/api/signals/stream")
async def signals_stream():
    """Stream signals progressively"""
    async def generate():
        tickers = get_all_tickers()
        total = len(tickers)
        yield f"data: {json.dumps({'type': 'init', 'total': total})}\n\n"
                
        # Sortiere Ticker: BUY-Signale zuerst, dann nach Score (absteigend)        sorted_tickers = sorted(
        sorted_tickers = sorted(
            [t for t in tickers if t in current_signals],
            key=lambda t: (
                # 0 für BUY (kommt zuerst), 1 für SELL (kommt danach)
                0 if current_signals[t].get('signal') == 'BUY' else 1,
                # Innerhalb BUY/SELL: höchster Score zuerst (negativ für absteigende Sortierung)
                -current_signals[t].get('score', 0)
            )
        )
        # Füge Ticker ohne Signale hinzu
        sorted_tickers += [t for t in tickers if t not in current_signals]


        # Additional API route for scan (alias for trigger_scan)
@app.post("/api/scan")
async def api_scan():
    """API: Manual Scan (alias)"""
    return await api_trigger_scan()


    # Portfolio Stream
@app.get("/api/portfolio/stream")
async def portfolio_stream(request: Request):
    async def generate():
        import time
        
        portfolio = engine.get_portfolio()
        stats = engine.get_stats()
        
        # ✅ SCORES ANREICHERN (wie in portfolio_page)
        for pos in portfolio:
            ticker = pos['ticker']
            if ticker in current_signals:
                pos['current_score'] = current_signals[ticker].get('score', 0)
                pos['current_signal'] = current_signals[ticker].get('signal', 'HOLD')
            else:
                pos['current_score'] = 0
                pos['current_signal'] = 'NO_DATA'
        
        data = {
            'type': 'init',
            'total': len(portfolio),
            'positions': portfolio,
            'stats': stats,
        }
        yield f"data: {json.dumps(data)}\n\n"
        
        while True:
            if await request.is_disconnected():
                break
            
            portfolio = engine.get_portfolio()
            stats = engine.get_stats()
            
            # ✅ SCORES AUCH BEIM UPDATE ANREICHERN
            for pos in portfolio:
                ticker = pos['ticker']
                if ticker in current_signals:
                    pos['current_score'] = current_signals[ticker].get('score', 0)
                    pos['current_signal'] = current_signals[ticker].get('signal', 'HOLD')
                else:
                    pos['current_score'] = 0
                    pos['current_signal'] = 'NO_DATA'
            
            data = {
                'type': 'update',
                'total': len(portfolio),
                'positions': portfolio,
                'stats': stats,
            }
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(5)
    
    return StreamingResponse(generate(), media_type="text/event-stream")


    # Trades Stream
@app.get("/api/trades/stream")
async def trades_stream(request: Request):
    """Stream trades updates progressively"""
    import json
    async def generate():
        # Initial data
        trades = engine.get_closed_orders()
        yield f"data: {json.dumps({'type': 'init', 'total': len(trades), 'trades': trades})}\n\n"
        
        while True:
            if await request.is_disconnected():
                break
            
            # Update data
            trades = engine.get_closed_orders()
            yield f"data: {json.dumps({'type': 'update', 'total': len(trades), 'trades': trades})}\n\n"
            await asyncio.sleep(5)
    
    return StreamingResponse(generate(), media_type="text/event-stream")


#import Dokumentation als statische Dateien
from fastapi.staticfiles import StaticFiles
app.mount("/Doku", StaticFiles(directory="Doku", html=True), name="doku")

# ===== Database Initialization =====
def init_database():
    """Initialisiert die Datenbank-Tabellen"""
    conn = sqlite3.connect('trading_bot.db')
    cursor = conn.cursor()
    
    # Trades-Tabelle erstellen
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            timestamp TEXT NOT NULL,
            strategy TEXT,
            total_value REAL,
            status TEXT DEFAULT 'open'
        )
    ''')
    
    # Signals-Tabelle erstellen (falls noch nicht vorhanden)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            price REAL NOT NULL,
            timestamp TEXT NOT NULL,
            rsi REAL,
            macd REAL,
            signal_line REAL,
            bb_position TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Datenbank initialisiert!")

# BEIM APP-START AUFRUFEN (vor dem ersten Scan):
if __name__ == "__main__":
    init_database()  # <-- HIER HINZUFÜGEN
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
