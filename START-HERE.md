# 👋 START HERE — Read this first

Hey. You have a folder called **DocMind**. Inside it are some files.
Don't panic. You only need to touch **two** of them yourself. The rest
run automatically.

This guide has two parts:

- **Part 1:** Install DocMind on your Mac and test it (15 minutes)
- **Part 2:** Put DocMind on GitHub so other people can download it (15 minutes)

Follow them in order. Part 2 assumes Part 1 worked.

---

# 📂 What's in this folder?

When you downloaded the project, you got one folder called `DocMind`
with this inside:

```
DocMind/
├── START-HERE.md          ← You are reading this
├── README.md              ← What visitors see on GitHub
├── LICENSE                ← Legal stuff, ignore
├── .gitignore             ← Technical stuff, ignore
│
├── install.sh             ← You'll run this in Part 1 ⭐
├── DocMind.py             ← The app itself (don't touch)
├── extract_v4.py          ← The engine (don't touch)
├── build_app.py           ← Builds the .app file (don't touch)
├── make_icon.py           ← Draws the icon (don't touch)
│
└── docs/
    ├── DEVELOPERS.md      ← For developers who want to tinker
    ├── PUBLISHING.md      ← Detailed GitHub guide (bookmark it)
    ├── screenshot.png     ← Hero image for README
    ├── drop.png           ← Small preview
    ├── running.png        ← Small preview
    └── done.png           ← Small preview
```

**The only file you'll ever run yourself is `install.sh`.**
Everything else is run BY the install script, or loaded BY the app.

---

# 🔧 PART 1 — Install DocMind on your Mac

## What you need before you start

- A Mac
- About 15 minutes
- Your Mac password (for installing things)

Don't worry if you've never used Terminal. I'll explain every step.

## Step 1: Put the DocMind folder somewhere findable

Right now the `DocMind` folder is probably in your Downloads. Move it
somewhere you'll remember. I suggest:

**Finder → your Documents folder → drag the DocMind folder there.**

So now you've got `~/Documents/DocMind/` (the `~` means "your home").

## Step 2: Open Terminal

Terminal is a built-in Mac app. Two ways to open it:

- Press **⌘ + Space** to open Spotlight search, type **"Terminal"**, press Enter
- OR open Finder → Applications → Utilities → Terminal

A black-and-white window opens. It looks scary but it's just a text
interface for your Mac.

## Step 3: Tell Terminal to go to the DocMind folder

Type exactly this — including the space at the end — but **don't press Enter yet**:

```
cd 
```

Now **drag the DocMind folder from Finder into the Terminal window**.
Terminal will fill in the full path for you automatically.

Now press Enter.

You just told Terminal "go into the DocMind folder."

## Step 4: Run the installer

Type exactly this and press Enter:

```
./install.sh
```

The installer will:

1. Ask for your Mac password (type it — you won't see the characters, that's normal — then press Enter)
2. Install some tools it needs (takes a few minutes)
3. Build the DocMind app
4. Put it in your Applications folder

When it's done you'll see:

```
╔════════════════════════════════════════╗
║            ✓  Done!                    ║
╚════════════════════════════════════════╝
```

**If it says "Done!", you're finished with installation.** Go to Step 5.

**If it crashed with a red error message,** the most common cause is
Homebrew failing to install. Scroll up in Terminal, find the error,
paste it into Google — the fix is usually one command you run and then
try `./install.sh` again.

## Step 5: Launch DocMind for the first time

1. Open Finder → Applications folder
2. Find **DocMind** in the list
3. **Right-click** it → choose **Open** from the menu
4. A warning appears: "DocMind can't be opened because it is from an unidentified developer"
5. Click **Open** anyway

⚠️ **You MUST right-click the first time.** If you just double-click,
macOS blocks it. After this first time, you can double-click it like a
normal app forever.

## Step 6: Test it

1. DocMind opens. You see the dark window with a drop zone.
2. Grab any folder that has a few PDFs in it. Drag it onto the drop zone.
3. Click **Extract**.
4. Watch the progress.
5. Click **Show in Finder** when it finishes.

If you see clean text files in the `extracted` folder, **it works**.
You're done with Part 1.

---

# 🌐 PART 2 — Put DocMind on GitHub

Now that DocMind works on your Mac, let's get it online so other people
can download it.

## What you need before you start

