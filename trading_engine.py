# trading_engine.py
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import yfinance as yf
import pandas as pd
from settings_loader import (
    USE_TRAILING_STOP, 
    TRAILING_STOP_ACTIVATION, 
    TRAILING_STOP_DISTANCE,
    MAX_PORTFOLIO_VALUE,
    MAX_POSITIONS_PCT,
    STOP_LOSS_PCT,
    MAX_PORTFOLIO_RISK,
    COOLING_PERIOD_HOURS
)
import logging
from risk_manager import RiskManager, RiskLimits
from data_validator import DataValidator, SafeYFinance, DataValidationError, APIError

@dataclass
class TradeOrder:
    id: int
    ticker: str
    quantity: int
    entryprice: float
    entrytime: str
    side: str  # BUY / SELL
    status: str  # OPEN / CLOSED / CANCELLED
    takeprofit: float
    stoploss: float
    exitprice: Optional[float] = None
    exittime: Optional[str] = None
    pnl: Optional[float] = None
    pnlpercent: Optional[float] = None
    exitreason: Optional[str] = None 
    trailing_stop_price: Optional[float] = None
    highest_price: Optional[float] = None
    atr_value: Optional[float] = None

class TradingEngine:
    """
    Lokale Trading-Engine mit SQLite - ALIGNED WITH BACKTEST_MAIN.PY
    
    Änderungen:
    - Slippage & Commission wie in Backtest
    - Trailing Stop wie in Backtest
    - Position Sizing wie in Backtest
    - Settings von settings_loader
    """
    
    def __init__(self, dbpath: str = "trading_data.db", commission: float = 0.001, slippage: float = 0.001):
        self.dbpath = dbpath
        self.commission = commission  # 0.1% default
        self.slippage = slippage      # 0.1% default
        self.init_database()
                
        # Risk Management und Data Validation
        self.risk_manager = RiskManager(dbpath=dbpath)
        self.data_validator = DataValidator(min_candles=50)
        self.safe_yf = SafeYFinance(validator=self.data_validator)
        
        # Account Balance (wird aktualisiert)
        self.account_balance = 10000.0  # Initial, sollte aus Config/DB kommen
    
    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.dbpath)
    
    def init_database(self) -> None:
        conn = self._conn()
        cur = conn.cursor()
        
        # Orders Table - ERWEITERT MIT TRAILING STOP FELDERN
        cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            entryprice REAL NOT NULL,
            entrytime TEXT NOT NULL,
            side TEXT NOT NULL,
            status TEXT NOT NULL,
            takeprofit REAL NOT NULL,
            stoploss REAL NOT NULL,
            exitprice REAL,
            exittime TEXT,
            pnl REAL,
            pnlpercent REAL,
            signalscore INTEGER,
            exitreason TEXT,
            highest_price REAL,
            trailing_stop_active INTEGER DEFAULT 0
        )
        """)
        
        # Portfolio Table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            ticker TEXT PRIMARY KEY,
            quantity INTEGER NOT NULL,
            avgentryprice REAL NOT NULL,
            currentprice REAL,
            totalcost REAL,
            currentvalue REAL,
            unrealizedpnl REAL,
            unrealizedpnlpercent REAL,
            lastupdate TEXT
        )
        """)
        
        # Signal History Table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS signalhistory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            score INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            rsi REAL,
            macdsignal TEXT,
            stochsignal TEXT,
            action TEXT
        )
        """)
        
        conn.commit()
        conn.close()
    
    # ---------- Quotes ----------
    def get_last_price(self, ticker: str) -> Optional[float]:
        """Hole aktuellen Preis - ROBUSTE VERSION"""
        try:
            ticker_obj = yf.Ticker(ticker)
        
            # Versuche fast_info zuerst (schneller)
            try:
                price = ticker_obj.fast_info.get('lastPrice')
                if price and price > 0:
                    return float(price)
            except:
                pass
        
            # Fallback: history
            data = ticker_obj.history(period="1d", interval="1d")
            if data is None or data.empty:
                return None
        
            return float(data["Close"].iloc[-1])
        
        except Exception as e:
            print(f"⚠️ Preis-Fehler {ticker}: {str(e)[:50]}")
            return None

    def calculate_position_size(self, price: float, atr: float = None) -> int:
        """ALIGNED WITH BACKTEST - Berechne Positionsgröße wie in backtest_main.py"""
        max_position_value = MAX_PORTFOLIO_VALUE * MAX_POSITIONS_PCT

        # Optional: ATR-basierte Positionsgröße
        if atr and atr > 0:
            risk_per_trade = self.account_balance * MAX_PORTFOLIO_RISK
            stop_distance = STOP_LOSS_PCT * price
            position_value = risk_per_trade / stop_distance * price
            position_value = min(position_value, max_position_value)
        else:
            position_value = max_position_value

        # Limitiere auf verfügbares Cash (95%)
        position_value = min(position_value, self.account_balance * 0.95)

        quantity = int(position_value / price)
        return max(1, quantity)
    
    # ---------- Orders / Portfolio ----------
    def create_buy_order(
        self,
        ticker: str,
        quantity: int,
        entryprice: float,
        signalscore: int,
        takeprofitpct: float,
        stoplosspct: float,
    ) -> Optional[TradeOrder]:
        """ALIGNED WITH BACKTEST - Buy Order mit Slippage & Commission"""
        
        # ===== RISK MANAGEMENT CHECKS =====
        # 1. Circuit Breaker Check
        risk_check = self.risk_manager.can_open_position(self.account_balance)
        if not risk_check['allowed']:
            logging.warning(f"Trade blockiert für {ticker}: {risk_check['reason']}")
            return None

        # 2. Cooling-Period Check
        last_trade_time = self.get_last_trade_time(ticker)
        if last_trade_time:
            hours_since_last_trade = (datetime.now() - last_trade_time).total_seconds() / 3600
            if hours_since_last_trade < COOLING_PERIOD_HOURS:
                logging.info(f"Cooling-Period: {ticker} wurde vor {hours_since_last_trade:.1f}h getradet (min: {COOLING_PERIOD_HOURS}h)")
                return None
        
        logging.info(f"Risk Check passed: {risk_check['current_positions']} offene Positionen")
        
        # 3. Hole ATR für Positionsgrößen-Berechnung
        atr_value = None
        try:
            ticker_data = self.safe_yf.download_data(ticker, period="1mo", interval="1d", validate=False)
            if not ticker_data.empty and len(ticker_data) >= 14:
                high_low = ticker_data['High'] - ticker_data['Low']
                high_close = abs(ticker_data['High'] - ticker_data['Close'].shift())
                low_close = abs(ticker_data['Low'] - ticker_data['Close'].shift())
                true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                atr_value = true_range.rolling(14).mean().iloc[-1]
                logging.info(f"ATR für {ticker}: {atr_value:.2f}")
        except Exception as e:
            logging.warning(f"ATR-Berechnung fehlgeschlagen für {ticker}: {e}")
        
        # 4. Berechne Positionsgröße ALIGNED WITH BACKTEST
        quantity = self.calculate_position_size(entryprice, atr_value)
        
        if quantity <= 0:
            logging.warning(f"Zu kleine Quantity für {ticker}: {quantity}")
            return None
        
        # ===== APPLY SLIPPAGE (wie in Backtest) =====
        actual_price = entryprice * (1 + self.slippage)
        
        # Berechne Kosten MIT COMMISSION
        cost = quantity * actual_price
        commission_cost = cost * self.commission
        total_cost = cost + commission_cost
        
        if total_cost > self.account_balance:
            logging.warning(f"Nicht genug Cash für {ticker}: {total_cost:.2f} > {self.account_balance:.2f}")
            return None
        
        # Update account balance
        self.account_balance -= total_cost
        
        # Berechne TP/SL basierend auf ACTUAL PRICE (mit Slippage)
        entrytime = datetime.now().isoformat()
        takeprofit = actual_price * (1 + float(takeprofitpct))
        stoploss = actual_price * (1 - float(stoplosspct))
        
        logging.info(f"Order: {ticker} x{quantity} @ {actual_price:.2f} (Slippage: {self.slippage*100:.2f}%, Commission: {commission_cost:.2f})")
        
        conn = self._conn()
        cur = conn.cursor()
        
        # Insert Order mit highest_price = actual_price (für Trailing Stop)
        cur.execute("""
        INSERT INTO orders
        (ticker, quantity, entryprice, entrytime, side, status, takeprofit, stoploss, signalscore, exitreason, highest_price, trailing_stop_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ticker, quantity, actual_price, entrytime, "BUY", "OPEN", takeprofit, stoploss, signalscore, None, actual_price, 0))
        
        order_id = cur.lastrowid
        
        # Update Portfolio
        cur.execute("SELECT quantity, avgentryprice, totalcost FROM portfolio WHERE ticker = ?", (ticker,))
        row = cur.fetchone()
        
        if row:
            old_qty, old_avg, old_totalcost = row
            old_qty = int(old_qty)
            old_totalcost = float(old_totalcost or (old_avg * old_qty))
            
            new_qty = old_qty + int(quantity)
            new_totalcost = old_totalcost + cost  # Ohne Commission in Portfolio
            new_avg = new_totalcost / new_qty if new_qty > 0 else float(actual_price)
            
            cur.execute("""
            UPDATE portfolio
            SET quantity = ?, avgentryprice = ?, totalcost = ?, lastupdate = ?
            WHERE ticker = ?
            """, (new_qty, new_avg, new_totalcost, entrytime, ticker))
        else:
            cur.execute("""
            INSERT INTO portfolio (ticker, quantity, avgentryprice, totalcost, lastupdate)
            VALUES (?, ?, ?, ?, ?)
            """, (ticker, int(quantity), float(actual_price), cost, entrytime))
        
        # Log Signal
        cur.execute("""
        INSERT INTO signalhistory (ticker, score, timestamp, action)
        VALUES (?, ?, ?, ?)
        """, (ticker, int(signalscore), entrytime, "TRADE_EXECUTED"))
        
        conn.commit()
        conn.close()
        
        return TradeOrder(
            id=order_id,
            ticker=ticker,
            quantity=int(quantity),
            entryprice=float(actual_price),
            entrytime=entrytime,
            side="BUY",
            status="OPEN",
            takeprofit=float(takeprofit),
            stoploss=float(stoploss),
            highest_price=float(actual_price),
        )
    
    def get_open_orders(self) -> List[Dict]:
        conn = self._conn()
        cur = conn.cursor()
        
        cur.execute("""
        SELECT id, ticker, quantity, entryprice, entrytime, takeprofit, stoploss, highest_price, trailing_stop_active
        FROM orders
        WHERE status = 'OPEN' AND side = 'BUY'
        ORDER BY entrytime ASC
        """)
        
        rows = cur.fetchall()
        conn.close()
        
        out = []
        for order_id, ticker, qty, entryprice, entrytime, tp, sl, highest, trailing_active in rows:
            out.append({
                "id": int(order_id),
                "ticker": ticker,
                "quantity": int(qty),
                "entryprice": float(entryprice),
                "entrytime": entrytime,
                "takeprofit": float(tp),
                "stoploss": float(sl),
                "highest_price": float(highest) if highest else float(entryprice),
                "trailing_stop_active": bool(trailing_active),
            })
        
        return out
    
    def check_exit_condition_for_order(self, order: Dict, currentprice: float) -> Optional[str]:
        """ALIGNED WITH BACKTEST - Exit Check wie in backtest_main.py"""
        
        entry_price = float(order["entryprice"])
        
        # 1. Take Profit Check
        if currentprice >= float(order["takeprofit"]):
            return "TAKEPROFIT"
        
        # 2. Stop Loss Check
        if currentprice <= float(order["stoploss"]):
            return "STOPLOSS"
        
        # 3. Trailing Stop Logic (ALIGNED WITH BACKTEST)
        if USE_TRAILING_STOP:
            # Update highest_price
            highest_price = order.get('highest_price', entry_price)
            if currentprice > highest_price:
                highest_price = currentprice
                order['highest_price'] = highest_price
                
                # Update in DB
                conn = self._conn()
                conn.execute(
                    "UPDATE orders SET highest_price = ? WHERE id = ?",
                    (highest_price, order['id'])
                )
                conn.commit()
                conn.close()
            
            # Prüfe ob Trailing Stop aktiviert werden soll
            if currentprice >= entry_price * (1 + TRAILING_STOP_ACTIVATION):
                # Trailing Stop ist jetzt aktiv
                if not order.get('trailing_stop_active', False):
                    conn = self._conn()
                    conn.execute(
                        "UPDATE orders SET trailing_stop_active = 1 WHERE id = ?",
                        (order['id'],)
                    )
                    conn.commit()
                    conn.close()
                    order['trailing_stop_active'] = True
                
                # Berechne Trailing Stop Price
                trailing_stop_price = highest_price * (1 - TRAILING_STOP_DISTANCE)
                
                # Prüfe ob Trailing Stop getroffen wurde
                if currentprice <= trailing_stop_price:
                    return "TRAILING_STOP"
        
        return None
    
    def close_position(self, ticker: str, order_id: int, exitprice: float, exitreason: str = "UNKNOWN") -> TradeOrder:
        """ALIGNED WITH BACKTEST - Close Position mit Slippage & Commission"""
        conn = self._conn()
        cur = conn.cursor()

        # Validiere exitprice
        if exitprice is None or exitprice <= 0:
            logging.warning(f"Invalid exitprice {exitprice} for {ticker} - cannot close position")
            conn.close()
            raise ValueError(f"Cannot close position for {ticker}: invalid exitprice {exitprice}")
        
        cur.execute("""
        SELECT quantity, entryprice, entrytime
        FROM orders
        WHERE id = ? AND ticker = ? AND status = 'OPEN'
        """, (int(order_id), ticker))
        
        row = cur.fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Order {order_id} for {ticker} not found or not open")
        
        qty, entryprice, entrytime = row
        qty = int(qty)
        entryprice = float(entryprice)
        
        # ===== APPLY SLIPPAGE (wie in Backtest) =====
        actual_exit_price = exitprice * (1 - self.slippage)
        
        # Berechne Proceeds MIT COMMISSION
        proceeds = qty * actual_exit_price
        commission_cost = proceeds * self.commission
        net_proceeds = proceeds - commission_cost
        
        # Update account balance
        self.account_balance += net_proceeds
        
        exittime = datetime.now().isoformat()
        pnl = net_proceeds - (qty * entryprice)  # PnL nach Commission
        pnlpercent = ((actual_exit_price - entryprice) / entryprice) * 100 if entryprice else 0.0
        
        logging.info(f"Close: {ticker} x{qty} @ {actual_exit_price:.2f} | PnL: {pnl:.2f} ({pnlpercent:.2f}%) | Reason: {exitreason}")
        
        # Update Order
        cur.execute("""
        UPDATE orders
        SET status = 'CLOSED', exitprice = ?, exittime = ?, pnl = ?, pnlpercent = ?, side = 'SELL', exitreason = ?
        WHERE id = ?
        """, (float(actual_exit_price), exittime, float(pnl), float(pnlpercent), exitreason, int(order_id)))
        
        # Update Portfolio
        cur.execute("SELECT quantity, avgentryprice, totalcost FROM portfolio WHERE ticker = ?", (ticker,))
        prow = cur.fetchone()
        
        if prow:
            pqty, pavg, ptotal = prow
            pqty = int(pqty)
            pavg = float(pavg)
            ptotal = float(ptotal or (pavg * pqty))
            
            new_qty = max(0, pqty - qty)
            removed_cost = pavg * qty
            new_total = max(0.0, ptotal - removed_cost)
            
            if new_qty == 0:
                cur.execute("""
                UPDATE portfolio
                SET quantity = 0, totalcost = 0, avgentryprice = 0, lastupdate = ?
                WHERE ticker = ?
                """, (exittime, ticker))
            else:
                new_avg = new_total / new_qty if new_qty else 0.0
                cur.execute("""
                UPDATE portfolio
                SET quantity = ?, totalcost = ?, avgentryprice = ?, lastupdate = ?
                WHERE ticker = ?
                """, (new_qty, new_total, new_avg, exittime, ticker))
        
        conn.commit()
        conn.close()
        
        return TradeOrder(
            id=int(order_id),
            ticker=ticker,
            quantity=qty,
            entryprice=entryprice,
            entrytime=entrytime,
            side="SELL",
            status="CLOSED",
            takeprofit=0.0,
            stoploss=0.0,
            exitprice=float(actual_exit_price),
            exittime=exittime,
            pnl=float(pnl),
            pnlpercent=float(pnlpercent),
            exitreason=exitreason,
        )
    
    def get_closed_orders(self, limit: int = 100) -> List[Dict]:
        conn = self._conn()
        cur = conn.cursor()
        
        cur.execute("""
        SELECT id, ticker, quantity, entryprice, entrytime, exitprice, exittime, pnl, pnlpercent, exitreason
        FROM orders
        WHERE status = 'CLOSED'
        ORDER BY exittime DESC
        LIMIT ?
        """, (int(limit),))
        
        rows = cur.fetchall()
        conn.close()
        
        out = []
        for r in rows:
            out.append({
                "id": int(r[0]),
                "ticker": r[1],
                "quantity": int(r[2]),
                "entryprice": float(r[3]),
                "entrytime": r[4],
                "exitprice": float(r[5]) if r[5] is not None else None,
                "exittime": r[6],
                "pnl": float(r[7]) if r[7] is not None else None,
                "pnlpercent": float(r[8]) if r[8] is not None else None,
                "exitreason": r[9],
            })
        
        return out
    
    def get_portfolio(self) -> List[Dict]:
        conn = self._conn()
        cur = conn.cursor()
    
        cur.execute("""
            SELECT ticker, quantity, avgentryprice, currentprice, totalcost, currentvalue, unrealizedpnl, unrealizedpnlpercent, lastupdate
            FROM portfolio
            WHERE quantity > 0
        """)
        rows = cur.fetchall()
        
        portfolio: List[Dict] = []
        
        for row in rows:
            ticker, qty, avgprice, currentprice, totalcost, currentvalue, upnl, upnlpct, lastupdate = row
            qty = int(qty)
            avgprice = float(avgprice or 0.0)
            totalcost = float(totalcost or (avgprice * qty))
            
            # ✅ HOLE KAUFZEITPUNKT UND SIGNALSCORE AUS ORDERS-TABELLE
            cur.execute("""
                SELECT entrytime, signalscore 
                FROM orders 
                WHERE ticker = ? AND status = 'OPEN' 
                ORDER BY entrytime ASC 
                LIMIT 1
            """, (ticker,))
            
            order_data = cur.fetchone()
            entrytime = order_data[0] if order_data else None
            signalscore = order_data[1] if order_data else 0
            
            # Update current price
            last = self.get_last_price(ticker)
            if last is not None:
                currentprice = float(last)
                currentvalue = currentprice * qty
                upnl = currentvalue - totalcost
                upnlpct = (upnl / totalcost) * 100 if totalcost else 0.0
            
            portfolio.append({
                "ticker": ticker,
                "quantity": qty,
                "avgentryprice": avgprice,
                "entrytime": entrytime,  
                "signalscore": signalscore,
                "currentprice": float(currentprice) if currentprice is not None else None,
                "totalcost": totalcost,
                "currentvalue": float(currentvalue) if currentvalue is not None else None,
                "unrealizedpnl": float(upnl) if upnl is not None else None,
                "unrealizedpnlpercent": float(upnlpct) if upnlpct is not None else None,
                "lastupdate": lastupdate,
            })
        
        conn.close()
        return portfolio

    
    def get_stats(self) -> Dict:
        conn = self._conn()
        cur = conn.cursor()
        
        cur.execute("SELECT COALESCE(SUM(pnl), 0) FROM orders WHERE status = 'CLOSED'")
        realized = float(cur.fetchone()[0] or 0.0)
        
        portfolio = self.get_portfolio()
        unrealized = float(sum(float(p.get("unrealizedpnl") or 0.0) for p in portfolio))
        
        cur.execute("SELECT COUNT(*) FROM orders WHERE status = 'CLOSED'")
        totaltrades = int(cur.fetchone()[0] or 0)
        
        cur.execute("SELECT COUNT(*) FROM orders WHERE status = 'CLOSED' AND pnl > 0")
        winning = int(cur.fetchone()[0] or 0)
        
        cur.execute("SELECT COALESCE(AVG(pnlpercent), 0) FROM orders WHERE status = 'CLOSED'")
        avgpnlpercent = float(cur.fetchone()[0] or 0.0)
        
        conn.close()
        
        return {
            "realizedpnl": realized,
            "unrealizedpnl": unrealized,
            "totalpnl": realized + unrealized,
            "totaltrades": totaltrades,
            "winningtrades": winning,
            "winrate": (winning / totaltrades) * 100 if totaltrades else 0.0,
            "avgpnlpercent": avgpnlpercent,
        }

    def get_last_trade_time(self, ticker: str):
        """Gibt Zeitpunkt des letzten Trades für ein Symbol zurück."""
        try:
            conn = sqlite3.connect(self.dbpath)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MAX(entrytime) as last_trade
                FROM orders
                WHERE ticker = ? AND status IN ('OPEN', 'CLOSED')
            """, (ticker,))
            row = cursor.fetchone()
            conn.close()
            
            if row and row[0]:
                return datetime.fromisoformat(row[0])
            return None
            
        except Exception as e:
            logging.error(f"Fehler beim Abrufen der letzten Trade-Zeit für {ticker}: {e}")
            return None
    def sell_position_by_ticker(self, ticker: str) -> dict:
        """
        Verkauft ALLE offenen Positionen für einen Ticker zum aktuellen Marktpreis
        Returns:
            dict mit Verkaufsdetails: {
                'success': bool,
                'ticker': str,
                'positions_closed': int,
                'total_pnl': float,
                'exit_price': float,
                'details': list
            }
        """
        import logging

        # Hole alle offenen Orders für diesen Ticker
        conn = self._conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, ticker, quantity, entryprice, signalscore
            FROM orders
            WHERE ticker = ? AND status = 'OPEN'
        """, (ticker,))

        open_orders = cur.fetchall()

        if not open_orders:
            conn.close()
            return {
                'success': False,
                'ticker': ticker,
                'error': 'Keine offenen Positionen gefunden',
                'positions_closed': 0
            }

        # Hole aktuellen Preis
        current_price = self.get_last_price(ticker)

        if current_price is None or current_price <= 0:
            conn.close()
            return {
                'success': False,
                'ticker': ticker,
                'error': 'Aktueller Preis konnte nicht abgerufen werden',
                'positions_closed': 0
            }

        # APPLY SLIPPAGE beim Verkauf (wie in create_buy_order)
        exit_price = current_price * (1 - self.slippage)

        total_pnl = 0
        details = []
        positions_closed = 0

        for order in open_orders:
            order_id = order[0]
            quantity = order[2]
            entry_price = order[3]

            # Berechne P&L MIT COMMISSION
            gross_pnl = (exit_price - entry_price) * quantity
            commission_cost = exit_price * quantity * self.commission
            net_pnl = gross_pnl - commission_cost
            pnl_percent = (net_pnl / (entry_price * quantity)) * 100

            # Schließe Position
            exit_time = datetime.now().isoformat()

            cur.execute("""
                UPDATE orders
                SET status = 'CLOSED',
                    exitprice = ?,
                    exittime = ?,
                    pnl = ?,
                    pnlpercent = ?,
                    exitreason = 'MANUAL_SELL'
                WHERE id = ?
            """, (exit_price, exit_time, net_pnl, pnl_percent, order_id))

            # Update Account Balance
            self.account_balance += (exit_price * quantity - commission_cost)

            total_pnl += net_pnl
            positions_closed += 1

            details.append({
                'order_id': order_id,
                'quantity': quantity,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl': net_pnl,
                'pnl_percent': pnl_percent,
                'commission': commission_cost
            })

            logging.info(f"Sold {ticker} x{quantity} @ {exit_price:.2f} | P&L: {net_pnl:.2f}€ ({pnl_percent:.2f}%) | Commission: {commission_cost:.2f}€")

        conn.commit()

        # Update Portfolio (entferne Position)
        cur.execute("DELETE FROM portfolio WHERE ticker = ?", (ticker,))
        conn.commit()
        conn.close()

        avg_pnl_percent = total_pnl / sum(d['entry_price'] * d['quantity'] for d in details) * 100 if details else 0

        return {
            'success': True,
            'ticker': ticker,
            'positions_closed': positions_closed,
            'total_pnl': total_pnl,
            'avg_pnl_percent': avg_pnl_percent,
            'exit_price': exit_price,
            'slippage_applied': self.slippage * 100,
            'total_commission': sum(d['commission'] for d in details),
            'details': details
        }
