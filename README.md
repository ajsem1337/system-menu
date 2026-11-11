# System Menu

![Made with AI](https://img.shields.io/badge/Made%20with-AI-76ddcf)

Noctalia v5 system menu with an Arch package browser and system information.
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

See [settings, requirements and controls](system-menu/README.md).

## Development

```sh
python3 -B -m unittest discover -s tests -v
(cd system-menu && lua5.4 ../tests/test_ui.lua)
noctalia plugins lint system-menu
```

Tests stay outside the installed plugin. They use mocked network/transactions,
real fzf filters (0.74.5+) and Lua UI stubs. The
[community PR](https://github.com/noctalia-dev/community-plugins/pull/1389) remains
a draft pending human review, screenshots and cross-compositor testing.

## Credits

MIT — [LICENSE](LICENSE). The package workflow is inspired by Omarchy's fzf scripts;
their [MIT notice](system-menu/packages/LICENSE-OMARCHY) is retained.

## AI assistance

**Made with AI.** This project was developed with AI assistance, including code, documentation, and testing.
