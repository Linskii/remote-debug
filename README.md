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
    This command creates the necessary VS Code launch configurations in `.vscode/launch.json`.

    ```bash
    remote-debug init
    ```

    > [!WARNING]
    > If `launch.json` exists but is malformed, it will be backed up to `launch.json.bak` and a new file will be created.

2.  **Run your script on the cluster**
    Prefix your usual Python command with `remote-debug debug`. This will start a debug server and wait for you to connect.

    ```bash
    # Instead of: python my_script.py --arg value
    # Run this:
    remote-debug debug my_script.py --arg value
    ```

3.  **Check your job's output**
    The job output will contain the connection details needed to attach the debugger.

    ```text
    --- Python Debugger Info ---
    Node: uc2n805.localdomain
    Port: 51041
    Remote Path: /path/to/your/project
    --------------------------
    Script is paused, waiting for debugger to attach..
    ```

4.  **Connect VS Code**
    Follow one of the two methods below depending on your setup. Once attached, you can set breakpoints and debug as if you were running the code locally.

---

## Debugging Workflow

### Method A: Connecting from your Local Machine

Use this method if you are running VS Code locally and want to connect to the remote cluster.

1.  **Create an SSH Tunnel**
    On your **local machine**, run the `tunnel` command using the `Node` and `Port` from the job output, along with your cluster's SSH login details.

    ```bash
    # remote-debug tunnel <NODE> <REMOTE_PORT> <SSH_LOGIN>
    remote-debug tunnel uc2n805.localdomain 51041 username@cluster.hostname.com
    ```

    This will generate an `ssh` command. Copy, paste, and run it in a new terminal to establish the tunnel. Keep this terminal open.

2.  **Attach VS Code**
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
| `remote-debug <script> [args...]` | Wraps a Python script to start a `debugpy` listener and waits for a client to attach. |
| `remote-debug init` | Creates or updates `.vscode/launch.json` with the required debugger configurations. |
| `remote-debug tunnel <node> <port> <login>` | Constructs the SSH command to establish a tunnel to the compute node. |

---