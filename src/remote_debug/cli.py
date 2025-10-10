import rich_click as click
from rich.panel import Panel
from rich.text import Text
from rich.console import Console
import socket
import os
import sys
import runpy
import debugpy
import json
import io


@click.group()
def cli():
    """A helper tool for remote debugging Python scripts on HPC clusters.

    This tool simplifies the process of starting a Python debugger on a compute node
    and connecting to it from a local VS Code instance.
    """
    pass


@cli.command(
    context_settings=dict(
        ignore_unknown_options=True,
        allow_interspersed_args=False,
    )
)
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
def debug(command):
    """Wraps a Python script to start a `debugpy` listener.

    This allows you to attach a remote debugger from your local machine.
    It is designed as a drop-in replacement for the `python` command.

    For example, instead of running:

        python my_script.py --arg1 value1

    You would run:

        rdg debug python my_script.py --arg1 value1
    """
    if not command or not command[0].endswith("python"):
        click.echo(
            "Usage: rdg debug python <script.py> [args...]",
            err=True,
        )
        sys.exit(1)

    script_path = command[1]
    script_args = command[2:]

    # 1. Find an open port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    # 2. Get the current hostname.
    hostname = socket.gethostname()
    remote_path = os.getcwd()

    # Print connection info for the user
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
    click.echo(output)

    # Also print the tunnel command for convenience
    default_local_port = 5678
    ssh_command = _construct_ssh_command(hostname, port, default_local_port)
    click.echo(
        "\nTo connect from a local VS Code instance, run this on your local machine:"
    )
    click.secho(ssh_command, fg="green")
    click.echo(f"Then, attach the debugger to localhost:{default_local_port}.\n")

    # Start listening for a connection.
    debugpy.listen(("0.0.0.0", port))

    click.echo("Script is paused, waiting for debugger to attach...")
    # This line blocks execution until you attach from VS  Code.
    debugpy.wait_for_client()
    click.echo("Debugger attached! Resuming script.")

    # Execute the target script
    # Set sys.argv to what the script would expect
    sys.argv = [script_path] + list(script_args)
    # Add the script's directory to the path to allow for relative imports
    sys.path.insert(0, os.path.dirname(script_path))

    runpy.run_path(script_path, run_name="__main__")


@cli.command()
def init():
    """Adds launch configurations to your VS Code settings (`.vscode/launch.json`).

    This command will add two configurations:

    1.  **Python Debugger: Remote Attach (via SSH Tunnel)**:
        For connecting from your local machine to a compute node via an SSH tunnel.

    2.  **Python Debugger: Attach to Compute Node**:
        For connecting directly when you are already on the cluster's login node using the VS Code SSH extension.
    """
    click.echo("Initializing debug configuration...")

    vscode_dir = ".vscode"
    launch_json_path = os.path.join(vscode_dir, "launch.json")

    # Define the new configurations and inputs
    new_configs = [
        {
            "name": "Python Debugger: Remote Attach (via SSH Tunnel)",
            "type": "debugpy",
            "request": "attach",
            "connect": {"host": "localhost", "port": "${input:localTunnelPort}"},
            "pathMappings": [
                {
                    "localRoot": "${workspaceFolder}",
                    "remoteRoot": "${input:remoteWorkspaceFolder}",
                }
            ],
        },
        {
            "name": "Python Debugger: Attach to Compute Node",
            "type": "debugpy",
            "request": "attach",
            "connect": {
                "host": "${input:computeNodeHost}",
                "port": "${input:computeNodePort}",
            },
            "pathMappings": [
                {"localRoot": "${workspaceFolder}", "remoteRoot": "${workspaceFolder}"}
            ],
        },
    ]

    new_inputs = [
        {
            "id": "localTunnelPort",
            "type": "promptString",
            "description": "Enter the local port your SSH tunnel is forwarding to (e.g., 5678).",
            "default": "5678",
        },
        {
            "id": "remoteWorkspaceFolder",
            "type": "promptString",
            "description": "Enter the absolute path to the project folder on the remote machine.",
        },
        {
            "id": "computeNodeHost",
            "type": "promptString",
            "description": "Enter the compute node hostname (e.g., node123.cluster.local).",
        },
        {
            "id": "computeNodePort",
            "type": "promptString",
            "description": "Enter the port the remote debugger is listening on.",
        },
    ]

    # Ensure .vscode directory exists
    os.makedirs(vscode_dir, exist_ok=True)

    # Read existing launch.json or create a new structure
    if os.path.exists(launch_json_path):
        with open(launch_json_path, "r") as f:
            try:
                launch_data = json.load(f)
                if "version" not in launch_data:
                    launch_data["version"] = "0.2.0"
                if "configurations" not in launch_data:
                    launch_data["configurations"] = []
            except json.JSONDecodeError:
                click.echo(
                    f"Warning: '{launch_json_path}' is malformed. Backing up and creating a new one.",
                    err=True,
                )
                os.rename(launch_json_path, launch_json_path + ".bak")
                launch_data = {"version": "0.2.0", "configurations": [], "inputs": []}
    else:
        launch_data = {"version": "0.2.0", "configurations": [], "inputs": []}

    # Add new configurations if they don't already exist
    existing_config_names = {
        c.get("name") for c in launch_data.get("configurations", [])
    }
    for config in new_configs:
        if config["name"] not in existing_config_names:
            launch_data["configurations"].append(config)
            click.echo(f"Added '{config['name']}' configuration.")

    # Add new inputs if they don't already exist
    if "inputs" not in launch_data:
        launch_data["inputs"] = []
    existing_input_ids = {i.get("id") for i in launch_data.get("inputs", [])}
    for new_input in new_inputs:
        if new_input["id"] not in existing_input_ids:
            launch_data["inputs"].append(new_input)

    # Write the updated launch.json back to the file
    with open(launch_json_path, "w") as f:
        json.dump(launch_data, f, indent=4)

    click.echo(f"Successfully updated '{launch_json_path}'.")


def _construct_ssh_command(compute_node, remote_port, local_port):
    """Builds the SSH tunnel command string."""

    # Try to get user and login host from Slurm environment variables
    user = os.environ.get("SLURM_JOB_USER") or os.environ.get("USER")
    submit_host_short = os.environ.get("SLURM_SUBMIT_HOST")

    if user and submit_host_short:
        try:
            # Attempt to resolve the fully qualified domain name
            submit_host_fqdn = socket.getfqdn(submit_host_short)
            # Fix for cases where getfqdn returns a doubled hostname (e.g., host.host.domain.com)
            if submit_host_fqdn.startswith(submit_host_short + "." + submit_host_short):
                submit_host_fqdn = submit_host_fqdn[len(submit_host_short) + 1 :]
            login_placeholder = f"{user}@{submit_host_fqdn}"
        except socket.gaierror:
            # Fallback to short name if resolution fails
            click.echo(
                "Warning: Could not automatically resolve FQDN for submit host. The hostname trailing the @ might be incomplete.",
                err=True,
            )
            login_placeholder = f"{user}@{submit_host_short}"
    else:
        login_placeholder = "<user@login.hostname>"

    return f"ssh -N -L {local_port}:{compute_node}:{remote_port} {login_placeholder}"


if __name__ == "__main__":
    cli()
