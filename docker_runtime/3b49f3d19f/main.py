import subprocess
import os
import sys

def run_openclaw_setup():
    """
    Ejecuta la configuración de OpenClaw.

    - Dentro de Docker: no se usa sudo.
    - En host normal: usa sudo si no estamos en Docker.
    """
    in_docker = os.getenv("IS_DOCKER", "false").lower() == "true"
    sudo_cmd = None if in_docker else "sudo"

    # Componer comando de onboarding
    openclaw_cmd = [c for c in [sudo_cmd, "openclaw", "onboard", "--install-daemon"] if c]

    try:
        print("Running OpenClaw setup...")
        subprocess.run(openclaw_cmd, check=True)

        # Verificar status
        status_cmd = [c for c in [sudo_cmd, "openclaw", "status"] if c]
        subprocess.run(status_cmd, check=True)

        print("OpenClaw setup completed successfully!")

    except subprocess.CalledProcessError as e:
        print(f"Error during OpenClaw setup: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Command not found: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    run_openclaw_setup()
