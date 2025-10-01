import click
import socket
import os
import sys
import runpy
import debugpy
import json


@click.group()
def cli():
    """A helper tool for remote debugging on HPC clusters."""
    pass


@cli.command(
    context_settings=dict(
        ignore_unknown_options=True,
    )
)
@click.argument("script_path", type=click.Path(exists=True))
@click.argument("script_args", nargs=-1, type=click.UNPROCESSED)
def debug(script_path, script_args):
    """Wraps a python script to start a debugpy listener."""
    # 1. Find an open port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    # 2. Get the current hostname.
    hostname = socket.gethostname()
    remote_path = os.getcwd()

    # Print connection info for the user
    click.echo("--- Python Debugger Info ---")
    click.echo(f"Node: {hostname}")
    click.echo(f"Port: {port}")
    click.echo(f"Remote Path: {remote_path}")
    click.echo("--------------------------")

    # Start listening for a connection.
    debugpy.listen(("0.0.0.0", port))

    click.echo("Script is paused, waiting for debugger to attach..")
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
    """Initializes the project with a VS Code launch configuration."""
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


@cli.command()
@click.argument("compute_node")
@click.argument("remote_port", type=int)
@click.argument("ssh_login")
@click.option(
    "--local-port", default=5678, help="The local port to forward.", show_default=True
)
def tunnel(compute_node, remote_port, ssh_login, local_port):
    """Constructs the SSH command to create a tunnel for remote debugging."""

    ssh_command = f"ssh -N -L {local_port}:{compute_node}:{remote_port} {ssh_login}"

    click.echo(
        "\nRun the following command in a new terminal on your local machine to create the SSH tunnel:"
    )
    click.echo("-" * 70)
    click.secho(ssh_command, fg="green")
    click.echo("-" * 70)
    click.echo("\nKeep that terminal open to maintain the connection.")
    click.echo(
        f"Once the tunnel is running, you can attach your VS Code debugger to localhost:{local_port}."
    )


if __name__ == "__main__":
    cli()
