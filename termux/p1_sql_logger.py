'''
Dit script haalt P1-meterdata op en schrijft deze direct naar een SQLite-database.
Het is bedoeld om via een cron-taak te worden uitgevoerd.
'''
import requests
import datetime
import os
import sqlite3

# --- Configuratie ---
P1_IP = "192.168.178.128"
API_URL = f"http://{P1_IP}/api/v1/data"

# Bepaal het pad naar de database direct in de home directory van de gebruiker.
DB_PATH = os.path.join(os.path.expanduser('~'), 'p1_data.db')
TABLE_NAME = "metingen"

def log_to_sqlite():
    """Haalt P1-data op en schrijft deze direct naar de SQLite-database."""
    
    if not os.path.exists(DB_PATH):
        print(f"Fout: Database '{DB_PATH}' niet gevonden. Zorg dat de database bestaat.")
        return

    try:
        # 1. Data ophalen van de P1 meter API
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status() 
        data = response.json()
        print("Data succesvol opgehaald van P1 meter.")

        # 2. Benodigde velden uit de JSON-data halen
        active_power = data.get('active_power_w', 0.0)
        import_kwh = data.get('total_power_import_kwh')
        export_kwh = data.get('total_power_export_kwh')

        if import_kwh is None or export_kwh is None:
            print("Fout: Essentiële data (import/export kWh) ontbreekt in API response.")
            return
            
        # Gebruik de huidige tijd voor de timestamp
        unix_timestamp = datetime.datetime.now().timestamp()

        # 3. Data naar SQLite schrijven
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        data_tuple = (
            unix_timestamp,
            active_power,
            import_kwh,
            export_kwh
        )

        cursor.execute(f'''
            INSERT OR IGNORE INTO {TABLE_NAME} (timestamp, active_power_w, total_power_import_kwh, total_power_export_kwh)
            VALUES (?, ?, ?, ?)
        ''', data_tuple)
        
        conn.commit()
        conn.close()

        print(f"Nieuwe meting opgeslagen in database {os.path.basename(DB_PATH)}.")

    except requests.RequestException as e:
        print(f"Fout bij ophalen data: {e}")
    except sqlite3.Error as e:
        print(f"Fout bij schrijven naar database: {e}")
    except Exception as e:
        print(f"Een onverwachte fout is opgetreden: {e}")

if __name__ == '__main__':
    log_to_sqlite()
