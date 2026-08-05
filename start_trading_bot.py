# start_trading_bot.py - KOMPLETT KORRIGIERT
import os
import sys
import webbrowser
from settings_loader import CONFIGS

def clear_screen():
    """Bildschirm löschen"""
    os.system("clear" if os.name == "posix" else "cls")

def print_header(title):
    """Schöner Header"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}\n")

def print_menu(options):
    """Menü anzeigen"""
    for i, option in enumerate(options, 1):
        print(f" {i}) {option}")
    print()

def select_mode():
    """Wähle Trading Mode"""
    print_header("🎯 STARTUP MODE")
    
    modes = [
        "🔴 LIVE TRADING (echte Auto-Trades mit Score >= 5)",
        "🟡 PAPER TRADING (Simulation, kein echtes Geld)",
        "🟢 DEMO MODE (nur Signale, keine Trades)",
        "⚙️ Konfig-Auswahl",
        "⬅️ Zurück zum Hauptmenü"
    ]
    
    print_menu(modes)
    choice = input("Wähle Mode (1-5): ").strip()
    
    if choice == "1":
        print("\n⚠️ WARNING: LIVE TRADING AKTIVIERT!")
        print(" Du wirst ECHTE Trades ausführen!")
        confirm = input(" Bestätige mit 'ja': ").strip().lower()
        if confirm == "ja":
            return "LIVE"
        else:
            print(" ❌ Abgebrochen!")
            return select_mode()
    elif choice == "2":
        return "PAPER"
    elif choice == "3":
        return "DEMO"
    elif choice == "4":
        return select_config()
    elif choice == "5":
        return print_menu()
    else:
        print("❌ Ungültige Auswahl!")
        return select_mode()

def select_config():
    """Wähle vordefinierte Konfiguration"""
    print_header("⚙️ VORDEFINIERTE KONFIGURATIONEN")
    
    configs = [
        "STANDARD (15 min Scan, +3% TP, -2% SL, Score >= 5)",
        "AGGRESSIVE (10 min Scan, +5% TP, -1% SL, Score >= 4)",
        "AGGRESSIVE_MM (10 min Scan, +8% TP, -3% SL, Score >= 5)",
        "CONSERVATIVE (30 min Scan, +2% TP, -3% SL, Score >= 6)",
        "SCALPING (5 min Scan, +1% TP, -0.5% SL, Score >= 5)",
        "⬅️ Zurück"
    ]
    
    print_menu(configs)
    choice = input("Wähle Konfiguration: ").strip()
    
    if choice == "1":
        return ("config", CONFIGS["STANDARD"])
    elif choice == "2":
        return ("config", CONFIGS["AGGRESSIVE"])
    elif choice == "3":
        return ("config", CONFIGS["AGGRESSIVE_MM"])
    elif choice == "4":
        return ("config", CONFIGS["CONSERVATIVE"])
    elif choice == "5":
        return ("config", CONFIGS["SCALPING"])
    elif choice == "6":
        return select_config()
    else:
        print("❌ Ungültige Auswahl!")
        return select_config()

def select_universe():
    """Wähle Markt-Universum"""
    print_header("🌍 MARKT-UNIVERSUM")
    
    universes = [
        "ALL (DAX + S&P500, alle 115 Tickers)",
        "DAX (nur 15 DAX-Aktien, schneller)",
        "SP500 (nur 100 US Tech-Stocks)",
        "⬅️ Zurück"
    ]
    
    print_menu(universes)
    choice = input("Wähle Universum (1-4): ").strip()
    
    if choice == "1":
        return "ALL"
    elif choice == "2":
        return "DAX"
    elif choice == "3":
        return "SP500"
    elif choice == "4":
        return select_mode()
    else:
        print("❌ Ungültige Auswahl!")
        return select_universe()

def show_status():
    """Zeige aktuellen Status"""
    print_header("📊 SYSTEM STATUS")
    
    # Test Imports
    try:
        from trading_engine import TradingEngine
        print(" ✅ trading_engine.py")
    except Exception as e:
        print(f" ❌ trading_engine.py - {e}")
    
    try:
        from indicators_aggressive import add_indicators
        print(" ✅ indicators_aggressive.py")
    except Exception as e:
        print(f" ❌ indicators_aggressive.py - {e}")
    
    try:
        from settings_loader import DAX_TICKERS
        print(" ✅ settings_loader.py")
    except Exception as e:
        print(f" ❌ settings_loader.py - {e}")
    
    try:
        import main_enhanced
        print(" ✅ main_enhanced.py")
    except Exception as e:
        print(f" ❌ main_enhanced.py - {e}")
    
    # Check Database
    if os.path.exists("trading_data.db"):
        size_mb = os.path.getsize("trading_data.db") / (1024*1024)
        print(f" ✅ trading_data.db ({size_mb:.2f} MB)")
    else:
        print(" ⏳ trading_data.db (wird auto-erstellt)")
    
    # Check Templates
    if os.path.exists("templates/"):
        print(" ✅ templates/ (Verzeichnis existiert)")
    else:
        print(" ⚠️ templates/ (wird benötigt)")
    
    if os.path.exists("templates/portfolio.html"):
        print(" ✅ templates/portfolio.html")
    else:
        print(" ⏳ templates/portfolio.html (wird benötigt)")
    
    print()

def show_help():
    """✅ FUNKTION IMPLEMENTIERT - Zeige Hilfe"""
    print_header("📖 HILFE & DOKUMENTATION")
    
    help_text = """
