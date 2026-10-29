# DocShield — User Guide

DocShield helps you safely use AI tools (ChatGPT, Claude, etc.) on
client documents. It scans a Word `.docx` file, replaces real names,
emails, IBANs, codici fiscali and other private details with
placeholders like `[PERSON_1]`, then lets you restore the real names
in the AI's reply. Everything happens on your computer — nothing is
sent online.

---

## 1. Install (one time)

1. Download `DocShield-windows.zip` from the link Jose sent you.
2. **Before unzipping**, right-click the `.zip` file → **Properties** →
   tick **Unblock** at the bottom → **OK**. (This step often prevents
   Windows from blocking the program later.)
3. Right-click the `.zip` → **Extract All…** → choose somewhere easy to
   find, like your Desktop or Documents folder. You can also extract it
   onto a USB stick. **No admin password needed.**
4. Open the new **DocShield** folder. Inside it, find `DocShield.exe`
   (a blue shield icon).

> **Tip:** keep the whole `DocShield` folder together. Don't move
> `DocShield.exe` out by itself — it needs the other files in the
> folder to work.

---

## 2. First launch

Double-click `DocShield.exe`.

You may see one of these warnings the first time:

- **"Windows protected your PC"** (a blue box) → click the small
  **More info** link → then **Run anyway**. This appears because the
  program isn't from a paid software publisher. It's safe.
- **"This app has been blocked by your administrator"** → your work
  laptop's IT team is blocking new programs. Forward this to them:
  > *"Could you please whitelist this open-source tool? It runs
  > entirely offline (no internet connection used) and helps me keep
  > client information confidential when using AI assistants. Source
  > code: <Jose's GitHub link>."*

The program window opens. The bottom of the window shows
*"Loading models in the background…"* — this takes 10–30 seconds the
first time only. Wait until it says **"Ready"**.

---

## 3. Anonymise a document

1. Open the **Anonymise** tab (it's the first one).
2. **Drag a `.docx` file from your computer onto the big empty area** —
   or click **Add files…** and pick one. You can drop several files at
   once if they're related; the program will keep names consistent
   across them.
3. Click **Anonymise batch**.
4. A small box asks for a **password**. Type something you'll remember
   (e.g. the client's reference plus a year). **Write this password
   down somewhere safe** — without it you cannot restore the real names
   later. The password is never stored.
5. After a few seconds, a **Review** window appears showing every name,
   email, IBAN, etc. the program found. Each one has a checkbox.
   - Untick anything that looks wrong (false alarms — a common word the
     program mistook for a name).
   - In the box at the bottom you can type extra things you want hidden
     (e.g. an internal project codename), separated by commas.
   - On the right you'll see a preview of your document with the words
     to be hidden highlighted in **amber**.
6. Click **Anonymise** at the bottom right.
7. Two new files appear in the same folder as your original document:
   - `YourFile_anon.docx` — the anonymised Word document. **This is
     what you copy and paste into ChatGPT/Claude/etc.**
   - `YourFile_mapping.dsm` — a small encrypted file that remembers
     which placeholder means what. **Keep this file safe** — you need
     it to restore the real names later.

> **Important:** the original file is never modified. You can re-run
> anonymisation as many times as you want.

---

## 4. Use the anonymised text with an AI

1. Open `YourFile_anon.docx` in Word.
2. Copy the text (Ctrl+A then Ctrl+C).
3. Paste it into ChatGPT, Claude, or any other AI assistant.
4. Ask whatever you need — summarise, draft a reply, find issues, etc.

The AI sees only `[PERSON_1]`, `[ORG_2]`, `[IBAN_1]` — no real names.

---

## 5. Restore real names in the AI's reply

When the AI gives you back text full of placeholders, you bring the
real names back:

1. In DocShield, click the **Rehydrate** tab (second tab).
2. Click **Browse…** and pick the `_mapping.dsm` file the program
   created earlier (it's next to your original document).
3. Type the same **password** you used when you anonymised.
4. Paste the AI's reply into the **LLM response** box.
5. Click **Rehydrate**.
6. The restored text appears below — real names back in place. Click
   **Copy result** to put it on your clipboard.

> **If you forget the password**, the mapping file becomes unusable
> and you'll have to redo the anonymisation from scratch (you keep
> the original document, so this isn't catastrophic — just inconvenient).

---

## 6. Optional: tune the program

**File → Settings…** lets you set a few things:

- **Allowlist** — words to *never* hide. Useful for things the program
  keeps mistaking for names: court names, common legal phrases, your
  firm's name. One per line.
- **Denylist** — words to *always* hide, even if the program doesn't
  spot them. Internal project codes, client nicknames. One per line.
- **Default output folder** — where anonymised files should be saved
  by default.
- **Confidence threshold** — leave at 0.6 unless you find the program
  is missing real names (lower it) or finding too many false ones
  (raise it).

Click **Save** when done. Settings stay between sessions.

---

## 7. History

The **History** tab shows every anonymisation you've ever done, with
date, file name, and where the output went. Useful if you forget
where you saved something, or for your own audit trail.

---

## 8. Common questions

**Does this send my documents anywhere?**
No. The program never uses the internet. You can disconnect from
Wi-Fi, run it, and it will work exactly the same.

**Can I trust the placeholders?**
Yes — the program preserves your document's formatting (bold, tables,
headers) and only replaces the actual private text. Open the
`_anon.docx` in Word to spot-check before sending it to an AI.

**The first run is very slow.**
Yes, ~20 seconds while it loads its language models. Every later run
is fast.

**A word I expected to be hidden wasn't caught.**
Add it to the **Denylist** in Settings, or paste it into the
*"Also redact"* box in the Review window before clicking Anonymise.

**A word I wanted kept got hidden.**
Untick it in the Review window, or add it to the **Allowlist** in
Settings so it's permanently ignored.

**I need a fresh version.**
Jose will send you a new download link. Replace the whole `DocShield`
folder; your settings and history stay where they are (in your user
profile, not in the program folder).

**Where are my files saved?**
- Anonymised documents and mapping files: next to the original
  document, unless you set a different folder in Settings.
- Settings and history: in your user profile, in a hidden folder
  Windows manages automatically. You don't need to touch these.

---

## 9. Trouble?

Send Jose:
- A screenshot of what you're seeing (especially any error message).
- The name of the document you were trying to anonymise.
- A short description of what you clicked just before the problem.

Almost everything is fixable. The program does not change your
original document under any circumstance, so you cannot lose data by
trying things.
