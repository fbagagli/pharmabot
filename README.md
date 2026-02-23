# Pharmabot

A CLI tool to compare medication prices on trovaprezzi.it.

## Development

See [DEV_GUIDELINES.md](DEV_GUIDELINES.md) for development instructions.

## Installation

### System Dependencies (Ubuntu 24.04)

To run the GUI, you need to install the following system dependencies (including development headers required to build PyGObject):

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1 \
    libcairo2-dev libgirepository1.0-dev libwebkit2gtk-4.1-dev pkg-config python3-dev gcc
```

### Python Dependencies

```bash
uv sync
```

## Usage

```bash
uv run pharmabot
```
