# === BLOK 1: CONFIGURATIE EN IMPORTS ===
import os
import json
from datetime import datetime, timedelta
from collections import defaultdict
import re

# Determine project root based on this script's location
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Define output directory based on environment
if os.path.isdir("/data/data/com.termux/files/home"): # Check if on Termux
    output_dir = os.path.join(os.path.expanduser('~'), 'p1logs')
else: # Fallback for other environments (e.g., Windows)
    output_dir = os.path.join(project_root, 'output')

output_file = os.path.join(output_dir, "energie_dashboard.html")

import sqlite3

# === BLOK 2: READ_DATA_FROM_CHROMADB FUNCTIE ===
def read_data_from_sqlite():
    '''
    Leest alle data uit de SQLite database en retourneert deze in het verwachte formaat.
    '''
    # Bepaal database pad dynamisch
    if os.path.isdir("/data/data/com.termux/files/home"): # Check if on Termux
        db_path = os.path.join(os.path.expanduser('~'), 'p1_data.db')
    else: # Fallback for other environments (e.g., Windows)
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'p1_data.db'))
    table_name = "metingen"

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"SQLite database niet gevonden op '{db_path}'.")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Toegang tot kolommen via naam
    cursor = conn.cursor()

    # Haal alle records op, gesorteerd op tijdstempel
    cursor.execute(f"SELECT * FROM {table_name} ORDER BY timestamp ASC")
    db_results = cursor.fetchall()
    conn.close()

    records = []
    for row in db_results:
        try:
            records.append({
                "ts": datetime.fromtimestamp(row["timestamp"]),
                "active_w": row["active_power_w"] / 10.0,
                "import_kwh": row["total_power_import_kwh"],
                "export_kwh": row["total_power_export_kwh"],
            })
        except Exception as e:
            print(f"Fout bij het verwerken van een record uit SQLite: {e}")
            pass
    
    return records

# === BLOK 3: HOOFDLOGICA - DATA VERWERKEN ===
records = read_data_from_sqlite()
if not records:
    raise SystemExit("Geen data gevonden.")

last = records[-1]
last_values = {
    "import_kwh": round(last["import_kwh"],3),
    "export_kwh": round(last["export_kwh"],3),
}

# === BLOK 4: AGGREGATE_DAY FUNCTIE ===
def aggregate_day(records):
    if not records:
        return {}
    
    daily_datasets = defaultdict(lambda: {"labels": [], "imports": [], "exports": [], "total_import": 0, "total_export": 0, "title": "", "type": "line"})
    
    first_record = records[0]
    last_record = records[-1]
    
    current_date = first_record["ts"].date()
    while current_date <= last_record["ts"].date():
        day_key = current_date.strftime("%Y-%m-%d")
        
        dag_nl = ["ma", "di", "wo", "do", "vr", "za", "zo"][current_date.weekday()]
        maand_nl = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"][current_date.month - 1]
        daily_datasets[day_key]["title"] = f"{dag_nl} {current_date.day} {maand_nl} {current_date.year}"
        
        current_date += timedelta(days=1)
    
    grouped = defaultdict(list)
    for r in records:
        day_key = r["ts"].strftime("%Y-%m-%d")
        grouped[day_key].append(r)
    
    for day, recs in grouped.items():
        prev_import = recs[0]["import_kwh"]
        prev_export = recs[0]["export_kwh"]
        
        for r in recs:
            daily_datasets[day]["labels"].append(r["ts"].strftime("%H:%M"))
            import_diff = (r["import_kwh"] - prev_import) * 1000
            export_diff = (r["export_kwh"] - prev_export) * 1000
            
            if import_diff < 0: import_diff = 0
            if export_diff < 0: export_diff = 0

            daily_datasets[day]["imports"].append(import_diff / 0.25)
            daily_datasets[day]["exports"].append(export_diff / 0.25)
            
            daily_datasets[day]["total_import"] += import_diff / 1000
            daily_datasets[day]["total_export"] += export_diff / 1000
            
            prev_import, prev_export = r["import_kwh"], r["export_kwh"]
        
        daily_datasets[day]["total_import"] = round(daily_datasets[day]["total_import"], 3)
        daily_datasets[day]["total_export"] = round(daily_datasets[day]["total_export"], 3)
            
    return daily_datasets

