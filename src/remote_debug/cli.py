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
import subprocess
import questionary


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
@click.option(
    "--lite",
    "-l",
    is_flag=True,
    help="Enable lite mode: arm the debugger but don't start it until triggered with 'rdg attach'.",
)
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
def debug(lite, command):
    """Wraps a Python script to start a `debugpy` listener.

    This allows you to attach a remote debugger from your local machine.
    It is designed as a drop-in replacement for the `python` command.

    For example, instead of running:

        python my_script.py --arg1 value1

    You would run:

        rdg debug python my_script.py --arg1 value1

    Use --lite mode for long-running jobs where you want the debugger on standby:

        rdg debug --lite python my_script.py --arg1 value1
    """
    if not command or not command[0].endswith("python"):
        click.echo(
            "Usage: rdg debug [--lite] python <script.py> [args...]",
            err=True,
        )
        sys.exit(1)

    script_path = command[1]
    script_args = command[2:]

    if lite:
        # Lite mode: inject signal handler and run script normally
        _run_lite_mode(script_path, script_args)
    else:
        # Normal mode: start debugger immediately
        _run_normal_mode(script_path, script_args)


def _run_normal_mode(script_path, script_args):
    """Run the script with debugger started immediately (original behavior)."""
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
    # This line blocks execution until you attach from VS Code.
    debugpy.wait_for_client()
    click.echo("Debugger attached! Resuming script.")

    # Execute the target script
    # Set sys.argv to what the script would expect
    sys.argv = [script_path] + list(script_args)
    # Add the script's directory to the path to allow for relative imports
    sys.path.insert(0, os.path.dirname(script_path))

    runpy.run_path(script_path, run_name="__main__")


def _run_lite_mode(script_path, script_args):
    """Run the script with signal-based debugger activation."""
    import signal

    # Print initial message
    job_id = os.environ.get("SLURM_JOB_ID", "UNKNOWN")
    pid = os.getpid()
    click.secho(f"\n[Lite Debugger] Armed and ready!", fg="green", bold=True)
    click.echo(f"  Job ID:  {job_id}")
    click.echo(f"  PID:     {pid}")
    click.echo(f"\nTo activate the debugger, run:")
    click.secho(f"  rdg attach {job_id}", fg="cyan", bold=True)
    click.echo()

    def _activate_debugger(signum, frame):
        """Signal handler that activates the debugger."""
        import socket
        import debugpy
        from rich.panel import Panel
        from rich.text import Text
        from rich.console import Console
        import io

        print(
            f"\n[DEBUGGER] Signal {signum} received! Waking up debugger...",
            flush=True,
        )

        # 1. Find an open port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            port = s.getsockname()[1]

        # 2. Get the current hostname
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
        print(output, flush=True)

        # Start listening
        debugpy.listen(("0.0.0.0", port))
        print(f"[DEBUGGER] Listening on 0.0.0.0:{port}", flush=True)

        # Print SSH tunnel command
        default_local_port = 5678
        ssh_command = _construct_ssh_command(hostname, port, default_local_port)
        print(
            "\nTo connect from a local VS Code instance, run this on your local machine:",
            flush=True,
        )
        print(f"\033[92m{ssh_command}\033[0m", flush=True)  # Green color
        print(
            f"Then, attach the debugger to localhost:{default_local_port}.\n",
            flush=True,
        )

        print(f"[DEBUGGER] Pausing execution. Attach your VS Code now!", flush=True)

        # Wait for client and break
        debugpy.wait_for_client()
        debugpy.breakpoint()

    # Register the signal handler
    signal.signal(signal.SIGUSR1, _activate_debugger)

    # Execute the target script
    sys.argv = [script_path] + list(script_args)
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


