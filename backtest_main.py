#!/usr/bin/env python3
"""
90-Tage Backtesting System für Trading Bot - UPDATED FOR NEW SETTINGS
"""

import json
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List
import warnings
warnings.filterwarnings('ignore')

# Import der bestehenden Indicator-Funktionen
try:
    from indicators_aggressive import add_indicators, get_signal_details
    from settings_loader import DAX_TICKERS, SP500_TOP100
    INDICATORS_AVAILABLE = True
except ImportError:
    print("⚠️ Warning: indicators_aggressive.py oder settings_loader.py nicht gefunden.")
    INDICATORS_AVAILABLE = False
    DAX_TICKERS = {}
    SP500_TOP100 = {}


class BacktestEngine:
    """Backtesting Engine für Trading Strategien"""

    def __init__(self, settings_path: str = "settings.json"):
        with open(settings_path, 'r') as f:
            config = json.load(f)
        
        # Load active profile or specified profile
        active_profile = config.get('active_profile', 'best_optimized')
        self.profile = config['profiles'][active_profile]
        
        # Extract backtest config
        backtest_cfg = self.profile.get('backtest_config', {})
        self.start_capital = backtest_cfg.get('start_capital', 10000)
        self.commission = backtest_cfg.get('commission_per_trade', 0.001)
        self.slippage = backtest_cfg.get('slippage_pct', 0.001)
        self.backtest_days = backtest_cfg.get('backtest_days', 90)
        
        # Extract universe settings
        universe_cfg = self.profile.get('universe', {})
        self.use_dax = universe_cfg.get('use_dax', True)
        self.use_sp500 = universe_cfg.get('use_sp500', True)
        self.blacklist = set(universe_cfg.get('blacklist', []))
        
        # Extract trading parameters
        trading_params = self.profile.get('trading_parameters', {})
        self.take_profit_pct = trading_params.get('TAKE_PROFIT_PCT', 0.03)
        self.stop_loss_pct = trading_params.get('STOP_LOSS_PCT', 0.02)
        self.auto_trade_score_threshold = trading_params.get('AUTO_TRADE_SCORE_THRESHOLD', 5)
        self.max_total_positions = trading_params.get('MAX_TOTAL_POSITIONS', 10)
        self.max_portfolio_value = trading_params.get('MAX_PORTFOLIO_VALUE', 50000)
        self.max_positions_pct = trading_params.get('MAX_POSITIONS_PCT', 0.1)
        self.use_trailing_stop = trading_params.get('USE_TRAILING_STOP', True)
        self.trailing_stop_activation = trading_params.get('TRAILING_STOP_ACTIVATION', 0.02)
        self.trailing_stop_distance = trading_params.get('TRAILING_STOP_DISTANCE', 0.01)
        
        # Extract filters
        filters = self.profile.get('filters', {})
        self.min_price = filters.get('MIN_PRICE', 5.0)
        self.max_price = filters.get('MAX_PRICE', 1000.0)
        self.min_avg_volume = filters.get('MIN_AVG_VOLUME', 100000)
        self.min_volume_spike = filters.get('VOLUME_SPIKE_THRESHOLD', 1.0)
        self.use_trend_filter = filters.get('USE_TREND_FILTER', False)
        
        # Extract risk management
        risk_mgmt = self.profile.get('risk_management', {})
        self.use_atr_sizing = risk_mgmt.get('USE_ATR_POSITION_SIZING', False)
        self.max_risk_per_trade = risk_mgmt.get('MAX_RISK_PER_TRADE', 0.02)
        self.max_portfolio_exposure = risk_mgmt.get('MAX_PORTFOLIO_EXPOSURE', 0.90)

        self.cash = self.start_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []

    def reset(self):
        self.cash = self.start_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []

    def get_universe(self) -> List[str]:
        tickers = []
        if self.use_dax:
            tickers.extend(list(DAX_TICKERS.keys()) if DAX_TICKERS else [])
        if self.use_sp500:
            tickers.extend(list(SP500_TOP100.keys()) if SP500_TOP100 else [])

        tickers = [t for t in tickers if t not in self.blacklist]

        return list(set(tickers))

    def download_historical_data(self, ticker: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """FIXED VERSION - Download mit korrektem Column-Handling"""
        try:
            extended_start = start_date - timedelta(days=250)

            # Download
            df = yf.download(ticker, start=extended_start, end=end_date, progress=False)

            if df is None or df.empty:
                return None

            # Reset index FIRST
            df = df.reset_index()

            # FIX 1: Flatten MultiIndex columns if present
            if isinstance(df.columns, pd.MultiIndex):
                # Nimm nur die erste Ebene des MultiIndex
                df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]

            # FIX 2: Sichere Spaltenumbenennung
            rename_map = {}
            for col in df.columns:
                # Konvertiere ALLES zu String, dann lowercase
                col_str = str(col).lower().strip()

                if 'date' in col_str:
                    rename_map[col] = 'Date'
                elif col_str == 'open':
                    rename_map[col] = 'Open'
                elif col_str == 'high':
                    rename_map[col] = 'High'
                elif col_str == 'low':
                    rename_map[col] = 'Low'
                elif col_str == 'close':
                    rename_map[col] = 'Close'
                elif col_str == 'volume':
                    rename_map[col] = 'Volume'

            if rename_map:
                df = df.rename(columns=rename_map)

            # Timezone fix
            if 'Date' in df.columns:
                if hasattr(df['Date'].dtype, 'tz') and df['Date'].dtype.tz is not None:
                    df['Date'] = df['Date'].dt.tz_localize(None)

            # Validierung
            required = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            if not all(col in df.columns for col in required):
                return None
            
            # FIX 3: Konvertiere Date zu date() für sichere Vergleiche
            df['Date'] = pd.to_datetime(df['Date']).dt.date

            return df

        except Exception as e:
            print(f"❌ Error downloading {ticker}: {e}")
            return None

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if INDICATORS_AVAILABLE:
            return add_indicators(df)
        else:
            df['RSI'] = 50
            df['Signal'] = 'HOLD'
            return df

    def get_signal(self, df: pd.DataFrame, date: datetime) -> Dict:
        # Konvertiere date zu date() für Vergleich
        date_only = date.date() if hasattr(date, 'date') else date
        historical_df = df[df['Date'] <= date_only].copy()

        if len(historical_df) < 50:
            return {'signal': 'HOLD', 'score': 0}

        if INDICATORS_AVAILABLE:
            historical_df = self.calculate_indicators(historical_df)
            signal = get_signal_details(historical_df)
        else:
            signal = {'signal': 'HOLD', 'score': 0}

        return signal

    def apply_filters(self, df: pd.DataFrame, date: datetime) -> bool:
        # Konvertiere date zu date() für Vergleich
        date_only = date.date() if hasattr(date, 'date') else date
        historical_df = df[df['Date'] <= date_only]

        if len(historical_df) < 50:
            return False

        current_row = historical_df.iloc[-1]

        if current_row['Close'] < self.min_price:
            return False
        if current_row['Close'] > self.max_price:
            return False

        avg_volume = historical_df['Volume'].tail(20).mean()
        if avg_volume < self.min_avg_volume:
            return False

        volume_ratio = current_row['Volume'] / avg_volume
        if volume_ratio < self.min_volume_spike:
            return False

        if self.use_trend_filter:
            if len(historical_df) >= 200:
                sma_200 = historical_df['Close'].tail(200).mean()
                if current_row['Close'] < sma_200:
                    return False

        return True

    def calculate_position_size(self, price: float, atr: float = None) -> int:
        max_position_value = self.max_portfolio_value * self.max_positions_pct

        if self.use_atr_sizing and atr:
            risk_per_trade = self.cash * self.max_risk_per_trade
            stop_distance = self.stop_loss_pct * price
            position_value = risk_per_trade / stop_distance * price
            position_value = min(position_value, max_position_value)
        else:
            position_value = max_position_value

        position_value = min(position_value, self.cash * 0.95)

        quantity = int(position_value / price)
        return max(1, quantity)

    def can_open_position(self) -> bool:
        if len(self.positions) >= self.max_total_positions:
            return False

        total_invested = sum(pos['qty'] * pos['entry_price'] for pos in self.positions.values())
        exposure_pct = total_invested / self.start_capital

        if exposure_pct >= self.max_portfolio_exposure:
            return False

        return True

    def open_position(self, ticker: str, date: datetime, price: float, score: int):
        quantity = self.calculate_position_size(price)

        if quantity < 1:
            return

        actual_price = price * (1 + self.slippage)
        cost = quantity * actual_price
        commission_cost = cost * self.commission
        total_cost = cost + commission_cost

        if total_cost > self.cash:
            return

        self.cash -= total_cost
        self.positions[ticker] = {
            'qty': quantity,
            'entry_price': actual_price,
            'entry_date': date,
            'score': score,
            'highest_price': price,
            'trailing_stop_active': False
        }

    def close_position(self, ticker: str, date: datetime, price: float, reason: str):
        if ticker not in self.positions:
            return

        pos = self.positions[ticker]

        actual_price = price * (1 - self.slippage)
        proceeds = pos['qty'] * actual_price
        commission_cost = proceeds * self.commission
        net_proceeds = proceeds - commission_cost

        self.cash += net_proceeds

        pnl = net_proceeds - (pos['qty'] * pos['entry_price'])
        pnl_pct = (actual_price - pos['entry_price']) / pos['entry_price']

        self.trades.append({
            'ticker': ticker,
            'entry_date': pos['entry_date'],
            'exit_date': date,
            'entry_price': pos['entry_price'],
            'exit_price': actual_price,
            'quantity': pos['qty'],
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'reason': reason,
            'score': pos['score'],
            'holding_days': (date - pos['entry_date']).days
        })

        del self.positions[ticker]

    def check_exit_conditions(self, ticker: str, date: datetime, current_price: float):
        if ticker not in self.positions:
            return

        pos = self.positions[ticker]
        entry_price = pos['entry_price']

        if current_price >= entry_price * (1 + self.take_profit_pct):
            self.close_position(ticker, date, current_price, 'TAKE_PROFIT')
            return

        if current_price <= entry_price * (1 - self.stop_loss_pct):
            self.close_position(ticker, date, current_price, 'STOP_LOSS')
            return

        if self.use_trailing_stop:
            if current_price > pos['highest_price']:
                pos['highest_price'] = current_price

            if current_price >= entry_price * (1 + self.trailing_stop_activation):
                pos['trailing_stop_active'] = True

            if pos['trailing_stop_active']:
                trailing_stop_price = pos['highest_price'] * (1 - self.trailing_stop_distance)
                if current_price <= trailing_stop_price:
                    self.close_position(ticker, date, current_price, 'TRAILING_STOP')
                    return

    def run_backtest(self, progress_callback=None) -> Dict:
        self.reset()

        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.backtest_days)

        tickers = self.get_universe()
        if not tickers:
            print("⚠️ Keine Tickers. Fallback.")
            tickers = ['AAPL', 'MSFT', 'GOOGL']

        print(f"\n🔍 Starte Backtest über {self.backtest_days} Tage")
        print(f"📅 Zeitraum: {start_date.date()} bis {end_date.date()}")
        print(f"💰 Start-Kapital: €{self.start_capital:,.2f}")
        print(f"📊 Universe: {len(tickers)} Tickers")
        print("=" * 60)

        print("\n📥 Lade historische Daten...")
        ticker_data = {}
        success_count = 0

        for i, ticker in enumerate(tickers, 1):
            if i % 10 == 0:
                print(f"  Progress: {i}/{len(tickers)} ({success_count} erfolgreich)")

            df = self.download_historical_data(ticker, start_date, end_date)
            if df is not None and len(df) > 50:
                ticker_data[ticker] = df
                success_count += 1

        print(f"✅ {len(ticker_data)} Tickers erfolgreich geladen\n")

        if len(ticker_data) == 0:
            print("❌ FEHLER: Keine Daten geladen!")
            return self.calculate_metrics()

        # Trading simulation
        trading_days = pd.date_range(start=start_date, end=end_date, freq='D')

        for day_num, current_date in enumerate(trading_days, 1):
            if current_date.weekday() >= 5:
                continue
            
            # Konvertiere current_date zu date() für Vergleiche
            current_date_only = current_date.date()

            # Exit checks
            for ticker in list(self.positions.keys()):
                if ticker in ticker_data:
                    df = ticker_data[ticker]
                    day_data = df[df['Date'] == current_date_only]
                    if not day_data.empty:
                        current_price = day_data.iloc[0]['Close']
                        self.check_exit_conditions(ticker, current_date, current_price)

            # Entry signals
            if self.can_open_position():
                signals = []

                for ticker, df in ticker_data.items():
                    if ticker in self.positions:
                        continue

                    if not self.apply_filters(df, current_date):
                        continue

                    signal = self.get_signal(df, current_date)

                    if signal.get('score', 0) >= self.auto_trade_score_threshold:
                        day_data = df[df['Date'] == current_date_only]
                        if not day_data.empty:
                            current_price = day_data.iloc[0]['Close']
                            signals.append({
                                'ticker': ticker,
                                'score': signal['score'],
                                'price': current_price
                            })

                signals.sort(key=lambda x: x['score'], reverse=True)

                for sig in signals:
                    if not self.can_open_position():
                        break
                    self.open_position(sig['ticker'], current_date, sig['price'], sig['score'])

            # Track equity
            portfolio_value = self.cash
            for ticker, pos in self.positions.items():
                if ticker in ticker_data:
                    df = ticker_data[ticker]
                    day_data = df[df['Date'] == current_date_only]
                    if not day_data.empty:
                        current_price = day_data.iloc[0]['Close']
                        portfolio_value += pos['qty'] * current_price

            self.equity_curve.append({
                'date': current_date,
                'portfolio_value': portfolio_value,
                'cash': self.cash,
                'open_positions': len(self.positions)
            })

        # Close all positions
        for ticker in list(self.positions.keys()):
            if ticker in ticker_data:
                df = ticker_data[ticker]
                last_price = df.iloc[-1]['Close']
                self.close_position(ticker, end_date, last_price, 'BACKTEST_END')

        return self.calculate_metrics()

    def calculate_metrics(self) -> Dict:
        if not self.trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'final_capital': self.cash,
                'total_return': 0,
                'total_return_pct': 0,
                'sharpe_ratio': 0,
                'max_drawdown_pct': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'avg_holding_days': 0
            }

        final_capital = self.cash
        total_return = final_capital - self.start_capital
        total_return_pct = (total_return / self.start_capital) * 100

        winning_trades = [t for t in self.trades if t['pnl'] > 0]
        losing_trades = [t for t in self.trades if t['pnl'] <= 0]

        win_rate = len(winning_trades) / len(self.trades) * 100 if self.trades else 0
        avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0

        total_wins = sum(t['pnl'] for t in winning_trades)
        total_losses = abs(sum(t['pnl'] for t in losing_trades))
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

        if len(self.equity_curve) > 1:
            equity_series = pd.Series([e['portfolio_value'] for e in self.equity_curve])
            returns = equity_series.pct_change().dropna()
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
        else:
            sharpe_ratio = 0

        equity_series = pd.Series([e['portfolio_value'] for e in self.equity_curve])
        cummax = equity_series.cummax()
        drawdown = (equity_series - cummax) / cummax * 100
        max_drawdown_pct = drawdown.min()

        return {
            'total_trades': len(self.trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'final_capital': final_capital,
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown_pct': max_drawdown_pct,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'avg_holding_days': np.mean([t['holding_days'] for t in self.trades])
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='90-Tage Backtest')
    parser.add_argument('--settings', default='settings.json', help='Path to settings.json')

    args = parser.parse_args()

    engine = BacktestEngine(args.settings)
    metrics = engine.run_backtest()

    print("\n" + "=" * 60)
    print("📊 BACKTEST ERGEBNISSE")
    print("=" * 60)
    print(f"Total Trades: {metrics['total_trades']}")
    print(f"Winning Trades: {metrics['winning_trades']}")
    print(f"Losing Trades: {metrics['losing_trades']}")
    print(f"Win Rate: {metrics['win_rate']:.2f}%")
    print(f"\nStart-Kapital: €{engine.start_capital:,.2f}")
    print(f"End-Kapital: €{metrics['final_capital']:,.2f}")
    print(f"Total Return: €{metrics['total_return']:,.2f} ({metrics['total_return_pct']:.2f}%)")
    print(f"\nSharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    print(f"Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
    print(f"Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"\nAvg Win: €{metrics['avg_win']:.2f}")
    print(f"Avg Loss: €{metrics['avg_loss']:.2f}")
    print(f"Avg Holding Days: {metrics['avg_holding_days']:.1f}")
    print("=" * 60)

    results_df = pd.DataFrame(engine.trades)
    if not results_df.empty:
        results_df.to_csv('backtest_trades.csv', index=False)
        print("\n✅ Trade-Details: backtest_trades.csv")

    equity_df = pd.DataFrame(engine.equity_curve)
    if not equity_df.empty:
        equity_df.to_csv('backtest_equity_curve.csv', index=False)
        print("✅ Equity Curve: backtest_equity_curve.csv")
