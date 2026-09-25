HERA CSV

Windows 10/11, 64-bit: extract the entire ZIP, then double-click HERA_CSV.exe.
Keep the _runtime folder beside the EXE. Python is included; no install needed.

Open CSV -> choose a file -> choose Line, Scatter, Histogram, Bar or Table
-> choose X and Y -> Export.

Open several CSVs at once and switch between them using the file dropdown.
Graph exports: PNG, SVG or PDF. Table export: all rows as CSV.
Everything runs locally. No accounts, server or internet connection at runtime.

Graphs omit missing or nonnumeric values. They retain the source units and do
not convert event counters into radiation rates. For the supplied HERA format,
elapsed minutes are available when Year/Month/Day/Hour/Minute/Second exist.
Elapsed time starts at the earliest valid record, not at launch. ISO timestamp
columns are also recognized; timestamps without a zone are treated as UTC.

Tables show 200 rows per page and export all rows. Line/scatter display and
image export use at most about 20,000 points for large files; the status line
reports this. Histograms use all valid values. Bar charts require at most
200 valid rows. Files larger than 150 MB are rejected to limit memory use.
CSV export regenerates numeric formatting and neutralizes formula-like text.

Source (in the source folder):
  Install Python 3.13 (64-bit), including Tk/Tcl.
  python -m pip install -r requirements.txt
  python hera_csv.py

Build an alternative single-file Windows EXE:
  On Windows, double-click Build_EXE.bat.
  The standalone result is dist\HERA_CSV.exe.
  Building needs internet; the resulting app does not need Python installed.

Runtime dependencies are Python/Tk, NumPy, pandas, and Matplotlib.

Validation: CSV loading was checked on all eight supplied research files;
graph/table behavior and exports were tested on Linux. The Windows executable
and its bundled Windows dependencies have not been run on a Windows machine.
