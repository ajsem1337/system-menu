# System Menu

![Made with AI](https://img.shields.io/badge/Made%20with-AI-76ddcf)

Noctalia v5 menu with an Arch package browser, btop, Kitty and system information.
Inspired by the GNOME [Logo Menu](https://github.com/Aryan20/Logomenu) extension.

## Install

```sh
noctalia msg plugins source add ajsem-system-menu git https://github.com/ajsem1337/system-menu.git
noctalia msg plugins enable ajsem1337/system-menu
```

Add **System Menu** (`ajsem1337/system-menu:button`) through Noctalia's bar settings,
or open it directly:

```sh
noctalia msg panel-toggle ajsem1337/system-menu:menu
```

See [requirements and controls](system-menu/README.md). Dependencies are installed
separately; package actions require Arch Linux or a compatible derivative.

## Development

Tests: [package frontend](system-menu/packages/README.md),
[collector and UI](system-menu/TESTING.md). The [community submission](https://github.com/noctalia-dev/community-plugins/pull/1389)
is a draft.

## Credits

MIT — [LICENSE](LICENSE). The package workflow is inspired by Omarchy's fzf scripts;
their [MIT notice](system-menu/packages/LICENSE-OMARCHY) is retained.

## AI assistance

**Made with AI.** This project was developed with AI assistance, including code, documentation, and testing.