# === BLOK 5: AGGREGATE_WEEK FUNCTIE ===
def aggregate_week(records):
    if not records:
        return {}
    
    daily_data = defaultdict(lambda: {"import": 0, "export": 0, "count": 0, "date": None})
    for i in range(1, len(records)):
        r_prev = records[i-1]
        r_current = records[i]
        
        import_diff = r_current["import_kwh"] - r_prev["import_kwh"]
        export_diff = r_current["export_kwh"] - r_prev["export_kwh"]
        
        if import_diff < 0 or export_diff < 0:
            continue
            
        date_current = r_current["ts"].date()
        day_key = date_current.strftime("%Y-%m-%d")
        
        daily_data[day_key]["import"] += import_diff
        daily_data[day_key]["export"] += export_diff
        daily_data[day_key]["count"] += 1
        daily_data[day_key]["date"] = date_current
        
    weekly_datasets = defaultdict(lambda: {"labels": [], "imports": [], "exports": [], "total_import": 0, "total_export": 0, "title": "", "type": "bar"})
    
    first_record_date = records[0]["ts"].date()
    last_record_date = records[-1]["ts"].date()
    
    current_date = first_record_date
    while current_date <= last_record_date:
        year, week_num, _ = current_date.isocalendar()
        week_key = f"{year}-{week_num:02d}"
        
        if week_key not in weekly_datasets:
            weekly_datasets[week_key]["title"] = f"Week {week_num}, {year}"

        current_date += timedelta(days=1)
        
    for day_key, data in sorted(daily_data.items()):
        if data["count"] > 0:
            date = data["date"]
            year, week_num, weekday = date.isocalendar()
            week_key = f"{year}-{week_num:02d}"
            
            dag_nl = ["ma", "di", "wo", "do", "vr", "za", "zo"][weekday - 1]
            label = f"{dag_nl} {date.day}/{date.month}"
            
            weekly_datasets[week_key]["labels"].append(label)
            weekly_datasets[week_key]["imports"].append(round(data["import"], 3))
            weekly_datasets[week_key]["exports"].append(round(data["export"], 3))
            weekly_datasets[week_key]["total_import"] += data["import"]
            weekly_datasets[week_key]["total_export"] += data["export"]
    
    for week in weekly_datasets.values():
        week["total_import"] = round(week["total_import"], 3)
        week["total_export"] = round(week["total_export"], 3)
        
    return weekly_datasets

# === BLOK 6: AGGREGATE_MONTH FUNCTIE ===
def aggregate_month(records):
    if not records:
        return {}

    daily_data = defaultdict(lambda: {"import": 0, "export": 0, "count": 0, "date": None})
    for i in range(1, len(records)):
        r_prev = records[i-1]
        r_current = records[i]
        
        import_diff = r_current["import_kwh"] - r_prev["import_kwh"]
        export_diff = r_current["export_kwh"] - r_prev["export_kwh"]
        
        if import_diff < 0 or export_diff < 0:
            continue
            
        date_current = r_current["ts"].date()
        day_key = date_current.strftime("%Y-%m-%d")
        
        daily_data[day_key]["import"] += import_diff
        daily_data[day_key]["export"] += export_diff
        daily_data[day_key]["count"] += 1
        daily_data[day_key]["date"] = date_current
        
    monthly_datasets = defaultdict(lambda: {"labels": [], "imports": [], "exports": [], "total_import": 0, "total_export": 0, "title": "", "type": "bar"})
    
    first_record_date = records[0]["ts"].date()
    last_record_date = records[-1]["ts"].date()
    
    current_date = first_record_date
    while current_date <= last_record_date:
        month_key = current_date.strftime("%Y-%m")
        if month_key not in monthly_datasets:
            year, month = month_key.split('-')
            maand_nl = ["januari", "februari", "maart", "april", "mei", "juni", 
                       "juli", "augustus", "september", "oktober", "november", "december"][int(month) - 1]
            monthly_datasets[month_key]["title"] = f"{maand_nl} {year}"
            
        current_date += timedelta(days=1)
    
    weekly_data = defaultdict(lambda: {"import": 0, "export": 0, "start_date": None, "end_date": None})
    for day_key, data in sorted(daily_data.items()):
        date = data["date"]
        year, week_num, _ = date.isocalendar()
        week_key = f"{year}-{week_num:02d}"
        
        weekly_data[week_key]["import"] += data["import"]
        weekly_data[week_key]["export"] += data["export"]
        
        if weekly_data[week_key]["start_date"] is None or date < weekly_data[week_key]["start_date"]:
            weekly_data[week_key]["start_date"] = date
        if weekly_data[week_key]["end_date"] is None or date > weekly_data[week_key]["end_date"]:
            weekly_data[week_key]["end_date"] = date

    for week_key, data in sorted(weekly_data.items()):
        if data["start_date"]:
            month_key = data["start_date"].strftime("%Y-%m")
            
            start_date_nl = f"{data['start_date'].day}-{data['start_date'].month}"
            end_date_nl = f"{data['end_date'].day}-{data['end_date'].month}"
            label = f"W{week_key.split('-')[1]} ({start_date_nl} t/m {end_date_nl})"
            
            monthly_datasets[month_key]["labels"].append(label)
            monthly_datasets[month_key]["imports"].append(round(data["import"], 3))
            monthly_datasets[month_key]["exports"].append(round(data["export"], 3))
            monthly_datasets[month_key]["total_import"] += data["import"]
            monthly_datasets[month_key]["total_export"] += data["export"]

    for month in monthly_datasets.values():
        month["total_import"] = round(month["total_import"], 3)
        month["total_export"] = round(month["total_export"], 3)

    return monthly_datasets

