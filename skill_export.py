"""
skill_export — package DocMind's extracted Markdown into an AI-ready skill folder.

Four targets are supported:
  - claude-skill  : Claude Code skill (invoked via `/skill-creator`)
  - chatgpt-gpt   : ChatGPT Custom GPT (knowledge upload)
  - cursor-rules  : Cursor `.cursor/rules/` entry
  - gemini-cli    : Gemini CLI extension (GEMINI.md + optional extension.json)

`build_package` copies the source `.md` files into a target-shaped subfolder
under `output_root` and writes a target-specific `PROMPT.md` the user pastes
into their LLM to finish wiring up the skill. DocMind does not generate the
skill metadata itself — the LLM does — but every reference file is already
pooled in the right place, so the hand-off is one copy-paste.

This module is pure Python. It has no Qt dependency and can be imported and
exercised from the CLI for testing.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path


# ─── Target definitions ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class Target:
    id: str
    display_name: str
    folder_prefix: str   # e.g. "skill-", "gpt-"
    files_subdir: str    # e.g. "references", "knowledge", "docs"
    prompt_template: str


# Prompt templates. Placeholders (Python .format()):
#   {name}           — slug-style or human skill name
#   {description}    — user-provided short description
#   {files_abs_list} — newline-joined bulleted list of absolute file paths
#   {package_root}   — absolute path to the package folder
# Literal curly braces inside a template are doubled ({{ / }}).

_CLAUDE_SKILL_PROMPT = """# Build a Claude Code skill from these reference files

Hey Claude — please use `/skill-creator` to build a new Claude Code skill
using the reference material I've placed in the `references/` subfolder of
this package.

**Skill name:** {name}
**Short description:** {description}

**Reference files (absolute paths — already pooled under `references/`):**

{files_abs_list}

**Package root:** `{package_root}`

Please:

1. Run `/skill-creator` to scaffold the skill interactively, pointing it at
   the reference files above.
2. Produce a `SKILL.md` at the package root (`{package_root}/SKILL.md`) with:
   - YAML frontmatter containing `name`, `description`, and any
     `allowed-tools` you think appropriate.
   - A short preamble describing when the skill should activate.
   - Clear pointers to the reference files in `references/`.
3. Pick natural trigger keywords so the skill auto-invokes when I ask about
   the topic.
4. Leave the `references/` folder intact — it is the skill's knowledge base.

When the skill is ready, I can move the whole folder to
`~/.claude/skills/{name}/` to install it.
"""


_CHATGPT_GPT_PROMPT = """# Build a Custom GPT from these knowledge files

Please help me create a new ChatGPT Custom GPT using the knowledge files in
the `knowledge/` subfolder of this package.

**GPT name:** {name}
**Description:** {description}

**Knowledge files to upload (absolute paths — already pooled under `knowledge/`):**

{files_abs_list}

**Package root:** `{package_root}`

Steps to follow:

1. Go to https://chatgpt.com/gpts/editor and start a new GPT.
2. In the **Configure** tab, set:
   - **Name:** {name}
   - **Description:** {description}
   - **Instructions:** write a 3–4 paragraph system prompt grounded in the
     knowledge files. The GPT should answer primarily from those files, cite
     specific passages when relevant, and acknowledge when a question falls
     outside the uploaded material.
   - **Conversation starters:** suggest 3 natural-language prompts the user
     might ask.
3. In the **Knowledge** section, upload every file listed above.
4. **Capabilities:** turn off Web Browsing and DALL-E unless the material
   warrants them; Code Interpreter is optional.
5. Save and publish (private or shared, your call).
"""


_CURSOR_RULES_PROMPT = """# Build a Cursor rules file from these docs

Please create a Cursor project-rules file that references the docs in the
`docs/` subfolder of this package.

**Rule name:** {name}
**Description:** {description}

**Doc files (absolute paths — already pooled under `docs/`):**

{files_abs_list}

**Package root:** `{package_root}`

Steps:

1. In the target project repo, create `.cursor/rules/{name}.md`.
2. Add YAML frontmatter:

   ```yaml
   ---
   description: {description}
   globs: ["**/*"]
   alwaysApply: false
   ---
   ```

3. In the rule body:
   - A short preamble explaining what the rule covers and when Cursor should
     surface it.
   - A bulleted list pointing to each doc file at its absolute path, with a
     one-line description of what that doc contains.

4. Refine `globs` to match the file types where this rule is most relevant
   (e.g. `["**/*.ts", "**/*.tsx"]` for a TypeScript-focused rule).

5. You can leave the `docs/` folder where it is and reference absolute paths
   from the rules file, or copy the docs into the target repo —  whatever
   fits the team's conventions.
"""


_GEMINI_CLI_PROMPT = """# Build a Gemini CLI extension from these reference files

Please create a Gemini CLI extension (or project memory) from the reference
files in the `references/` subfolder of this package.

**Extension name:** {name}
**Description:** {description}

