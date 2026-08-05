#!/usr/bin/env python3
"""
Optuna-Runner für den BacktestOptimizer
"""

import os
import sys
import optuna
import pandas as pd
from backtest_optimizer import parallel_jobs

# Anzahl Trials für ersten Test klein halten
n_trials = 40

# Pfade setzen: dieses Skript liegt im Unterordner "optuna"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Projekt-Root in sys.path aufnehmen, damit backtest_main importierbar ist
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from backtest_optimizer import BacktestOptimizer
from backtest_optimizer import parallel_jobs


def main():
    print("=" * 80)
    print("🚀 OPTUNA TRADING OPTIMIZER")
    print("=" * 80)

    # Pfad zur Optuna-Konfig
    config_path = os.path.join(SCRIPT_DIR, "optuna_config.json")

    if not os.path.exists(config_path):
        print(f"❌ optuna_config.json nicht gefunden unter: {config_path}")
        sys.exit(1)

    # Optimizer initialisieren
    optimizer = BacktestOptimizer(config_path)

    # Storage: für Debugging zuerst OHNE SQLite laufen lassen
    use_storage = True  # auf True setzen, wenn stabil

    if use_storage:
        storage_url = f"sqlite:///{os.path.join(SCRIPT_DIR, 'optuna_backtests.db')}"
        study_name = "trading_strategy_v1"
    else:
        storage_url = None
        study_name = None

    print(f"\n⚙️  Starte Studie:")
    print(f"   • Trials:        {n_trials}")
    print(f"   • Direction:     maximize (total_return)")
    print(f"   • Storage:       {storage_url or 'in-memory'}")
    print(f"   • Study-Name:    {study_name or '(auto)'}")
    print(f"   • Parallel Jobs: {parallel_jobs}")
    print("=" * 80)

    # Study anlegen
    if use_storage:
        study = optuna.create_study(
            direction="maximize",
            storage=storage_url,
            study_name=study_name,
            load_if_exists=True,
        )
    else:
        study = optuna.create_study(direction="maximize")

    # Optimization starten
    study = optimizer.run_optuna_optimization(
        n_trials=n_trials,
        direction="maximize",
        storage=storage_url,
        study_name=study_name,
        n_jobs=parallel_jobs,          # wichtig: 1 Job, solange viel Debug-Output
    )

    print("\n" + "=" * 80)
    print("✅ OPTIMIERUNG ABGESCHLOSSEN")
    print("=" * 80)

    # Ergebnisse
    if len(study.trials) == 0:
        print("❌ Keine abgeschlossenen Trials. Prüfe Log-Ausgaben.")
        return

    best = study.best_trial

    print(f"\n🏆 Best Trial: {best.number}")
    print(f"   • Best Value (total_return): {best.value:.2f}")
    print("   • Params:")
    if not best.params:
        print("      (keine Params gespeichert – prüfe _build_trial_params / optimization_ranges)")
    else:
        for k, v in best.params.items():
            print(f"      - {k}: {v}")

    # Ergebnisse in CSV
    df = optimizer.get_results_df()
    if df.empty:
        print("\n⚠️ Keine Resultate in optimizer.results. Prüfe _objective-Fehler.")
    else:
        results_path = os.path.join(SCRIPT_DIR, "optuna_results.csv")
        df.to_csv(results_path, index=False)
        print(f"\n💾 Ergebnisse gespeichert unter: {results_path}")

        # Top 5 nach Value
        cols = [c for c in ["trial", "value",
                            "TAKE_PROFIT_PCT", "STOP_LOSS_PCT",
                            "AUTO_TRADE_SCORE_THRESHOLD", "MAX_TOTAL_POSITIONS",
                            "total_trades", "win_rate", "sharpe_ratio",
                            "max_drawdown_pct", "final_capital"] if c in df.columns]

        print("\n📊 Top 5 Konfigurationen:")
        print(df.sort_values("value", ascending=False)
                .head(5)[cols].to_string(index=False))


if __name__ == "__main__":
    main()
