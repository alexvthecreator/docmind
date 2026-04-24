#!/usr/bin/env python3
"""
bundle_binaries.py — Make DocMind.app self-contained for drag-to-Applications.

Run AFTER `python3 build_app.py py2app` has produced `dist/DocMind.app`.

What this does:
  1. Copy the host tesseract binary into `.app/Contents/Resources/bin/`.
  2. Copy the host tessdata/ (language packs) into `.app/Contents/Resources/tessdata/`.
  3. Use `dylibbundler` to walk tesseract's dylib chain, copy every non-system
     library into `.app/Contents/Frameworks/`, and rewrite install names so
     the binary loads them from inside the app bundle via @executable_path.
  4. Verify the bundled tesseract runs with `tesseract --version`.

After this, DocMind.app is portable: it does not need Homebrew-installed
tesseract/leptonica on the end-user's Mac.

REQUIREMENTS (on the build machine):
    brew install tesseract leptonica dylibbundler

USAGE:
    python3 bundle_binaries.py
    # or from CI:
    python3 bundle_binaries.py --app dist/DocMind.app
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def find_tool(name: str) -> Path | None:
    r = subprocess.run(["which", name], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        return Path(r.stdout.strip())
    return None


def find_tessdata() -> Path | None:
    """Locate the tessdata/ directory from the host Tesseract install."""
    # 1. TESSDATA_PREFIX env (overrides everything)
    env = os.environ.get("TESSDATA_PREFIX")
    if env and Path(env).is_dir():
        return Path(env)
    # 2. Standard Homebrew locations (arm64, then Intel)
    for candidate in (
        "/opt/homebrew/share/tessdata",
        "/usr/local/share/tessdata",
    ):
        if Path(candidate).is_dir():
            return Path(candidate)
    # 3. Derive from `brew --prefix tesseract`
    r = subprocess.run(
        ["brew", "--prefix", "tesseract"], capture_output=True, text=True
    )
    if r.returncode == 0:
        candidate = Path(r.stdout.strip()) / "share" / "tessdata"
        if candidate.is_dir():
            return candidate
    return None


def bundle(app: Path) -> int:
    if not app.is_dir():
        print(f"ERROR: {app} does not exist or is not a directory.",
              file=sys.stderr)
        print("Run `python3 build_app.py py2app` first.", file=sys.stderr)
        return 2

    tesseract = find_tool("tesseract")
    if not tesseract:
        print("ERROR: tesseract not on PATH. "
              "`brew install tesseract` first.", file=sys.stderr)
        return 2

    dylibbundler = find_tool("dylibbundler")
    if not dylibbundler:
        print("ERROR: dylibbundler not on PATH. "
              "`brew install dylibbundler` first.", file=sys.stderr)
        return 2

    tessdata = find_tessdata()
    if tessdata is None:
        print("ERROR: tessdata/ not found — is tesseract fully installed?",
              file=sys.stderr)
        return 2

    contents = app / "Contents"
    resources = contents / "Resources"
    frameworks = contents / "Frameworks"
    bin_dir = resources / "bin"
    tessdata_dest = resources / "tessdata"

    bin_dir.mkdir(parents=True, exist_ok=True)
    frameworks.mkdir(parents=True, exist_ok=True)

    # ── 1. Copy tesseract ───────────────────────────────────────────────
    dest_tesseract = bin_dir / "tesseract"
    shutil.copy2(tesseract, dest_tesseract)
    os.chmod(dest_tesseract, 0o755)
    print(f"Copied tesseract → {dest_tesseract.relative_to(app)}")

    # ── 2. Copy tessdata ────────────────────────────────────────────────
    if tessdata_dest.exists():
        shutil.rmtree(tessdata_dest)
    shutil.copytree(tessdata, tessdata_dest, symlinks=False)
    # Drop any unnecessarily large non-English language packs that may
    # have been installed alongside; if the user explicitly wants them,
    # they can set TESSDATA_KEEP_ALL=1 and we leave the tree untouched.
    if os.environ.get("TESSDATA_KEEP_ALL") != "1":
        kept = {"eng.traineddata", "osd.traineddata"}
        for entry in tessdata_dest.iterdir():
            if entry.is_file() and entry.name not in kept:
                entry.unlink()
    n_data = sum(1 for _ in tessdata_dest.iterdir())
    print(f"Copied tessdata  → {tessdata_dest.relative_to(app)} "
          f"({n_data} language file(s))")

    # ── 3. Bundle dylib chain via dylibbundler ──────────────────────────
    # Prefix resolves at runtime to `.app/Contents/Frameworks/` because
    # tesseract lives at `.app/Contents/Resources/bin/tesseract` and
    # macOS sets @executable_path to the directory of the running binary.
    prefix = "@executable_path/../../Frameworks/"
    print("Running dylibbundler…")
    cmd = [
        str(dylibbundler),
        "-of",                    # overwrite existing dylibs
        "-b",                     # bundle deps
        "-cd",                    # create dest dir if missing
        "-x", str(dest_tesseract),
        "-d", str(frameworks),
        "-p", prefix,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("ERROR: dylibbundler failed.", file=sys.stderr)
        sys.stderr.write(r.stdout)
        sys.stderr.write(r.stderr)
        return 1
    # Print only the summary lines for readability
    for line in r.stdout.splitlines():
        if line.strip():
            print(f"  {line}")

    # ── 4. Verify ───────────────────────────────────────────────────────
    print("Verifying bundled tesseract…")
    verify_env = os.environ.copy()
    verify_env["TESSDATA_PREFIX"] = str(tessdata_dest)
    r = subprocess.run(
        [str(dest_tesseract), "--version"],
        capture_output=True, text=True, env=verify_env,
    )
    if r.returncode != 0:
        print("ERROR: bundled tesseract failed to execute.", file=sys.stderr)
        sys.stderr.write(r.stdout)
        sys.stderr.write(r.stderr)
        return 1
    first_line = (r.stdout + r.stderr).splitlines()[0] if (r.stdout + r.stderr) else "(no output)"
    print(f"  OK: {first_line}")

    # Quick OCR sanity: make sure a synthetic image can be read
    print("Verifying OCR end-to-end on a synthetic image…")
    try:
        from PIL import Image, ImageDraw  # available on the build machine
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            img_path = Path(td) / "probe.png"
            img = Image.new("RGB", (300, 80), color="white")
            ImageDraw.Draw(img).text((20, 25), "Hello world", fill="black")
            img.save(img_path)
            r = subprocess.run(
                [str(dest_tesseract), str(img_path), "stdout"],
                capture_output=True, text=True, env=verify_env,
            )
            if r.returncode != 0:
                print("ERROR: bundled tesseract OCR probe failed.",
                      file=sys.stderr)
                sys.stderr.write(r.stderr)
                return 1
            if "hello" not in r.stdout.lower() and "world" not in r.stdout.lower():
                print(f"ERROR: OCR probe returned unexpected output: {r.stdout!r}",
                      file=sys.stderr)
                return 1
            print(f"  OK — OCR returned: {r.stdout.strip()!r}")
    except ImportError:
        print("  (Skipped — PIL not importable in this environment.)")

    print(f"\n✓ Binary bundling complete for {app.name}")
    print(f"  .app size: {du_human(app)}")
    return 0


def du_human(path: Path) -> str:
    """Human-readable disk usage for a directory."""
    r = subprocess.run(["du", "-sh", str(path)],
                       capture_output=True, text=True)
    return r.stdout.split()[0] if r.returncode == 0 else "?"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", type=Path,
                    default=Path(__file__).resolve().parent / "dist" / "DocMind.app",
                    help="Path to the built .app bundle "
                         "(default: ./dist/DocMind.app)")
    args = ap.parse_args()
    return bundle(args.app.resolve())


if __name__ == "__main__":
    sys.exit(main())