- A GitHub account (free — sign up at [github.com](https://github.com) if you don't have one)
- The same DocMind folder you installed from in Part 1
- About 15 minutes

## Step 1: Create a GitHub repo (or reset your existing one)

### If you want to keep your current repo URL:

1. Go to your existing repo on GitHub
2. Click **Settings** (tab at the top)
3. Scroll all the way down to the red **Danger Zone**
4. Click **Delete this repository** and confirm
5. Click **+** icon (top right of GitHub) → **New repository**
6. Name it `docmind` (lowercase)
7. Make sure it's **Public**
8. **Don't check any boxes** (no README, no license, no gitignore — we have our own)
9. Click **Create repository**

### If you'd rather make a brand new one as a backup:

1. Click **+** top right → **New repository**
2. Name it `docmind`
3. **Public**
4. **No** README, license, or gitignore
5. Click **Create repository**

Either way, you'll land on a page with setup instructions. **Leave that
page open** — we need one line from it.

## Step 2: Connect your Mac to GitHub (one-time setup)

If you've never pushed anything to GitHub from this Mac before, you
need to set up a Personal Access Token. This is how GitHub lets you
upload files from Terminal. (GitHub stopped accepting passwords for
this in 2021.)

1. On GitHub, click your profile picture (top right) → **Settings**
2. Scroll way down the left sidebar → **Developer settings** (very bottom)
3. Click **Personal access tokens** → **Tokens (classic)**
4. Click **Generate new token (classic)**
5. Give it a name like "My Mac"
6. Expiration: **No expiration** (or whatever you prefer)
7. Check the box next to **repo** (gives it permission to upload to your repos)
8. Scroll down, click **Generate token**
9. **Copy the token that appears.** It looks like `ghp_xxxxxxxxxxxx...`
10. **Save it somewhere safe** (like Notes app). You can't see it again after you close the page.

## Step 3: Upload DocMind to your repo

Back to Terminal. If you closed it, reopen it and `cd` into the
DocMind folder again (same as Part 1, Step 3).

Now copy and paste each command below, one at a time, pressing Enter
after each.

**Command 1 — start tracking this folder with git:**
```
git init
```

**Command 2 — set the main branch name:**
```
git branch -M main
```

**Command 3 — tell git to include all the files:**
```
git add .
```

**Command 4 — save a snapshot (this is called a "commit"):**
```
git commit -m "Initial release of DocMind"
```

**Command 5 — connect to your GitHub repo.** Get this exact command
from the GitHub page you left open in Step 1. It looks like this but
with YOUR username:
```
git remote add origin https://github.com/YOUR-USERNAME/docmind.git
```

**Command 6 — upload everything:**
```
git push -u origin main
```

Terminal will ask:

- **Username:** type your GitHub username, press Enter
- **Password:** paste your Personal Access Token from Step 2 (not your real password!), press Enter

**Wait a few seconds.** If it succeeds, you'll see lines ending with
something like `Branch 'main' set up to track...`.

## Step 4: Check that it worked

Go to `https://github.com/YOUR-USERNAME/docmind` in your browser.
Refresh the page. You should now see all the DocMind files there.

The README you wrote will auto-display below the file list.

## Step 5: Polish your repo page

Small things that make a big difference:

1. On your repo page, next to **About** on the right, click the **⚙**
   gear icon
2. Add a **description:** "Turn your PDF collection into clean text your AI can actually read. Mac app."
3. In **Topics**, type these one at a time: `macos`, `pdf`, `ocr`,
   `llm`, `ai-tools`, `rag`
4. Click **Save changes**

## Step 6: Make it easy for non-coders to install DocMind

Right now, someone who wants to use DocMind has to download your repo,
open Terminal, and run your installer. That filters out most people.

**The fix:** upload the pre-built `DocMind.app` so they can just
download and double-click.

1. On your Mac, open Finder → Applications
2. Right-click **DocMind** → **Compress "DocMind"**
3. You now have `DocMind.app.zip` in Applications
4. Drag that ZIP to your Desktop
5. Back on GitHub, on your repo page, click **Releases** (right sidebar) → **Create a new release**
6. **Choose a tag:** type `v1.0.0` and click "Create new tag"
7. **Release title:** `DocMind 1.0`
8. **Description:** write something like "First public release. Drag a folder of PDFs, get clean text for your AI."
9. **Drag `DocMind.app.zip` from your Desktop into the attachments area** at the bottom
10. Click **Publish release**

Now when someone visits your repo, they can click **Releases** and
download a working app with one click. No Terminal needed.

---

# 🎉 You're done

Your app is on GitHub. Anyone can find it, read the README, download
the release, and use DocMind in 2 minutes.

## Updating DocMind later

When you change something and want to push the update to GitHub:

```
cd ~/Documents/DocMind
git add .
git commit -m "describe what you changed"
git push
```

That's it. The first upload was the complicated one. Updates are three
lines.

---

# Help — something went wrong

**"git: command not found"**
Run this in Terminal: `xcode-select --install`. Apple will pop up a
dialog asking to install developer tools. Click Install. Wait. Retry.

**"Permission denied (publickey)"**
You're using SSH but haven't set up keys. Easy fix — switch to HTTPS:
```
git remote set-url origin https://github.com/YOUR-USERNAME/docmind.git
```
Then retry `git push`.

**"fatal: refusing to merge unrelated histories"**
Your GitHub repo already has a README or something on it. Fix:
```
git pull origin main --allow-unrelated-histories
git push
```

**The installer crashed.**
Scroll up in Terminal to find the red error message. Copy-paste the
error into Google or ChatGPT. Most installer problems are fixed by
running one command Apple suggests.

**DocMind opens but the drop zone doesn't accept my folder.**
Make sure you're dragging a **folder**, not individual PDF files.
The folder should contain at least one `.pdf` file.

**DocMind extracts but the text looks garbled.**
Check the "Force OCR on every page" box at the bottom of the window
and try again. That re-reads every page visually instead of trusting
the PDF's built-in text layer.

---

# More detail if you want it

- For developers who want to understand how DocMind works → `docs/DEVELOPERS.md`
- For a more detailed publishing guide with troubleshooting → `docs/PUBLISHING.md`
- The README that shows up on GitHub itself → `README.md`
