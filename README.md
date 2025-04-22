# dsi24-qtm-trigger-sync

Synchronize parallel‑port triggers for the DSI‑24 trigger hub with event markers for Qualisys QTM.  
Supports simultaneous hardware/software markers for high‑precision MoBI experiments.

## Features

- Async QTM recording via `qtm-rt` SDK  
- Parallel‑port pulses via PsychoPy’s `parallel` module  
- BIDS‑compatible output filenames & directory structure  
- CLI for quick setup (`--triggers` to enable hardware pulses)  
- Unit tests & CI via GitHub Actions  

## Installation

```bash
git clone https://github.com/your-org/dsi24-qtm-trigger-sync.git
cd dsi24-qtm-trigger-sync
pip install -r requirements.txt
