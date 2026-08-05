# data_validator.py
"""Datenvalidierung und Error-Handling-Utilities.

Verantwortlich für:
- Candle-Daten validieren (NaN, Lücken, Timestamp-Checks)
- Retry-Logik für API-Calls mit exponential backoff
- Robuste Error-Handler für yfinance/API-Fehler
"""

import logging
import time
import pandas as pd
import numpy as np
from typing import Optional, Callable, Any
from datetime import datetime, timedelta
from functools import wraps

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataValidationError(Exception):
    """Custom Exception für Datenvalidierungs-Fehler."""
    pass


class APIError(Exception):
    """Custom Exception für API-Fehler."""
    pass


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Decorator für Retry-Logik mit exponential backoff.
    
    Args:
        max_retries: Maximale Anzahl Versuche
        initial_delay: Initiale Wartezeit in Sekunden
        backoff_factor: Multiplikator für Delay (exponential)
        exceptions: Tuple von Exceptions, die geretried werden sollen
    
    Example:
        @retry_with_backoff(max_retries=3, initial_delay=1.0)
        def fetch_data(ticker):
            return yf.download(ticker)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Versuch {attempt+1}/{max_retries} fehlgeschlagen für {func.__name__}: {e}. "
                            f"Retry in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(
                            f"Alle {max_retries} Versuche fehlgeschlagen für {func.__name__}: {e}"
                        )
            
            # Wenn alle Retries fehlschlagen, raise last exception
            raise last_exception
        
        return wrapper
    return decorator


class DataValidator:
    """Validiert Trading-Daten (OHLCV, Candles)."""
    
    def __init__(self, min_candles: int = 50, max_gap_minutes: int = 10):
        """
        Args:
            min_candles: Minimale Anzahl Candles für valide Daten
            max_gap_minutes: Max erlaubte Lücke zwischen Candles (Minuten)
        """
        self.min_candles = min_candles
        self.max_gap_minutes = max_gap_minutes
    
    def validate_ohlcv(self, df: pd.DataFrame, ticker: str = "UNKNOWN") -> dict:
        """Validiert OHLCV DataFrame.
        
        Prüft:
        - Mindestanzahl Rows
        - NaN/Inf Values
        - Preis-Plausibilität (High >= Low, Close zwischen High/Low)
        - Monoton steigende Timestamps
        - Zeitliche Lücken
        
        Returns:
            Dict mit 'valid' (bool), 'errors' (list), 'warnings' (list)
        """
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'ticker': ticker
        }
        
        # Check 1: Mindestanzahl Rows
        if len(df) < self.min_candles:
            result['valid'] = False
            result['errors'].append(
                f"Zu wenig Daten: {len(df)} Candles (min: {self.min_candles})"
            )
            return result  # Weitere Checks sinnlos
        
        # Check 2: NaN/Inf Values
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in required_cols:
            if col not in df.columns:
                result['valid'] = False
                result['errors'].append(f"Fehlende Spalte: {col}")
                continue
            
            nan_count = df[col].isna().sum()
            inf_count = np.isinf(df[col]).sum()
            
            if nan_count > 0:
                result['valid'] = False
                result['errors'].append(f"{col}: {nan_count} NaN-Werte gefunden")
            
            if inf_count > 0:
                result['valid'] = False
                result['errors'].append(f"{col}: {inf_count} Inf-Werte gefunden")
        
        if not result['valid']:
            return result  # Bei NaN/Inf: keine weiteren Checks
        
        # Check 3: Preis-Plausibilität
        invalid_prices = (
            (df['High'] < df['Low']) |
            (df['Close'] > df['High']) |
            (df['Close'] < df['Low']) |
            (df['Open'] > df['High']) |
            (df['Open'] < df['Low'])
        )
        
        if invalid_prices.any():
            count = invalid_prices.sum()
            result['valid'] = False
            result['errors'].append(
                f"{count} Candles mit unplausiblen Preisen (High < Low oder Close außerhalb Range)"
            )
        
        # Check 4: Negative/Null-Preise
        zero_or_negative = (df[['Open', 'High', 'Low', 'Close']] <= 0).any(axis=1)
        if zero_or_negative.any():
            result['valid'] = False
            result['errors'].append(
                f"{zero_or_negative.sum()} Candles mit Preis <= 0"
            )
        
        # Check 5: Timestamps monoton steigend
        if isinstance(df.index, pd.DatetimeIndex):
            if not df.index.is_monotonic_increasing:
                result['warnings'].append("Timestamps nicht monoton steigend")
            
            # Check 6: Zeitliche Lücken
            time_diffs = df.index.to_series().diff()
            max_gap = time_diffs.max()
            
            if pd.notna(max_gap) and max_gap > timedelta(minutes=self.max_gap_minutes):
                result['warnings'].append(
                    f"Größte zeitliche Lücke: {max_gap} (überschreitet {self.max_gap_minutes}min)"
                )
        else:
            result['warnings'].append("Kein DatetimeIndex, Timestamp-Checks übersprungen")
        
        # Check 7: Volume-Warnungen
        zero_volume = (df['Volume'] == 0).sum()
        if zero_volume > len(df) * 0.1:  # Mehr als 10% Zero-Volume
            result['warnings'].append(
                f"{zero_volume} Candles mit Volume=0 ({zero_volume/len(df)*100:.1f}%)"
            )
        
        return result
    
    def validate_and_raise(self, df: pd.DataFrame, ticker: str = "UNKNOWN") -> None:
        """Validiert Daten und wirft Exception bei Fehler.
        
        Raises:
            DataValidationError: Wenn Daten invalid
        """
        result = self.validate_ohlcv(df, ticker)
        
        if not result['valid']:
            error_msg = f"Datenvalidierung fehlgeschlagen für {ticker}:\n"
            error_msg += "\n".join(f"  - {e}" for e in result['errors'])
            logger.error(error_msg)
            raise DataValidationError(error_msg)
        
        if result['warnings']:
            warning_msg = f"Datenvalidierungs-Warnungen für {ticker}:\n"
            warning_msg += "\n".join(f"  - {w}" for w in result['warnings'])
            logger.warning(warning_msg)
    
    def clean_ohlcv(self, df: pd.DataFrame) -> pd.DataFrame:
        """Bereinigt OHLCV DataFrame (Forward-Fill, Duplikate entfernen).
        
        Vorsicht: Nur für kleine Lücken verwenden!
        """
        df_clean = df.copy()
        
        # Duplikate entfernen
        df_clean = df_clean[~df_clean.index.duplicated(keep='first')]
        
        # Forward-Fill für kleine Lücken (max 3 Candles)
        df_clean = df_clean.fillna(method='ffill', limit=3)
        
        # Verbleibende NaN droppen
        df_clean = df_clean.dropna()
        
        return df_clean


