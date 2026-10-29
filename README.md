# iphone-notes-pipeline

Hands-off prepis klientskych stretnutí: **iPhone Voice Memos → Obsidian / priečinok**.
Beží lokálne na Apple Silicon. 50-min meeting = **~20 sekúnd** celá pipeline.

## Features

- **Rýchlosť:** 150-300× real-time (Voz transcription + Who diarization, native Swift binárky)
- **Lokálne, offline:** žiadne cloud API, žiadne HF tokeny, žiadne externé requesty
- **Diarizácia:** Speaker A/B/C labels s ~5-sekundovou segmentáciou
- **Jazyk:** 25 EU jazykov vrátane SK, CZ, EN (auto-detect)
- **Výstup:** čistý Markdown s YAML frontmatter + pripravený AI prompt pre copy-paste do ChatGPT/Claude/Gemini
- **Zero-config daemon:** launchd WatchPaths na Voice Memos iCloud folder
- **Distribúcia:** jediný `.pkg` installer (34 MB)

## Architektúra

```
iPhone Voice Memo → iCloud sync → macOS
          ↓
    launchd WatchPaths daemon (Python)
          ├─ voz-cli  (Swift, Voz by Desert Ant Labs)   → text + word timestamps
          ├─ who-cli  (Swift, Who by Desert Ant Labs)   → speaker turns
          ├─ merge                                       → Speaker A/B/C labels
          ├─ render Jinja2 template
          └─ write .md to Obsidian vault or folder
          ↓
    osascript notifikácia
```

Transcription + diarization bežia ako natívne Swift CLI binárky volané
z Python daemona cez `subprocess`. Žiadne HF tokeny, žiadny PyTorch,
žiadne MLX. Modely sa automaticky stiahnu pri prvom behu (~550 MB spolu).

## Pre kolegov

1. Stiahni `.pkg` z internej linky (dostaneš cez Slack).
2. Double-click → macOS povie *"unidentified developer"* → System Settings →
   Privacy & Security → **Open Anyway** (len raz).
3. Prejdi installerom. Na konci sa spýta kam ukladať prepisy:
   - **Obsidian vault** — vyberieš zo zoznamu detegovaných vaultov
   - **Priečinok na disku** — file picker, pre teba keď nemáš Obsidian
4. **Jednorazový krok — Full Disk Access:** macOS zablokuje prístup k iPhone
   nahrávkam. Installer ti otvorí správne okno: `+` → pridaj
   `/usr/local/bin/meet-transcriber` → zapni.
5. Hotovo. Nahraj na iPhone cez Voice Memos → do pár minút notifikácia
   s prepisom.

## Zmena nastavení

```bash
meet-transcriber reconfigure
```

Prepne vault / priečinok, znova sa opýta kam.

## Dôležité — iCloud sync Voice Memos

macOS **nestahuje** nové Voice Memos nahrávky z iCloud automaticky.
Sync je **lazy** — spustí sa až keď otvoríš Voice Memos app (buď na iPhone,
alebo na Mac).

**Praktický workflow:**
Je to **dve fázy sync**:
1. **Metadata push** (automaticky, rýchle) — Mac vidí že nahrávka existuje
   ako placeholder `.filename.m4a.icloud` (0 B, len info)
2. **Content download** (lazy, on-demand) — audio bytes sa stiahnu až keď
   explicitne klikneš na nahrávku v Voice Memos app (na iPhone alebo Mac)

Takže:
- Po nahrávaní na iPhone otvor Voice Memos.app na Mac **a klikni na novú
  nahrávku v zozname**. iCloud daemon ju stiahne, placeholder sa premenuje
  na reálny `.m4a`, launchd WatchPaths detekuje change → naš daemon spracuje.
- **Len otvorenie appky bez klik-u na nahrávku zrejme nestačí.**

**Alternatíva — zapnúť always-download:**
- iPhone: Settings → [tvoje meno] → iCloud → Voice Memos → **Optimize iPhone
  Storage** = **OFF** → iCloud sťahuje full copy automaticky
- Mac: System Settings → Apple ID → iCloud → **Optimize Mac Storage** = OFF
- Trade-off: viac miesta na disku (každá nahrávka drží full copy aj po
  background cleanup), ale **žiadne manuálne kliky**

**Technický detail:** Voice Memos používa CloudKit (nie CloudDocs), takže
`brctl download` ani launchd WatchPaths nevedia prinútiť sync. Dá sa to
obísť automaticky spustením Voice Memos.app silently cez
`open -g -j /System/Applications/VoiceMemos.app` v cron / LaunchAgent-e —
nie je zatiaľ súčasť pipeline, ale ak sa to stane bolestivé, viď open items.

## Dev install

Prereqs: macOS 15+ (Sequoia), Xcode CLI tools (`xcode-select --install`),
`uv` (`brew install uv`), `ffmpeg` (`brew install ffmpeg`).

```bash
./dev/install-local.sh
```

Script:
1. Zbuilduje `swift-voz-wrapper` a `swift-who-wrapper` (prvý raz ~2-3 min
   kvôli SPM dependency resolution).
2. Vytvorí Python venv, nainštaluje balík editable.
3. Symlinkuje `/usr/local/opt/meet-transcriber` → repo.
4. Nainštaluje `/usr/local/bin/meet-transcriber` wrapper.
5. Spustí config wizard (ak config ešte neexistuje).
6. Zavedie LaunchAgent.

Po inštalácii treba manuálne pridať binárku do Full Disk Access (viď bod 4
sekcie "Pre kolegov").

## Build .pkg pre distribúciu

```bash
./pkg/build-pkg.sh
```

Vyprodukuje `build/meet-transcriber-v1.0.pkg` (**~34 MB** — bundled Python
runtime + slim venv + Swift binárky + app code; Voz/Who modely sa stiahnu
na strane kolegu pri prvom behu, ~550 MB). Nahraj ručne na NAS a pošli link.

## CLI príkazy

```bash
meet-transcriber doctor         # over že ffmpeg/voz-cli/who-cli/config sú OK
meet-transcriber status         # vault path, counts processed vs failed
meet-transcriber process FILE   # spracuj jeden audio súbor
meet-transcriber watch          # sweep (daemon ho volá automaticky)
meet-transcriber reconfigure    # vault/folder picker wizard
```

## Credits

- **[Voz](https://desertant.com/models/voz/)** a **[Who](https://desertant.com/models/who/)**
  by [Desert Ant Labs](https://desertant.com) — on-device Apple Silicon speech + diarization modely.
  Zdarma do 100 k monthly active devices, zdieľané cez
  [desert-ant-core SPM package](https://github.com/Desert-Ant-Labs/desert-ant-core).

## License

[MIT](LICENSE) — Copyright © 2026 František Kocúrik.

Note: Voz & Who modely (Desert Ant Labs) sú proprietary — free do 100 k
monthly active devices, viac v [LICENSE](LICENSE).
