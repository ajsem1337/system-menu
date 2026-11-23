# System Menu

![Made with AI](https://raw.githubusercontent.com/ajsem1337/ajsem1337/main/assets/made-with-ai.svg)

A Noctalia launcher for your package manager, system monitor and terminal,
with a native system-information panel.

## Install

```sh
noctalia msg plugins source add ajsem-system-menu git https://github.com/ajsem1337/system-menu.git
noctalia msg plugins enable ajsem1337/system-menu
```

Add `ajsem1337/system-menu:button` in bar settings, then choose your applications
in plugin settings. See [configuration and usage](system-menu/README.md).

## Development

```sh
python3 -B -m unittest discover -s tests
(cd system-menu && lua5.4 ../tests/test_ui.lua)
noctalia plugins lint system-menu
```

MIT — [LICENSE](LICENSE). Inspired by [GNOME Logo Menu](https://github.com/Aryan20/Logomenu).

---

<p align="center"><sub>Built by <a href="https://github.com/ajsem1337">ajsem</a> with AI assistance.</sub></p>
