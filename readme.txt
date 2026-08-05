Dein [trading_app](https://github.com/moraine128/trading_app) Repository ist eine umfassende automatisierte Trading-Bot-Plattform mit Machine Learning Optimierung, FastAPI-basiertem Web-Dashboard und umfangreichem Backtesting.

## Hauptkomponenten

### Core Trading System
- **main_enhanced.py**: Haupt-Applikation mit FastAPI-Server, Scheduler für automatische Scans und Exit-Checks sowie Dashboard-Routen
- **trading_engine.py**: Trading-Engine für Order-Management, Portfolio-Tracking und Risk-Management
- **indicators_aggressive.py**: Technische Indikatoren und Signal-Generierung mit verschiedenen Strategien
- **settings.json**: Zentrale JSON-Konfiguration für Trading-Parameter, Risk-Limits und Universe-Definitionen

### Backtesting & Optimierung
- **backtest_main.py**: Komplettes Backtesting-Framework mit Trade-Simulation
- **backtest_optimizer.py**: Optuna-Integration für Hyperparameter-Optimierung
- **OPTUNA/**: Separates Verzeichnis für erweiterte ML-Optimierung

### Web Interface
- **templates/**: Jinja2-Templates für Dashboard, Portfolio, Trades, Signals und Statistics
- **static/**: CSS-Styling für das Web-Interface
- **Live Streaming API**: Server-Sent Events für Echtzeit-Updates von Signals, Portfolio und Trades

## Funktionalität

### Trading Modi
- **PAPER**: Simulierter Handel ohne echtes Kapital
- **LIVE**: Echter Handel (Implementierung erforderlich)
- **DEMO**: Test-Modus

### Risk Management
Das System implementiert mehrschichtige Risk-Limits:
- Maximale Anzahl Gesamtpositionen (`MAX_TOTAL_POSITIONS`)
- Maximale Positions pro Ticker (`MAX_POSITION_SIZE`)
- Maximaler Portfolio-Wert (`MAX_PORTFOLIO_VALUE`)
- Maximale Position in % vom Portfolio (`MAX_POSITIONS_PCT`)

### Signal-Generierung
- Automatische Scans in konfigurierbaren Intervallen (z.B. alle paar Stunden)
- Score-basiertes System mit einstellbarem Threshold für Auto-Trading
- DAX 30 und S&P 500 Top 100 Universe-Unterstützung
- Take-Profit und Stop-Loss Management mit optionalem Trailing Stop

### API Endpoints
- `/`: Dashboard mit Übersicht
- `/portfolio`: Aktive Positionen
- `/trades`: Abgeschlossene Trades
- `/signals`: Aktuelle Trading-Signale
- `/stats`: Performance-Statistiken
- `/api/*`: JSON-APIs für programmatischen Zugriff und Streaming

### Datenvalidierung
- **data_validator.py**: Prüfung von Marktdaten-Qualität
- **risk_manager.py**: Zusätzliche Risk-Management-Logik

### Batch-Dateien
- `Start_Trading_BOT.bat`: Startet den Trading Bot
- `start_backtest_aggressive_settings.bat`: Führt Backtests aus
- `start_optimizer_backtest_aggressive_settings.bat`: Startet Optuna-Optimierung

## Technologie-Stack
- **Python**: Hauptprogrammiersprache
- **FastAPI**: Web-Framework für API und Dashboard
- **yfinance**: Marktdaten-Download
- **Optuna**: Machine Learning Hyperparameter-Optimierung
- **APScheduler**: Job-Scheduling für periodische Scans
- **SQLite**: Datenbank für Trade-History (`trading_data.db`)

Das Repository ist modular aufgebaut und ermöglicht flexible Strategieanpassungen 
über die zentrale JSON-Konfigurationsdatei `settings.json`.