class SafeYFinance:
    """Wrapper für yfinance mit Retry-Logik und Validierung."""
    
    def __init__(self, validator: Optional[DataValidator] = None):
        self.validator = validator or DataValidator()
    
    @retry_with_backoff(max_retries=3, initial_delay=2.0)
    def download_data(
        self,
        ticker: str,
        period: str = "1mo",
        interval: str = "1d",
        validate: bool = True
    ) -> pd.DataFrame:
        """Lädt Daten mit yfinance (mit Retry).
        
        Args:
            ticker: Ticker-Symbol
            period: Zeitraum (z.B. "1mo", "3mo", "1y")
            interval: Interval (z.B. "1d", "1h", "5m")
            validate: Validierung durchführen
        
        Returns:
            Validated DataFrame
        
        Raises:
            APIError: Bei persistenten Download-Fehlern
            DataValidationError: Bei invaliden Daten
        """
        import yfinance as yf
        
        try:
            logger.info(f"Lade Daten: {ticker}, period={period}, interval={interval}")
            df = yf.download(ticker, period=period, interval=interval, progress=False)
            
            if df.empty:
                raise APIError(f"Keine Daten für {ticker} erhalten")
            
            if validate:
                self.validator.validate_and_raise(df, ticker)
            
            logger.info(f"Daten erfolgreich geladen: {ticker}, {len(df)} Candles")
            return df
            
        except Exception as e:
            logger.error(f"Fehler beim Laden von {ticker}: {e}")
            raise APIError(f"Download fehlgeschlagen für {ticker}: {e}") from e


