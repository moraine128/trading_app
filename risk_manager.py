# risk_manager.py
"""Risk Management Layer für Trading Bot.

Verantwortlich für:
- Circuit Breaker (Tages/Wochen Drawdown-Limits)
- Positionsgrößen-Berechnung (ATR-basiert)
- Max Positions/Trades Kontrolle
- Volatilitäts-Anpassungen
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional
import sqlite3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RiskLimits:
    """Konfigurierbare Risk-Parameter."""
    # Prozentuale Limits
    max_risk_per_trade: float = 0.05  # 5% des Kontos pro Trade
    max_daily_drawdown: float = 0.1  # 10% max Tagesverlust
    max_weekly_drawdown: float = 0.2  # 20% max Wochenverlust
    
    # Position Limits
    max_open_positions: int = 12
    max_position_size: float = 1200.0  # EUR
    max_trades_per_day: int = 20
    
    # Volatilitäts-Multiplikator
    volatility_adjustment: bool = True
    min_position_size: float = 200.0  # EUR


class RiskManager:
    """Zentrales Risk Management."""
    
    def __init__(self, dbpath: str = "trading_data.db", limits: Optional[RiskLimits] = None):
        self.dbpath = dbpath
        self.limits = limits or RiskLimits()
        self.trading_enabled = True
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.trades_today = 0
        self.last_reset = datetime.now()
        
    def _get_connection(self) -> sqlite3.Connection:
        """Datenbankverbindung."""
        conn = sqlite3.connect(self.dbpath)
        conn.row_factory = sqlite3.Row
        return conn
    
    def update_statistics(self) -> None:
        """Aktualisiert PnL und Trade-Zähler aus DB."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Tages-PnL
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            cursor.execute("""
                SELECT SUM(pnl) as daily_pnl, COUNT(*) as trades_count
                FROM trades
                WHERE exittime >= ? AND status = 'CLOSED'
            """, (today_start.isoformat(),))
            row = cursor.fetchone()
            self.daily_pnl = row['daily_pnl'] or 0.0
            self.trades_today = row['trades_count'] or 0
            
            # Wochen-PnL
            week_start = today_start - timedelta(days=today_start.weekday())
            cursor.execute("""
                SELECT SUM(pnl) as weekly_pnl
                FROM trades
                WHERE exittime >= ? AND status = 'CLOSED'
            """, (week_start.isoformat(),))
            row = cursor.fetchone()
            self.weekly_pnl = row['weekly_pnl'] or 0.0
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Fehler beim Update der Risk-Statistiken: {e}")
    
    def check_circuit_breaker(self, account_balance: float) -> Dict[str, any]:
        """Prüft ob Circuit Breaker greifen.
        
        Returns:
            Dict mit 'trading_allowed' (bool) und 'reason' (str)
        """
        self.update_statistics()
        
        # Daily Drawdown Check
        daily_dd_pct = self.daily_pnl / account_balance if account_balance > 0 else 0
        if daily_dd_pct <= -self.limits.max_daily_drawdown:
            self.trading_enabled = False
            return {
                'trading_allowed': False,
                'reason': f'CIRCUIT BREAKER: Tages-Drawdown {daily_dd_pct*100:.2f}% überschreitet Limit von {self.limits.max_daily_drawdown*100}%'
            }
        
        # Weekly Drawdown Check
        weekly_dd_pct = self.weekly_pnl / account_balance if account_balance > 0 else 0
        if weekly_dd_pct <= -self.limits.max_weekly_drawdown:
            self.trading_enabled = False
            return {
                'trading_allowed': False,
                'reason': f'CIRCUIT BREAKER: Wochen-Drawdown {weekly_dd_pct*100:.2f}% überschreitet Limit von {self.limits.max_weekly_drawdown*100}%'
            }
        
        # Max Trades pro Tag
        if self.trades_today >= self.limits.max_trades_per_day:
            return {
                'trading_allowed': False,
                'reason': f'Max Trades heute ({self.limits.max_trades_per_day}) erreicht'
            }
        
        return {'trading_allowed': True, 'reason': 'OK'}
    
    def calculate_position_size(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss: float,
        atr: Optional[float] = None
    ) -> float:
        """Berechnet sichere Positionsgröße.
        
        Args:
            account_balance: Aktuelles Konto-Kapital
            entry_price: Einstiegspreis
            stop_loss: Stop-Loss-Preis
            atr: Average True Range (optional für Volatilitäts-Adjustment)
        
        Returns:
            Positionsgröße in EUR
        """
        # Basis: Max Risk pro Trade
        max_risk_eur = account_balance * self.limits.max_risk_per_trade
        
        # Risiko pro Aktie
        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share <= 0:
            logger.warning(f"Stop-Loss zu nah am Entry: {entry_price} vs {stop_loss}")
            return 0.0
        
        # Anzahl Shares
        shares = max_risk_eur / risk_per_share
        position_eur = shares * entry_price
        
        # Volatilitäts-Anpassung (falls ATR verfügbar)
        if self.limits.volatility_adjustment and atr and atr > 0:
            # Bei hoher Volatilität (ATR > 3% vom Preis) → kleinere Position
            atr_pct = atr / entry_price
            if atr_pct > 0.03:
                vol_factor = 0.03 / atr_pct  # Reduziere Position
                position_eur *= vol_factor
                logger.info(f"Volatilitäts-Anpassung: ATR {atr_pct*100:.2f}%, Faktor {vol_factor:.2f}")
        
        # Hard Limits
        position_eur = min(position_eur, self.limits.max_position_size)
        position_eur = max(position_eur, self.limits.min_position_size)
        
        return round(position_eur, 2)
    
    def can_open_position(self, account_balance: float) -> Dict[str, any]:
        """Prüft ob neue Position eröffnet werden darf.
        
        Returns:
            Dict mit 'allowed' (bool), 'reason' (str), 'current_positions' (int)
        """
        # Circuit Breaker Check
        cb_result = self.check_circuit_breaker(account_balance)
        if not cb_result['trading_allowed']:
            return {
                'allowed': False,
                'reason': cb_result['reason'],
                'current_positions': self._count_open_positions()
            }
        
        # Anzahl offener Positionen prüfen
        open_count = self._count_open_positions()
        if open_count >= self.limits.max_open_positions:
            return {
                'allowed': False,
                'reason': f'Max offene Positionen ({self.limits.max_open_positions}) erreicht',
                'current_positions': open_count
            }
        
        return {
            'allowed': True,
            'reason': 'OK',
            'current_positions': open_count
        }
    
    def _count_open_positions(self) -> int:
        """Zählt offene Positionen."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as cnt
                FROM trades
                WHERE status = 'OPEN'
            """)
            row = cursor.fetchone()
            conn.close()
            return row['cnt'] or 0
        except Exception as e:
            logger.error(f"Fehler beim Zählen offener Positionen: {e}")
            return 0
    
    def get_risk_status(self, account_balance: float) -> Dict:
        """Liefert aktuellen Risk-Status für Monitoring."""
        self.update_statistics()
        
        return {
            'trading_enabled': self.trading_enabled,
            'daily_pnl': self.daily_pnl,
            'daily_dd_pct': (self.daily_pnl / account_balance * 100) if account_balance > 0 else 0,
            'weekly_pnl': self.weekly_pnl,
            'weekly_dd_pct': (self.weekly_pnl / account_balance * 100) if account_balance > 0 else 0,
            'trades_today': self.trades_today,
            'max_trades_per_day': self.limits.max_trades_per_day,
            'open_positions': self._count_open_positions(),
            'max_open_positions': self.limits.max_open_positions,
        }
    
    def enable_trading(self) -> None:
        """Setzt Circuit Breaker zurück (manuell)."""
        self.trading_enabled = True
        logger.info("Trading manuell wieder aktiviert")
