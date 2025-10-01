
'''
Dit script is voor een eenmalige datamigratie van een ChromaDB database naar een SQLite database.
Het leest de meterstanden uit de "smartmeter_master" collectie en schrijft deze naar een tabel genaamd "metingen" in een `p1_data.db` bestand.
'''

import os
import sqlite3
import chromadb

# --- CONFIGURATIE ---

# Bepaal de hoofdmap van het project op basis van de locatie van dit script
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Pad naar de bron ChromaDB database.
# Dit pad gaat twee mappen omhoog vanaf de scriptlocatie (src -> project root -> bovenliggende map)
# en zoekt dan naar de map 'smartmeter-rag/chroma_db'.
CHROMA_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'smartmeter-rag', 'chroma_db'))
COLLECTION_NAME = "smartmeter_master"

# Pad naar de nieuwe SQLite database (wordt aangemaakt in de hoofdmap van het project)
SQLITE_DB_PATH = os.path.join(PROJECT_ROOT, 'p1_data.db')
SQLITE_TABLE_NAME = "metingen"


def migrate_chroma_to_sqlite():
    """
    Leest data uit een ChromaDB collectie en schrijft deze naar een nieuwe SQLite database.
    """
    print("--- Start Datamigratie ---")

    # 1. Verbind met ChromaDB en haal data op
    print(f"Verbinden met ChromaDB op: {CHROMA_DB_PATH}")
    if not os.path.exists(CHROMA_DB_PATH):
        print(f"Fout: ChromaDB database niet gevonden op '{CHROMA_DB_PATH}'.")
        print("Zorg ervoor dat het 'smartmeter-rag' project in dezelfde bovenliggende map staat als 'P1-energie-dashboard'.")
        return

    try:
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        collection = client.get_collection(name=COLLECTION_NAME)
        db_results = collection.get()
        print(f"Succesvol verbonden met collectie '{COLLECTION_NAME}'.")
    except Exception as e:
        print(f"Fout bij het verbinden met ChromaDB of ophalen van de collectie: {e}")
        return

    if not db_results or not db_results.get('ids'):
        print("Geen records gevonden in ChromaDB. Niets te migreren.")
        return

    records_to_migrate = db_results['metadatas']
    print(f"{len(records_to_migrate)} records gevonden om te migreren.")

    # 2. Verbind met SQLite en maak de tabel aan
    print(f"Aanmaken/verbinden met SQLite database op: {SQLITE_DB_PATH}")
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cursor = conn.cursor()

        print(f"Tabel '{SQLITE_TABLE_NAME}' aanmaken (indien niet bestaand).")
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {SQLITE_TABLE_NAME} (
                timestamp REAL PRIMARY KEY,
                active_power_w REAL,
                total_power_import_kwh REAL,
                total_power_export_kwh REAL
            )
        ''')
        conn.commit()
    except sqlite3.Error as e:
        print(f"SQLite fout tijdens setup: {e}")
        return

    # 3. Voeg data toe aan SQLite
    print("Records worden in SQLite ingevoegd...")
    migrated_count = 0
    skipped_count = 0
    for meta in records_to_migrate:
        try:
            data_tuple = (
                meta["timestamp"],
                meta.get("active_power_w", 0),
                meta["total_power_import_kwh"],
                meta["total_power_export_kwh"]
            )
            
            # Gebruik INSERT OR IGNORE om fouten bij dubbele timestamps te voorkomen
            cursor.execute(f'''
                INSERT OR IGNORE INTO {SQLITE_TABLE_NAME} (timestamp, active_power_w, total_power_import_kwh, total_power_export_kwh)
                VALUES (?, ?, ?, ?)
            ''', data_tuple)
            
            if cursor.rowcount > 0:
                migrated_count += 1
            else:
                skipped_count += 1

        except KeyError as e:
            print(f"Record overgeslagen wegens ontbrekende sleutel: {e}. Record: {meta}")
            skipped_count += 1

    # Wijzigingen opslaan en verbinding sluiten
    conn.commit()
    conn.close()

    print("\n--- Migratie Voltooid ---")
    print(f"Succesvol gemigreerd: {migrated_count} records.")
    print(f"Overgeslagen (duplicaten of fouten): {skipped_count} records.")
    print(f"Data is nu beschikbaar in '{SQLITE_DB_PATH}'")

if __name__ == '__main__':
    migrate_chroma_to_sqlite()
