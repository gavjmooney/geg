import argparse
import glob
import os
import re
import shutil
import subprocess
import sys


PYPROJECT_PATH = os.path.join(os.path.dirname(__file__), "pyproject.toml")


def read_pyproject() -> str:
    with open(PYPROJECT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def write_pyproject(content: str) -> None:
    with open(PYPROJECT_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def bump_version(text: str, part: str = "patch") -> tuple[str, str]:
    """
    Increment version in [project] section. Supports semantic x.y.z only.
    Returns (new_text, new_version).
    """
    pattern = re.compile(r"^(version\s*=\s*\")([0-9]+)\.([0-9]+)\.([0-9]+)(\")",
                         re.MULTILINE)

    def repl(m: re.Match[str]) -> str:
        major, minor, patch = int(m.group(2)), int(m.group(3)), int(m.group(4))
        if part == "major":
            major, minor, patch = major + 1, 0, 0
        elif part == "minor":
            minor, patch = minor + 1, 0
        else:
            patch += 1
        return f"{m.group(1)}{major}.{minor}.{patch}{m.group(5)}"

    new_text, n = pattern.subn(repl, text, count=1)
    if n == 0:
        raise RuntimeError("Could not find version = \"x.y.z\" in pyproject.toml")

    m2 = pattern.search(new_text)
    # We just replaced; extract via second pattern for safety
    ver_search = re.search(r"^version\s*=\s*\"([0-9]+\.[0-9]+\.[0-9]+)\"",
                           new_text, re.MULTILINE)
    new_version = ver_search.group(1) if ver_search else "unknown"
    return new_text, new_version


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.check_call(cmd)


def clean() -> None:
    for d in ("dist", "build"):
        if os.path.isdir(d):
            shutil.rmtree(d)
    for path in glob.glob("*.egg-info"):
        shutil.rmtree(path, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and upload package with version bump")
    parser.add_argument("--repo", choices=["pypi", "testpypi"], default="pypi",
                        help="Repository to upload to (default: pypi)")
    parser.add_argument("--part", choices=["patch", "minor", "major"], default="patch",
                        help="Which part of version to bump (default: patch)")
    parser.add_argument("--no-upload", action="store_true",
                        help="Only build, do not upload")
    args = parser.parse_args()

    # 1) Bump version
    content = read_pyproject()
    new_content, new_version = bump_version(content, part=args.part)
    write_pyproject(new_content)
    print(f"Bumped version to {new_version}")

    # 2) Clean old artifacts
    clean()

    # 3) Build
    run([sys.executable, "-m", "build"]) 
    run([sys.executable, "-m", "twine", "check", "dist/*"]) 

    if args.no_upload:
        print("Build complete. Skipping upload.")
        return

    # 4) Upload
    upload_cmd = [sys.executable, "-m", "twine", "upload"]
    if args.repo == "testpypi":
        upload_cmd += ["--repository", "testpypi"]
    # If credentials are present in environment, pass them explicitly to avoid prompts
    tw_user = os.environ.get("TWINE_USERNAME")
    tw_pass = os.environ.get("TWINE_PASSWORD")
    if tw_user and tw_pass:
        upload_cmd += ["--username", tw_user, "--password", tw_pass]
    upload_cmd += ["dist/*"]
    run(upload_cmd)


if __name__ == "__main__":
    main()


