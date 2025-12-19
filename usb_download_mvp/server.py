#!/usr/bin/env python3
"""
USB Download MVP - Modular Flask server
Serves a one-click ZIP download of data directory.
"""
import os
import io
import zipfile
from flask import Flask, send_file, render_template

try:
    from . import config  # when used as a package
except ImportError:  # when run as a standalone script
    import config

PORT = int(os.environ.get("USB_MVP_PORT", "80"))
DATA_DIR = config.DATA_DIR

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"))


def create_zip():
    """Create ZIP of all data files - SIMPLE VERSION"""
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(DATA_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, DATA_DIR)
                zf.write(file_path, arcname)
    memory_file.seek(0)
    return memory_file


@app.route("/")
def index():
    """SINGLE PAGE - Just shows download button"""
    return render_template("index.html", data_dir=DATA_DIR)


@app.route("/download_all")
def download_all():
    """ONE-CLICK DOWNLOAD - Sends ZIP file"""
    try:
        zip_buffer = create_zip()
        return send_file(
            zip_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"data_backup_{os.path.basename(DATA_DIR)}.zip",
        )
    except Exception as e:
        return f"Error: {str(e)}", 500


def main():
    print("🚀 MVP Download Server Starting...")
    print(f"📁 Serving files from: {DATA_DIR}")
    print("🌐 Connect via: http://192.168.7.2 or http://raspberrypi.local")
    print("✅ Ready for USB connection -> Browser -> Click Download")
    app.run(host="0.0.0.0", port=PORT, debug=False)


if __name__ == "__main__":
    main()
