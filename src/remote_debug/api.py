"""Public API for programmatic debugger control."""

import socket
import os
import debugpy
from rich.panel import Panel
from rich.text import Text
from rich.console import Console
import io


# Global state to track if debugger is already started
_debugger_started = False
_debugger_port = None
_debugger_host = None

# Default port to try (unlikely to be in use)
DEFAULT_DEBUG_PORT = 5679


def _is_port_free(port):
    """Check if a port is available."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", port))
            return True
    except OSError:
        return False


def _find_free_port():
    """Find an available port, preferring the default."""
    # Try default port first
    if _is_port_free(DEFAULT_DEBUG_PORT):
        return DEFAULT_DEBUG_PORT

    # Fall back to finding any free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _get_ssh_command(compute_node, remote_port, local_port=5678):
    """Build SSH tunnel command string."""
    user = os.environ.get("SLURM_JOB_USER") or os.environ.get("USER")
    submit_host_short = os.environ.get("SLURM_SUBMIT_HOST")

    if user and submit_host_short:
        try:
            submit_host_fqdn = socket.getfqdn(submit_host_short)
            if submit_host_fqdn.startswith(submit_host_short + "." + submit_host_short):
                submit_host_fqdn = submit_host_fqdn[len(submit_host_short) + 1 :]
            login_host = f"{user}@{submit_host_fqdn}"
        except socket.gaierror:
            login_host = f"{user}@{submit_host_short}"
    else:
        login_host = "<user@login.hostname>"

    return f"ssh -N -L {local_port}:{compute_node}:{remote_port} {login_host}"


def start_debugger(wait=True):
    """Start the debugpy server and optionally wait for a client to attach.

    This function starts a debugpy server on an available port and prints
    connection information. It can be called from within your Python script
    to enable remote debugging at any point.

    Args:
        wait: If True (default), execution pauses until a debugger attaches.
              If False, the server starts but execution continues immediately.

    Returns:
        dict: Connection info with keys 'hostname', 'port', 'remote_path'

    Example:
        >>> import remote_debug as rdg
        >>> # Start debugger and wait for connection
        >>> rdg.start_debugger()
        >>>
        >>> # Or start without waiting, continue execution
        >>> rdg.start_debugger(wait=False)
        >>> # ... do some work ...
        >>> rdg.pause()  # Pause here when ready
    """
    global _debugger_started, _debugger_port, _debugger_host

    if _debugger_started:
        print(f"[DEBUGGER] Already started on {_debugger_host}:{_debugger_port}", flush=True)
        if wait:
            pause()
        return {
            "hostname": _debugger_host,
            "port": _debugger_port,
            "remote_path": os.getcwd(),
        }

    # Find an open port
    port = _find_free_port()
    hostname = socket.gethostname()
    remote_path = os.getcwd()

    # Store global state
    _debugger_started = True
    _debugger_port = port
    _debugger_host = hostname

    # Print connection info
    console = Console(file=io.StringIO())
    info_text = Text(justify="left")
    info_text.append("Node:        ", style="bold")
    info_text.append(hostname, style="cyan")
    info_text.append("\nPort:        ", style="bold")
    info_text.append(str(port), style="cyan")
    info_text.append("\nRemote Path: ", style="bold")
    info_text.append(remote_path, style="cyan")

    panel = Panel(
        info_text,
        title="[bold yellow]Python Debugger Info[/bold yellow]",
        border_style="blue",
        expand=False,
    )
    console.print(panel)
    output = console.file.getvalue()
    print(output, flush=True)

    # Start listening
    debugpy.listen(("0.0.0.0", port))
    print(f"[DEBUGGER] Listening on 0.0.0.0:{port}", flush=True)

    # Print SSH tunnel command
    default_local_port = 5678
    ssh_command = _get_ssh_command(hostname, port, default_local_port)
    print(
        "\nTo connect from a local VS Code instance, run this on your local machine:",
        flush=True,
    )
    print(f"\033[92m{ssh_command}\033[0m", flush=True)  # Green color
    print(
        f"Then, attach the debugger to localhost:{default_local_port}.\n",
        flush=True,
    )

    if wait:
        pause()

    return {
        "hostname": hostname,
        "port": port,
        "remote_path": remote_path,
    }


def pause():
    """Pause execution and wait for a debugger to attach.

    This function blocks execution until a VS Code debugger connects.
    Must be called after start_debugger() has been called with wait=False.

    Example:
        >>> import remote_debug as rdg
        >>> rdg.start_debugger(wait=False)
        >>> # ... some initialization code ...
        >>> rdg.pause()  # Now wait here for debugger
    """
    if not _debugger_started:
        raise RuntimeError(
            "Debugger not started. Call start_debugger() first."
        )

    print("[DEBUGGER] Pausing execution. Attach your VS Code now!", flush=True)
    debugpy.wait_for_client()
    debugpy.breakpoint()
    print("[DEBUGGER] Debugger attached! Resuming execution.", flush=True)
