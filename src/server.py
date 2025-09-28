import os
import sys
import subprocess
from flask import Flask, send_from_directory, jsonify

# --- Configuratie met Vaste Paden voor Termux ---
# Dit script is aangepast om te werken wanneer het, samen met het generatie-script,
# in de Termux home directory staat: /data/data/com.termux/files/home/

# Pad naar het script dat het dashboard genereert.
SCRIPT_TO_RUN = '/data/data/com.termux/files/home/generate_P1_dashboard.py'

# Pad naar de map waar de uiteindelijke 'energie_dashboard.html' wordt opgeslagen.
OUTPUT_DIR = '/data/data/com.termux/files/home/p1logs/'


# --- Flask Applicatie ---
app = Flask(__name__)

@app.route('/')
def index():
    """
    Deze functie serveert het 'energie_dashboard.html' bestand.
    """
    if not os.path.exists(OUTPUT_DIR):
        return f"Fout: De output map ({OUTPUT_DIR}) bestaat niet.", 404
    try:
        return send_from_directory(OUTPUT_DIR, 'energie_dashboard.html')
    except FileNotFoundError:
        return f"Fout: 'energie_dashboard.html' niet gevonden in {OUTPUT_DIR}. Draai eerst het generate script.", 404

@app.route('/refresh')
def refresh():
    """
    Deze functie voert het generate_P1_dashboard.py script opnieuw uit.
    """
    if not os.path.isfile(SCRIPT_TO_RUN):
        return jsonify(status="error", message=f"Fout: Het generate script is niet gevonden op {SCRIPT_TO_RUN}."), 500
    try:
        # Voer het script uit met dezelfde Python-interpreter als de server.
        subprocess.run(
            [sys.executable, SCRIPT_TO_RUN], 
            check=True,
            capture_output=True,
            text=True
        )
        return jsonify(status="success", message="Dashboard is vernieuwd.")
    except subprocess.CalledProcessError as e:
        # Vang fouten op die het script zelf genereert.
        error_message = f"Het generate script gaf een foutmelding:\n{e.stderr}"
        return jsonify(status="error", message=error_message), 500

if __name__ == '__main__':
    print(f"Server wordt gestart...")
    print(f"Dashboard is bereikbaar op http://<IP-ADRES-VAN-TELEFOON>:8000")
    print(f"HTML-bestand wordt verwacht in: {OUTPUT_DIR}")
    print(f"Refresh-knop voert uit: {SCRIPT_TO_RUN}")
    app.run(host='0.0.0.0', port=8000, debug=False)