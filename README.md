# System Menu

[![AI-assisted](https://img.shields.io/badge/AI--assisted-development-8A2BE2)](#ai-disclosure)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A small Noctalia v5 system menu: Packages, btop, Kitty and About This System.
The package browser is a bundled Python-standard-library frontend for fzf,
pacman and paru, not a new package manager or a background service.

See the [plugin documentation](system-menu/README.md) for requirements, controls,
installation, privacy and security limitations.

## Install from this repository

```sh
noctalia msg plugins source add ajsem-system-menu git https://github.com/ajsem1337/system-menu.git
noctalia msg plugins enable ajsem1337/system-menu
noctalia msg panel-toggle ajsem1337/system-menu:menu
```

Add the **System Menu** widget (`ajsem1337/system-menu:button`) to a bar through
Noctalia's bar settings. Existing custom buttons can instead invoke
`panel-toggle ajsem1337/system-menu:menu`.

This is a development submission; a draft community PR is not an endorsement
or acceptance by Noctalia. Nothing here installs dependencies, edits pacman/paru,
or downloads and executes setup scripts for you.

## Tests

```sh
python3 -B -m unittest discover -s system-menu/packages -p 'test_*.py' -v
python3 -B -m unittest discover -s system-menu -p 'test_collect.py' -v
(cd system-menu && lua test_ui.lua)
noctalia plugins lint system-menu
```

The tests mock package transactions and API responses; real fzf filter tests do
not require a graphical session, root access or network access.

## Credits

Inspired by Omarchy's fzf package scripts; their MIT notice is preserved in
[`LICENSE-OMARCHY`](system-menu/packages/LICENSE-OMARCHY). Traur, fzf, paru,
pacman, downgrade, btop, Kitty and Noctalia are separate projects.

## AI disclosure

Built with AI assistance using OpenCode. Maintained by
[ajsem1337](https://github.com/ajsem1337). AI assistance and passing tests do not
constitute a security audit.

---

AI-assisted development · Human review required · MIT licensed
