# HERA CSV GUI

A graphical interface for CSV importing, character-level text evaluation, and data processing for HERA.

## Screenshot

<img width="992" height="715" alt="image" src="https://github.com/user-attachments/assets/56fee472-8f59-48a1-a656-368f2101f9bf" />


## Installation

1. Clone the repository and navigate to the root directory:
```bash
git clone <repository_url>
cd hera-csv-gui

```


2. Ensure you have Python installed, then install the necessary dependencies using the provided requirements file:
```bash
pip install -r requirements.txt

```



## Usage

To launch the application directly from the source code, run the main Python script:

```bash
python hera_csv.py

```

Alternatively, you can start the application using the secondary Python launcher by running `launch.py`. The tool processes your data locally, ensuring offline functionality.

## Building and Compilation

To compile the application into a standalone executable, run the provided Windows batch script:

```cmd
Build_EXE.bat

```

This batch script orchestrates the build process, utilizing `launcher.c` to wrap the Python scripts into a deployable format.
