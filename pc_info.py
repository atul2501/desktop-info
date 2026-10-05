"""PC Info - shows the key hardware and Windows details of this PC."""

import base64
import datetime
import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

PS_SCRIPT = r"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$ErrorActionPreference = 'SilentlyContinue'
function Q($cls, $filter = $null) {
    try {
        if ($filter) { Get-CimInstance -ClassName $cls -Filter $filter -ErrorAction Stop }
        else { Get-CimInstance -ClassName $cls -ErrorAction Stop }
    } catch { $null }
}

$r = [ordered]@{}
$r.cs    = Q Win32_ComputerSystem | Select-Object Manufacturer, Model, TotalPhysicalMemory
$r.csp   = Q Win32_ComputerSystemProduct | Select-Object Version, IdentifyingNumber
$r.bios  = Q Win32_BIOS | Select-Object SerialNumber
$r.os    = Q Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, OSArchitecture
$r.cpu   = @(Q Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors)
$r.ram   = @(Q Win32_PhysicalMemory | Select-Object Capacity, Speed, ConfiguredClockSpeed)
$r.disks = @(Q Win32_DiskDrive | Select-Object Model, Size)
$r.vols  = @(Q Win32_LogicalDisk 'DriveType=3' | Select-Object DeviceID, Size, FreeSpace)
$r.gpu   = @(Q Win32_VideoController | Select-Object Name)
$r | ConvertTo-Json -Depth 4 -Compress
"""


COMPANY = "F.T. Solutions Pvt. Ltd."
BRAND_RED = "#E30016"
BRAND_BLUE = "#004985"


def resource(name):
    """Path to a bundled file, both when run from source and from the PyInstaller exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", name)


def run_powershell():
    encoded = base64.b64encode(PS_SCRIPT.encode("utf-16-le")).decode("ascii")
    out = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-EncodedCommand", encoded],
        capture_output=True, timeout=120,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    text = out.stdout.decode("utf-8", errors="replace").strip()
    if not text:
        raise RuntimeError(out.stderr.decode("utf-8", errors="replace") or "No output from PowerShell")
    return json.loads(text)


def as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def val(v):
    if v is None or v == "" or v == []:
        return "N/A"
    if isinstance(v, list):
        return ", ".join(str(x) for x in v if x not in (None, ""))
    if isinstance(v, bool):
        return "Yes" if v else "No"
    return str(v).strip()


def gb(v):
    try:
        return f"{int(v) / 1024 ** 3:.2f} GB"
    except (TypeError, ValueError):
        return "N/A"


def build_sections(d):
    """Turn raw JSON into [(section_title, [(label, value), ...]), ...]."""
    cs = d.get("cs") or {}
    csp = d.get("csp") or {}
    bios = d.get("bios") or {}
    os_ = d.get("os") or {}
    rows = []

    # Some brands (e.g. Lenovo) keep the friendly model name in ComputerSystemProduct.Version
    model = val(cs.get("Model"))
    friendly = (csp.get("Version") or "").strip()
    if friendly and friendly.lower() not in ("none", "system version", "to be filled by o.e.m.")             and friendly != model:
        model = f"{friendly} ({model})"

    rows.append(("Brand", val(cs.get("Manufacturer"))))
    rows.append(("Model Number", model))
    rows.append(("Serial Number", val(bios.get("SerialNumber") or csp.get("IdentifyingNumber"))))
    rows.append(("Windows Version",
                 f"{val(os_.get('Caption'))} {val(os_.get('OSArchitecture'))}"
                 f" (Version {val(os_.get('Version'))}, Build {val(os_.get('BuildNumber'))})"))

    for c in as_list(d.get("cpu")):
        rows.append(("Processor", f"{val(c.get('Name'))} ({val(c.get('NumberOfCores'))} cores,"
                                  f" {val(c.get('NumberOfLogicalProcessors'))} threads)"))

    sticks = as_list(d.get("ram"))
    installed = sum(int(s.get("Capacity") or 0) for s in sticks) or cs.get("TotalPhysicalMemory")
    speed = next((s.get("ConfiguredClockSpeed") or s.get("Speed") for s in sticks
                  if s.get("ConfiguredClockSpeed") or s.get("Speed")), None)
    ram = f"{gb(installed)} ({len(sticks)} stick{'s' if len(sticks) != 1 else ''}"
    ram += f", {speed} MHz)" if speed else ")"
    rows.append(("RAM", ram))

    for g in as_list(d.get("gpu")):
        rows.append(("GPU", val(g.get("Name"))))

    for k in as_list(d.get("disks")):
        rows.append(("Hard Disk", f"{val(k.get('Model'))} ({gb(k.get('Size'))})"))
    for v in as_list(d.get("vols")):
        rows.append((f"  Drive {val(v.get('DeviceID'))}",
                     f"{gb(v.get('FreeSpace'))} free of {gb(v.get('Size'))}"))

    return [("PC Details", rows)]


