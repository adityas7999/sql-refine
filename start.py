#!/usr/bin/env python3
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
ENV_EXAMPLE = ROOT / ".env.example"
ENV_FILE = ROOT / ".env"
BACKEND_VENV = BACKEND_DIR / ".venv"
PYTHON_BIN = BACKEND_VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_env_file() -> None:
    if not ENV_FILE.exists() and ENV_EXAMPLE.exists():
        shutil.copy2(ENV_EXAMPLE, ENV_FILE)
        print(f"Created {ENV_FILE.name} from {ENV_EXAMPLE.name}")


def resolve_executable(command_name: str) -> str:
    resolved = shutil.which(command_name)
    if resolved:
        return resolved
    if os.name == "nt":
        resolved = shutil.which(f"{command_name}.cmd")
        if resolved:
            return resolved
        resolved = shutil.which(f"{command_name}.exe")
        if resolved:
            return resolved
    return ""


def ensure_tool(name: str, command: list[str]) -> str:
    executable = resolve_executable(command[0])
    if not executable:
        raise SystemExit(f"Missing required tool: {name}. Install it and try again.\nExpected command: {' '.join(command)}")
    return executable


def ensure_backend_venv() -> Path:
    if not BACKEND_VENV.exists():
        print("Creating backend virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", str(BACKEND_VENV)], check=True)

    if not PYTHON_BIN.exists():
        raise SystemExit(f"Backend Python environment is incomplete: {PYTHON_BIN}")

    return PYTHON_BIN


def ensure_backend_dependencies(python_bin: Path) -> None:
    print("Installing backend dependencies...")
    subprocess.run([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"], cwd=str(BACKEND_DIR), check=True)
    subprocess.run([str(python_bin), "-m", "pip", "install", "-r", "requirements.txt"], cwd=str(BACKEND_DIR), check=True)


def ensure_frontend_dependencies() -> None:
    if not (FRONTEND_DIR / "node_modules").exists():
        print("Installing frontend dependencies...")
        subprocess.run(["npm", "install"], cwd=str(FRONTEND_DIR), check=True)


def wait_for_url(url: str, timeout_seconds: int = 60) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return True
        except Exception:
            time.sleep(1)
    return False


def start_process(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.Popen:
    return subprocess.Popen(command, cwd=str(cwd), env=env, start_new_session=os.name != "nt")


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        process.terminate()
    else:
        process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()


def main() -> int:
    ensure_env_file()
    ensure_tool("Python", [sys.executable, "--version"])
    node_bin = ensure_tool("Node.js", ["node", "--version"])
    npm_bin = ensure_tool("npm", ["npm", "--version"])

    python_bin = ensure_backend_venv()
    ensure_backend_dependencies(python_bin)
    ensure_frontend_dependencies()

    backend = start_process([str(python_bin), "app.py"], BACKEND_DIR)
    frontend = start_process([npm_bin, "run", "dev", "--", "--host", "0.0.0.0", "--port", "4173"], FRONTEND_DIR)

    print("\nStarting SQLRefine...")
    print("Backend: http://127.0.0.1:5000")
    print("Frontend: http://localhost:4173")

    try:
        backend_ready = wait_for_url("http://127.0.0.1:5000/api/health", timeout_seconds=45)
        frontend_ready = wait_for_url("http://localhost:4173", timeout_seconds=45)
        if not backend_ready:
            raise SystemExit("Backend did not become ready in time.")
        if not frontend_ready:
            raise SystemExit("Frontend did not become ready in time.")

        try:
            import webbrowser
            webbrowser.open("http://localhost:4173")
        except Exception:
            pass

        print("\nSQLRefine is running. Press Ctrl+C to stop it.\n")
        while True:
            time.sleep(1)
            if backend.poll() is not None or frontend.poll() is not None:
                if backend.poll() is not None:
                    raise SystemExit(f"Backend exited unexpectedly with code {backend.returncode}")
                raise SystemExit(f"Frontend exited unexpectedly with code {frontend.returncode}")
    except KeyboardInterrupt:
        print("\nStopping services...")
    finally:
        stop_process(frontend)
        stop_process(backend)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
