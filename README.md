# meet-transcriber

iPhone Voice Memos → prepis do Obsidian vaultu alebo priečinka na disku.
Lokálne, offline po inštalácii. 50-min meeting = ~20 sekúnd na M-chip.

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
- Po nahrávaní na iPhone otvor Voice Memos.app na Mac (stačí raz na začiatku
  dňa / po návrate k počítaču). Beží v pozadí, iCloud začne sťahovať.
- Alebo otvor Voice Memos na iPhone — tiež triggerne sync.
- Po stiahnutí daemon spracuje za pár sekúnd.

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

Vyprodukuje `build/meet-transcriber-v1.0.pkg` (~200 MB — bundled Python
runtime + venv + Swift binárky + app code; Voz/Who modely sa stiahnu
na strane kolegu pri prvom behu). Nahraj ručne na NAS a pošli link.

## CLI príkazy

```bash
meet-transcriber doctor         # over že ffmpeg/voz-cli/who-cli/config sú OK
meet-transcriber status         # vault path, counts processed vs failed
meet-transcriber process FILE   # spracuj jeden audio súbor
meet-transcriber watch          # spravý jeden sweep (daemon ho volá)
meet-transcriber reconfigure    # vault/folder picker wizard
```
