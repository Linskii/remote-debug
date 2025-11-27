# 🚀 remote-debug

A CLI tool to simplify visual debugging of Python scripts on remote HPC clusters directly from your local VS Code instance.

`remote-debug` helps you bridge the gap between your local editor and a script running on a remote compute node, making it easy to debug GPU-specific issues or complex cluster jobs with a full-featured debugger.

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Debugging Workflow](#debugging-workflow)
  - [Method A: Connecting from your Local Machine](#method-a-connecting-from-your-local-machine)
  - [Method B: Connecting via VS Code Remote-SSH](#method-b-connecting-via-vs-code-remote-ssh)
- [Lite Mode - On-Demand Debugging](#lite-mode---on-demand-debugging)
- [Programmatic API](#programmatic-api)
- [Command Reference](#command-reference)

---

## Installation

Install from PyPI:

```bash
pip install remote-debug
```

Or, build from source using [Pixi](https://pixi.sh/):

```bash
# Install pixi with: curl -fsSL https://pixi.sh/install.sh | sh
pixi install
```

---

## Quick Start

1.  **Initialize your project**
    Run this command from your project root to add the necessary VS Code launch configurations in `.vscode/launch.json`.

    ```bash
    rdg init
    ```

> [!WARNING]
> If `launch.json` exists but is malformed, it will be backed up to `launch.json.bak` and a new file will be created.

2.  **Run your script on the cluster**
    Prefix your usual Python command with `rdg debug`. This will start a debug server and wait for you to connect.

    ```bash
    # Instead of: python my_script.py --arg value
    # Run this:
    rdg debug python my_script.py --arg value
    ```

3.  **Check your job's output**
    The job output will contain the connection details and the SSH command needed to attach the debugger.

    ```text
    --- Python Debugger Info ---
    Node: uc2n805.localdomain
    Port: 51041
    Remote Path: /path/to/your/project
    --------------------------

    To connect from a local VS Code instance, run this on your local machine:
    ssh -N -L 5678:uc2n805.localdomain:51041 <user@login.hostname>
    Then, attach the debugger to localhost:5678.

    Script is paused, waiting for debugger to attach...
    ```

4.  **Connect VS Code**
    Follow one of the two methods below depending on your setup. Once attached, you can set breakpoints and debug as if you were running the code locally.

---

## Debugging Workflow

> [!NOTE]
> For the debugger to work, your VS Code editor must have access to the exact source code that is running on the remote compute node.
> - **If you are developing locally:** Make sure you have an identical copy of the project on your local machine (e.g., by using `git clone`).
> - **If you are using VS Code Remote-SSH:** You are already viewing the project files on the remote machine, so no extra steps are needed.

### Method A: Connecting from your Local Machine

Use this method if you are running your IDE locally and want to connect to the remote cluster.

1.  **Create an SSH Tunnel**
    Copy and paste the `ssh` command directly from your job's output. If `remote-debug` was able to detect your username and the hostname of the cluster automatically you are good to go, otherwise just replace the `<user@login.hostname>` placeholder. Keep this terminal open.

2.  **Attach Debugger (example with VS Code)**
    - Open the "Run and Debug" panel in VS Code (Ctrl+Shift+D).
    - Select **"Python Debugger: Remote Attach (via SSH Tunnel)"** from the dropdown and click the play button.
    - You will be prompted for:
      - **`localTunnelPort`**: The local port for the tunnel (default is `5678`).
      - **`remoteWorkspaceFolder`**: The `Remote Path` from the job output.

### Method B: Connecting via VS Code Remote-SSH

Use this method if you are already connected to a remote machine (like a login node) using the [VS Code Remote - SSH](https://code.visualstudio.com/docs/remote/ssh) extension.

1.  **Attach VS Code**
    - Open the "Run and Debug" panel in VS Code (Ctrl+Shift+D).
    - Select **"Python Debugger: Attach to Compute Node"** from the dropdown and click the play button.
    - You will be prompted for:
      - **`computeNodeHost`**: The `Node` from the job output.
      - **`computeNodePort`**: The `Port` from the job output.

---

## Post-Mortem Debugging

When you want to debug crashes without the overhead of running with an active debugger, use **post-mortem mode**:

```bash
rdg debug --post-mortem python my_script.py --arg value
```

In post-mortem mode:
- The script runs normally with zero debugger overhead
- If an unhandled exception occurs, the debugger starts automatically
- You can inspect the full call stack at the crash point
- The traceback is printed before the debugger starts

You can combine post-mortem with lite mode for maximum flexibility:

```bash
rdg debug --lite --post-mortem python my_script.py --arg value
```

This combination allows you to:
- Run the script normally without any debugger overhead
- Activate the debugger on-demand with `rdg attach` if needed
- Automatically start the debugger if the script crashes

---

## Lite Mode - On-Demand Debugging

For long-running jobs where you don't want to pause execution immediately but want the option to debug later, use **lite mode**:

1.  **Start your job with lite mode**

    ```bash
    rdg debug --lite python my_script.py --arg value
    ```

    The script runs normally without pausing. The output shows the Job ID and PID:

    ```text
    [Lite Debugger] Armed and ready!
      Job ID:  12345
      PID:     67890

    To activate the debugger, run:
      rdg attach 12345
    ```

2.  **Activate the debugger when needed**

    When you want to start debugging, run from the login node:

    ```bash
    rdg attach
    ```

    This will:
    - Show an interactive menu to select your running job
    - Prompt you for the PID from the job output
    - Send a signal to activate the debugger

    Alternatively, provide the Job ID and PID directly:

    ```bash
    rdg attach 12345 67890
    ```

3.  **Connect as usual**

    Once activated, check the job output for connection details and follow the standard workflow above to attach VS Code.

> [!TIP]
> Lite mode is perfect for jobs that run for hours or days. The debugger stays dormant until you need it, avoiding any performance impact. You can disconnect and reconnect multiple times during the job's lifetime.

---

## Programmatic API

For maximum control, trigger the debugger directly from your Python code:

```python
import remote_debug as rdg

# Option 1: Start and wait immediately
rdg.start_debugger()

# Option 2: Start without waiting, pause later
rdg.start_debugger(wait=False)
# ... initialization code runs ...
rdg.pause()  # Pause here when ready to debug
```

---

## Command Reference

| Command | Description |
|---|---|
| `rdg debug python <script> [args...]` | Wraps a Python script to start a `debugpy` listener and waits for a client to attach. |
| `rdg debug --lite python <script> [args...]` | Arms the debugger in lite mode - runs the script normally until you activate it with `rdg attach`. |
| `rdg debug --post-mortem python <script> [args...]` | Runs the script normally and automatically starts the debugger if an unhandled exception occurs. |
| `rdg attach [job_id] [pid]` | Activates a lite-mode debugger. Prompts interactively if arguments are omitted. |
| `rdg init` | Creates or updates `.vscode/launch.json` with the required debugger configurations. |

**Flags:**
- `--lite` / `-l` - Enable lite mode (on-demand debugging via signal)
- `--post-mortem` / `-p` - Enable post-mortem debugging (start debugger on crash)
- These flags can be combined: `rdg debug --lite --post-mortem python script.py` or `rdg debug -lp python script.py`

**Python API:**
- `remote_debug.start_debugger(wait=True)` - Start debugger server and optionally wait for connection
- `remote_debug.pause()` - Pause execution and wait for debugger to attach

---