#!/usr/bin/env python3
"""
Terminal-based Meter UI for SSH Access
Interactive command-line interface for viewing meter readings and managing the system
without a desktop environment.
"""

import curses
import os
import sys
import csv
import time
import subprocess
import json
from datetime import datetime
from pathlib import Path


class TerminalMeterUI:
    """Terminal UI for meter monitoring and data management over SSH."""
    
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.current_menu = "main"
        self.selected_index = 0
        self.running = True
        self.csv_dir = Path(__file__).parent / "data" / "csv"
        self.logs_dir = Path(__file__).parent / "logs"
        
        # Setup colors
        curses.start_color()
        curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)     # Headers
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)    # Success
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)   # Warning
        curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)      # Error
        curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)     # Selected
        curses.init_pair(6, curses.COLOR_MAGENTA, curses.COLOR_BLACK)  # Values
        
        # Hide cursor
        curses.curs_set(0)
        
        # Enable keypad
        self.stdscr.keypad(True)
        
    def draw_header(self):
        """Draw the application header."""
        height, width = self.stdscr.getmaxyx()
        title = "═══ METER MONITORING SYSTEM - Terminal UI ═══"
        try:
            self.stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
            self.stdscr.addstr(0, max(0, (width - len(title)) // 2), title[:width-1])
            self.stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
            
            # System info line
            hostname = os.uname().nodename
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            info = f"Host: {hostname} | {timestamp}"
            self.stdscr.addstr(1, max(0, (width - len(info)) // 2), info[:width-1])
            
            # Separator
            self.stdscr.addstr(2, 0, "═" * (width - 1))
        except curses.error:
            pass
    
    def draw_footer(self, menu_type="main"):
        """Draw footer with navigation hints."""
        height, width = self.stdscr.getmaxyx()
        try:
            self.stdscr.attron(curses.color_pair(3))
            if menu_type == "main":
                footer = "↑/↓: Navigate | ENTER: Select | Q: Quit"
            elif menu_type == "readings":
                footer = "R: Refresh | B: Back | Q: Quit"
            elif menu_type == "view":
                footer = "↑/↓: Scroll | B: Back | Q: Quit"
            else:
                footer = "B: Back | Q: Quit"
            
            self.stdscr.addstr(height - 1, max(0, (width - len(footer)) // 2), footer[:width-1])
            self.stdscr.attroff(curses.color_pair(3))
        except curses.error:
            pass
    
    def show_main_menu(self):
        """Display main menu options."""
        height, width = self.stdscr.getmaxyx()
        
        menu_items = [
            ("1", "Live Meter Readings", "View real-time meter data"),
            ("2", "Export CSV Data", "Copy CSV files for download"),
            ("3", "View Latest Readings", "Show last readings from CSV"),
            ("4", "System Status", "Check disk, services, and logs"),
            ("5", "View Configuration", "Display current config files"),
            ("6", "Start Manual Reading", "Run one-time meter reading"),
            ("7", "View Logs", "Display recent log entries"),
            ("8", "Help & Info", "SSH download instructions"),
            ("Q", "Quit", "Exit application"),
        ]
        
        start_y = 4
        
        try:
            self.stdscr.attron(curses.A_BOLD)
            self.stdscr.addstr(start_y, 2, "MAIN MENU")
            self.stdscr.attroff(curses.A_BOLD)
            
            for i, (key, title, desc) in enumerate(menu_items):
                y_pos = start_y + 2 + i
                if y_pos >= height - 2:
                    break
                    
                if i == self.selected_index:
                    self.stdscr.attron(curses.color_pair(5) | curses.A_BOLD)
                    line = f" ► [{key}] {title:<25} - {desc} "
                    self.stdscr.addstr(y_pos, 2, line[:width-4])
                    self.stdscr.attroff(curses.color_pair(5) | curses.A_BOLD)
                else:
                    self.stdscr.attron(curses.color_pair(2))
                    self.stdscr.addstr(y_pos, 2, f"   [{key}]")
                    self.stdscr.attroff(curses.color_pair(2))
                    self.stdscr.addstr(f" {title:<25}")
                    self.stdscr.attron(curses.color_pair(3))
                    self.stdscr.addstr(f" - {desc}"[:width-35])
                    self.stdscr.attroff(curses.color_pair(3))
        except curses.error:
            pass
    
    def show_live_readings(self):
        """Display live meter readings from CSV."""
        self.stdscr.clear()
        self.draw_header()
        
        height, width = self.stdscr.getmaxyx()
        
        try:
            self.stdscr.attron(curses.A_BOLD | curses.color_pair(1))
            self.stdscr.addstr(3, 2, "LIVE METER READINGS")
            self.stdscr.attroff(curses.A_BOLD | curses.color_pair(1))
            
            # Find the main CSV file (symlink or actual file)
            csv_file = self.csv_dir / "readings_all.csv"
            
            if not csv_file.exists():
                self.stdscr.attron(curses.color_pair(4))
                self.stdscr.addstr(5, 2, "No readings file found!")
                self.stdscr.attroff(curses.color_pair(4))
                self.stdscr.addstr(6, 2, f"Expected: {csv_file}")
                self.draw_footer("readings")
                self.stdscr.refresh()
                return
            
            # Read and display latest readings
            try:
                with open(csv_file, 'r') as f:
                    reader = list(csv.reader(f))
                
                if len(reader) < 2:
                    self.stdscr.attron(curses.color_pair(3))
                    self.stdscr.addstr(5, 2, "No data available yet")
                    self.stdscr.attroff(curses.color_pair(3))
                else:
                    header = reader[0]
                    # Get latest rows per meter
                    latest_rows = {}
                    for row in reversed(reader[1:]):
                        if len(row) >= 2:
                            meter_name = row[1]
                            if meter_name not in latest_rows:
                                latest_rows[meter_name] = row
                    
                    y_pos = 5
                    for meter_name, row in latest_rows.items():
                        if y_pos >= height - 3:
                            break
                        
                        # Meter header
                        self.stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
                        self.stdscr.addstr(y_pos, 2, f"╔═ {meter_name} {'═' * (width - len(meter_name) - 8)}"[:width-2])
                        self.stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
                        y_pos += 1
                        
                        # Display key parameters
                        for i, (param, value) in enumerate(zip(header, row)):
                            if y_pos >= height - 3:
                                break
                            
                            if param in ["Time", "Model"]:
                                self.stdscr.addstr(y_pos, 4, f"{param}:")
                                self.stdscr.attron(curses.color_pair(6) | curses.A_BOLD)
                                self.stdscr.addstr(f" {value}"[:width-20])
                                self.stdscr.attroff(curses.color_pair(6) | curses.A_BOLD)
                                y_pos += 1
                            elif param not in ["Device_ID", "Meter_Name"] and i < 10:  # First few params
                                param_short = param[:20]
                                value_short = str(value)[:15]
                                self.stdscr.addstr(y_pos, 4, f"{param_short}:")
                                self.stdscr.attron(curses.color_pair(6))
                                self.stdscr.addstr(f" {value_short}")
                                self.stdscr.attroff(curses.color_pair(6))
                                y_pos += 1
                        
                        y_pos += 1  # Space between meters
                
            except Exception as e:
                self.stdscr.attron(curses.color_pair(4))
                self.stdscr.addstr(5, 2, f"Error reading CSV: {str(e)[:width-10]}")
                self.stdscr.attroff(curses.color_pair(4))
        
        except curses.error:
            pass
        
        self.draw_footer("readings")
        self.stdscr.refresh()
    
    def export_csv_data(self):
        """Prepare CSV files for download and show instructions."""
        self.stdscr.clear()
        self.draw_header()
        
        height, width = self.stdscr.getmaxyx()
        
        try:
            self.stdscr.attron(curses.A_BOLD | curses.color_pair(1))
            self.stdscr.addstr(3, 2, "EXPORT CSV DATA")
            self.stdscr.attroff(curses.A_BOLD | curses.color_pair(1))
            
            # Create export directory
            export_dir = Path(__file__).parent / "exports"
            export_dir.mkdir(exist_ok=True)
            
            y_pos = 5
            self.stdscr.addstr(y_pos, 2, "Preparing files for download...")
            self.stdscr.refresh()
            y_pos += 2
            
            # Copy all CSV files to export directory
            csv_files = list(self.csv_dir.glob("*.csv"))
            
            if csv_files:
                import shutil
                for csv_file in csv_files:
                    dest = export_dir / csv_file.name
                    shutil.copy2(csv_file, dest)
                    if y_pos < height - 8:
                        self.stdscr.attron(curses.color_pair(2))
                        self.stdscr.addstr(y_pos, 4, f"✓ Copied: {csv_file.name}"[:width-6])
                        self.stdscr.attroff(curses.color_pair(2))
                        y_pos += 1
                
                y_pos += 1
                self.stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
                self.stdscr.addstr(y_pos, 2, "Download Instructions (from your laptop):")
                self.stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
                y_pos += 2
                
                # Get IP address
                try:
                    import socket
                    hostname = socket.gethostname()
                    ip_addr = socket.gethostbyname(hostname)
                except:
                    ip_addr = "RPI_IP_ADDRESS"
                
                instructions = [
                    f"1. From your laptop terminal, run:",
                    f"",
                    f"   scp -r pi@{ip_addr}:{export_dir}/*.csv ./meter_data/",
                    f"",
                    f"2. Or download individual file:",
                    f"",
                    f"   scp pi@{ip_addr}:{export_dir}/readings_all.csv ./",
                    f"",
                    f"3. Files are ready in: {export_dir}",
                ]
                
                for line in instructions:
                    if y_pos < height - 3:
                        self.stdscr.attron(curses.color_pair(3))
                        self.stdscr.addstr(y_pos, 2, line[:width-4])
                        self.stdscr.attroff(curses.color_pair(3))
                        y_pos += 1
            else:
                self.stdscr.attron(curses.color_pair(4))
                self.stdscr.addstr(y_pos, 2, "No CSV files found to export!")
                self.stdscr.attroff(curses.color_pair(4))
        
        except Exception as e:
            self.stdscr.attron(curses.color_pair(4))
            self.stdscr.addstr(y_pos, 2, f"Error: {str(e)[:width-10]}")
            self.stdscr.attroff(curses.color_pair(4))
        
        self.draw_footer("view")
        self.stdscr.refresh()
    
    def show_system_status(self):
        """Display system status information."""
        self.stdscr.clear()
        self.draw_header()
        
        height, width = self.stdscr.getmaxyx()
        
        try:
            self.stdscr.attron(curses.A_BOLD | curses.color_pair(1))
            self.stdscr.addstr(3, 2, "SYSTEM STATUS")
            self.stdscr.attroff(curses.A_BOLD | curses.color_pair(1))
            
            y_pos = 5
            
            # Disk space
            self.stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
            self.stdscr.addstr(y_pos, 2, "Disk Space:")
            self.stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
            y_pos += 1
            
            try:
                result = subprocess.run(['df', '-h', '.'], capture_output=True, text=True)
                lines = result.stdout.strip().split('\n')
                for line in lines[:3]:
                    if y_pos < height - 3:
                        self.stdscr.addstr(y_pos, 4, line[:width-6])
                        y_pos += 1
            except:
                self.stdscr.addstr(y_pos, 4, "Unable to check disk space")
                y_pos += 1
            
            y_pos += 1
            
            # Service status
            self.stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
            self.stdscr.addstr(y_pos, 2, "Dashboard Service:")
            self.stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
            y_pos += 1
            
            try:
                result = subprocess.run(['systemctl', 'is-active', 'meter-dashboard'], 
                                      capture_output=True, text=True)
                status = result.stdout.strip()
                if status == "active":
                    self.stdscr.attron(curses.color_pair(2))
                    self.stdscr.addstr(y_pos, 4, "✓ Running")
                    self.stdscr.attroff(curses.color_pair(2))
                else:
                    self.stdscr.attron(curses.color_pair(4))
                    self.stdscr.addstr(y_pos, 4, f"✗ {status}")
                    self.stdscr.attroff(curses.color_pair(4))
            except:
                self.stdscr.addstr(y_pos, 4, "Service status unknown")
            
            y_pos += 2
            
            # Recent log files
            self.stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
            self.stdscr.addstr(y_pos, 2, "Recent Log Files:")
            self.stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
            y_pos += 1
            
            if self.logs_dir.exists():
                log_files = sorted(self.logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
                for log_file in log_files[:5]:
                    if y_pos < height - 3:
                        size_kb = log_file.stat().st_size / 1024
                        mtime = datetime.fromtimestamp(log_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                        self.stdscr.addstr(y_pos, 4, f"{log_file.name:<30} {size_kb:>8.1f}KB  {mtime}"[:width-6])
                        y_pos += 1
            else:
                self.stdscr.addstr(y_pos, 4, "No logs directory found")
        
        except curses.error:
            pass
        
        self.draw_footer("view")
        self.stdscr.refresh()
    
    def show_configuration(self):
        """Display current configuration."""
        self.stdscr.clear()
        self.draw_header()
        
        height, width = self.stdscr.getmaxyx()
        
        try:
            self.stdscr.attron(curses.A_BOLD | curses.color_pair(1))
            self.stdscr.addstr(3, 2, "CURRENT CONFIGURATION")
            self.stdscr.attroff(curses.A_BOLD | curses.color_pair(1))
            
            y_pos = 5
            
            # Load config.json
            config_file = Path(__file__).parent / "config.json"
            if config_file.exists():
                try:
                    with open(config_file, 'r') as f:
                        config = json.load(f)
                    
                    self.stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
                    self.stdscr.addstr(y_pos, 2, "config.json:")
                    self.stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
                    y_pos += 1
                    
                    for key, value in config.items():
                        if y_pos < height - 3:
                            self.stdscr.addstr(y_pos, 4, f"{key}:")
                            self.stdscr.attron(curses.color_pair(6))
                            self.stdscr.addstr(f" {value}"[:width-len(key)-10])
                            self.stdscr.attroff(curses.color_pair(6))
                            y_pos += 1
                except Exception as e:
                    self.stdscr.attron(curses.color_pair(4))
                    self.stdscr.addstr(y_pos, 4, f"Error reading config: {e}"[:width-6])
                    self.stdscr.attroff(curses.color_pair(4))
            else:
                self.stdscr.attron(curses.color_pair(4))
                self.stdscr.addstr(y_pos, 2, "config.json not found")
                self.stdscr.attroff(curses.color_pair(4))
            
            y_pos += 2
            
            # Load device_config.json
            try:
                from paths import get_config_dir
                device_config_file = Path(get_config_dir()) / "device_config.json"
                
                if device_config_file.exists():
                    with open(device_config_file, 'r') as f:
                        devices = json.load(f)
                    
                    self.stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
                    self.stdscr.addstr(y_pos, 2, f"Devices ({len(devices)}):")
                    self.stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
                    y_pos += 1
                    
                    for i, device in enumerate(devices[:5]):
                        if y_pos < height - 3:
                            name = device.get('name', 'Unknown')
                            model = device.get('model', 'Unknown')
                            addr = device.get('address', '?')
                            self.stdscr.addstr(y_pos, 4, f"• {name} ({model}) @ {addr}"[:width-6])
                            y_pos += 1
                else:
                    self.stdscr.addstr(y_pos, 4, "No devices configured")
            except Exception as e:
                self.stdscr.attron(curses.color_pair(4))
                self.stdscr.addstr(y_pos, 4, f"Error reading devices: {e}"[:width-6])
                self.stdscr.attroff(curses.color_pair(4))
        
        except curses.error:
            pass
        
        self.draw_footer("view")
        self.stdscr.refresh()
    
    def show_help(self):
        """Display help and SSH instructions."""
        self.stdscr.clear()
        self.draw_header()
        
        height, width = self.stdscr.getmaxyx()
        
        try:
            self.stdscr.attron(curses.A_BOLD | curses.color_pair(1))
            self.stdscr.addstr(3, 2, "SSH DOWNLOAD GUIDE")
            self.stdscr.attroff(curses.A_BOLD | curses.color_pair(1))
            
            # Get IP address
            try:
                import socket
                hostname = socket.gethostname()
                ip_addr = socket.gethostbyname(hostname)
            except:
                ip_addr = "RPI_IP_ADDRESS"
            
            help_text = [
                "",
                "CONNECTING TO THIS DEVICE:",
                f"  ssh pi@{ip_addr}",
                "",
                "DOWNLOADING CSV DATA:",
                f"  scp pi@{ip_addr}:~/Desktop/offline-setup-12Sep/data/csv/*.csv ./",
                "",
                "DOWNLOADING LOGS:",
                f"  scp pi@{ip_addr}:~/Desktop/offline-setup-12Sep/logs/*.log ./logs/",
                "",
                "DOWNLOADING ENTIRE DATA FOLDER:",
                f"  scp -r pi@{ip_addr}:~/Desktop/offline-setup-12Sep/data ./",
                "",
                "VIEWING LIVE DATA VIA SSH:",
                "  1. SSH into the device",
                "  2. Run this UI: python3 terminal_meter_ui.py",
                "  3. Or tail CSV: tail -f data/csv/readings_all.csv",
                "",
                "TIPS:",
                "  • Use option 2 'Export CSV' to prepare files in exports/ folder",
                "  • Files are smaller and organized for easy download",
                "  • Default SSH password is usually 'raspberry' (change it!)",
            ]
            
            y_pos = 5
            for line in help_text:
                if y_pos < height - 3:
                    if line.startswith("  ") and not line.startswith("   "):
                        self.stdscr.attron(curses.color_pair(3))
                        self.stdscr.addstr(y_pos, 2, line[:width-4])
                        self.stdscr.attroff(curses.color_pair(3))
                    elif line.isupper() and line.endswith(":"):
                        self.stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
                        self.stdscr.addstr(y_pos, 2, line[:width-4])
                        self.stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
                    else:
                        self.stdscr.addstr(y_pos, 2, line[:width-4])
                    y_pos += 1
        
        except curses.error:
            pass
        
        self.draw_footer("view")
        self.stdscr.refresh()
    
    def start_manual_reading(self):
        """Start a manual meter reading session."""
        self.stdscr.clear()
        self.draw_header()
        
        height, width = self.stdscr.getmaxyx()
        
        try:
            self.stdscr.attron(curses.A_BOLD | curses.color_pair(1))
            self.stdscr.addstr(3, 2, "MANUAL READING SESSION")
            self.stdscr.attroff(curses.A_BOLD | curses.color_pair(1))
            
            y_pos = 5
            self.stdscr.addstr(y_pos, 2, "Starting one-time meter reading...")
            self.stdscr.refresh()
            y_pos += 2
            
            # Run dashboard with --run flag
            dashboard_path = Path(__file__).parent / "simple_rpi_dashboard.py"
            
            if dashboard_path.exists():
                self.stdscr.attron(curses.color_pair(3))
                self.stdscr.addstr(y_pos, 2, "Running: python3 simple_rpi_dashboard.py --run")
                self.stdscr.attroff(curses.color_pair(3))
                y_pos += 1
                self.stdscr.refresh()
                
                try:
                    # Run in background and show result
                    result = subprocess.run(
                        ['python3', str(dashboard_path), '--run'],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    y_pos += 1
                    if result.returncode == 0:
                        self.stdscr.attron(curses.color_pair(2))
                        self.stdscr.addstr(y_pos, 2, "✓ Reading completed successfully")
                        self.stdscr.attroff(curses.color_pair(2))
                    else:
                        self.stdscr.attron(curses.color_pair(4))
                        self.stdscr.addstr(y_pos, 2, f"✗ Failed with code {result.returncode}")
                        self.stdscr.attroff(curses.color_pair(4))
                        y_pos += 1
                        if result.stderr:
                            for line in result.stderr.split('\n')[:5]:
                                if y_pos < height - 3:
                                    self.stdscr.addstr(y_pos, 4, line[:width-6])
                                    y_pos += 1
                
                except subprocess.TimeoutExpired:
                    self.stdscr.attron(curses.color_pair(4))
                    self.stdscr.addstr(y_pos, 2, "✗ Reading timed out (30s)")
                    self.stdscr.attroff(curses.color_pair(4))
                except Exception as e:
                    self.stdscr.attron(curses.color_pair(4))
                    self.stdscr.addstr(y_pos, 2, f"Error: {str(e)[:width-10]}")
                    self.stdscr.attroff(curses.color_pair(4))
            else:
                self.stdscr.attron(curses.color_pair(4))
                self.stdscr.addstr(y_pos, 2, "Dashboard script not found!")
                self.stdscr.attroff(curses.color_pair(4))
        
        except curses.error:
            pass
        
        self.draw_footer("view")
        self.stdscr.refresh()
    
    def view_logs(self):
        """Display recent log entries."""
        self.stdscr.clear()
        self.draw_header()
        
        height, width = self.stdscr.getmaxyx()
        
        try:
            self.stdscr.attron(curses.A_BOLD | curses.color_pair(1))
            self.stdscr.addstr(3, 2, "RECENT LOG ENTRIES")
            self.stdscr.attroff(curses.A_BOLD | curses.color_pair(1))
            
            y_pos = 5
            
            if self.logs_dir.exists():
                log_files = sorted(self.logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
                
                if log_files:
                    latest_log = log_files[0]
                    self.stdscr.attron(curses.color_pair(2))
                    self.stdscr.addstr(y_pos, 2, f"Showing: {latest_log.name}"[:width-4])
                    self.stdscr.attroff(curses.color_pair(2))
                    y_pos += 2
                    
                    try:
                        # Show last 20 lines
                        with open(latest_log, 'r') as f:
                            lines = f.readlines()
                        
                        for line in lines[-20:]:
                            if y_pos < height - 3:
                                # Color code by log level
                                if 'ERROR' in line or 'Failed' in line:
                                    self.stdscr.attron(curses.color_pair(4))
                                elif 'WARNING' in line or 'WARN' in line:
                                    self.stdscr.attron(curses.color_pair(3))
                                elif 'INFO' in line or 'success' in line:
                                    self.stdscr.attron(curses.color_pair(2))
                                
                                self.stdscr.addstr(y_pos, 2, line.rstrip()[:width-4])
                                self.stdscr.attroff(curses.color_pair(4))
                                self.stdscr.attroff(curses.color_pair(3))
                                self.stdscr.attroff(curses.color_pair(2))
                                y_pos += 1
                    except Exception as e:
                        self.stdscr.attron(curses.color_pair(4))
                        self.stdscr.addstr(y_pos, 2, f"Error reading log: {e}"[:width-6])
                        self.stdscr.attroff(curses.color_pair(4))
                else:
                    self.stdscr.addstr(y_pos, 2, "No log files found")
            else:
                self.stdscr.addstr(y_pos, 2, "Logs directory not found")
        
        except curses.error:
            pass
        
        self.draw_footer("view")
        self.stdscr.refresh()
    
    def run(self):
        """Main application loop."""
        while self.running:
            self.stdscr.clear()
            self.draw_header()
            self.show_main_menu()
            self.draw_footer("main")
            self.stdscr.refresh()
            
            # Handle input
            try:
                key = self.stdscr.getch()
                
                if key in [ord('q'), ord('Q')]:
                    self.running = False
                
                elif key == curses.KEY_UP:
                    self.selected_index = max(0, self.selected_index - 1)
                
                elif key == curses.KEY_DOWN:
                    self.selected_index = min(8, self.selected_index + 1)
                
                elif key in [curses.KEY_ENTER, ord('\n'), ord('\r')]:
                    # Execute selected option
                    if self.selected_index == 0:  # Live Readings
                        self.show_live_readings()
                        self.wait_for_key()
                    elif self.selected_index == 1:  # Export CSV
                        self.export_csv_data()
                        self.wait_for_key()
                    elif self.selected_index == 2:  # View Latest
                        self.show_live_readings()
                        self.wait_for_key()
                    elif self.selected_index == 3:  # System Status
                        self.show_system_status()
                        self.wait_for_key()
                    elif self.selected_index == 4:  # Configuration
                        self.show_configuration()
                        self.wait_for_key()
                    elif self.selected_index == 5:  # Manual Reading
                        self.start_manual_reading()
                        self.wait_for_key()
                    elif self.selected_index == 6:  # View Logs
                        self.view_logs()
                        self.wait_for_key()
                    elif self.selected_index == 7:  # Help
                        self.show_help()
                        self.wait_for_key()
                    elif self.selected_index == 8:  # Quit
                        self.running = False
                
                # Direct number key selection
                elif key in [ord('1'), ord('2'), ord('3'), ord('4'), ord('5'), 
                           ord('6'), ord('7'), ord('8')]:
                    self.selected_index = int(chr(key)) - 1
            
            except KeyboardInterrupt:
                self.running = False
    
    def wait_for_key(self):
        """Wait for user to press a key before continuing."""
        height, width = self.stdscr.getmaxyx()
        try:
            self.stdscr.attron(curses.color_pair(3) | curses.A_BOLD)
            self.stdscr.addstr(height - 2, 2, "Press any key to continue..."[:width-4])
            self.stdscr.attroff(curses.color_pair(3) | curses.A_BOLD)
            self.stdscr.refresh()
            self.stdscr.getch()
        except curses.error:
            pass


def main(stdscr):
    """Main entry point for curses application."""
    app = TerminalMeterUI(stdscr)
    app.run()


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
