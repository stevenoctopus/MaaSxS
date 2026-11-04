from pathlib import Path

import json
import shutil
import sys

try:
    import jsonc
except ModuleNotFoundError as e:
    raise ImportError(
        "Missing dependency 'json-with-comments' (imported as 'jsonc').\n"
        f"Install it with:\n  {sys.executable} -m pip install json-with-comments\n"
        "Or add it to your project's requirements."
    ) from e

from configure import configure_ocr_model


working_dir = Path(__file__).parent.parent.resolve()
install_path = working_dir / Path("install")
version = len(sys.argv) > 1 and sys.argv[1] or "v0.0.1"

# the first parameter is self name
if sys.argv.__len__() < 4:
    print("Usage: python install.py <version> <os> <arch>")
    print("Example: python install.py v1.0.0 win x86_64")
    sys.exit(1)

os_name = sys.argv[2]
arch = sys.argv[3]


def get_dotnet_platform_tag():
    """Detect the current platform and return its .NET platform tag"""
    if os_name == "win" and arch == "x86_64":
        platform_tag = "win-x64"
    elif os_name == "win" and arch == "aarch64":
        platform_tag = "win-arm64"
    elif os_name == "macos" and arch == "x86_64":
        platform_tag = "osx-x64"
    elif os_name == "macos" and arch == "aarch64":
        platform_tag = "osx-arm64"
    elif os_name == "linux" and arch == "x86_64":
        platform_tag = "linux-x64"
    elif os_name == "linux" and arch == "aarch64":
        platform_tag = "linux-arm64"
    else:
        print("Unsupported OS or architecture.")
        print("available parameters:")
        print("version: e.g., v1.0.0")
        print("os: [win, macos, linux, android]")
        print("arch: [aarch64, x86_64]")
        sys.exit(1)

    return platform_tag


def install_deps():
    if not (working_dir / "deps" / "bin").exists():
        print('Please download the MaaFramework to "deps" first.')
        print('Download MaaFramework into "deps" first.')
        sys.exit(1)

    if os_name == "android":
        shutil.copytree(
            working_dir / "deps" / "bin",
            install_path,
            dirs_exist_ok=True,
        )
        shutil.copytree(
            working_dir / "deps" / "share" / "MaaAgentBinary",
            install_path / "MaaAgentBinary",
            dirs_exist_ok=True,
        )
    else:
        shutil.copytree(
            working_dir / "deps" / "bin",
            install_path / "runtimes" / get_dotnet_platform_tag() / "native",
            ignore=shutil.ignore_patterns(
                "*MaaDbgControlUnit*",
                "*MaaThriftControlUnit*",
                "*MaaRpc*",
                "*MaaHttp*",
                "plugins",
                "*.node",
                "*MaaPiCli*",
            ),
            dirs_exist_ok=True,
        )
        shutil.copytree(
            working_dir / "deps" / "share" / "MaaAgentBinary",
            install_path / "libs" / "MaaAgentBinary",
            dirs_exist_ok=True,
        )
        shutil.copytree(
            working_dir / "deps" / "bin" / "plugins",
            install_path / "plugins" / get_dotnet_platform_tag(),
            dirs_exist_ok=True,
        )



def install_resource():

    configure_ocr_model()

    shutil.copytree(
        working_dir / "assets" / "resource",
        install_path / "resource",
        dirs_exist_ok=True,
    )
    shutil.copy2(
        working_dir / "assets" / "interface.json",
        install_path,
    )

    with open(install_path / "interface.json", "r", encoding="utf-8") as f:
        interface = jsonc.load(f)

    interface["version"] = version

    with open(install_path / "interface.json", "w", encoding="utf-8") as f:
        jsonc.dump(interface, f, ensure_ascii=False, indent=4)


def install_chores():
    shutil.copy2(
        working_dir / "README.md",
        install_path,
    )
    shutil.copy2(
        working_dir / "LICENSE",
        install_path,
    )


def install_agent():
    shutil.copytree(
        working_dir / "agent",
        install_path / "agent",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__"),
    )


# Windows builds ship an embedded Python so users need nothing installed.
EMBED_PYTHON = "3.12.10"


def install_python():
    if os_name != "win":
        return  # macOS/Linux use the system python3 (see interface.json agent)

    import subprocess
    import urllib.request
    import zipfile

    embed_arch = "amd64" if arch == "x86_64" else "arm64"
    pip_platform = "win_amd64" if arch == "x86_64" else "win_arm64"
    py_dir = install_path / "python"

    if not (py_dir / "python.exe").exists():
        url = (f"https://www.python.org/ftp/python/{EMBED_PYTHON}/"
               f"python-{EMBED_PYTHON}-embed-{embed_arch}.zip")
        archive = working_dir / "deps" / Path(url).name
        if not archive.exists():
            print(f"Downloading {url}")
            urllib.request.urlretrieve(url, archive)
        with zipfile.ZipFile(archive) as z:
            z.extractall(py_dir)

    # The embedded Python only searches the paths in its ._pth file.
    site_packages = py_dir / "Lib" / "site-packages"
    pth = next(py_dir.glob("python*._pth"))
    lines = pth.read_text(encoding="utf-8").splitlines()
    if "Lib/site-packages" not in lines:
        lines.insert(1, "Lib/site-packages")
        pth.write_text("\n".join(lines) + "\n", encoding="utf-8")

    major_minor = "".join(EMBED_PYTHON.split(".")[:2])
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "--upgrade",
        "--target", str(site_packages),
        "--platform", pip_platform,
        "--python-version", major_minor,
        "--only-binary=:all:",
        "-r", str(working_dir / "agent" / "requirements.txt"),
    ])

    # Point the GUI at the bundled interpreter.
    with open(install_path / "interface.json", "r", encoding="utf-8") as f:
        interface = jsonc.load(f)
    interface["agent"]["child_exec"] = "./python/python.exe"
    with open(install_path / "interface.json", "w", encoding="utf-8") as f:
        jsonc.dump(interface, f, ensure_ascii=False, indent=4)


def install_gui_defaults():
    """MFAAvalonia defaults for a fresh install: English, and stop the run
    when a task fails (Settings > Running > "Whether to continue running
    other tasks after a task fails": later tasks may need what the failed
    one ran out of, e.g. Dawnium). Each file is only written when missing,
    so an existing install keeps its settings."""
    defaults = {
        install_path / "config" / "config.json": {"CurrentLanguage": "en-US"},
        install_path / "config" / "instances" / "default.json": {"ContinueRunningWhenError": False},
    }
    for path, values in defaults.items():
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(values, indent=2), encoding="utf-8")


if __name__ == "__main__":
    install_deps()
    install_resource()
    install_chores()
    install_agent()
    install_python()
    install_gui_defaults()

    print(f"Install to {install_path} successfully.")
