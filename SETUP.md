# 🐾 Setup guide: the cat-themed profile

Everything you need to put this profile live on **github.com/Miaoricle**, keep it updating by itself, and make it yours.

```text
Miaoricle/                      ← your special "profile" repository
├── README.md                   ← the profile page itself (edit text, links, badges here)
├── SETUP.md                    ← this guide
├── cat.config.json             ← name, banner text, colours, the cat's look, moods, quotes
├── profile/                    ← all images (redrawn by GitHub Actions, don't hand-edit)
├── scripts/cat_widgets.py      ← draws the pixel cats and cards (Python, no dependencies)
└── .github/workflows/
    ├── profile-widgets.yml     ← every 6 h: stats, languages, streak, cat status, prophecy
    └── feed-the-cat.yml        ← when a visitor clicks "feed the cat"
```

---

## Step 0 · The special profile repository

A repository named **exactly like your username** is special: GitHub shows its `README.md` at the top of your profile.

You already have one (`Miaoricle/Miaoricle`), so you can skip to Step 1. If you ever need to create it again:

1. Go to **github.com/new**.
2. Repository name: `Miaoricle` (same spelling and capitals as your username). GitHub shows a note that this is a ✨special✨ repository.
3. Make it **Public** and tick **Add a README file**.
4. Click **Create repository**.

> 💡 Your old README stays in the repo's commit history, so you can always go back. Your profile-view count also carries over, because the counter is tied to your username.

---

## Step 1 · Put the files in the repo

### Option A: in the browser (no Git needed)

1. Unzip `Miaoricle-profile.zip`.
2. Open **github.com/Miaoricle/Miaoricle** → **Add file** → **Upload files**.
3. Drag in `README.md`, `SETUP.md`, `cat.config.json`, `.gitignore` and the folders **`profile`** and **`scripts`** (dragging a folder keeps its structure).
4. Commit message: `🐾 New cat-themed profile` → **Commit changes**. If it asks, replace the existing `README.md`.
5. The two workflow files live in a hidden folder (`.github`), which Finder/Explorer often hide, so create them by hand:
   - **Add file** → **Create new file**
   - In the name box type `.github/workflows/profile-widgets.yml` (typing the `/` creates the folders)
   - Open that file from the zip in a text editor, copy everything, paste it in → **Commit changes**
   - Do the same for `.github/workflows/feed-the-cat.yml`

### Option B: with Git

```bash
git clone https://github.com/Miaoricle/Miaoricle.git
cd Miaoricle
# copy everything from the unzipped folder in here, including the hidden .github folder
git add -A
git commit -m "🐾 New cat-themed profile"
git push
```

> ⚠️ The bot commits refreshed images to `main` every few hours, so always `git pull` before you push changes from your computer.

---

## Step 2 · Let the workflows save their images

The workflows commit the redrawn SVGs back to the repo, so they need write access.

1. Repo → **Settings** → **Actions** → **General**
2. Under **Workflow permissions**, choose **Read and write permissions** → **Save**
3. Under **Actions permissions**, keep **Allow all actions and reusable workflows** (the stats cards use the community action `stats-organization/github-readme-stats-action`).

---

## Step 3 · Run it once

1. Repo → **Actions** tab. (If Actions are switched off for the repo, turn them on under Settings → Actions → General.)
2. Click **🐾 Update profile widgets** → **Run workflow** → **Run workflow**.
3. Wait about a minute for the green tick, then open your profile.

The "Waiting for the first workflow run" placeholders are replaced by your real stats, streak, contribution chase and cat status. From now on it refreshes every 6 hours by itself.

> 🔄 GitHub caches images for a few minutes. If nothing changes, wait a moment and hard-refresh (Ctrl/Cmd + Shift + R).

---

## Step 4 · Count your private work (recommended)

Most of your projects are coursework or client work, so they aren't public. Without a token, the cards only see public repositories (right now that's basically `wikipedia-edit-analysis`), so the numbers will look smaller than your real activity.

1. **Show private contributions on the graph:** open your profile → **Contribution settings** (just above the green contribution graph) → turn on **Private contributions**. Only counts are shown, never repo names or code.
2. **Create a token:** GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**
   - Note: `profile stats`
   - Expiration: 90 days (put a reminder in your calendar) or longer
   - Scopes: tick **`repo`** and **`read:user`**
   - **Generate token** and copy it (you only see it once)
3. **Save it as a secret:** profile repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
   - Name: `STATS_TOKEN`
   - Secret: paste the token → **Add secret**
4. Run the workflow again (Step 3).

