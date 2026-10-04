# Treasure Runner

A multi-language dungeon exploration game engine built in C and Python. The C backend handles world generation, room layout, player movement, and game state. Python bindings expose the engine through a ctypes interface, powering both a CLI integration runner and an interactive terminal UI with player profiles, a real-time minimap, and a full victory condition.

---

## Project Structure

```
.devcontainer/          # Dev container configuration
assets/                 # World generation config files (.ini)
c/
  src/                  # C source files (player, room, world_loader, game_engine, graph)
  include/              # C header files
  tests/                # C unit tests (Check framework)
  tools/                # Developer tools (c-render, puzzlegen_demo)
dist/                   # Pre-built puzzle generator libraries
  libpuzzlegen-linux-amd64.so
  libpuzzlegen-linux-arm64.so
python/
  run_integration.py    # CLI integration runner
  treasure_runner/
    bindings/           # ctypes bindings to the C library
    models/             # GameEngine, Player, exceptions
  tests/                # Python unit tests
Makefile                # Root build system
env.sh                 # Environment setup
```

---

## Getting Started

### Option 1: Dev Container (Recommended)

Requires [Docker](https://www.docker.com/) and [VS Code](https://code.visualstudio.com/) with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

1. Clone the repository
2. Open in VS Code
3. Click **Reopen in Container** when prompted or by pressing **F1** and typing **Dev Containers: Reopen in Container**

The container image is publicly available on Docker Hub and includes all required dependencies: `gcc`, `clang`, `clang-tidy`, `libcheck-dev`, Python 3, and coverage tools.

## Option 2: Linux Setup (Linux only)

The pre-built puzzle generator in `dist/` supports **Linux x86-64 and ARM64 only**. macOS and Windows are not supported without the dev container.

```bash
sudo apt-get install gcc clang clang-tidy libcheck-dev \
    python3 python3-pip python3-coverage pkg-config
```

---

## Building


```bash
# 1. Source environment variables
source env.sh

# 2. Detect platform, symlink the correct libpuzzlegen.so, and build the C library
make dist

# Clean build artifacts (does not touch dist/)
make clean
```

`make dist` selects the correct pre-built `.so` for your platform (amd64 or arm64) and compiles the C source into `dist/libbackend.so`.

---

## C Unit Tests

```bash
source env.sh
make -C c test
```

Tests use the [Check](https://libcheck.github.io/check/) framework. The test runner is built at `c/build/tests/test_runner`.

---

## CLI Integration Runner

Executes a deterministic sweep sequence through a generated world and writes a structured log file for comparison against a reference implementation.

### Usage

```bash
source env.sh
python3 python/run_integration.py --config assets/your_world.ini --log output.log
```

### Log Format

```
RUN_START|config=...|rooms=N|room_width=W|room_height=H
STATE|step=0|phase=SPAWN|state=room=R|x=X|y=Y|collected=C
ENTRY|direction=DIRNAME
MOVE|step=N|phase=SWEEP_SOUTH|dir=SOUTH|result=OK|before=...|after=...|delta_collected=N
SWEEP_START|phase=SWEEP_WEST|dir=WEST
SWEEP_END|phase=SWEEP_WEST|reason=BLOCKED|moves=N
STATE|step=N|phase=FINAL|state=room=R|x=X|y=Y|collected=C
RUN_END|steps=N|collected_total=N
```

Sweep order is fixed: `SOUTH → WEST → NORTH → EAST`.

### Python Unit Tests

```bash
cd python
python3 -m coverage run --source=run_integration -m unittest discover -s tests -p "*.py" -v
python3 -m coverage report -m
```

Coverage configuration is in `python/.coveragerc`.

---

## Terminal UI

An interactive curses-based terminal game with MVC architecture, player profile persistence, and extended gameplay features.

### Usage

```bash
source env.sh
python3 python/main.py --config assets/your_world.ini
```

### Controls

| Key | Action |
|---|---|
| `W` / `↑` | Move North |
| `S` / `↓` | Move South |
| `A` / `←` | Move West |
| `D` / `→` | Move East |
| `Q` | Quit |

Additional controls are shown in the in-game legend.

### Architecture

```
View (curses renderer)
  ↕
Controller (input handler)
  ↕
Model: Python GameEngine / Player
  ↕ ctypes
C library: libbackend.so
  ↕
libpuzzlegen.so (pre-built world generator)
```

### Features

#### Collect All Treasure
Tracks total treasure count across the entire world. Collecting every treasure triggers a victory screen showing the player profile, total steps taken, rooms visited, and time elapsed. The status bar displays live progress (e.g., `15/20 treasures collected`).

#### Enhanced UI
- Colour-coded display using curses colour pairs
- Real-time minimap of the room graph with the player's current location highlighted
- Rooms colour-coded by visit status and whether they contain uncollected treasure
- Minimap built from a C-side adjacency matrix — the raw C graph is never passed to Python directly

---

## Architecture Notes

### Error Handling

C functions return a `Status` enum. The Python bindings map these to Python exceptions:

| C Status | Python Exception |
|---|---|
| `ROOM_IMPASSABLE` | `ImpassableError` |
| `INTERNAL_ERROR` / `GE_NO_SUCH_ROOM` | `GameEngineError` |

### Memory Management

The C library owns all heap memory. Python holds opaque `c_void_p` handles and must call `engine.destroy()` when done to free C-side resources. `destroy()` guards against double-free by setting the internal pointer to `None` after the first call.