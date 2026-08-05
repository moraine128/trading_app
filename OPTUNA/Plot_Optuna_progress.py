#!/usr/bin/env python3
"""
Optuna Visualisierung für Trading Strategy Optimization
"""

import os
import optuna
from optuna.visualization import (
    plot_optimization_history,
    plot_param_importances,
    plot_parallel_coordinate,
)


def plot_optuna_progress():
    """Erstellt HTML-Visualisierungen der Optuna Study."""
    # Pfad zur DB im OPTUNA-Ordner
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, "optuna_backtests.db")
    storage_url = f"sqlite:///{db_path}"

    print(f"📂 Lade Study von: {db_path}")

    try:
        study = optuna.load_study(
            storage=storage_url,
            study_name="trading_strategy_v1",
        )
    except KeyError:
        print("❌ Study 'trading_strategy_v1' nicht gefunden.")
        print("   Führe zuerst optuna_main.py mit use_storage=True aus.")
        return

    n_trials = len(study.trials)
    print(f"✅ Study geladen: {n_trials} Trials gefunden")

    if n_trials < 3:
        print("⚠️ Zu wenige Trials für sinnvolle Visualisierung (min. 3 empfohlen).")
        return

    # 1. Optimization History
    fig1 = plot_optimization_history(study)
    fig1.write_html(os.path.join(script_dir, "optimization_history.html"))

    # 2. Param Importances
    fig2 = plot_param_importances(study)
    fig2.write_html(os.path.join(script_dir, "param_importances.html"))

    # 3. Parallel Coordinate
    fig3 = plot_parallel_coordinate(study)
    fig3.write_html(os.path.join(script_dir, "parallel_coordinate.html"))

    print("📊 Visualisierungen erstellt:")
    print("   - optimization_history.html")
    print("   - param_importances.html")
    print("   - parallel_coordinate.html")


if __name__ == "__main__":
    plot_optuna_progress()
