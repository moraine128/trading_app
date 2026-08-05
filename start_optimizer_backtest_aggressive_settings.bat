@REM # Ermittelt die besten Einstellungen mit dem Optimizer
python backtest_optimizer.py --settings aggressive_settings.json
@REM # Mit Begrenzung auf 20 Tests
@REM python backtest_optimizer.py --settings aggressive_settings.json --max-tests 20
