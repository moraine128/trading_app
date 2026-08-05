#!/usr/bin/env python3
"""
Backtest Optimizer - Finde die besten Trading-Parameter
"""

import json
import pandas as pd
from itertools import product
from datetime import datetime
from typing import List, Dict
import warnings
warnings.filterwarnings('ignore')

# Import BacktestEngine (benötigt backtest_main.py)
try:
    from backtest_main import BacktestEngine
except ImportError:
    print("❌ Fehler: Kann backtest_main.py nicht finden!")
    exit(1)


class BacktestOptimizer:
    """Parameter-Optimierung für Trading-Strategien"""

    def __init__(self, settings_path: str = "settings.json", profile: str = None):
        """Initialize optimizer with new settings.json structure"""
        with open(settings_path, 'r') as f:
            config = json.load(f)
        
        # Use specified profile or active profile
        if profile is None:
            profile = config.get('active_profile', 'best_optimized')
        
        self.profile_name = profile
        self.base_settings = config['profiles'][profile]
        self.optimization_ranges = config.get('optimization_ranges', {})
        self.results = []

    def generate_parameter_combinations(self) -> List[Dict]:
        """Generiere alle Parameter-Kombinationen aus optimization_ranges"""

        if not self.optimization_ranges:
            print("⚠️ Keine optimization_ranges in Settings gefunden!")
            return []

        # Extrahiere die Parameter die optimiert werden sollen
        param_names = list(self.optimization_ranges.keys())
        param_values = [self.optimization_ranges[name] for name in param_names]

        # Generiere alle Kombinationen
        combinations = list(product(*param_values))

        print(f"\n🔍 Generiere {len(combinations)} Parameter-Kombinationen")
        print(f"📊 Optimiere: {', '.join(param_names)}")

        return [
            {param_names[i]: combo[i] for i in range(len(param_names))}
            for combo in combinations
        ]

    def create_settings_with_params(self, params: Dict) -> Dict:
        """Erstelle Settings-Dict mit neuen Parametern (neue JSON-Struktur)"""
        import copy
        settings = copy.deepcopy(self.base_settings)

        # Update trading_parameters
        for key, value in params.items():
            if key in settings.get('trading_parameters', {}):
                settings['trading_parameters'][key] = value

        return settings

    def create_temp_settings_file(self, settings: Dict, idx: int) -> str:
        """Create temporary settings.json file for backtest"""
        temp_path = f"temp_settings_{idx}.json"
        
        # Wrap in settings.json structure
        temp_config = {
            "active_profile": "temp",
            "profiles": {
                "temp": settings
            },
            "optimization_ranges": self.optimization_ranges
        }
        
        with open(temp_path, 'w') as f:
            json.dump(temp_config, f, indent=2)
        
        return temp_path

    def run_optimization(self, max_tests: int = None) -> pd.DataFrame:
        """Führe Optimierung durch"""

        combinations = self.generate_parameter_combinations()

        if max_tests and len(combinations) > max_tests:
            print(f"⚠️ Limitiere auf {max_tests} von {len(combinations)} Tests")
            import random
            combinations = random.sample(combinations, max_tests)

        total = len(combinations)

        print(f"\n🚀 Starte Optimierung mit {total} Tests...")
        print("=" * 80)

        for idx, params in enumerate(combinations, 1):
            # Erstelle temporäre Settings
            settings = self.create_settings_with_params(params)
            temp_settings_path = self.create_temp_settings_file(settings, idx)

            try:
                # Suppress output für schnellere Ausführung
                import sys
                import io
                old_stdout = sys.stdout
                sys.stdout = io.StringIO()

                # Führe Backtest durch
                engine = BacktestEngine(temp_settings_path)
                metrics = engine.run_backtest()

                # Restore output
                sys.stdout = old_stdout

                # Speichere Ergebnisse
                result = {
                    'test_id': idx,
                    'profile': self.profile_name,
                    **params,
                    **metrics
                }
                self.results.append(result)

                # Print Progress alle 10 Tests
                if idx % 10 == 0 or idx == total:
                    print(f"[{idx}/{total}] Trades: {metrics['total_trades']}, "
                          f"Return: {metrics['total_return_pct']:.2f}%, "
                          f"Win Rate: {metrics['win_rate']:.1f}%")

            except Exception as e:
                sys.stdout = old_stdout
                print(f"  ❌ Error in Test #{idx}: {e}")
                self.results.append({
                    'test_id': idx,
                    'profile': self.profile_name,
                    **params,
                    'error': str(e)
                })

            # Cleanup
            import os
            if os.path.exists(temp_settings_path):
                os.remove(temp_settings_path)

        # Konvertiere zu DataFrame
        results_df = pd.DataFrame(self.results)

        print("\n" + "=" * 80)
        print("✅ OPTIMIERUNG ABGESCHLOSSEN")
        print("=" * 80)

        return results_df

    def analyze_results(self, results_df: pd.DataFrame) -> Dict:
        """Analysiere Optimierungsergebnisse"""

        # Entferne fehlerhafte Tests
        valid_results = results_df[~results_df['total_trades'].isna()].copy()

        if valid_results.empty:
            print("❌ Keine gültigen Ergebnisse!")
            return {}

        print(f"\n📊 OPTIMIERUNGS-ANALYSE")
        print("=" * 80)
        print(f"Gültige Tests: {len(valid_results)} von {len(results_df)}")

        # Zeige TOP 5 nach Return
        print(f"\n🏆 TOP 5 NACH RETURN:")
        print("=" * 80)

        top5 = valid_results.nlargest(5, 'total_return_pct')

        for idx, row in top5.iterrows():
            print(f"\n#{int(row['test_id'])}: {row['total_return_pct']:.2f}% Return")
            print(f"  Trades: {int(row['total_trades'])}, Win Rate: {row['win_rate']:.1f}%, Sharpe: {row['sharpe_ratio']:.2f}")
            print(f"  Max DD: {row['max_drawdown_pct']:.2f}%, Profit Factor: {row['profit_factor']:.2f}")

            # Parameter anzeigen
            param_cols = [c for c in valid_results.columns 
                         if c in self.optimization_ranges.keys()]
            params = {col: row[col] for col in param_cols}
            print(f"  Parameter: {params}")

        # Beste Config speichern
        best_row = valid_results.loc[valid_results['total_return_pct'].idxmax()]

        best_settings = self.create_settings_with_params({
            key: best_row[key] 
            for key in self.optimization_ranges.keys()
        })
        
        # Save to new settings.json structure
        best_config = {
            "active_profile": "optimized",
            "profiles": {
                "optimized": best_settings,
                self.profile_name: self.base_settings
            },
            "optimization_ranges": self.optimization_ranges
        }

        with open('best_settings_optimized.json', 'w') as f:
            json.dump(best_config, f, indent=2)

        print(f"\n💾 Beste Settings gespeichert: best_settings_optimized.json")

        # Speichere alle Ergebnisse
        results_df.to_csv('optimization_results.csv', index=False)
        print(f"💾 Alle Ergebnisse gespeichert: optimization_results.csv")

        print("\n" + "=" * 80)

        return best_settings


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Backtest Parameter Optimization')
    parser.add_argument('--settings', default='settings.json',
                       help='Settings file with profiles and optimization_ranges')
    parser.add_argument('--profile', default=None,
                       help='Profile to optimize (default: active_profile from settings.json)')
    parser.add_argument('--max-tests', type=int, default=None,
                       help='Maximum number of tests (default: all combinations)')

    args = parser.parse_args()

    # Erstelle Optimizer
    optimizer = BacktestOptimizer(args.settings, args.profile)

    # Führe Optimierung durch
    results = optimizer.run_optimization(max_tests=args.max_tests)

    # Analysiere Ergebnisse
    optimizer.analyze_results(results)

    print("\n✅ Optimierung komplett!")
    print("\nNächste Schritte:")
    print("  1. Prüfe optimization_results.csv für alle Tests")
    print("  2. Teste beste Settings: python backtest_main.py --settings best_settings_optimized.json")