# === BLOK 7: AGGREGATE_YEAR FUNCTIE ===
def aggregate_year(records):
    if not records:
        return {}
    
    monthly_data = defaultdict(lambda: {"import": 0, "export": 0, "count": 0})
    
    for i in range(1, len(records)):
        r_prev = records[i-1]
        r_current = records[i]
        
        import_diff = r_current["import_kwh"] - r_prev["import_kwh"]
        export_diff = r_current["export_kwh"] - r_prev["export_kwh"]
        
        if import_diff < 0 or export_diff < 0:
            continue
            
        month_key = r_current["ts"].strftime("%Y-%m")
        
        monthly_data[month_key]["import"] += import_diff
        monthly_data[month_key]["export"] += export_diff
        monthly_data[month_key]["count"] += 1
    
    years = defaultdict(lambda: {"labels": [], "imports": [], "exports": [], "total_import": 0, "total_export": 0, "title": "", "type": "bar"})
    
    first_record_date = records[0]["ts"].date()
    last_record_date = records[-1]["ts"].date()
    
    current_date = first_record_date
    while current_date <= last_record_date:
        year_key = str(current_date.year)
        if year_key not in years:
            years[year_key]["title"] = year_key
        
        current_date += timedelta(days=1)
        
    for month_key, data in sorted(monthly_data.items()):
        if data["count"] > 0:
            year = month_key[:4]
            maand_nl = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"][int(month_key.split('-')[1]) - 1]
            
            years[year]["labels"].append(maand_nl)
            years[year]["imports"].append(round(data["import"], 3))
            years[year]["exports"].append(round(data["export"], 3))
            years[year]["total_import"] += data["import"]
            years[year]["total_export"] += data["export"]
    
    for year in years.values():
        year["total_import"] = round(year["total_import"], 3)
        year["total_export"] = round(year["total_export"], 3)
        
    return years


# === BLOK 7.1: AGGREGATE_YEARS FUNCTIE ===
def aggregate_years(records):
    if not records:
        return {}

    # Reuse the aggregate_year function to get yearly totals
    yearly_data_from_agg_year = aggregate_year(records) # This already has total_import and total_export per year

    all_years = sorted(yearly_data_from_agg_year.keys())
    years_datasets = defaultdict(lambda: {"labels": [], "imports": [], "exports": [], "total_import": 0, "total_export": 0, "title": "", "type": "bar"})
    
    chunk_size = 10
    for i in range(0, len(all_years), chunk_size):
        year_chunk_keys = all_years[i:i + chunk_size]
        first_year = year_chunk_keys[0]
        last_year = year_chunk_keys[-1]
        chunk_key = f"{first_year}-{last_year}"
        
        years_datasets[chunk_key]["title"] = f"Jaren {first_year} t/m {last_year}"
        
        for year_key in year_chunk_keys:
            year_data = yearly_data_from_agg_year[year_key]
            years_datasets[chunk_key]["labels"].append(str(year_key))
            years_datasets[chunk_key]["imports"].append(round(year_data["total_import"], 3))
            years_datasets[chunk_key]["exports"].append(round(year_data["total_export"], 3))
            years_datasets[chunk_key]["total_import"] += year_data["total_import"]
            years_datasets[chunk_key]["total_export"] += year_data["total_export"]
        
        years_datasets[chunk_key]["total_import"] = round(years_datasets[chunk_key]["total_import"], 3)
        years_datasets[chunk_key]["total_export"] = round(years_datasets[chunk_key]["total_export"], 3)

    return years_datasets


