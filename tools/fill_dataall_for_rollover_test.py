import csv
from datetime import datetime, timedelta
from pathlib import Path

# Settings
csv_path = Path(__file__).resolve().parent.parent / "data" / "csv" / "DATA_ALL.csv"
retention_days = 14
rows_to_fill = (retention_days * 24 * 60) - 1  # 1-minute interval, just under 14 days
start_time = datetime.now() - timedelta(days=retention_days, minutes=-1)

header = ["Device_ID", "Meter_Name", "Time", "Model", "Voltage", "Current", "Power"]

# Fill with dummy data
with open(csv_path, "w", newline='') as f:
    writer = csv.writer(f)
    writer.writerow(header)
    for i in range(rows_to_fill):
        t = start_time + timedelta(minutes=i)
        row = [1, "TestMeter", t.strftime("%Y-%m-%d %H:%M:%S"), "LG6400", 230.0, 5.0, 1150.0]
        writer.writerow(row)

print(f"Filled {rows_to_fill} rows up to {(start_time + timedelta(minutes=rows_to_fill-1)).strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Now add a few more rows with your system to trigger rollover.")