**Reference files (absolute paths — already pooled under `references/`):**

{files_abs_list}

**Package root:** `{package_root}`

Steps:

1. Create `GEMINI.md` at the package root (`{package_root}/GEMINI.md`). It
   should describe:
   - What knowledge domain this covers.
   - When the extension should activate (trigger conditions / keywords).
   - Pointers to each reference file in `references/`, with a one-line
     description of what's in it.

2. (Optional) Create `gemini-extension.json` at the package root with:

   ```json
   {{
     "name": "{name}",
     "version": "0.1.0",
     "contextFileName": ["GEMINI.md"]
   }}
   ```

3. To install:
   - `cd` into this folder before running `gemini` (project-local memory), or
   - Move the whole folder to `~/.gemini/extensions/{name}/` for a proper
     extension install.
"""


TARGETS: dict[str, Target] = {
    "claude-skill": Target(
        id="claude-skill",
        display_name="Claude Code (skill via /skill-creator)",
        folder_prefix="skill-",
        files_subdir="references",
        prompt_template=_CLAUDE_SKILL_PROMPT,
    ),
    "chatgpt-gpt": Target(
        id="chatgpt-gpt",
        display_name="ChatGPT (Custom GPT)",
        folder_prefix="gpt-",
        files_subdir="knowledge",
        prompt_template=_CHATGPT_GPT_PROMPT,
    ),
    "cursor-rules": Target(
        id="cursor-rules",
        display_name="Cursor (rules)",
        folder_prefix="cursor-",
        files_subdir="docs",
        prompt_template=_CURSOR_RULES_PROMPT,
    ),
    "gemini-cli": Target(
        id="gemini-cli",
        display_name="Gemini CLI (extension)",
        folder_prefix="gemini-",
        files_subdir="references",
        prompt_template=_GEMINI_CLI_PROMPT,
    ),
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

_SLUG_STRIP = re.compile(r"[^\w\s-]")
_SLUG_GAP = re.compile(r"[\s_]+")
_SLUG_DUP = re.compile(r"-+")


def slugify_name(name: str) -> str:
    """Folder-safe slug: lowercase, hyphen-separated, no punctuation."""
    s = name.lower().strip()
    s = _SLUG_STRIP.sub("", s)
    s = _SLUG_GAP.sub("-", s)
    s = _SLUG_DUP.sub("-", s)
    return s.strip("-") or "skill"


# ─── Main entry point ────────────────────────────────────────────────────────

def build_package(
    target_id: str,
    name: str,
    description: str,
    source_files: list[Path],
    output_root: Path,
) -> Path:
    """Create a target-shaped skill package and return its root folder path.

    Raises:
        KeyError: if target_id is not in TARGETS.
        FileNotFoundError: if any source_files entry does not exist.
        ValueError: if source_files is empty.
    """
    if target_id not in TARGETS:
        raise KeyError(
            f"Unknown target {target_id!r}. Known: {sorted(TARGETS)}"
        )
    if not source_files:
        raise ValueError("source_files is empty — nothing to package.")
    for p in source_files:
        if not Path(p).is_file():
            raise FileNotFoundError(f"Source file missing: {p}")

    target = TARGETS[target_id]
    slug = slugify_name(name)
    package_root = Path(output_root) / f"{target.folder_prefix}{slug}"

    # Clean slate — remove prior export to the same target for the same name.
    if package_root.exists():
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True)

    files_dir = package_root / target.files_subdir
    files_dir.mkdir()

    copied_abs_paths: list[str] = []
    for src in source_files:
        dest = files_dir / Path(src).name
        shutil.copy2(src, dest)
        copied_abs_paths.append(str(dest.resolve()))

    files_list_str = "\n".join(f"- `{p}`" for p in copied_abs_paths)

    prompt = target.prompt_template.format(
        name=name,
        description=description,
        files_abs_list=files_list_str,
        package_root=str(package_root.resolve()),
    )
    (package_root / "PROMPT.md").write_text(prompt, encoding="utf-8")

    return package_root


# ─── CLI smoke test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Quick smoke: list targets, optionally build a package.
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="skill_export packager")
    ap.add_argument("--list", action="store_true", help="List target IDs and exit.")
    ap.add_argument("--target", choices=sorted(TARGETS), help="Target to build.")
    ap.add_argument("--name", help="Skill/GPT/rule name.")
    ap.add_argument("--description", default="", help="Short description.")
    ap.add_argument("--out", type=Path, help="Output root folder.")
    ap.add_argument("sources", type=Path, nargs="*", help="Source .md files.")
    args = ap.parse_args()

    if args.list or not args.target:
        for t in TARGETS.values():
            print(f"  {t.id:<16} {t.display_name}")
        sys.exit(0)

    pkg = build_package(
        target_id=args.target,
        name=args.name or "untitled",
        description=args.description,
        source_files=args.sources,
        output_root=args.out or Path.cwd(),
    )
    print(f"✓ Package written to: {pkg}")
