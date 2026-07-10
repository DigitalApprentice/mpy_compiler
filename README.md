# MPY Cross Compiler Suite

The **MPY Cross Compiler Suite** is a collection of utilities to compile standard Python source files (`.py`) into MicroPython bytecode binaries (`.mpy`). 

## Why Cross-Compile?
1. **Reduce Memory Usage**: Raw `.py` files must be parsed and compiled into bytecode in the ESP32's RAM. pre-compiling to `.mpy` bypasses this compilation phase, saving precious heap memory.
2. **Speed Up Boot Time**: Bytecode runs immediately without load-time parsing overhead.
3. **Source Protection**: Compiling turns human-readable source code into binary format, preventing simple reverse-engineering of files stored on the board's flash.

---

## File Structure

The compiler suite consists of four files:
- **`Start_MPY_Compiler.bat`**: A Windows batch shortcut to launch the compiler backend and open the web browser interface.
- **`mpy_compiler_backend.py`**: A Python HTTP server (running on port `8765`) that serves the HTML UI and handles compilation requests via a REST endpoint.
- **`mpy_compiler.html`**: The HTML/CSS/JavaScript web interface containing compile options, drag-and-drop support, and download links.
- **`mpy_compiler_server.py`**: A self-contained, single-file server that embeds the HTML frontend inside the python file itself. Ideal for portable use.

---

## Prerequisites

Before running the compiler, you must install the `mpy-cross` compiler.

### Option A: Install via Pip (Recommended)
Open a terminal and run:
```bash
pip install mpy-cross
```
The python scripts will automatically detect and import the package.

### Option B: Executable Binary
Download the `mpy-cross` executable binary suitable for your OS and place it on your system's `PATH`. The scripts will fallback to invoking this binary if the Python package is not found.

---

## How to Run

### Method 1: Using the Windows Batch File (Recommended)
Double-click **`Start_MPY_Compiler.bat`**. 
- It starts the Python backend server on `http://127.0.0.1:8765`.
- It automatically opens your default web browser to the interface.

### Method 2: Running the Standard Backend
Open terminal in the `tools` folder and run:
```powershell
python mpy_compiler_backend.py
```
Then navigate to `http://localhost:8765` in your browser.

### Method 3: Running the Standalone Portable Server
If you want to move the tool or run it in isolation without needing the adjacent `mpy_compiler.html` file, copy only `mpy_compiler_server.py` and run:
```powershell
python mpy_compiler_server.py
```
It has the complete frontend embedded directly in its source code.

---

## Web Interface Guide

### 1. Adding Files
- Drag and drop `.py` files directly onto the dotted dropzone card.
- Or click the dropzone to browse your local file system and select files.

### 2. Configure Compilation Settings
- **Target Architecture (-march)**: Choose the CPU instruction set of your MicroPython board:
  - `None` (Default, generic bytecode)
  - `xtensa` (ESP8266 / standard ESP32)
  - `xtensawin` (ESP32-S2 / ESP32-S3)
  - `rv32imac` (ESP32-C3)
  - `armv6m` (Raspberry Pi Pico RP2040)
- **Optimization Level (-O)**:
  - `-O0` (No optimization)
  - `-O3` (Default maximum optimizations, includes dead-code removal and folding).

### 3. Compile and Download
- Click **Compile All** to process all loaded files.
- The status next to each file will update:
  - **Success (Green)**: Click the **Download** button to save the `.mpy` binary. Or click **Download All (.zip)** to grab all of them packed inside a single ZIP file.
  - **Failed (Red)**: Displays the syntax or compiler error trace. Read the message to fix syntax issues in your source `.py` files.