def sections_to_text(sections):
    width = max((len(k) for _, rows in sections for k, _ in rows), default=20) + 2
    lines = [f"{COMPANY} - PC Info", f"Generated {datetime.datetime.now():%Y-%m-%d %H:%M}", ""]
    for title, rows in sections:
        lines += [f"== {title} ==", *(f"{k:<{width}}: {v}" for k, v in rows), ""]
    return "\n".join(lines)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"PC Info - {COMPANY}")
        self.geometry("760x440")
        self.minsize(520, 400)
        self.configure(bg="white")
        self.sections = []
        self.pc_name = os.environ.get("COMPUTERNAME", "PC")
        try:
            self.iconbitmap(resource("icon.ico"))
        except tk.TclError:
            pass

        header = tk.Frame(self, bg="white", padx=12, pady=10)
        header.pack(fill="x")
        try:
            self.logo = tk.PhotoImage(file=resource("logo_header.png"))
            tk.Label(header, image=self.logo, bg="white").pack(side="left")
        except tk.TclError:
            tk.Label(header, text=COMPANY, font=("Segoe UI", 16, "bold"),
                     fg=BRAND_BLUE, bg="white").pack(side="left")
        tk.Label(header, text="PC Information", font=("Segoe UI", 18, "bold"),
                 fg=BRAND_BLUE, bg="white").pack(side="right")
        tk.Frame(self, bg=BRAND_RED, height=3).pack(fill="x")

        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        self.status = ttk.Label(bar, text="")
        self.status.pack(side="left")
        self.btn_refresh = ttk.Button(bar, text="Refresh", command=self.load)
        self.btn_refresh.pack(side="right", padx=3)
        ttk.Button(bar, text="Save to TXT", command=self.save).pack(side="right", padx=3)
        ttk.Button(bar, text="Copy All", command=self.copy).pack(side="right", padx=3)

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.text = tk.Text(frame, wrap="word", font=("Consolas", 10), padx=10, pady=8,
                            borderwidth=1, relief="solid")
        sb = ttk.Scrollbar(frame, command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.tag_configure("head", font=("Segoe UI", 12, "bold"), foreground=BRAND_RED,
                                spacing1=10, spacing3=4)
        self.text.tag_configure("key", foreground="#555555")
        self.text.tag_configure("value", font=("Consolas", 10, "bold"))

        self.load()

    def load(self):
        self.btn_refresh.state(["disabled"])
        self.status.config(text="Collecting PC details, please wait...")
        self.show_message("Loading...")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            sections = build_sections(run_powershell())
            self.after(0, self._done, sections, None)
        except Exception as e:  # noqa: BLE001 - show any failure to the user
            self.after(0, self._done, None, e)

    def _done(self, sections, error):
        self.btn_refresh.state(["!disabled"])
        if error:
            self.status.config(text="Failed to collect details")
            self.show_message(f"Error: {error}")
            return
        self.sections = sections
        self.status.config(text=f"Updated {datetime.datetime.now():%H:%M:%S}")
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        width = max(len(k) for _, rows in sections for k, _ in rows) + 2
        for title, rows in sections:
            self.text.insert("end", title + "\n", "head")
            for k, v in rows:
                self.text.insert("end", f"{k:<{width}}", "key")
                self.text.insert("end", f"{v}\n", "value")
        self.text.config(state="disabled")

    def show_message(self, msg):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", msg)
        self.text.config(state="disabled")

    def copy(self):
        if not self.sections:
            return
        self.clipboard_clear()
        self.clipboard_append(sections_to_text(self.sections))
        self.status.config(text="Copied to clipboard")

    def save(self):
        if not self.sections:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", initialfile=f"{self.pc_name}_info.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(sections_to_text(self.sections))
            self.status.config(text=f"Saved to {path}")
        except OSError as e:
            messagebox.showerror("Save failed", str(e))


if __name__ == "__main__":
    App().mainloop()
