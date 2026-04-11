# VOFA Workspace Presets

## Stream Preset Folders (NEW — how the dashboard works now)

Each stream has its own preset folder:
- `stream_a/vofa+.config.json` — Frame A channel names + settings (port 1347)
- `stream_a/vofa+.tabviews.json` — Frame A tab layout
- `stream_b/vofa+.config.json` — Frame B channel names + settings (port 1348)
- `stream_b/vofa+.tabviews.json` — Frame B tab layout

### How to set up your own layout

1. Open VOFA manually (not via dashboard).
2. Rename all channel variables and organize tabs the way you want.
3. Close VOFA (it saves to `%LOCALAPPDATA%/vofa+/100/context/`).
4. Click the dashboard "Capture A Config" or "Capture B Config" button
   (or call `_capture_vofa_stream_preset("a")` / `("b")` in code).
5. The preset files will be updated.

### How the dashboard button works

Clicking "Frame A Workspace":
1. Kills any running VOFA.
2. Copies `stream_a/vofa+.config.json` and `stream_a/vofa+.tabviews.json`
   into `%LOCALAPPDATA%/vofa+/100/context/`.
3. Patches UDP port to 1347.
4. Launches VOFA.

Clicking "Frame B Workspace": same, but uses `stream_b/` files and port 1348.

No contamination is possible — each button always overwrites the system context
with its own preset before launching.

---

Save all VOFA workspace files in this folder.

Ready-to-use presets created in this folder:

- full.tabviews.json
- mrac_errors.tabviews.json
- weights.tabviews.json
- pid_all.tabviews.json
- channel_reference.json

VOFA 1.3.x saves layouts as tabviews JSON (not classic .vofa files).
Use the menu option "Save widget windows and tabs".

Current dashboard buttons map to these exact file names:

- mrac_errors.vofa
- weights.vofa
- pid_all.vofa
- full.vofa

The dashboard now auto-resolves these compatible saved names too:

- mrac_errors.tabviews.json
- weights.tabviews.json
- pid_all.tabviews.json
- full.tabviews.json

Also supported if VOFA appends suffix after a typed .vofa name:

- mrac_errors.vofa.tabviews.json
- weights.vofa.tabviews.json
- pid_all.vofa.tabviews.json
- full.vofa.tabviews.json

Recommended strategy:

1. Fast stream (port 1347, Frame A):
   - Keep one workspace file as your main fast monitor.
   - Suggested file: full.tabviews.json

2. Slow stream (port 1348, Frame B):
   - Keep multiple focused workspaces because channel count is high.
   - Suggested files:
     - pid_all.tabviews.json
     - weights.tabviews.json
     - mrac_errors.tabviews.json

Professional preset wiring used by the dashboard sidebar:

1. A Fast Monitor -> full.tabviews.json (Frame A / 1347)
2. B MRAC Errors -> mrac_errors.tabviews.json (Frame B / 1348)
3. B Adaptive Weights -> weights.tabviews.json (Frame B / 1348)
4. B PID Loops -> pid_all.tabviews.json (Frame B / 1348)

Variable/channel naming reference:

- Use channel_reference.json for exact index -> name mapping.
- Frame B index groups in the presets assume MAX_NUM_BASIS = 6.

You can create extra workspaces too, for example:
- b_path_debug.tabviews.json
- b_safety_debug.tabviews.json

If you add new dashboard buttons, map them to files in this folder.
