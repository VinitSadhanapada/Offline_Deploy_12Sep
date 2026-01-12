#!/usr/bin/env python3
"""
USB Download MVP - Modular Flask server
Serves a one-click ZIP download of data directory.
"""
import os
import io
import zipfile
import csv
import datetime
from flask import Flask, send_file, render_template, request, jsonify

try:
    from . import config  # when used as a package
except ImportError:  # when run as a standalone script
    import config

PORT = int(os.environ.get("USB_MVP_PORT", "8080"))
DATA_DIR = config.DATA_DIR

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"))



# --- Helper functions for CSV/ZIP export ---
def parse_date(date_str):
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.datetime.strptime(date_str, fmt)
            return parsed.date()
        except Exception:
            continue
    return None

def list_csv_files():
    if not os.path.isdir(DATA_DIR):
        return []
    files = []
    for f in os.listdir(DATA_DIR):
        if f.lower().endswith('.csv'):
            files.append(os.path.join(DATA_DIR, f))
    return files

def read_csv_rows(filepath):
    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)

def filter_rows_by_date(rows, date_field, start_date, end_date):
    filtered = []
    for row in rows:
        date_val = row.get(date_field)
        if not date_val:
            continue
        try:
            row_date = parse_date(date_val)
        except Exception:
            continue
        if row_date and start_date <= row_date <= end_date:
            filtered.append(row)
    return filtered

def get_date_field(rows):
    # Try to guess the date field
    if not rows:
        return None
    # Try exact matches first
    for k in rows[0].keys():
        if k.lower() == 'date':
            return k
    # Then try fields containing 'date'
    for k in rows[0].keys():
        if 'date' in k.lower():
            return k
    # Try timestamp fields as they often contain dates
    for k in rows[0].keys():
        if 'time' in k.lower():
            return k
    return None

def group_rows_by_day(rows, date_field):
    days = {}
    for row in rows:
        date_val = row.get(date_field)
        if not date_val:
            continue
        d = parse_date(date_val)
        if not d:
            continue
        days.setdefault(d, []).append(row)
    return days

def safe_float(val):
    try:
        return float(val)
    except Exception:
        return None

def daily_summary(rows, date_field, fields):
    # Returns dict: date -> {field: {min, max, avg}}
    days = group_rows_by_day(rows, date_field)
    summary = {}
    for d, day_rows in days.items():
        entry = {'date': d.isoformat()}
        for f in fields:
            vals = [safe_float(r.get(f)) for r in day_rows if safe_float(r.get(f)) is not None]
            if vals:
                entry[f+'_min'] = min(vals)
                entry[f+'_max'] = max(vals)
                entry[f+'_avg'] = sum(vals)/len(vals)
            else:
                entry[f+'_min'] = entry[f+'_max'] = entry[f+'_avg'] = ''
        summary[d] = entry
    return summary

def daily_wh_delta(rows, date_field, wh_field):
    days = group_rows_by_day(rows, date_field)
    deltas = {}
    for d, day_rows in days.items():
        vals = [safe_float(r.get(wh_field)) for r in day_rows if safe_float(r.get(wh_field)) is not None]
        if vals:
            delta = vals[-1] - vals[0] if len(vals) > 1 else 0
            deltas[d] = {'date': d.isoformat(), 'Wh_received_delta': delta}
        else:
            deltas[d] = {'date': d.isoformat(), 'Wh_received_delta': ''}
    return deltas

