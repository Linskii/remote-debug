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

## Command Reference

| Command | Description |
|---|---|
| `rdg rebug python <script> [args...]` | Wraps a Python script to start a `debugpy` listener and waits for a client to attach. |
| `rdg init` | Creates or updates `.vscode/launch.json` with the required debugger configurations. |
| `rdg tunnel <node> <port> <login> [--local-port <port>]` | Constructs the SSH command to establish a tunnel to the compute node. |

---