# === BLOK 7.1: AGGREGATE_YEARS FUNCTIE ===
def aggregate_years(records):
    if not records:
        return {}

    daily_data = defaultdict(lambda: {"import": 0, "export": 0, "count": 0, "date": None})
    for i in range(1, len(records)):
        r_prev = records[i-1]
        r_current = records[i]
        
        import_diff = r_current["import_kwh"] - r_prev["import_kwh"]
        export_diff = r_current["export_kwh"] - r_prev["export_kwh"]
        
        if import_diff < 0 or export_diff < 0:
            continue
            
        date_current = r_current["ts"].date()
        day_key = date_current.strftime("%Y-%m-%d")
        
        daily_data[day_key]["import"] += import_diff
        daily_data[day_key]["export"] += export_diff
        daily_data[day_key]["count"] += 1
        daily_data[day_key]["date"] = date_current

    yearly_totals = defaultdict(lambda: {"import": 0, "export": 0})
    for day_key, data in daily_data.items():
        year = data["date"].year
        yearly_totals[year]["import"] += data["import"]
        yearly_totals[year]["export"] += data["export"]

    all_years = sorted(yearly_totals.keys())
    years_datasets = defaultdict(lambda: {"labels": [], "imports": [], "exports": [], "total_import": 0, "total_export": 0, "title": "", "type": "bar"})
    
    chunk_size = 10
    for i in range(0, len(all_years), chunk_size):
        year_chunk = all_years[i:i + chunk_size]
        first_year = year_chunk[0]
        last_year = year_chunk[-1]
        chunk_key = f"{first_year}-{last_year}"
        
        years_datasets[chunk_key]["title"] = f"Jaren {first_year} t/m {last_year}"
        
        for year in year_chunk:
            years_datasets[chunk_key]["labels"].append(str(year))
            years_datasets[chunk_key]["imports"].append(round(yearly_totals[year]["import"], 3))
            years_datasets[chunk_key]["exports"].append(round(yearly_totals[year]["export"], 3))
            years_datasets[chunk_key]["total_import"] += yearly_totals[year]["import"]
            years_datasets[chunk_key]["total_export"] += yearly_totals[year]["export"]
        
        years_datasets[chunk_key]["total_import"] = round(years_datasets[chunk_key]["total_import"], 3)
        years_datasets[chunk_key]["total_export"] = round(years_datasets[chunk_key]["total_export"], 3)

    return years_datasets


# === BLOK 8: DATA AGGREGATIE ===
all_periods = {
    "day": aggregate_day(records),
    "week": aggregate_week(records),
    "month": aggregate_month(records),
    "year": aggregate_year(records),
    "years": aggregate_years(records)
}

