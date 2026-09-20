# Archivary — User Manual

A complete guide to every screen, option and workflow in Archivary.

**Contents**

1. [What is Archivary?](#1-what-is-archivary)
2. [Installing and launching](#2-installing-and-launching)
3. [The workspace](#3-the-workspace)
4. [Setting up an account](#4-setting-up-an-account)
5. [Settings reference](#5-settings-reference)
6. [Uploading](#6-uploading)
7. [Downloading](#7-downloading)
8. [Searching](#8-searching)
9. [Editing metadata](#9-editing-metadata)
10. [Listing and deleting files](#10-listing-and-deleting-files)
11. [Tasks (derive and processing)](#11-tasks-derive-and-processing)
12. [The Transfers panel](#12-the-transfers-panel)
13. [The Console](#13-the-console)
14. [Menus and keyboard shortcuts](#14-menus-and-keyboard-shortcuts)
15. [Recipes and common workflows](#15-recipes-and-common-workflows)
16. [How upload options work](#16-how-upload-options-work)
17. [Troubleshooting and error messages](#17-troubleshooting-and-error-messages)
18. [Glossary](#18-glossary)
19. [Files, storage and privacy](#19-files-storage-and-privacy)
20. [FAQ](#20-faq)

---

## 1. What is Archivary?

Archivary is a desktop application for the [Internet Archive](https://archive.org).
It lets you upload items, download files, search the archive, edit item metadata,
list and delete files, and watch processing tasks — all without using the `ia`
command line.

It is built on the official `internetarchive` Python library, so anything you do
in Archivary is exactly what the command line tool would do.

Useful vocabulary:

- **Item** — a page on archive.org, identified by a permanent **identifier**
  (e.g. `nasa`). An item holds files plus metadata.
- **File** — a single object inside an item (a video, image, XML, …).
- **Collection** — a grouping of items (e.g. `opensource`, `community_video`).
- **IAS3 keys** — the access/secret key pair that authorises uploads, edits and
  deletes. Downloads of public items normally need no account.
- **Derive** — automatic processing the Internet Archive runs after an upload to
  create derivatives (thumbnails, streaming formats, OCR text, …).

---

## 2. Installing and launching

### Requirements

- Python 3.11 or newer
- The packages listed in `requirements.txt` (installed for you below)

### Install

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

On Linux/macOS use `.venv/bin/python` in place of `.venv\Scripts\python.exe`.

### Launch

```powershell
.\.venv\Scripts\python.exe run.py
```

or double-click the generated `Archivary.bat` / desktop shortcut. The shortcut
uses `pythonw.exe`, so no console window appears.

---

## 3. The workspace

Archivary has three areas:

- **Left sidebar** — the feature tabs:
  **Upload · Download · Search · Metadata · List & Delete · Tasks · Settings**.
  The account currently in use is shown at the bottom.
- **Main area** — the selected tab.
- **Bottom panel** — two tabs side by side:
  - **Transfers** — every upload/download/edit job and its progress.
  - **Console** — the raw log, for troubleshooting.

### Resizing the bottom panel

Drag the horizontal divider between the main area and the bottom panel. The panel
remembers its height between launches. Press `Ctrl+J` to hide or show it, `Ctrl+1`
to jump to Transfers, and `Ctrl+2` to jump to the Console.

### Theme

Archivary follows your operating system's light/dark setting by default. Change it
under **View → Theme** or in **Settings → Preferences**.

---

## 4. Setting up an account

You only need an account to **upload, edit, delete and view your own tasks**.
Downloading public items and searching work without signing in.

### Option A — paste IAS3 keys (recommended)

1. Open <https://archive.org/account/s3.php> and copy your **access key** and
   **secret key**.
2. Go to **Settings → Account**.
3. Fill in **Access key** and **Secret key** (tick **Show secret key** to check
   for typos).
4. Optionally add a **Profile name** (e.g. `personal`) and your **Email**.
5. Click **Save profile**, then **Test connection**.

### Option B — sign in with email and password

1. In **Settings → Sign in with email and password**, enter your archive.org
   **Email** and **Password**.
2. Click **Fetch keys**. Archivary exchanges them for IAS3 keys and fills in the
   fields above. Your password is never stored.
3. Give the profile a name, then **Save profile**.

### Multiple accounts

Every saved profile is listed in the **Saved profiles** dropdown. Use
**Set active** to switch accounts — all uploads and edits then use that account.
Secrets are stored in the operating system keychain; if no keychain is available,
Archivary falls back to an encrypted file and tells you so in Settings.

**Test connection** contacts archive.org and confirms your keys work.

---

## 5. Settings reference

### Account

| Control | Meaning |
| --- | --- |
| **Saved profiles** | Choose which account to view/edit. |
| **Set active** | Make the chosen profile the one used for uploads and edits. |
| **Profile name** | A label for this account (any text). |
| **Email (optional)** | For your reference only. |
| **Access key / Secret key** | Your IAS3 credentials. |
| **Show secret key** | Reveals the secret so you can verify it. |
| **Save profile** | Store the profile and its keys. |
| **Test connection** | Verify the credentials against archive.org. |
| **Delete profile** | Remove the profile and its stored keys (uploads are untouched). |

The line at the bottom shows where credentials are stored
(e.g. `keyring (WinVaultKeyring)` or `encrypted file`).

### Preferences

| Setting | Effect |
| --- | --- |
| **Theme** | `system` (follow OS), `dark`, or `light`. Applies immediately. |
| **Concurrent jobs** | How many transfers run at the same time. Applies immediately. |
| **Default download folder** | Where the Download tab saves files. |
| **Verify checksums after download** | Default for the Download tab's verify switch. |
| **Count downloads as a view by default** | Default for the Download tab's view switch. |
| **Skip uploads whose checksums already match** | Default for the Upload tab's checksum-skip switch. |
| **Delete local file after successful upload** | Default for the Upload tab's delete switch. |
| **Queue derive tasks after upload** | Default for the Upload tab's derive switch. |
| **Raw HTTP logging in the console** | Raises third-party HTTP loggers to DEBUG for deep troubleshooting. |

The checkboxes here seed the matching options in the Upload and Download tabs when
the app starts; each job can still override them with its own switches.

---

## 6. Uploading

Uploading creates a new item, or **adds files to an existing item** if the
identifier already exists and belongs to you.

### The form

| Field | Notes |
| --- | --- |
| **Identifier** | Permanent, unique id for the item. Letters, digits, dashes and underscores. |
| **Title** | The item's display title. |
| **Creator** | Person or organisation. |
| **Collection** | One or more collections, comma-separated (e.g. `opensource, community_video`). Leave blank to use the default open collection. |
| **Media type** | e.g. `movies`, `audio`, `texts`, `image`, `software`, `data`, `web`. |
| **Subject tags** | Comma-separated keywords. |
| **License URL** | e.g. a Creative Commons URL. |
| **Description** | Free text. |
| **Custom metadata** | Any extra `key → value` pairs. Add the same key twice to create a multi-value field. |

### Files

- **Drag and drop** files or folders onto the list, or use **Add files…** /
  **Add folder…**.
- **Remove selected** / **Clear** manage the list.
- **Flatten folders** — off by default, which means dropping a folder preserves
  its directory names in the item (e.g. `tapes/a.mp4`). Turn it on to place every
  file at the top level of the item.

### Upload options

| Option | What it does |
| --- | --- |
| **Queue derive task after upload** | Ask the Internet Archive to run its derive pipeline when the upload finishes. |
| **Skip unchanged files (checksum)** | Before uploading each file, compare its MD5 with the copy already in the item; skip identical files. This is also how you **resume an interrupted upload**. |
| **Verify uploads with Content-MD5** | Send the file's checksum so the server rejects a corrupted transfer. |
| **Delete local files after successful upload** | Remove your local copy only after the upload is verified. |
| **Keep old version (do not overwrite)** | If a file with the same name exists, keep the old one as a previous version instead of replacing it. |
| **Validate identifier before uploading** | Ask the server to reject invalid identifiers before sending data. |
| **Retries on overload** | How many times to retry when S3 reports it is overloaded (503). |

### Starting the upload

Click **Start upload**. A job appears in the **Transfers** panel with live speed,
ETA and per-file progress. You can keep using the rest of the app, queue more
jobs, or pause/cancel at any time.

### Adding files to an existing item (a "list")

1. Set **Identifier** to the existing item's id.
2. Add the new files.
3. Leave **metadata untouched** — metadata is applied when an item is *created*;
   it does not update existing items.
4. Keep **Skip unchanged files (checksum)** on so existing files aren't re-sent.
5. Leave **Keep old version** off to replace a same-named file, or on to preserve
   the old version alongside the new one.
6. Click **Start upload**.

### Batch upload from a spreadsheet

Click **Batch upload from spreadsheet…** and pick a `.csv` or `.xlsx` file.
Each row becomes one upload job.

- An **identifier** column is required. Recognised names:
  `identifier`, `id`, `item`, `item_identifier`.
- A **file** column holds the local path(s), separated by `|`. Recognised names:
  `file`, `files`, `path`, `paths`, `filename`, `filenames`. Relative paths are
  resolved next to the spreadsheet.
- Every **other column becomes metadata**, and a value containing `|` is split
  into multiple values.

Example:

| identifier | file | title | subject |
| --- | --- | --- | --- |
| my-item-1 | video.mp4\|poster.jpg | My First Item | history\|archive |
| my-item-2 | /data/scan.pdf | A Scanned Book | books |

---

## 7. Downloading

Downloading needs no account for public items.

### Source

- Paste an **identifier** or a full URL
  (`https://archive.org/details/<id>`, `/download/…`, `/embed/…`). Archivary
  extracts the identifier automatically. The **Paste** button reads your clipboard.
- Click **Load file list** to fetch the item's files.

### Destination and filters

| Control | Meaning |
| --- | --- |
| **Download to** | Destination folder. |
| **Include globs** | Only files matching these patterns, comma-separated (e.g. `*.mp4, *.jpg`). |
| **Exclude globs** | Skip files matching these patterns (e.g. `*_thumb.jpg, *.xml`). |
| **Formats** | Only files of these formats (e.g. `MPEG4, JPEG`). |

### Options

| Option | What it does |
| --- | --- |
| **Skip files that already exist** | Don't re-download a file whose local size already matches. |
| **Verify checksums after download** | Compare each downloaded file with its archive.org MD5; a mismatch is deleted and reported. |
| **Flatten output (no item subfolder)** | Save directly into the destination folder instead of a subfolder named after the identifier. |
| **Resume partial downloads** | Continue an interrupted file with an HTTP range request. |
| **Count this download as a view** | By default downloads **do not** count toward the item's public view count; tick this to make them count. |
| **Concurrent downloads** | How many files download at once (1–16). |

### Downloading

- **Download selected / all listed** downloads the files you ticked, or every
  listed file if none are ticked.
- **Download everything matching filters** ignores the list and downloads
  everything that matches your globs/formats.

Progress appears in **Transfers** under one job per item (files inside run
concurrently up to your limit).

---

## 8. Searching

### Query modes

- **Simple** — type words or a phrase; e.g. `market street`.
- **Advanced (field:value)** — write archive.org's advanced syntax directly,
  e.g. `subject:"market street" collection:prelinger`.
  Use the **Field / Value / Add field** helper to append clauses like
  `mediatype:"movies"` without knowing the syntax.

### Filters

| Control | Meaning |
| --- | --- |
| **Media type** | Restrict to one mediatype (Any for all). |
| **Collection** | Restrict to a collection. |
| **Sort** | Relevance, Most downloaded, Newest first, Oldest first, Title A-Z. |
| **Max results** | Stop after this many results (1–10000). |

Click **Search**. Results appear with **Title, Identifier, Media type, Date, Size
and Downloads**. The summary line shows how many of the total matches are shown.

### Using results

- **Double-click** a row (or **Send to Metadata**) to open the item's metadata.
- **Send to Download** jumps to the Download tab with the identifier filled in.
- **Open in List** jumps to the file listing.
- **Export…** saves the results as **CSV** or **JSON**.

---

## 9. Editing metadata

The Metadata tab views and edits any item's fields.

### Loading and viewing

Enter an identifier or URL and click **Load**. The summary line shows the title,
media type, file count and total size. The table lists every field; multi-value
fields are shown with values separated by `|`.

### Editing

| Button | Action |
| --- | --- |
| **Add field** | Add an empty row for a new key. |
| **Reload** | Discard local edits and re-fetch from archive.org. |
| **Append values** | Add your values to existing multi-value fields without removing anything (uses archive.org's `append_list`). |
| **Save (overwrite)** | Replace the submitted fields entirely. |
| **Remove selected field(s)** | Delete the selected fields after a confirmation. |

Editing a `Value` cell containing `|` creates a multi-value field. For example,
setting `subject` to `history|archive` stores two values.

> **Overwrite vs Append:** Overwrite is what you want when fixing a typo or
> replacing a value. Append is what you want when *adding* a second collection or
> another subject without clobbering the existing ones.

### Batch metadata edits

Under **Batch edit from spreadsheet**:

1. Choose **Append values** or **Overwrite values**.
2. Click **Import spreadsheet…** and pick a `.csv`/`.xlsx` file where each row has
   an **identifier** column plus the metadata columns to change. Use `|` for
   multiple values.
3. Archivary queues a job and reports how many items succeeded or failed.

Example:

| identifier | collection | subject |
| --- | --- | --- |
| item-a | community_video | remastered |
| item-b | | fixed\|restored |

---

## 10. Listing and deleting files

This tab shows every file in an item and lets you act on them.

1. Enter an identifier or URL and click **Load files**.
2. The table lists **File, Size, Format, MD5 and Source**.
3. Tick the files you want.

**Download selected** downloads the ticked files to your default download folder.

**Delete selected…** opens a safety dialog that:

- lists exactly what will be removed,
- offers **cascade delete** (also delete derivatives and the original),
- requires you to tick *"I understand these files will be permanently removed"*,
- requires you to **type the identifier** to confirm.

Only then does the **Delete files** button enable.

---

## 11. Tasks (derive and processing)

The **Tasks** tab shows the Internet Archive catalog task queue, e.g. the derive
processing that runs after an upload.

- Leave **Identifier** blank to see tasks for all of your items, or enter one item
  to filter.
- **Refresh** reloads; **Auto-refresh** reloads on a timer you set (5–600 s,
  default 15 s).
- The table shows **Task ID, Identifier, Command, Status, Submitted and Server**,
  with status coloured (running/queued/paused/error/done).
- **View task log** (or double-click a row) opens the raw task log.

---

## 12. The Transfers panel

Every operation — upload, download, metadata edit, delete, search, task load —
becomes a job with a status: **queued, running, paused, done, failed** or
**cancelled**.

Each row shows the job type, its title, a progress bar with percentage, the size
transferred, live speed, ETA and status. The buttons change with the state:

| State | Buttons |
| --- | --- |
| Queued | Cancel |
| Running | Pause, Cancel |
| Paused | Resume, Cancel |
| Done | Remove |
| Failed / Cancelled | Retry, Remove |

Toolbar controls:

- **Filter** — **All**, **Active only**, or **Problems** (failed/cancelled).
- **Follow newest** — keep the newest job in view.
- **Clear finished** — remove completed/failed/cancelled jobs from the list (the
  files and remote state are unaffected).

Jobs run in parallel up to **Concurrent jobs** from Settings, so you can start a
long upload and a download at the same time.

---

## 13. The Console

The Console shows the underlying log — useful when something goes wrong.

- **Level** — filter to Debug, Info, Warning or Error.
- **Raw HTTP logging** — show every HTTP request/response (very verbose; great
  for diagnosing network problems).
- **Auto-scroll** — keep the newest line visible.
- **Show details** — expands error dialogs' details here.
- **Copy all** / **Clear**.

Error dialogs also offer a **Show in console** button, so the full stack trace is
one click away.

---

## 14. Menus and keyboard shortcuts

| Menu | Items |
| --- | --- |
| **File** | Exit |
| **View** | Transfers & Console panel, Transfers, Console, Theme (System/Dark/Light) |
| **Account** | Manage accounts…, Test connection… |
| **Help** | About Archivary |

| Shortcut | Action |
| --- | --- |
| `Ctrl+J` | Show / hide the bottom panel |
| `Ctrl+1` | Focus Transfers |
| `Ctrl+2` | Focus Console |
| `Ctrl+Q` | Quit |

---

## 15. Recipes and common workflows

**Back up a local folder to a new item**
1. Upload → enter a new identifier, fill in Title/Collection/Mediatype.
2. Drop the folder, keep **Queue derive** on, **Skip unchanged** on.
3. Start upload.

**Add extra files to an item you already made**
1. Upload → enter the existing identifier → add files.
2. Keep **Skip unchanged files** on → Start upload.

**Resume an interrupted upload**
Re-run the same upload with **Skip unchanged files (checksum)** enabled. Files
already delivered are skipped and the rest continue.

**Download only the videos from an item**
Download → paste the identifier → set **Include globs** to `*.mp4` → **Download
everything matching filters**.

**Download a whole item anonymously**
No account needed — set the destination and click **Download everything matching
filters** with empty filters.

**Move an item into an additional collection**
Metadata → load the item → ensure `collection` contains all values joined by `|`
→ click **Append values** (or set the full list and **Save (overwrite)**).

**Batch-fix the title of many items**
Metadata → Batch edit → import a CSV with `identifier,title` → choose Overwrite →
**Import spreadsheet…**.

**Delete a few bad files from an item**
List & Delete → load → tick the files → **Delete selected…** → tick the
acknowledgement and type the identifier.

**Check whether derive has finished**
Tasks → Auto-refresh on → look for the item's `derive.php` task turning `done`.

---

## 16. How upload options work

- **Content-MD5** is a checksum of the file sent with the upload. The server
  recomputes it and rejects the transfer if they differ, so corruption is caught
  instead of silently stored. Archivary sends it when you enable **Verify uploads
  with Content-MD5** (and always before deleting a local file).
- **Skip unchanged files (checksum)** computes the local MD5 and compares it to
  the copy already in the item. Identical files are skipped — cheap resumes and
  no wasted bandwidth.
- **Keep old version** tells the archive to retain the previous file as a version
  rather than replacing it.
- **Queue derive** triggers the archive's derivative pipeline (thumbnails,
  streaming versions, full-text search, …). Turning it off uploads the item
  without processing it.

For the precise mechanics, see the
[Internet Archive upload docs](https://archive.org/services/docs/api/ias3.html).

---

## 17. Troubleshooting and error messages

Archivary translates technical failures into plain language. Common ones:

| Message | Meaning and fix |
| --- | --- |
| **Cannot write to that collection** | Your account can't upload into the collection you chose. Clear **Collection** or use an open one such as `opensource` or `community`. |
| **Sign-in failed** | The IAS3 keys are wrong or missing. Re-copy them from <https://archive.org/account/s3.php>. |
| **Permission denied** | The item belongs to another account, or your keys lack permission. |
| **Item already exists** | Use a different identifier, or enable **Keep old version**. |
| **Network unavailable** | archive.org couldn't be reached. Check your connection. |
| **Request timed out** | Usually temporary; retry. |
| **Rate limited** | Too many requests; wait a minute. |
| **Internet Archive is busy** | S3 is overloaded (503). Archivary retries automatically. |
| **Checksum mismatch** | A downloaded file didn't match; it was removed. Retry the download. |
| **Item not found** | The identifier doesn't exist or the item is "dark". |

For anything else, open the **Console**, enable **Raw HTTP logging**, reproduce the
problem, and read the request/response detail.

---

## 18. Glossary

- **IAS3** — the Internet Archive's S3-compatible storage API used for uploads,
  edits and deletes.
- **Identifier** — an item's permanent unique name.
- **Derive** — server-side processing that produces derivative files.
- **Content-MD5** — checksum header used to verify an upload.
- **append_list** — archive.org metadata update mode that adds values without
  replacing existing ones.
- **Glob** — a filename pattern such as `*.mp4`.
- **Reporter / Job** — Archivary's internal progress and task objects.

---

## 19. Files, storage and privacy

| What | Where |
| --- | --- |
| Profiles (no secrets) | `%APPDATA%\Archivary\profiles.json` (Windows), `~/.config/Archivary/profiles.json` (Linux/macOS) |
| Settings | `settings.json` in the same folder |
| Encrypted fallback secrets | `secrets.enc` in the same folder (only when no OS keychain exists) |
| Secrets (normal) | OS keychain, service name **Archivary** |
| Log file | `%LOCALAPPDATA%\Archivary\archivary.log` (Windows), `~/.config/Archivary/data/archivary.log` |
| Checksum cache | `.../Archivary/data/cache/_checksum_archive.txt` |

Archivary never stores your password; it is used once to exchange for IAS3 keys
and then discarded. Downloads of public items are anonymous.

---

## 20. FAQ

**Do I need an account to download?**
No, public items can be downloaded without signing in.

**Where do downloads go by default?**
Your home `Downloads/Archivary` folder, configurable in Settings.

**Can I run several uploads at once?**
Yes. Increase **Concurrent jobs** in Settings. Each transfer is independent and
can be paused/resumed individually.

**Does downloading affect the item's popularity?**
By default no. Tick **Count this download as a view** if you want it to count.

**How do I rename an item's identifier?**
Identifiers are permanent. Create a new item with the desired identifier and
re-upload, then delete the old files if needed.

**Why did my file get skipped?**
**Skip unchanged files** found an identical checksum already in the item. Turn
the option off to force re-upload.

**The upload failed halfway — did I lose progress?**
No. Re-run with **Skip unchanged files** enabled and the already-delivered files
are skipped.

**Can I use a custom archive.org host?**
Yes — set the **Host** field for the profile (defaults to `archive.org`).

**How do I see the exact request that failed?**
Open the Console, turn on **Raw HTTP logging**, and reproduce the action.