@cli.command()
@click.argument("job_id", required=False)
@click.argument("pid", required=False)
def attach(job_id, pid):
    """Attach to a running lite-mode debugger job.

    Send a SIGUSR1 signal to activate the debugger in a job started with 'rdg debug --lite'.

    If JOB_ID is not provided, you'll be prompted to select from your running jobs.
    If PID is not provided, you'll be prompted to enter it.

    Examples:
        rdg attach 12345 98765
        rdg attach 12345  (will prompt for PID)
        rdg attach        (will prompt for both)
    """
    # If no job_id provided, show interactive selection
    if not job_id:
        job_id = _select_job_interactive()
        if not job_id:
            click.echo("No job selected. Exiting.", err=True)
            sys.exit(1)

    # If no PID provided, prompt for it
    if not pid:
        click.echo(
            f"\nCheck the job output for the PID (look for 'PID:' in the output)."
        )
        pid = questionary.text(
            "Enter the Python process PID:",
            validate=lambda text: text.isdigit() or "Please enter a valid PID number",
        ).ask()

        if not pid:
            click.echo("No PID provided. Exiting.", err=True)
            sys.exit(1)

    # Send the SIGUSR1 signal using srun
    click.echo(f"Sending activation signal to job {job_id} (PID {pid})...")
    try:
        subprocess.run(
            ["srun", f"--jobid={job_id}", "--pty", "bash", "-c", f"kill -USR1 {pid}"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        click.secho(f"✓ Signal sent successfully to job {job_id}!", fg="green")
    except subprocess.TimeoutExpired:
        click.secho(f"✗ Timeout sending signal to job {job_id}", fg="red", err=True)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        click.secho(f"✗ Failed to send signal to job {job_id}", fg="red", err=True)
        if e.stderr:
            click.echo(f"Error: {e.stderr.strip()}", err=True)
        sys.exit(1)
    except FileNotFoundError:
        click.secho(
            "✗ 'srun' command not found. Are you on a Slurm cluster?",
            fg="red",
            err=True,
        )
        sys.exit(1)

    # Print instructions
    click.echo(f"\nThe debugger should now be activating in job {job_id}.")
    click.echo(f"Check your job output file (typically slurm-{job_id}.out) for:")
    click.echo("  • Debugger connection details (hostname, port)")
    click.echo("  • SSH tunnel command")
    click.echo("\nThen create the tunnel and attach VS Code as usual.")


def _select_job_interactive():
    """Show an interactive job selection menu using squeue.

    Returns:
        str: Selected job ID, or None if cancelled
    """
    user, _ = _get_user_and_host()

    if not user:
        click.echo("Error: Could not determine username.", err=True)
        return None

    # Run squeue to get user's jobs across all partitions
    try:
        result = subprocess.run(
            ["squeue", "-u", user, "-h", "-o", "%i|%j|%T|%M|%N", "-a"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        click.secho("✗ Failed to retrieve job list", fg="red", err=True)
        if e.stderr:
            click.echo(f"Error: {e.stderr.strip()}", err=True)
        return None
    except FileNotFoundError:
        click.secho(
            "✗ 'squeue' command not found. Are you on a Slurm cluster?",
            fg="red",
            err=True,
        )
        return None

    # Parse squeue output
    jobs = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 5:
            job_id, job_name, state, time, node = parts
            jobs.append(
                {
                    "id": job_id,
                    "name": job_name,
                    "state": state,
                    "time": time,
                    "node": node,
                }
            )

    if not jobs:
        click.echo(f"No running jobs found for user '{user}'.", err=True)
        return None

    # Create questionary choices
    choices = [
        {
            "name": f"{job['id']:>8} | {job['name']:<30} | {job['state']:<10} | {job['time']:<10} | {job['node']}",
            "value": job["id"],
        }
        for job in jobs
    ]

    # Show interactive selection
    click.echo(f"\nFound {len(jobs)} job(s) for user '{user}':\n")
    selected = questionary.select(
        "Select a job to attach to:",
        choices=choices,
    ).ask()

    return selected


def _get_user_and_host():
    """Get the current user and login host from Slurm environment variables.

    Returns:
        tuple: (user, login_host) where login_host is the FQDN if possible, or None if not available
    """
    user = os.environ.get("SLURM_JOB_USER") or os.environ.get("USER")
    submit_host_short = os.environ.get("SLURM_SUBMIT_HOST")

    if user and submit_host_short:
        try:
            # Attempt to resolve the fully qualified domain name
            submit_host_fqdn = socket.getfqdn(submit_host_short)
            # Fix for cases where getfqdn returns a doubled hostname (e.g., host.host.domain.com)
            if submit_host_fqdn.startswith(submit_host_short + "." + submit_host_short):
                submit_host_fqdn = submit_host_fqdn[len(submit_host_short) + 1 :]
            return user, submit_host_fqdn
        except socket.gaierror:
            # Fallback to short name if resolution fails
            click.echo(
                "Warning: Could not automatically resolve FQDN for submit host. The hostname trailing the @ might be incomplete.",
                err=True,
            )
            return user, submit_host_short

    return user, None


def _construct_ssh_command(compute_node, remote_port, local_port):
    """Builds the SSH tunnel command string."""
    user, login_host = _get_user_and_host()

    if user and login_host:
        login_placeholder = f"{user}@{login_host}"
    else:
        login_placeholder = "<user@login.hostname>"

    return f"ssh -N -L {local_port}:{compute_node}:{remote_port} {login_placeholder}"


if __name__ == "__main__":
    cli()
