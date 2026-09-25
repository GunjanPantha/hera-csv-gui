from __future__ import annotations

import csv
import math
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from dataclasses import dataclass

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

ROW = 'Record number'
ELAPSED = 'Elapsed time (min)'
PAGE_SIZE = 200
DISPLAY_POINTS = 20_000
VIEWS = ('Line', 'Scatter', 'Histogram', 'Bar', 'Table')


@dataclass
class Dataset:
    path: Path
    frame: pd.DataFrame
    numbers: dict[str, np.ndarray]
    elapsed: np.ndarray | None

    @property
    def x_fields(self):
        return [ROW] + ([ELAPSED] if self.elapsed is not None else []) + list(self.numbers)

    def values(self, name):
        if name == ROW:
            return np.arange(1, len(self.frame) + 1, dtype=float)
        if name == ELAPSED and self.elapsed is not None:
            return self.elapsed
        return self.numbers[name]


def read_dataset(path):
    path = Path(path)
    if path.stat().st_size > 150 * 1024 * 1024:
        raise ValueError('Please use a CSV smaller than 150 MB.')
    encoding = 'utf-8-sig'
    try:
        with path.open(encoding=encoding) as stream:
            sample = stream.read(16384)
    except UnicodeDecodeError:
        encoding = 'cp1252'
        with path.open(encoding=encoding) as stream:
            sample = stream.read(16384)
    try:
        separator = csv.Sniffer().sniff(sample, delimiters=',;\t').delimiter
    except csv.Error:
        separator = '\t' if path.suffix.lower() == '.tsv' else ','
    try:
        frame = pd.read_csv(path, sep=separator, encoding=encoding, low_memory=False)
    except UnicodeDecodeError:
        frame = pd.read_csv(path, sep=separator, encoding='cp1252', low_memory=False)
    if frame.empty:
        raise ValueError('This file has no data rows. Include a header and at least one row.')
    if len(frame.columns) > 250:
        raise ValueError('This file has more than 250 columns.')
    frame.columns = [str(c).strip() for c in frame.columns]
    # Reserve the two virtual X-axis names, and keep every physical column unique.
    seen = {ROW, ELAPSED}
    headers = []
    for original in frame.columns:
        name, count = original, 2
        while name in seen:
            name = f'{original} ({count})'
            count += 1
        seen.add(name)
        headers.append(name)
    frame.columns = headers
    numbers = {}
    for column in frame.columns:
        values = pd.to_numeric(frame[column], errors='coerce').to_numpy(dtype=float)
        if np.isfinite(values).any():
            numbers[column] = values
    elapsed = None
    keys = {c.strip().lower(): c for c in frame.columns}
    parts = ('year', 'month', 'day', 'hour', 'minute', 'second')
    dates = None
    if all(k in keys for k in parts):
        components = pd.DataFrame({k: pd.to_numeric(frame[keys[k]], errors='coerce') for k in parts})
        # Pandas can roll overflowing time components into another date. Do not do that.
        valid = components.notna().all(axis=1)
        for key, low, high in [('year', 1900, 2200), ('month', 1, 12), ('day', 1, 31),
                               ('hour', 0, 23), ('minute', 0, 59), ('second', 0, 59.999999)]:
            valid &= components[key].between(low, high)
        for key in parts[:-1]:
            valid &= components[key].mod(1).eq(0)
        dates = pd.to_datetime(components, utc=True, errors='coerce').where(valid)
    else:
        time_column = next((keys[k] for k in ('timestamp', 'datetime', 'date time', 'time_utc', 'utc') if k in keys), None)
        if time_column and not pd.api.types.is_numeric_dtype(frame[time_column]):
            dates = pd.to_datetime(frame[time_column], format='mixed', utc=True, errors='coerce')
    if dates is not None and dates.notna().any():
        elapsed = (dates - dates.min()).dt.total_seconds().to_numpy() / 60.0
    return Dataset(path, frame, numbers, elapsed)


