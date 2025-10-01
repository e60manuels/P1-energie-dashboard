
'''
Dit script leest alle .jsonl bestanden uit de 'sample_logs' map, 
verwerkt de data en voegt deze toe aan de SQLite database.
Het is ontworpen om om te gaan met variaties in de JSON-structuur.
'''

import os
import glob
import json
import sqlite3
from datetime import datetime

def import_jsonl_to_sqlite():
    """
    Leest .jsonl-bestanden uit de logmap en importeert de data in SQLite.
    """
    # --- Padinstellingen ---
    # Bepaal de log-map dynamisch
    logs_dir = "/data/data/com.termux/files/home/p1logs"
    if not os.path.isdir(logs_dir):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        logs_dir = os.path.join(project_root, 'sample_logs')

    # Bepaal database pad dynamisch
    if os.path.isdir("/data/data/com.termux/files/home"): # Check if on Termux
        db_path = os.path.join(os.path.expanduser('~'), 'p1_data.db')
    else: # Fallback for other environments (e.g., Windows)
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        db_path = os.path.join(project_root, 'p1_data.db')
    
    table_name = "metingen"

    # Vind alle .jsonl bestanden in de logmap
    jsonl_files = glob.glob(os.path.join(logs_dir, '*.jsonl'))
    if not jsonl_files:
        print(f"Geen .jsonl bestanden gevonden in '{logs_dir}'.")
        return

    print(f"{len(jsonl_files)} .jsonl bestanden gevonden om te verwerken.")

    # --- Databaseverbinding en tabel creatie ---
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Maak de tabel aan als deze nog niet bestaat
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                timestamp REAL PRIMARY KEY,
                active_power_w REAL,
                total_power_import_kwh REAL,
                total_power_export_kwh REAL
            )
        ''')
        conn.commit()
    except sqlite3.Error as e:
        print(f"SQLite fout bij verbinden of tabel aanmaken: {e}")
        return

    # --- Verwerking ---
    total_processed = 0
    total_inserted = 0
    total_skipped = 0

    for file_path in jsonl_files:
        print(f"\nVerwerken van bestand: {os.path.basename(file_path)}...")
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                total_processed += 1
                try:
                    record = json.loads(line)
                    data = record.get('data', {})
                    timestamp_str = record.get('timestamp')

                    # Sla records zonder timestamp of data-object over
                    if not timestamp_str or not data:
                        total_skipped += 1
                        continue

                    # Converteer ISO 8601 timestamp naar Unix timestamp
                    # Verwijdert eventuele timezone info voor compatibiliteit
                    dt_object = datetime.fromisoformat(timestamp_str.split('+')[0])
                    unix_timestamp = dt_object.timestamp()

                    # Haal benodigde velden op, met standaardwaarden voor ontbrekende velden
                    active_power = data.get('active_power_w', 0.0)
                    import_kwh = data.get('total_power_import_kwh')
                    export_kwh = data.get('total_power_export_kwh')

                    # Sla record over als essentiële data ontbreekt
                    if import_kwh is None or export_kwh is None:
                        total_skipped += 1
                        continue

                    # Data voorbereiden voor invoegen
                    data_tuple = (
                        unix_timestamp,
                        active_power,
                        import_kwh,
                        export_kwh
                    )

                    # Voeg toe aan database, negeer als timestamp al bestaat
                    cursor.execute(f'''
                        INSERT OR IGNORE INTO {table_name} (timestamp, active_power_w, total_power_import_kwh, total_power_export_kwh)
                        VALUES (?, ?, ?, ?)
                    ''', data_tuple)

                    if cursor.rowcount > 0:
                        total_inserted += 1
                    else:
                        total_skipped += 1 # Record was al aanwezig (duplicaat)

                except (json.JSONDecodeError, TypeError, ValueError) as e:
                    # print(f"Waarschuwing: Regel overgeslagen door fout: {e} -> '{line.strip()}'")
                    total_skipped += 1
    
    # --- Afronding ---
    conn.commit()
    conn.close()

    print("\n--- Import Voltooid ---")
    print(f"Totaal aantal regels verwerkt: {total_processed}")
    print(f"Nieuwe records toegevoegd:    {total_inserted}")
    print(f"Records overgeslagen:        {total_skipped} (fouten of duplicaten)")

if __name__ == '__main__':
    import_jsonl_to_sqlite()
