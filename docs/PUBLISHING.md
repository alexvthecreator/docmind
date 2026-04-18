# How to put DocMind on GitHub (step-by-step)

You said you already have a repo but want to start fresh. Here's how to
do that cleanly from your Mac, start to finish.

This guide assumes zero prior command-line knowledge. If something
already makes sense to you, skip ahead.

---

## Step 1 — Start fresh on GitHub

Since you already have a repo, there are two ways to "start fresh."
Pick the one that fits.

### Option A: Wipe the existing repo (keep the URL)

Use this if you want `github.com/yourname/docmind` to stay the same
link.

1. Go to your existing repo on GitHub in your browser.
2. Click **Settings** (top right tabs).
3. Scroll all the way to the bottom to the red **Danger Zone**.
4. Click **Delete this repository**.
5. Type the repo name to confirm.
6. Now make a new one: click the **+** in the top right of GitHub →
   **New repository**.
7. Use the same name (`docmind`), description, public or private, no
   README (leave everything unchecked — we'll push our own).
8. Click **Create repository**.

### Option B: Make a second repo (safer, keeps a backup)

1. Click **+** top right → **New repository**.
2. Name it something new, e.g. `docmind-v2` or `docmind-public`.
3. No README, no .gitignore, no license (we'll push our own).
4. Click **Create repository**.

Either way, you'll land on a page titled something like:
"Quick setup — if you've done this kind of thing before."
**Keep this page open.** We'll need one line from it in Step 4.

---

## Step 2 — Get the DocMind files on your Mac

1. Download the DocMind project folder from wherever you have it.
2. Put it somewhere sensible, like `~/Documents/Coding Projects/docmind`.

Your folder should look like this:

```
docmind/
├── DocMind.py
├── extract_v4.py
├── build_app.py
├── make_icon.py
├── install.sh
├── README.md
├── LICENSE
├── .gitignore
└── docs/
    ├── DEVELOPERS.md
    ├── PUBLISHING.md
    └── (screenshots go here — see Step 3)
```

---

## Step 3 — Add screenshots (important for the README)

Non-technical visitors skim. A good screenshot sells the project
faster than any paragraph. The README references four images:

- `docs/screenshot.png` — the main hero shot (app in use)
- `docs/drop.png` — drop-zone close-up
- `docs/running.png` — progress view close-up
- `docs/done.png` — finished state

**To take them:**

1. Launch DocMind (right-click → Open the first time, as explained in
   the README).
2. Press **⌘ + Shift + 4** then tap **Space** and click the DocMind
   window to screenshot just that window.
3. The image saves to your Desktop.
4. Rename it and drag it into the `docmind/docs/` folder.
5. Repeat for each state.

If you don't have screenshots yet, delete the `![...](docs/screenshot.png)`
lines in the README for now — you can add them later.

---

## Step 4 — Push it to GitHub

Now the terminal part. Open **Terminal** (Applications → Utilities or
Spotlight search "Terminal").

1. **Go to your DocMind folder.** Type `cd ` (with a space), drag the
   docmind folder into the Terminal window, press Enter.

2. **Initialize git** (one-time setup for this folder):
   ```bash
   git init
   git branch -M main
   ```

3. **Add all the files:**
   ```bash
   git add .
   ```

4. **Save this as the first commit:**
   ```bash
   git commit -m "Initial commit — DocMind v1"
   ```

5. **Connect your local folder to the GitHub repo.** Go back to that
   GitHub page you left open from Step 1. Copy the command that looks
   like:
   ```bash
   git remote add origin https://github.com/YOUR-USERNAME/docmind.git
   ```
   Paste it into Terminal and press Enter.

6. **Push everything up:**
   ```bash
   git push -u origin main
   ```

   If it asks for your GitHub username and password, note that GitHub
   doesn't accept passwords anymore — you need a **Personal Access
   Token** instead. To create one: go to GitHub → click your profile
   picture → **Settings** → **Developer settings** (very bottom left) →
   **Personal access tokens** → **Tokens (classic)** → **Generate new
   token (classic)**. Check the `repo` box, generate, copy the token,
   and paste it as the password when Terminal asks. Save the token
   somewhere safe — you won't see it again.

That's it. Refresh your GitHub page — everything is there.

---

## Step 5 — Make it look good on GitHub

Now the repo exists. A few polish steps that matter:

### Set the repo description and topics

On your GitHub repo page, click the **⚙** (gear icon) next to
"About" in the right sidebar.

- **Description:** "Turn your PDF collection into clean text your AI
  can actually read. Mac app."
- **Website:** leave blank or link to a demo video / your site
- **Topics:** `macos`, `ocr`, `pdf`, `pdf-extraction`, `llm`,
  `ai-tools`, `text-extraction`, `rag`, `python`, `pyside6`

Topics help people find your project through GitHub search.

### Pin it to your profile

On your GitHub profile page (top right → Your profile), scroll down
to "Popular repositories" → **Customize your pins** → select DocMind.
Now it shows up for anyone who visits your profile.

### Add releases (optional but nice)

When DocMind is working well, create a release:

1. On the repo page, click **Releases** (right sidebar) → **Create
   a new release**.
2. Tag: `v1.0.0`
3. Title: `DocMind v1.0`
4. Description: a short changelog (what's in this version).
5. Attach the actual `DocMind.app` as a ZIP so non-technical users
   can download the ready-made app without building it themselves.
   To make the ZIP: right-click `dist/DocMind.app` → Compress.
6. Publish release.

This is what lets non-developers download a working app with one
click.

---

## Updating the repo later

When you change something and want to push the update:

```bash
cd ~/Documents/Coding\ Projects/docmind
git add .
git commit -m "describe what changed"
git push
```

That's the whole loop.

---

## Troubleshooting

**"git: command not found"** — Xcode Command Line Tools aren't
installed. Run `xcode-select --install` and follow the prompts.

**"Permission denied (publickey)"** — You're using SSH, but haven't
set up an SSH key. Easiest fix: use HTTPS instead. In Terminal:
```bash
git remote set-url origin https://github.com/YOUR-USERNAME/docmind.git
```
Then `git push` again and it'll ask for username + personal access
token.

**"fatal: refusing to merge unrelated histories"** — This happens if
the repo already had a README from GitHub's side. Fix:
```bash
git pull origin main --allow-unrelated-histories
git push
```

**"failed to push some refs"** — Someone (probably you) made a change
on GitHub's side that you don't have locally. Fix:
```bash
git pull origin main
git push
```

---

## Done

Your repo is live. Share the link anywhere — Twitter, Reddit, Hacker
News, your email signature, Discord communities. Anyone with a Mac can
download it and have a working app in 5 minutes.
