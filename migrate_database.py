#!/usr/bin/env python3
"""
Database Migration Script
Fügt fehlende Spalten zur orders-Tabelle hinzu
"""

import sqlite3
import os
import sys

def migrate_database(dbpath: str = "trading_data.db"):
    """
    Fügt neue Spalten hinzu falls sie nicht existieren:
    - highest_price
    - trailing_stop_active
    """
    
    if not os.path.exists(dbpath):
        print(f"❌ Datenbank nicht gefunden: {dbpath}")
        print("Erstelle neue Datenbank...")
        # Neue Datenbank wird automatisch beim ersten Start erstellt
        return
    
    print(f"🔧 Starte Migration für: {dbpath}")
    print("=" * 60)
    
    conn = sqlite3.connect(dbpath)
    cur = conn.cursor()
    
    # Prüfe welche Spalten bereits existieren
    cur.execute("PRAGMA table_info(orders)")
    existing_columns = {row[1] for row in cur.fetchall()}
    
    print(f"Vorhandene Spalten: {existing_columns}")
    
    migrations_applied = 0
    
    # Migration 1: highest_price hinzufügen
    if 'highest_price' not in existing_columns:
        print("\n🔧 Migration 1: Füge 'highest_price' hinzu...")
        try:
            cur.execute("ALTER TABLE orders ADD COLUMN highest_price REAL")
            
            # Setze highest_price = entryprice für bestehende Orders
            cur.execute("""
                UPDATE orders 
                SET highest_price = entryprice 
                WHERE highest_price IS NULL AND status = 'OPEN'
            """)
            
            print("✅ Migration 1 erfolgreich")
            migrations_applied += 1
        except Exception as e:
            print(f"❌ Migration 1 fehlgeschlagen: {e}")
    else:
        print("\n✅ 'highest_price' existiert bereits")
    
    # Migration 2: trailing_stop_active hinzufügen
    if 'trailing_stop_active' not in existing_columns:
        print("\n🔧 Migration 2: Füge 'trailing_stop_active' hinzu...")
        try:
            cur.execute("ALTER TABLE orders ADD COLUMN trailing_stop_active INTEGER DEFAULT 0")
            
            # Setze trailing_stop_active = 0 für bestehende Orders
            cur.execute("""
                UPDATE orders 
                SET trailing_stop_active = 0 
                WHERE trailing_stop_active IS NULL
            """)
            
            print("✅ Migration 2 erfolgreich")
            migrations_applied += 1
        except Exception as e:
            print(f"❌ Migration 2 fehlgeschlagen: {e}")
    else:
        print("\n✅ 'trailing_stop_active' existiert bereits")
    
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 60)
    if migrations_applied > 0:
        print(f"✅ {migrations_applied} Migration(s) erfolgreich ausgeführt!")
    else:
        print("✅ Datenbank ist bereits aktuell - keine Migrationen nötig")
    print("=" * 60)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Database Migration')
    parser.add_argument('--db', default='trading_data.db', help='Database path')
    
    args = parser.parse_args()
    
    migrate_database(args.db)
