import subprocess
import os
import sys

def run_openclaw_setup_with_root():
    """
    Launch OpenClaw setup with root privileges,
    enabling the bot full access and capability to self-modify.

    This script assumes:
    - You have root/sudo access on the system.
    - OpenClaw is installed or the repo is locally cloned.
    - You want to run the OpenClaw onboarding setup daemon,
      which installs necessary background services with proper privileges.
    """

    # Detect platform-specific sudo command
    sudo_cmd = "sudo"
    if os.name == "nt":
        raise RuntimeError("This script is intended for Unix-like systems with sudo")

    # Optional: set environment variables for custom paths if needed
    # Example:
    # os.environ["OPENCLAW_HOME"] = "/root/.openclaw"
    # os.environ["OPENCLAW_STATE_DIR"] = "/var/lib/openclaw/state"
    # os.environ["OPENCLAW_CONFIG_PATH"] = "/etc/openclaw/config.json"

    # Compose the openclaw onboarding command with daemon install flag
    openclaw_cmd = [sudo_cmd, "openclaw", "onboard", "--install-daemon"]

    try:
        print("Running OpenClaw setup with root privileges...")
        subprocess.run(openclaw_cmd, check=True)
        print("OpenClaw onboarding with daemon installation completed successfully.")

        # Verify installation status
        print("Verifying OpenClaw status...")
        subprocess.run([sudo_cmd, "openclaw", "status"], check=True)

    except subprocess.CalledProcessError as e:
        print(f"Error during OpenClaw setup: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    run_openclaw_setup_with_root()