> 🔐 The token is only used by the scheduled `profile-widgets` workflow. The `feed-the-cat` workflow, which strangers can trigger, never touches it. When the token expires, the cards keep showing their last good version until you generate a new token and replace the secret.

---

## Step 5 · Feed the cat 🐟

Click **feed the cat** (or the cat status card) on your profile. It opens a new issue titled `🐟 feed-the-cat`; press **Create**. Within a minute or two the bot:

- adds a fish to the counter and remembers who fed it,
- switches the status card to **SNACK TIME** for a few hours,
- replies with a thank-you, then closes and locks the issue.

Good to know:

- **Issues must be enabled:** Settings → General → Features → **Issues** ✅ (it's on by default).
- Each visitor can feed the cat once every 12 hours (`feed.cooldown_hours` in `cat.config.json`). Extra issues get a polite "still digesting" reply.
- Every feed opens an issue, so GitHub will notify you. To mute them: **Watch** (top of the repo) → **Custom** → untick **Issues**.
- Safety: the workflow only reads the visitor's username. The issue title and body are never run as code.

---

## Step 6 · Make it yours

### ✏️ Text, links and badges (`README.md`)

Click the ✏️ pencil on `README.md` to edit in the browser. Everything is plain Markdown/HTML, with a few `<!-- ✏️ -->` hints that don't show up on the page.

| What | Where in `README.md` | How |
|---|---|---|
| Typing animation | `<picture>` block at the top | Lines are separated by `;` and spaces are `+`. Build a new link at [readme-typing-svg.demolab.com/demo](https://readme-typing-svg.demolab.com/demo/). There are **three** copies (dark, light, fallback), so update all of them. |
| About me | `## 🐾 About me` | Edit the bullets and the `cat profile.yaml` block (CGPA, Dean's List, languages). |
| Portfolio / Discord | `## 🤝 Let's connect` | Ready-made badges are commented out. Swap in your link, then delete the two marker lines (`<!-- ✏️ ...` and `end portfolio -->`). |
| Email | `## 🤝 Let's connect` | Change the address in `mailto:amirnazhann@gmail.com`. |
| Projects | `## 🚀 Featured projects` | Each project is one `<td>` cell. Copy a cell to add one. To link a repo, make the title a link: `### 🏃 [FitAlign](https://github.com/Miaoricle/FitAlign)` and copy the **view repo** badge from the Wikipedia cell. |
| Tech badges | `## 🧶 Tech stack` | `https://img.shields.io/badge/<Name>-1E1E2E?style=for-the-badge&logo=<slug>&logoColor=<hex>`. Find slugs on [simpleicons.org](https://simpleicons.org). The `title="..."` is the hover text. |

> ℹ️ LinkedIn, C# and VS Code logos were removed from Simple Icons, so those badges use small custom icons (C# shows the .NET logo). That's expected, not a bug.

### 🖼️ Banner, chips and status pill (`cat.config.json`)

The banner is drawn from `cat.config.json`: `name`, `headline`, `subline`, `status_pill` (the green pill, top-right), `terminal_title`, `prompt_path` and up to 7 `chips`. Edit, commit, and the workflow redraws the banner within a minute (it runs automatically whenever `cat.config.json` changes).

### 🎨 Colours and themes

Everything drawn by the workflows (banner, cat cards, stats and language cards) follows the `theme` in `cat.config.json`:

| `theme` | Look |
|---|---|
| `mocha` *(default)* | darkest, purple-pink accents |
| `macchiato` | dark, slightly bluer |
| `frappe` | softer dark grey-blue |
| `latte` | light cards |

Override any single colour with `theme_overrides`, for example `"theme_overrides": { "accent": "F5C2E7", "green": "94E2D5" }`. Colour names are `base`, `surface0`, `text`, `mauve`, `pink`, `peach`, `yellow`, `green`, `teal`, `sky`, `blue`, `lavender`, `red` and so on (the [Catppuccin](https://catppuccin.com/palette) names).

Badge and typing colours live in `README.md` as hex codes inside the URLs. To restyle, use **Find & Replace** in your editor:

| Used for | Hex (Mocha) |
|---|---|
| Badge background | `1E1E2E` |
| Languages, titles, typing text (dark mode) | `CBA6F7` mauve |
| Frameworks & libraries | `FAB387` peach |
| Databases | `89DCEB` sky |
| Developer tools, "feed the cat" | `F5C2E7` pink |
| APIs, AI & hardware | `A6E3A1` green |
| LinkedIn | `89B4FA` blue |
| Email | `F38BA8` red |
| Typing text (light mode) | `8839EF` |

### 🐈 The cat itself

In `cat.config.json` → `cat`, set its `name` and colours. Two quick looks to try:

```jsonc
// black cat with yellow eyes
"fur": "313244", "stripes": "1E1E2E", "belly": "585B70", "eyes": "F9E2AF"
// grey tabby
"fur": "9399B2", "stripes": "6C7086", "belly": "CDD6F4", "eyes": "11111B"
```

- `moods` decides when the status cat is **ON A ROLL**, **CODING**, **NAPPING** or **DAYDREAMING** (based on your streak, contributions this week and days since your last contribution).
- `oracle.quotes`: add your own sayings to the daily Miaoricle. Set `use_builtin_quotes` to `false` to use only yours.
- `footer` and `pet` hold the closing banner and the "Pet the cat" text.

### 🖼️ Adding your own images or a favourite meme GIF

Every cat on the page is original pixel art living in your repo, so nothing can vanish when another site goes down. To add a GIF you like:

1. Download it from a source that allows reuse (GIPHY's download option, for example), keep it small (under ~3 MB loads fast).
2. Upload it into a new `assets/` folder (Add file → Upload files).
3. Reference it with a relative path, e.g. inside the "Pet the cat" block: `<img src="./assets/typing-cat.gif" width="300" alt="cat typing furiously">`

Avoid hot-linking random GIF URLs from the web; those links break or change without warning.

---

## Step 7 · WakaTime coding time (optional)

1. Sign up at [wakatime.com](https://wakatime.com) and install the plugin for your editor (VS Code: the **WakaTime** extension; Android Studio: Settings → Plugins → WakaTime). Paste your API key when it asks.
2. On WakaTime, set a **username** and turn on **Display code time publicly** and **Display languages, editors, operating systems publicly** (in your profile/privacy settings).
3. Profile repo → **Settings** → **Secrets and variables** → **Actions** → **Variables** tab → **New repository variable**: name `WAKATIME_USERNAME`, value = your WakaTime username.
4. In `README.md`, find the `⏱️ WakaTime` comment under **GitHub metrics** and delete its two marker lines so the image shows.
5. Run the workflow. The card fills in once WakaTime has a day or two of data.

---

## How it all works

- **Every 6 hours** (and whenever you change `cat.config.json` or the script), `profile-widgets.yml`:
  1. generates the **stats** and **top languages** cards with the GitHub Readme Stats Action, using colours read from your config;
  2. runs `scripts/cat_widgets.py update`, which reads your contribution calendar from the GitHub API and redraws the banner, divider, cat status, streak, contribution chase, prophecy and footer;
  3. commits only the files that changed.
- **When someone feeds the cat**, `feed-the-cat.yml` updates `profile/cat-state.json`, redraws the status card, replies and closes the issue. If a feed and a refresh happen at the same moment, both workflows retry until neither overwrites the other.
- **Why not the usual public card URLs?** In 2026 the shared public servers behind github-readme-stats and github-profile-trophy were paused or heavily rate-limited, which broke a lot of READMEs. Generating the cards inside your own repo with Actions is the route the stats maintainers now recommend, and other people's traffic can't rate-limit it.
- **Accessibility:** every image has alt text, and all animations stop for visitors who turn on "reduce motion" (the cards still show their final state).

### Preview on your computer (optional)

```bash
python3 scripts/cat_widgets.py demo     # writes demo-preview/ with made-up data; open the SVGs in a browser
python3 scripts/cat_widgets.py render   # redraw ./profile from the cached data, no network needed
```

`demo-preview/` is in `.gitignore`, so it won't be committed by accident.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Cards say "Waiting for the first workflow run" | Run the workflow (Step 3) and check Step 2. |
| Workflow fails at **Commit and push** with a 403 / permission error | Step 2: set **Read and write permissions**. |
| Stats look tiny or only show Python | Step 4: add `STATS_TOKEN` and turn on private contributions. |
| Stats card didn't change but the run is green | That step is set to keep the previous card if the API hiccups. Look at the step's log for the error; it fixes itself on the next run. |
| Scheduled runs stopped | GitHub pauses schedules after 60 days without repo activity. Actions tab → the workflow → **Enable workflow**. |
| A feed issue never got a reply | Check the **🐟 Feed the cat** run in the Actions tab. Issues must be enabled and the title must contain `feed-the-cat`. |
| Typing text or badges don't load | Those come from readme-typing-svg and shields.io; they're occasionally slow. Reload the page. |
| Too many bot commits for your taste | Change the cron line in `profile-widgets.yml` (e.g. `"17 3 * * *"` = once a day), or disable the workflow in the Actions tab. |