def create_zip_with_options(start_date, end_date, mode):
    """
    mode: 'single' (all data in one CSV), 'daily' (one CSV per day)
    Returns: BytesIO ZIP
    """
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
        all_rows = []
        date_field = None
        wh_field = 'Wh_received'
        aavg_field = 'A_average'
        # Collect all rows in range
        for csvfile in list_csv_files():
            rows = read_csv_rows(csvfile)
            if not date_field:
                date_field = get_date_field(rows)
            if not date_field:
                continue
            filtered = filter_rows_by_date(rows, date_field, start_date, end_date)
            all_rows.extend(filtered)
        if not all_rows or not date_field:
            raise Exception("No data in selected range.")
        # Write data CSV(s)
        if mode == 'single':
            # Write all rows to one CSV
            csv_bytes = io.StringIO()
            writer = csv.DictWriter(csv_bytes, fieldnames=all_rows[0].keys())
            writer.writeheader()
            writer.writerows(all_rows)
            zf.writestr('all_data.csv', csv_bytes.getvalue())
        elif mode == 'daily':
            # Write one CSV per day
            days = group_rows_by_day(all_rows, date_field)
            for d, day_rows in days.items():
                csv_bytes = io.StringIO()
                writer = csv.DictWriter(csv_bytes, fieldnames=day_rows[0].keys())
                writer.writeheader()
                writer.writerows(day_rows)
                zf.writestr(f"daily/{d.isoformat()}.csv", csv_bytes.getvalue())
        # Write summary CSV
        summary = daily_summary(all_rows, date_field, [wh_field, aavg_field])
        deltas = daily_wh_delta(all_rows, date_field, wh_field)
        # Merge summary and deltas
        summary_rows = []
        for d in sorted(summary.keys()):
            row = summary[d].copy()
            if d in deltas:
                row.update(deltas[d])
            summary_rows.append(row)
        if summary_rows:
            csv_bytes = io.StringIO()
            writer = csv.DictWriter(csv_bytes, fieldnames=summary_rows[0].keys())
            writer.writeheader()
            writer.writerows(summary_rows)
            zf.writestr('summary/summary.csv', csv_bytes.getvalue())
    memory_file.seek(0)
    return memory_file



# --- New: Data download page with options ---
@app.route("/")
def index():
    return render_template("index.html", data_dir=DATA_DIR)


# --- Endpoint: Get available dates ---
@app.route("/available_dates", methods=["GET"])
def available_dates():
    csv_files = list_csv_files()
    all_dates = set()
    for csvfile in csv_files:
        rows = read_csv_rows(csvfile)
        date_field = get_date_field(rows)
        if not date_field:
            continue
        for row in rows:
            d = parse_date(row.get(date_field, ""))
            if d:
                all_dates.add(d)
    if not all_dates:
        return jsonify([])
    min_date = min(all_dates)
    max_date = max(all_dates)
    return jsonify({
        "min": min_date.isoformat(),
        "max": max_date.isoformat(),
        "all": sorted([d.isoformat() for d in all_dates])
    })



# --- New: Download with options and date range ---
@app.route("/download_data", methods=["POST"])
def download_data():
    try:
        data = request.json or request.form
        mode = data.get("mode", "single")  # 'single' or 'daily'
        start = data.get("start_date")
        end = data.get("end_date")
        if not (start and end):
            return jsonify({"error": "Missing date range"}), 400
        start_date = parse_date(start)
        end_date = parse_date(end)
        if not (start_date and end_date):
            return jsonify({"error": "Invalid date format"}), 400
        if start_date > end_date:
            return jsonify({"error": "Start date must be before or equal to end date."}), 400
        csv_files = list_csv_files()
        if not csv_files:
            return jsonify({"error": "No data files available."}), 404
        try:
            zip_buffer = create_zip_with_options(start_date, end_date, mode)
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        fname = f"data_{start_date}_to_{end_date}.zip"
        return send_file(
            zip_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name=fname,
        )
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


def main():
    print("🚀 MVP Download Server Starting...")
    print(f"📁 Serving files from: {DATA_DIR}")
    print(f"🌐 Connect via: http://192.168.7.2:{PORT} or http://raspberrypi.local:{PORT}")
    print("✅ Ready for USB connection -> Browser -> Click Download")
    app.run(host="0.0.0.0", port=PORT, debug=False)


if __name__ == "__main__":
    main()