🚀 QUICK START:
1. Wähle "QUICK START" aus dem Menü
2. Wähle Mode (DEMO/PAPER/LIVE)
3. Server startet auf http://localhost:8000
4. Browser öffnet sich automatisch

📊 DASHBOARD:
- / → Hauptdashboard
- /portfolio → Portfolio & Positionen
- /trades → Abgeschlossene Trades
- /api/signals → Aktuelle Signale (JSON)
- /api/stats → Statistiken (JSON)

⚙️ MODES:
🔴 LIVE: Echte Trades mit echtem Geld
🟡 PAPER: Simulierte Trades
🟢 DEMO: Nur Signale, keine Trades

🌍 UNIVERSES:
ALL → DAX + S&P500 (115 Tickers)
DAX → Nur deutsche Aktien (15)
SP500 → Nur US Tech Stocks (100)

📈 AUTO-TRADE:
Wenn Score >= 5 → Automatischer Trade (PAPER/LIVE)
Score ist Summe aller technischen Signale

⏹️ BEENDE:
Ctrl+C im Terminal drücken

🆘 PROBLEME?
- Überprüfe "SYSTEM STATUS"
- Alle Python-Module müssen installiert sein
- pip install -r requirements.txt
- Starte neu mit python start_trading_bot.py
"""
    print(help_text)

def quick_start():
    """Quick Start mit Standard-Einstellungen"""
    clear_screen()
    print_header("⚡ QUICK START")
    
    print("Starte Trading Bot mit Standard-Konfiguration...")
    print(" - Mode: PAPER (Simulation)")
    print(" - Universe: ALL (DAX + S&P500)")
    print(" - Konfiguration: STANDARD")
    print("\n🌐 Browser öffnet sich automatisch:")
    print(" - Dashboard: http://localhost:8000/")
    print(" - Portfolio: http://localhost:8000/portfolio")
    print(" - Trades: http://localhost:8000/trades")
    print(" - API: http://localhost:8000/api/stats")
    print()
    
    input("Drücke ENTER zum Starten...")
    start_server()

def custom_mode():
    """Custom Mode mit Konfiguration"""
    clear_screen()
    print_header("⚙️ CUSTOM MODE")
    
    mode = select_mode()
    
    if mode not in ["LIVE", "PAPER", "DEMO"]:
        return
    
    universe = select_universe()
    
    if universe not in ["ALL", "DAX", "SP500"]:
        return
    
    clear_screen()
    print_header("📋 KONFIGURATION ZUSAMMENFASSUNG")
    
    print(f" Mode: {mode}")
    print(f" Universe: {universe}")
    print(f" Scan: Alle 15 Minuten")
    print(f" TP/SL: 5% / -2%")
    print()
    
    confirm = input("Konfiguration OK? (ja/nein): ").strip().lower()
    
    if confirm == "ja":
        input("Drücke ENTER zum Starten...")
        start_server()
    else:
        print("❌ Abgebrochen!")
        input("Drücke ENTER zum Zurückkehren...")

def start_server():
    """✅ FUNKTION IMPLEMENTIERT - Starte uvicorn Server"""
    clear_screen()
    print_header("🚀 STARTE SERVER")
    
    print("Starting FastAPI Server auf Port 8000...")
    print("📊 Dashboard: http://localhost:8000")
    print("💰 Portfolio: http://localhost:8000/portfolio")
    print("📈 Trades: http://localhost:8000/trades")
    print("ℹ️ API: http://localhost:8000/api/stats")
    print()
    
    print("Drücke Ctrl+C zum Stoppen")
    print()
    
    # Versuche Browser zu öffnen
    try:
        webbrowser.open("http://localhost:8000", new=1)
    except:
        pass
    
    # Starte Server
    try:
        import uvicorn
        uvicorn.run("main_enhanced:app", host="0.0.0.0", port=8000, reload=False)
    except KeyboardInterrupt:
        print("\n\n👋 Server gestoppt!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fehler beim Starten des Servers: {e}")
        print("Stelle sicher, dass:")
        print("1. main_enhanced.py im aktuellen Verzeichnis existiert")
        print("2. Alle Dependencies installiert sind: pip install -r requirements.txt")
        input("Drücke ENTER zum Zurückkehren...")

def main_menu():
    """Hauptmenü"""
    while True:
        clear_screen()
        print_header("🚀 TRADING BOT STARTER v2.0")
        
        options = [
            "✅ QUICK START (Standard Konfiguration)",
            "⚙️ CUSTOM MODE (Menü-basiert)",
            "📊 SYSTEM STATUS prüfen",
            "📖 HILFE anzeigen",
            "❌ Beenden"
        ]
        
        print_menu(options)
        choice = input("Wähle Option (1-5): ").strip()
        
        if choice == "1":
            quick_start()
        elif choice == "2":
            custom_mode()
        elif choice == "3":
            show_status()
            input("\nDrücke ENTER um fortzufahren...")
        elif choice == "4":
            show_help()
            input("\nDrücke ENTER um fortzufahren...")
        elif choice == "5":
            print("\n👋 Auf Wiedersehen!\n")
            sys.exit(0)
        else:
            print("❌ Ungültige Auswahl!")
            input("Drücke ENTER um fortzufahren...")

# ===== Main =====
if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\n👋 Programm beendet!\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fehler: {e}")
        input("Drücke ENTER...")
        sys.exit(1)