# === BLOK 9: HTML TEMPLATE ===
html_content = f"""
<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Energie Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
:root {{
    --bg-primary: #1e1e1e;
    --bg-secondary: #2c2c2e;
    --text-primary: #ffffff;
    --text-secondary: #aaaaaa;
    --accent-import: #9370DB;
    --accent-export: #32CD32;
    --accent-active: #4169E1;
    --grid-color: #3a3a3c;
}}

body {{ 
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
    margin: 0; 
    padding: 0; 
    background: var(--bg-primary); 
    color: var(--text-primary);
}}

.container {{ 
    max-width: 100%; 
    margin: 0 auto; 
    padding: 16px; 
}}

.header {{ 
    text-align: center; 
    margin-bottom: 10px; 
}}

.header h1 {{ 
    font-size: 24px; 
    font-weight: 600; 
    margin: 0 0 5px 0; 
    color: var(--text-primary);
}}

.period-title {{ 
    text-align: center; 
    font-size: 18px; 
    font-weight: 600; 
    margin: 10px 0;
}}

.period-totals {{ 
    text-align: center; 
    margin: 8px 0; 
    font-size: 14px;
}}

.period-totals .import {{ color: var(--accent-import); }}
.period-totals .export {{ color: var(--accent-export); }}

.chart-container {{ 
    position: relative; 
    height: 40vh; 
    width: 100%; 
    margin-bottom: 10px;
}}

.chart-canvas {{ 
    background: var(--bg-secondary); 
    border-radius: 12px; 
    padding: 16px; 
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}}

.period-nav {{ 
    display: flex; 
    justify-content: center; 
    gap: 8px; 
    margin: 10px 0;
}}

.period-nav button, .period-nav select {{ 
    background: var(--bg-secondary); 
    border: none; 
    color: var(--text-primary); 
    padding: 8px 16px; 
    border-radius: 20px; 
    font-size: 14px; 
    cursor: pointer; 
    transition: all 0.2s ease;
}}

.period-nav select {{
    -webkit-appearance: none;
    -moz-appearance: none;
    appearance: none;
}}

.period-nav button:hover {{ 
    background: #3a3a3c; 
}}

.period-nav button.active, .period-nav select.active {{ 
    background: var(--accent-active); 
    font-weight: 600;
}}

.nav-controls {{ 
    display: flex; 
    justify-content: center; 
    gap: 8px; 
    margin: 10px 0;
}}

.nav-controls button {{ 
    background: var(--bg-secondary); 
    border: none; 
    color: var(--text-primary); 
    padding: 8px 12px; 
    border-radius: 20px; 
    font-size: 14px; 
    font-weight: 500; 
    cursor: pointer; 
    transition: all 0.2s ease;
}}

.nav-controls button:hover {{ 
    background: #3a3a3c; 
}}

.nav-controls button:disabled {{ 
    opacity: 0.5; 
    cursor: not-allowed;
}}

.info-text {{ 
    text-align: center; 
    color: var(--text-secondary); 
    font-size: 12px; 
    margin-top: 15px;
}}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>Energie Dashboard</h1>
        <button id="refreshBtn" onclick="refreshDashboard()" style="padding: 8px 16px; border-radius: 20px; border: none; background: var(--accent-active); color: var(--text-primary); cursor: pointer; font-size: 14px; margin-top: 10px;">Vernieuwen</button>
        <div id="refreshStatus" class="info-text" style="margin-top: 5px;"></div>
    </div>

    <div class="period-title" id="periodTitle">Huidig verbruik</div>
    
    <div class="period-totals" id="periodTotals"></div>

    <div class="chart-container">
        <canvas id="energyChart" class="chart-canvas"></canvas>
    </div>

    <div class="nav-controls">
        <button id="btnPrev" onclick="navigatie(-1)" disabled>←</button>
        <button id="btnCurrent" onclick="navigatie(0)" disabled>Huidige</button>
        <button id="btnNext" onclick="navigatie(1)" disabled>→</button>
    </div>

    <div class="period-nav">
        <button id="btnYears" onclick="setPeriod('years')">Jaren</button>
        <button id="btnDay" onclick="setPeriod('day')">Dag</button>
        <button id="btnWeek" onclick="setPeriod('week')">Week</button>
        <button id="btnMonth" onclick="setPeriod('month')">Maand</button>
                <select id="yearSelector" class="period-nav-button" onchange="showYear(this.value)"><option value="">Jaar</option></select>
    </div>

    <div class="info-text" id="updateInfo">Laatste update: {datetime.now().strftime('%d-%m-%Y %H:%M')}</div>
</div>

<script>
function refreshDashboard() {{
    const refreshBtn = document.getElementById('refreshBtn');
    const refreshStatus = document.getElementById('refreshStatus');

    refreshBtn.disabled = true;
    refreshBtn.textContent = 'Bezig...';
    refreshStatus.textContent = '';

    fetch('/refresh')
        .then(response => {{
            if (!response.ok) {{
                return response.json().then(err => {{
                    // Probeer een specifieke serverfout te krijgen, anders een algemene melding
                    throw new Error(err.message || `Serverfout: ${{response.statusText}}`);
                }});
            }}
            return response.json();
        }})
        .then(data => {{
            if (data.status === 'success') {{
                refreshStatus.textContent = 'Succes! Pagina wordt herladen...';
                setTimeout(() => {{
                    window.location.reload();
                }}, 1000); // Wacht 1 seconde zodat de gebruiker de melding kan zien
            }} else {{
                throw new Error(data.message || 'Onbekende fout opgetreden.');
            }}
        }})
        .catch(error => {{
            console.error('Fout bij vernieuwen:', error);
            refreshStatus.textContent = `Fout: ${{error.message}}`;
            refreshBtn.disabled = false;
            refreshBtn.textContent = 'Opnieuw proberen';
        }});
}}

const allData = {json.dumps(all_periods)};

const myLabelsPlugin = {{
    id: 'my-labels',
    afterDraw: (chart, args, options) => {{
        if (chart.config.type !== 'bar' || state.period === 'day') return;

        const ctx = chart.ctx;
        ctx.font = '11px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';

        const currentClicked = clickedStates[state.currentKey] || [];

        chart.data.datasets.forEach(function(dataset, i) {{
            const meta = chart.getDatasetMeta(i);
            meta.data.forEach(function(bar, index) {{
                if (currentClicked[index]) {{
                    const data = dataset.data[index];
                    ctx.fillStyle = dataset.borderColor;
                    ctx.fillText(data.toFixed(2), bar.x, bar.y - 5);
                }}
            }});
        }});
    }}
}};
Chart.register(myLabelsPlugin);

const ctx = document.getElementById('energyChart').getContext('2d');
let chart = null;

const colorImport = '#9370DB';
const colorExport = '#32CD32';
const gridColor = '#3a3a3c';

let clickedStates = {{}};
let state = {{
    period: 'now',
    currentKey: null,
    history: []
}};

const lastRecord = {{
    ts: '{records[-1]["ts"].strftime("%Y-%m-%d %H:%M") if records else "Geen data"}',
    active_w: {records[-1]["active_w"] if records else 0},
    is_export: {str(records[-1]["active_w"] < 0).lower() if records else "false"},
    total_import: {last_values["import_kwh"]},
    total_export: {last_values["export_kwh"]}
}};

function init() {{
    const firstDayKey = Object.keys(allData.day).sort()[0];
    const firstWeekKey = Object.keys(allData.week).sort()[0];
    const firstMonthKey = Object.keys(allData.month).sort()[0];
    const firstYearKey = Object.keys(allData.year).sort()[0];

    const lastDayKey = Object.keys(allData.day).sort().pop();
    const lastWeekKey = Object.keys(allData.week).sort().pop();
    const lastMonthKey = Object.keys(allData.month).sort().pop();
    const lastYearKey = Object.keys(allData.year).sort().pop();

    state.initialKeys = {{
        'day': firstDayKey,
        'week': firstWeekKey,
        'month': firstMonthKey,
        'year': firstYearKey,
        'years': Object.keys(allData.years).sort()[0] // First chunk of years
    }};
    state.lastKeys = {{
        'day': lastDayKey,
        'week': lastWeekKey,
        'month': lastMonthKey,
        'year': lastYearKey,
        'years': Object.keys(allData.years).sort().pop() // Last chunk of years
    }};

    const yearSelect = document.getElementById('yearSelector');
    const years = Object.keys(allData.year).sort();
    years.forEach(year => {{
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year;
        yearSelect.appendChild(option);
    }});
    
    setPeriod('years');
}}

function findPeriodKey(periodType, date) {{
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const week = getWeekNumber(date);
    const paddedWeek = String(week).padStart(2, '0');
    
    switch (periodType) {{
        case 'day':
            return `${{year}}-${{month}}-${{day}}`;
        case 'week':
            return `${{year}}-${{paddedWeek}}`;
        case 'month':
            return `${{year}}-${{month}}`;
        case 'year':
            return year.toString();
        default:
            return null;
    }}
}}

function getWeekNumber(d) {{
    d = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    const weekNo = Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
    return weekNo;
}}

function showYear(year) {{
    if (year) {{
        state.period = 'year';
        state.currentKey = year;
        document.querySelectorAll('.period-nav button').forEach(btn => {{
            btn.classList.remove('active');
        }});
        document.getElementById('yearSelector').classList.add('active');
        updateChart();
    }}
}}

function updateChart() {{
    if (chart) {{
        chart.destroy();
    }}

    if (state.period === 'now') {{
        renderNowView();
        return;
    }}
    
    const currentItem = allData[state.period][state.currentKey];

    if (!currentItem || !currentItem.labels || currentItem.labels.length === 0) {{
        renderNoData();
        return;
    }}
    
    updateNavigationButtons();
    
    document.getElementById('periodTitle').textContent = currentItem.title;
    document.getElementById('periodTotals').innerHTML = 
        `<span class="import">Verbruik: ${{currentItem.total_import.toFixed(2)}} kWh</span> • ` +
        `<span class="export">Teruglevering: ${{currentItem.total_export.toFixed(2)}} kWh</span>`;
    
    const gradientImport = ctx.createLinearGradient(0, 0, 0, 400);
    gradientImport.addColorStop(0, 'rgba(147, 112, 219, 0.6)');
    gradientImport.addColorStop(1, 'rgba(147, 112, 219, 0.1)');
    
    const gradientExport = ctx.createLinearGradient(0, 0, 0, 400);
    gradientExport.addColorStop(0, 'rgba(50, 205, 50, 0.6)');
    gradientExport.addColorStop(1, 'rgba(50, 205, 50, 0.1)');
    
    let yAxisLabel = 'W';
    let scaleCallback = (value) => `${{value}} W`;
    let tooltipCallback = (context) => `${{context.dataset.label}}: ${{context.parsed.y.toFixed(2)}} W`;
    
    if (state.period !== 'day') {{
        yAxisLabel = 'kWh';
        scaleCallback = (value) => `${{value}} kWh`;
        tooltipCallback = (context) => `${{context.dataset.label}}: ${{context.parsed.y.toFixed(2)}} kWh`;
    }}
    
    const chartData = {{
        labels: currentItem.labels,
        datasets: [
            {{
                label: `Verbruik (${{yAxisLabel}})`,
                data: currentItem.imports,
                backgroundColor: gradientImport,
                borderColor: colorImport,
                borderWidth: 2,
                tension: 0.3,
                fill: true
            }},
            {{
                label: `Teruglevering (${{yAxisLabel}})`,
                data: currentItem.exports,
                backgroundColor: gradientExport,
                borderColor: colorExport,
                borderWidth: 2,
                tension: 0.3,
                fill: true
            }}
        ]
    }};
    
    const options = {{
        responsive: true,
        maintainAspectRatio: false,
        onClick: (evt) => {{
            if (state.period === 'day') return;
            const points = chart.getElementsAtEventForMode(evt, 'index', {{ intersect: true }}, true);
            if (points.length) {{
                const firstPoint = points[0];
                const index = firstPoint.index;
                
                if (!clickedStates[state.currentKey]) {{
                    clickedStates[state.currentKey] = [];
                }}
                clickedStates[state.currentKey][index] = !clickedStates[state.currentKey][index];
                chart.update();
            }}
        }},
        plugins: {{
            legend: {{ display: false }},
            tooltip: {{
                mode: 'index',
                intersect: false,
                backgroundColor: 'rgba(44, 44, 46, 0.9)',
                titleColor: '#ffffff',
                bodyColor: '#ffffff',
                borderColor: 'rgba(255, 255, 255, 0.1)',
                borderWidth: 1,
                callbacks: {{ label: tooltipCallback }}
            }}
        }},
        scales: {{
            x: {{
                grid: {{ color: gridColor, drawBorder: false }},
                ticks: {{ color: '#aaaaaa', maxRotation: 45, font: {{ size: 11 }} }}
            }},
            y: {{
                grid: {{ color: gridColor, drawBorder: false }},
                ticks: {{ color: '#aaaaaa', font: {{ size: 11 }}, callback: scaleCallback }}
            }}
        }},
        animation: {{ duration: 800, easing: 'easeOutQuart' }}
    }};
    
    chart = new Chart(ctx, {{
        type: currentItem.type,
        data: chartData,
        options: options
    }});
}}

function renderNowView() {{
    document.getElementById('periodTitle').textContent = 'Huidig verbruik';
    document.getElementById('periodTotals').innerHTML = 
        `Laatste meting: ${{lastRecord.ts}}`;
    
    const value = Math.abs(lastRecord.active_w);
    const isExport = lastRecord.is_export;
    
    const chartData = {{
        labels: ['Huidig verbruik'],
        datasets: [
            {{
                label: isExport ? 'Teruglevering' : 'Verbruik',
                data: [value],
                backgroundColor: isExport ? colorExport : colorImport,
                borderColor: isExport ? colorExport : colorImport,
                borderWidth: 2,
                borderRadius: 6,
                barPercentage: 0.6
            }}
        ]
    }};
    
    const options = {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
            legend: {{ display: false }},
            tooltip: {{
                callbacks: {{
                    label: (context) => `${{isExport ? 'Teruglevering' : 'Verbruik'}}: ${{context.parsed.y}} W`
                }}
            }}
        }},
        scales: {{
            x: {{
                grid: {{ display: false, drawBorder: false }},
                ticks: {{ color: '#aaaaaa' }}
            }},
            y: {{
                grid: {{ color: gridColor, drawBorder: false }},
                ticks: {{ color: '#aaaaaa', callback: (value) => `${{value}} W` }},
                beginAtZero: true
            }}
        }},
        animation: {{ duration: 1000 }}
    }};
    
    if (chart) {{
        chart.destroy();
    }}
    chart = new Chart(ctx, {{
        type: 'bar',
        data: chartData,
        options: options
    }});
    
    document.getElementById('btnPrev').disabled = true;
    document.getElementById('btnCurrent').disabled = true;
    document.getElementById('btnNext').disabled = true;
}}

function renderNoData() {{
    document.getElementById('periodTitle').textContent = 'Geen data beschikbaar';
    document.getElementById('periodTotals').innerHTML = '';
    
    if (chart) {{
        chart.destroy();
    }}
    
    document.getElementById('btnPrev').disabled = true;
    document.getElementById('btnCurrent').disabled = true;
    document.getElementById('btnNext').disabled = true;
}}

function updateNavigationButtons() {{
    const sortedKeys = Object.keys(allData[state.period]).sort();
    const currentIndex = sortedKeys.indexOf(state.currentKey);
    
    document.getElementById('btnPrev').disabled = currentIndex === 0;
    document.getElementById('btnCurrent').disabled = currentIndex === sortedKeys.length - 1;
    document.getElementById('btnNext').disabled = currentIndex === sortedKeys.length - 1;
}}

function setPeriod(period) {{
    clickedStates = {{}}; // Reset clicked states
    document.querySelectorAll('.period-nav button').forEach(btn => {{
        btn.classList.remove('active');
    }});
    document.getElementById('yearSelector').classList.remove('active');
    document.getElementById('yearSelector').value = "";

    if (period === 'years') {{
        document.getElementById('btnYears').classList.add('active');
    }} else {{
        const buttonId = 'btn' + period.charAt(0).toUpperCase() + period.slice(1);
        const periodButton = document.getElementById(buttonId);
        if (periodButton) {{
            periodButton.classList.add('active');
        }}
    }}

    const prevPeriod = state.period;
    const prevKey = state.currentKey;
    state.period = period;

    let newKey = state.lastKeys[period]; // Default to the latest available key

    if (prevPeriod !== 'now' && prevKey) {{
        const today = new Date();
        let contextDate = null;

        // Create a context date from the previous selection
        switch(prevPeriod) {{
            case 'day':
                const dayParts = prevKey.split('-');
                contextDate = new Date(Date.UTC(dayParts[0], dayParts[1] - 1, dayParts[2]));
                break;
            case 'week':
                const weekParts = prevKey.split('-');
                const year_week = parseInt(weekParts[0]);
                const week_num = parseInt(weekParts[1]);
                contextDate = new Date(Date.UTC(year_week, 0, 1 + (week_num - 1) * 7));
                while (contextDate.getUTCDay() !== 1) contextDate.setUTCDate(contextDate.getUTCDate() - 1);
                break;
            case 'month':
                const monthParts = prevKey.split('-');
                contextDate = new Date(Date.UTC(parseInt(monthParts[0]), parseInt(monthParts[1]) - 1, 15)); // Use mid-month to avoid timezone issues
                break;
            case 'year':
                contextDate = new Date(Date.UTC(parseInt(prevKey), today.getUTCMonth(), today.getUTCDate()));
                break;
        }}

        if (contextDate) {{
            // Find the ideal key in the new period based on the context date
            const potentialKey = findPeriodKey(period, contextDate);

            if (allData[period][potentialKey]) {{
                newKey = potentialKey;
            }} else {{
                // Fallback: find the last available key within the previous context
                const sortedKeys = Object.keys(allData[period]).sort();
                let filteredKeys = [];

                if (prevPeriod === 'year' || prevPeriod === 'month') {{
                    filteredKeys = sortedKeys.filter(k => k.startsWith(prevKey));
                }}
                
                if (filteredKeys.length > 0) {{
                    newKey = filteredKeys.pop(); // Get the last available key in that context
                }}
                // If no keys are found in the context, we just stick with the default newKey (latest overall).
            }}
        }}
    }}

    state.currentKey = newKey;
    updateChart();
}}

function navigatie(direction) {{
    if (state.period === 'now') return;
    
    const sortedKeys = Object.keys(allData[state.period]).sort();
    let currentIndex = sortedKeys.indexOf(state.currentKey);

    if (direction === 0) {{ // Current button
        state.currentKey = sortedKeys[sortedKeys.length - 1];
    }} else {{
        const newIndex = currentIndex + direction;
        if (newIndex >= 0 && newIndex < sortedKeys.length) {{
            state.currentKey = sortedKeys[newIndex];
        }}
    }}

    if (state.period === 'year') {{
        document.getElementById('yearSelector').value = state.currentKey;
    }}

    updateChart();
}}

document.addEventListener('DOMContentLoaded', function() {{
    init();
}});
</script>
</body>
</html>
"""

# === BLOK 10: BESTANDSOPERATIE ===
os.makedirs(os.path.dirname(output_file), exist_ok=True)
with open(output_file, "w", encoding="utf-8") as f:
    f.write(html_content)
