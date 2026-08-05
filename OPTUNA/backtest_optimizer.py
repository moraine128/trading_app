import json
import optuna
import pandas as pd
from typing import Dict
import os
import sys

# MM: multihreading support
parallel_jobs = 1 # max(1, os.cpu_count()//2 - 1) # MM:leave one core free for system
# print(f"\n Threads used for the run: {parallel_jobs}")

# Import BacktestEngine
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest_main import BacktestEngine


class BacktestOptimizer:
    """Parameter-Optimierung für Trading-Strategien mit Optuna"""

    def __init__(self, base_settings_path: str):
        with open(base_settings_path, 'r', encoding='utf-8') as f:
            self.base_settings = json.load(f)
        self.results = []

    def create_settings_with_params(self, params: Dict) -> Dict:
        """Erstellt Settings-Dict mit optimierten Parametern"""
        import copy
        settings = copy.deepcopy(self.base_settings)
        
        # Update trading_parameters mit optimierten Werten
        for key, value in params.items():
            if key in settings['trading_parameters']:
                settings['trading_parameters'][key] = value
        
        return settings

    def _build_trial_params(self, trial: optuna.Trial) -> Dict:
        """
        Erzeugt aus base_settings['optimization_ranges'] die Optuna-Suchräume
        """
        ranges = self.base_settings.get('optimization_ranges', {})
        params = {}
        
        for name, spec in ranges.items():
            t = spec.get("type", "float")
            
            if t == "float":
                params[name] = trial.suggest_float(
                    name,
                    spec["low"],
                    spec["high"],
                    log=spec.get("log", False)
                )
            elif t == "int":
                params[name] = trial.suggest_int(
                    name,
                    spec["low"],
                    spec["high"],
                    log=spec.get("log", False)
                )
            elif t == "categorical":
                params[name] = trial.suggest_categorical(
                    name,
                    spec["choices"]
                )
            else:
                raise ValueError(f"Unbekannter Parametertyp für {name}: {t}")
        
        return params

    def _objective(self, trial: optuna.Trial) -> float:
        """
        Optuna-Objective: Parameter → Backtest → Score (Net PnL mit Drawdown/Sharpe-Adjust)
        """
        params = self._build_trial_params(trial)
        settings = self.create_settings_with_params(params)

        # Temporäre Settings-Datei
        temp_path = f"temp_optuna_trial_{trial.number}.json"

        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)

            import io
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()

            try:
                engine = BacktestEngine(temp_path)
                metrics = engine.run_backtest()
            except Exception as backtest_error:
                sys.stdout = old_stdout
                print(f"\n❌ Trial {trial.number} backtest failed: {backtest_error}")
                return -1000.0
            finally:
                captured = sys.stdout.getvalue()
                sys.stdout = old_stdout

            if not isinstance(metrics, dict):
                print(f"\n❌ Trial {trial.number}: metrics is not a dict, got {type(metrics)}")
                return -1000.0

            net_pnl = float(metrics.get("total_return", -1000.0))
            total_trades = int(metrics.get("total_trades", 0))
            sharpe = float(metrics.get("sharpe_ratio", 0.0))
            max_dd = float(abs(metrics.get("max_drawdown_pct", 100.0)))

            # Mindestanzahl Trades (sonst zu noisy)
            MIN_TRADES = 3
            if total_trades < MIN_TRADES:
                print(f"  ⚠️ Trial {trial.number}: only {total_trades} trades – penalizing")
                score = -1000
            else:
                # Basis-Score ist Netto-PnL
                score = net_pnl

                # Drawdown-Penalty
                if max_dd > 50:
                    score *= 0.5
                if max_dd > 70:
                    score *= 0.5  # insgesamt 0.25 bei DD > 70%

                # Sharpe-Bonus
                if sharpe > 1.5:
                    score *= 1.1
                if sharpe > 2.0:
                    score *= 1.2

            # Debug-Log
            print(
                f"Trial {trial.number}: PnL={net_pnl:.2f}, trades={total_trades}, "
                f"Sharpe={sharpe:.2f}, DD={max_dd:.1f} → score={score:.2f}"
            )

            # Trial-Metadaten
            trial.set_user_attr("params", params)
            trial.set_user_attr("metrics", metrics)
            trial.set_user_attr("total_trades", total_trades)
            trial.set_user_attr("win_rate", metrics.get("win_rate", 0.0))
            trial.set_user_attr("sharpe_ratio", sharpe)
            trial.set_user_attr("max_drawdown_pct", max_dd)
            trial.set_user_attr("final_capital", metrics.get("final_capital", 0.0))

            return score

        except Exception as e:
            print(f"\n❌ Trial {trial.number} failed: {e}")
            import traceback
            traceback.print_exc()
            return -1000.0

        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass

 
    def run_optuna_optimization(
        self,
        n_trials: int = 50,
        direction: str = "maximize",
        storage: str = None,
        study_name: str = None,
        n_jobs: int = parallel_jobs, #parallel jobs
    ) -> optuna.Study:
        """
        Startet Optuna-Optimierung
        
        Args:
            n_trials: Anzahl der Trials
            direction: 'maximize' oder 'minimize'
            storage: z.B. 'sqlite:///optuna_backtests.db'
            study_name: Name der Studie
            n_jobs: Anzahl paralleler Jobs (1 = sequential)
        """
        study = optuna.create_study(
            direction=direction,
            study_name=study_name,
            storage=storage,
            load_if_exists=bool(storage),
        )
        
        study.optimize(
            self._objective,
            n_trials=n_trials,
            n_jobs=n_jobs,
            show_progress_bar=True
        )

        # Ergebnisse in self.results speichern
        self.results = []
        for trial in study.trials:
            if trial.state == optuna.trial.TrialState.COMPLETE:
                row = {
                    "trial": trial.number,
                    "value": trial.value,
                    "state": str(trial.state),
                }
                # alle gesampelten Parameter
                for k, v in trial.params.items():
                    row[k] = v

                # wichtige Metriken aus user_attrs
                for key in [
                    "total_trades",
                    "win_rate",
                    "sharpe_ratio",
                    "max_drawdown_pct",
                    "final_capital",
                ]:
                    row[key] = trial.user_attrs.get(key, None)

                self.results.append(row)


        return study

    def get_results_df(self) -> pd.DataFrame:
        """Gibt Ergebnisse als DataFrame zurück"""
        return pd.DataFrame(self.results)
'''
print("📄 VOLLSTÄNDIGE backtest_optimizer.py")
print("=" * 80)
print(complete_optimizer)
print("\n" + "=" * 80)
'''