def make_plot_data(data, view, x_name, y_name):
    y = data.values(y_name)
    if view == 'Histogram':
        y = y[np.isfinite(y)]
        return None, y, len(y), False
    x = data.values(x_name)
    valid = np.isfinite(x) & np.isfinite(y)
    x, y = x[valid], y[valid]
    count = len(y)
    if view in ('Line', 'Bar'):
        order = np.argsort(x, kind='stable')
        x, y = x[order], y[order]
    if view == 'Bar' and len(x) > 200:
        raise ValueError('Bar graphs are limited to 200 valid rows. Choose Line, Scatter, or Histogram for this file.')
    reduced = len(x) > DISPLAY_POINTS
    if reduced:
        if view == 'Line':
            # Preserve extrema within consecutive buckets; use the same points for export.
            bucket = math.ceil(len(x) / (DISPLAY_POINTS // 2))
            selected = {0, len(x) - 1}
            for start in range(0, len(x), bucket):
                end = min(start + bucket, len(x))
                selected.add(start + int(np.argmin(y[start:end])))
                selected.add(start + int(np.argmax(y[start:end])))
            indices = np.array(sorted(selected))
        else:
            indices = np.linspace(0, len(x) - 1, DISPLAY_POINTS, dtype=int)
        x, y = x[indices], y[indices]
    return x, y, count, reduced


def populate_plot(figure, data, view, x_name, y_name):
    x, y, count, reduced = make_plot_data(data, view, x_name, y_name)
    if not len(y):
        raise ValueError('These columns do not contain any matching numeric values.')
    figure.clear()
    ax = figure.add_subplot(111)
    if view == 'Histogram':
        ax.hist(y, bins=40, color='#3264b6', edgecolor='white', linewidth=.5)
        ax.set_xlabel(y_name)
        ax.set_ylabel('Record count')
    elif view == 'Scatter':
        ax.scatter(x, y, s=8, alpha=.6, color='#3264b6', linewidths=0)
        ax.set_xlabel(x_name)
        ax.set_ylabel(y_name)
    elif view == 'Bar':
        ax.bar(x, y, color='#3264b6')
        ax.set_xlabel(x_name)
        ax.set_ylabel(y_name)
    else:
        ax.plot(x, y, color='#3264b6', linewidth=1)
        ax.set_xlabel(x_name)
        ax.set_ylabel(y_name)
    ax.grid(axis='y', alpha=.2)
    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(labelsize=9)
    ax.set_title(data.path.name, fontsize=10, pad=12)
    figure.set_layout_engine('constrained')
    return count, len(y), reduced


def export_table(data, path):
    # Escape spreadsheet formulas in text while preserving actual numeric cells.
    frame = data.frame.copy(deep=False)
    for column in frame.select_dtypes(include=['object', 'string']).columns:
        series = frame[column]
        dangerous = series.astype('string').str.match(r'^[=+\-@\t\r]', na=False)
        if dangerous.any():
            safe = series.copy()
            safe.loc[dangerous] = "'" + safe.loc[dangerous].astype(str)
            frame[column] = safe
    safe_headers = ["'" + c if c.startswith(('=', '+', '-', '@', '\t', '\r')) else c for c in frame.columns]
    frame.to_csv(path, index=False, encoding='utf-8-sig', header=safe_headers)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('HERA CSV')
        self.geometry('1000x680')
        self.minsize(760, 480)
        self.data = None
        self.paths = []
        self.loaded_index = None
        self.page = 0
        self.events = queue.Queue()
        self.loading = False
        self.plot_ready = False
        self.filename = tk.StringVar()
        self.view = tk.StringVar(value='Line')
        self.x_name = tk.StringVar()
        self.y_name = tk.StringVar()
        self.status = tk.StringVar(value='Open a CSV file to begin.')
        style = ttk.Style(self)
        if 'vista' in style.theme_names():
            style.theme_use('vista')
        style.configure('TButton', padding=(10, 5))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        top = ttk.Frame(self, padding=(12, 12, 12, 6))
        top.grid(row=0, column=0, sticky='ew')
        top.columnconfigure(1, weight=1)
        self.open_button = ttk.Button(top, text='Open CSV...', command=self.open_files)
        self.open_button.grid(row=0, column=0, padx=(0, 10))
        self.file_combo = ttk.Combobox(top, textvariable=self.filename, state='disabled')
        self.file_combo.grid(row=0, column=1, sticky='ew')
        self.file_combo.bind('<<ComboboxSelected>>', self.file_changed)
        self.export_button = ttk.Button(top, text='Export...', command=self.export, state='disabled')
        self.export_button.grid(row=0, column=2, padx=(10, 0))

        controls = ttk.Frame(self, padding=(12, 4, 12, 10))
        controls.grid(row=1, column=0, sticky='ew')
        controls.columnconfigure(3, weight=1)
        controls.columnconfigure(5, weight=1)
        ttk.Label(controls, text='View').grid(row=0, column=0, padx=(0, 5))
        self.view_combo = ttk.Combobox(controls, textvariable=self.view, values=VIEWS, width=12, state='disabled')
        self.view_combo.grid(row=0, column=1, padx=(0, 14))
        ttk.Label(controls, text='X').grid(row=0, column=2, padx=(0, 5))
        self.x_combo = ttk.Combobox(controls, textvariable=self.x_name, state='disabled')
        self.x_combo.grid(row=0, column=3, sticky='ew', padx=(0, 14))
        ttk.Label(controls, text='Y').grid(row=0, column=4, padx=(0, 5))
        self.y_combo = ttk.Combobox(controls, textvariable=self.y_name, state='disabled')
        self.y_combo.grid(row=0, column=5, sticky='ew')
        for combo in (self.view_combo, self.x_combo, self.y_combo):
            combo.bind('<<ComboboxSelected>>', lambda event: self.refresh())

        self.preview = ttk.Frame(self, padding=(8, 0, 8, 0))
        self.preview.grid(row=2, column=0, sticky='nsew')
        self.preview.columnconfigure(0, weight=1)
        self.preview.rowconfigure(0, weight=1)
        self.figure = Figure(figsize=(8, 5), dpi=100, facecolor='white')
        self.figure.text(.5, .5, 'Open a CSV file to begin', ha='center', va='center', color='#777777', fontsize=13)
        self.canvas = FigureCanvasTkAgg(self.figure, self.preview)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky='nsew')
        self.table_frame = ttk.Frame(self.preview)
        self.table_frame.columnconfigure(0, weight=1)
        self.table_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(self.table_frame, show='headings', selectmode='browse')
        self.tree.grid(row=0, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(self.table_frame, orient='vertical', command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal = ttk.Scrollbar(self.table_frame, orient='horizontal', command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky='ew')
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        page_bar = ttk.Frame(self.table_frame, padding=(0, 6))
        page_bar.grid(row=2, column=0, sticky='ew')
        self.previous = ttk.Button(page_bar, text='Previous', command=lambda: self.change_page(-1))
        self.previous.pack(side='left')
        self.page_label = ttk.Label(page_bar)
        self.page_label.pack(side='left', padx=12)
        self.next = ttk.Button(page_bar, text='Next', command=lambda: self.change_page(1))
        self.next.pack(side='left')
        status_label = ttk.Label(self, textvariable=self.status, padding=(12, 7), anchor='w', wraplength=960)
        status_label.grid(row=3, column=0, sticky='ew')
        status_label.bind('<Configure>', lambda event: status_label.configure(wraplength=max(100, event.width - 24)))
        self.bind('<Control-o>', lambda event: self.open_files())
        self.bind('<Control-s>', lambda event: self.export())
        self.after(80, self.poll)

    def open_files(self):
        if self.loading:
            return
        files = filedialog.askopenfilenames(parent=self, title='Open CSV files', filetypes=[('CSV / TSV files', '*.csv *.tsv'), ('All files', '*.*')])
        if not files:
            return
        for file in files:
            path = Path(file)
            if path not in self.paths:
                self.paths.append(path)
        labels = [f'{i + 1}. {p.name}' for i, p in enumerate(self.paths)]
        self.file_combo.configure(values=labels)
        index = self.paths.index(Path(files[0]))
        self.file_combo.current(index)
        self.load(index)

    def file_changed(self, _event=None):
        if not self.loading:
            self.load(self.file_combo.current())

    def load(self, index):
        if index < 0 or index >= len(self.paths):
            return
        self.loading = True
        self.status.set(f'Opening {self.paths[index].name}...')
        self.set_controls(False)
        def work():
            try:
                self.events.put(('loaded', index, read_dataset(self.paths[index])))
            except Exception as error:
                self.events.put(('error', index, str(error)))
        threading.Thread(target=work, daemon=True).start()

    def set_controls(self, ready):
        self.open_button.configure(state='normal' if not self.loading else 'disabled')
        self.file_combo.configure(state='readonly' if not self.loading and self.paths else 'disabled')
        self.view_combo.configure(state='readonly' if ready else 'disabled')
        numeric = ready and bool(self.data.numbers if self.data else False)
        self.x_combo.configure(state='readonly' if numeric and self.view.get() not in ('Table', 'Histogram') else 'disabled')
        self.y_combo.configure(state='readonly' if numeric and self.view.get() != 'Table' else 'disabled')
        self.export_button.configure(state='normal' if ready and (self.view.get() == 'Table' or self.plot_ready) else 'disabled')

    def poll(self):
        try:
            while True:
                action, index, value = self.events.get_nowait()
                self.loading = False
                if action == 'error':
                    if self.loaded_index is not None:
                        self.file_combo.current(self.loaded_index)
                    else:
                        self.filename.set('')
                    self.set_controls(self.data is not None)
                    self.status.set('Could not open that file. Choose another CSV.')
                    messagebox.showerror('Could not open CSV', value, parent=self)
                elif action == 'exported':
                    self.set_controls(self.data is not None)
                    self.status.set(f'Exported {value}')
                elif action == 'export_error':
                    self.set_controls(self.data is not None)
                    messagebox.showerror('Could not export', value, parent=self)
                else:
                    self.data = value
                    self.loaded_index = index
                    self.page = 0
                    self.x_combo.configure(values=value.x_fields)
                    self.y_combo.configure(values=list(value.numbers))
                    self.x_name.set(ELAPSED if value.elapsed is not None else ROW)
                    preferred = next((c for c in value.numbers if 'altitude' in c.lower()), None)
                    preferred = preferred or next((c for c in value.numbers if c.lower() not in ('year','month','day','hour','minute','second')), None)
                    self.y_name.set(preferred or next(iter(value.numbers), ''))
                    if not value.numbers:
                        self.view.set('Table')
                    self.refresh()
        except queue.Empty:
            pass
        self.after(80, self.poll)

    def refresh(self):
        if self.data is None or self.loading:
            return
        self.plot_ready = False
        if self.view.get() == 'Table':
            self.canvas.get_tk_widget().grid_remove()
            self.table_frame.grid(row=0, column=0, sticky='nsew')
            self.show_table()
        else:
            self.table_frame.grid_remove()
            self.canvas.get_tk_widget().grid(row=0, column=0, sticky='nsew')
            try:
                count, shown, reduced = populate_plot(self.figure, self.data, self.view.get(), self.x_name.get(), self.y_name.get())
                self.plot_ready = True
                note = f'{len(self.data.frame):,} rows · {count:,} valid values'
                if reduced:
                    note += f' · Display/export reduced to {shown:,} points; table export keeps all rows'
                if self.x_name.get() == ELAPSED:
                    note += ' · Time begins at earliest valid timestamp'
                self.status.set(note)
            except (KeyError, ValueError) as error:
                self.figure.clear()
                self.figure.text(.5, .5, str(error), ha='center', va='center', fontsize=11, wrap=True)
                self.status.set('Choose another view or numeric column.')
            self.canvas.draw_idle()
        self.set_controls(True)

    def show_table(self):
        frame = self.data.frame
        start = self.page * PAGE_SIZE
        self.tree.delete(*self.tree.get_children())
        keys = [str(i) for i in range(len(frame.columns))]
        self.tree.configure(columns=keys)
        for key, name in zip(keys, frame.columns):
            self.tree.heading(key, text=name)
            self.tree.column(key, width=max(95, min(210, len(name) * 8)), minwidth=70, stretch=False)
        for row in frame.iloc[start:start + PAGE_SIZE].itertuples(index=False, name=None):
            self.tree.insert('', 'end', values=['' if pd.isna(v) else str(v) for v in row])
        pages = max(1, math.ceil(len(frame) / PAGE_SIZE))
        self.previous.configure(state='normal' if self.page else 'disabled')
        self.next.configure(state='normal' if self.page + 1 < pages else 'disabled')
        self.page_label.configure(text=f'Page {self.page + 1} / {pages}')
        self.status.set(f'{len(frame):,} rows · {len(frame.columns)} columns · Export saves the entire table')

    def change_page(self, delta):
        if self.data is None:
            return
        self.page = max(0, min(self.page + delta, math.ceil(len(self.data.frame) / PAGE_SIZE) - 1))
        self.show_table()

    def export(self):
        if self.data is None or self.loading:
            return
        if self.view.get() == 'Table':
            path = filedialog.asksaveasfilename(parent=self, title='Export table', defaultextension='.csv', initialfile=self.data.path.stem + '_export.csv', filetypes=[('CSV', '*.csv')])
            if not path:
                return
            self.loading = True
            self.set_controls(False)
            self.status.set('Exporting table...')
            data = self.data
            def work():
                try:
                    export_table(data, path)
                    self.events.put(('exported', 0, Path(path).name))
                except Exception as error:
                    self.events.put(('export_error', 0, str(error)))
            threading.Thread(target=work, daemon=True).start()
        elif self.plot_ready:
            path = filedialog.asksaveasfilename(parent=self, title='Export graph', defaultextension='.png', initialfile=self.data.path.stem + '_' + self.view.get().lower() + '.png', filetypes=[('PNG image', '*.png'), ('SVG vector', '*.svg'), ('PDF', '*.pdf')])
            if path:
                try:
                    self.figure.savefig(path, dpi=200, bbox_inches='tight', facecolor='white')
                    self.status.set(f'Exported {Path(path).name}')
                except Exception as error:
                    messagebox.showerror('Could not export', str(error), parent=self)


def main():
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    App().mainloop()


if __name__ == '__main__':
    main()
