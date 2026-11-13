# System Menu

![Made with AI](https://img.shields.io/badge/Made%20with-AI-76ddcf)

Noctalia v5 launcher for your choice of package manager, system monitor and terminal,
with a native system-information panel. Supports GUI commands, terminal TUIs and
desktop entries, without a required package manager or monitor.
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

Tests stay outside the installed plugin. They use mocked system-information
commands and Lua UI stubs; no applications or package transactions are started. The
[community PR](https://github.com/noctalia-dev/community-plugins/pull/1389) remains
a draft pending human review, screenshots and cross-compositor testing.

## Credits

MIT — [LICENSE](LICENSE).

## Separate package TUI

The former bundled frontend is now [package-menu](https://github.com/ajsem1337/package-menu),
with its own history, releases and installation. It runs without Noctalia and is
one optional launcher target, never a requirement. Version 2.0 users choose their
Packages and Task Manager applications in plugin settings; see the
[migration guide](system-menu/README.md#upgrading-from-1x).

## AI assistance

**Made with AI.** This project was developed with AI assistance, including code, documentation, and testing.
