# System Menu

![Made with AI](https://img.shields.io/badge/Made%20with-AI-76ddcf)

A Noctalia launcher for your choice of package manager, system monitor and
terminal. About This System remains a native Noctalia panel, with hardware,
software, technical details, copy/refresh and the installed widget version.
The bar, menu and About panel use your distribution's logo.

## Requirements

- Noctalia plugin API 43+.
- `python3` (3.11+) and `fastfetch` for About; standard Linux tools such as `lsblk`.
- Your chosen applications, installed separately. Nothing is auto-installed.
- `gtk-launch` (GTK 3 tools) only when using Desktop entry mode.

The launcher is not Arch-specific. The separate, optional
[package-menu TUI](https://github.com/ajsem1337/package-menu) is for Arch Linux.
No package manager, monitor, fzf, AUR helper or package-menu is a plugin dependency.

## Settings

Open **Settings → Plugins → System Menu**. Packages and Task Manager each have
three independent settings:

| Setting | Meaning |
| --- | --- |
| Launch mode | **Direct** for GUI/custom commands; **In configured terminal** for TUIs; **Desktop entry** for an installed desktop ID |
| Executable or desktop ID | Program name or absolute path in Direct/Terminal mode; desktop ID in Desktop entry mode |
| Arguments | One argument per item; active only in Direct/Terminal mode |

Neither application is preselected. Choose whichever you use; there is no fixed
provider list and no fallback to our own software. An unconfigured action shows
where to configure it, rather than starting a different application.

### Examples

| Application | Mode | Executable / ID | Argument items |
| --- | --- | --- | --- |
| Pacseek | In configured terminal | `pacseek` | As needed |
| Pacsea | In configured terminal | `pacsea` | As needed |
| Our optional TUI | In configured terminal | `package-menu` | Optional: `--aur-helper`, `yay` |
| GNOME Software | Direct | `gnome-software` | As needed |
| GNOME Software, native desktop launch | Desktop entry | `org.gnome.Software.desktop` | Inactive |
| Mission Center | Direct | `missioncenter` | As needed |
| Mission Center, native desktop launch | Desktop entry | `io.missioncenter.MissionCenter.desktop` | Inactive |
| btop / htop | In configured terminal | `btop` / `htop` | As needed |
| Flatpak GUI | Direct | `flatpak` | `run`, then the installed app ID |

For Shelly or any other application, use its actual installed executable or
desktop ID. Desktop IDs can be found in the filenames under
`~/.local/share/applications`, `/usr/share/applications` or Flatpak exports.
Desktop mode delegates Exec, Terminal and D-Bus activation to `gtk-launch`;
it does not reinterpret the desktop file or append custom command-line arguments.
An entry with `Terminal=true` uses the desktop environment's terminal selection,
not this widget's terminal. Use Terminal mode when you want the widget's terminal.

### Terminal options

| Setting | Default | Meaning |
| --- | --- | --- |
| Terminal executable | `kitty` | Program name/path, without arguments |
| Advanced terminal options | Off | Show the terminal argument lists and command format |
| Terminal arguments | Empty | Options used for an empty terminal and for TUI launchers |
| Run-program arguments | `-e` | Separator/options before a TUI command |
| Terminal child-command format | Separate arguments | Use one quoted string only when the terminal expects it |

Use `-e` for Kitty/foot/Alacritty, `--` for GNOME Terminal, or an empty list for a
terminal that accepts the command directly. Other terminals may need multiple
items, such as `start`, `--` for WezTerm. Consult that terminal's launch syntax.
The assembled command is:

```text
TERMINAL [terminal arguments] [run-program arguments] PROGRAM [program arguments]
```

Hidden argument lists retain their values. Terminal options do not affect Direct
or Desktop entry mode. Commands are never guessed from application names.
For a terminal option that expects a single command string (rather than argv),
choose **One POSIX-quoted command string**: the program and every argument are
escaped automatically and passed as one terminal argument. Do not prequote them.
This requires the terminal to parse POSIX-style quotes; it is not needed for
the recommended argv-style examples above.

### Literal arguments

Arguments are passed as an array, not through a shell. Do not add shell quotes,
combine a command and options in the executable field, or use aliases, pipes,
redirections, `$VARIABLE` or `$(...)`. A path containing spaces stays one item.
`~/` is expanded only in executable paths; argument items are always literal.
For custom environment variables, choose `env` as the executable with arguments
such as `NAME=value`, `program`, `--option` (in the appropriate launch mode).
Executable checks use the PATH inherited by Noctalia; an absolute path avoids PATH
differences. Missing applications produce an error; nothing is installed/retried.

## Upgrading from 1.x

Version 2.0 separates the package TUI from the widget. Install
[package-menu](https://github.com/ajsem1337/package-menu) only if you want to keep
using it, then choose `package-menu` and **In configured terminal** in settings.
Alternatively choose any other package application. Configure Task Manager too
(e.g. `missioncenter` + Direct or `btop` + In configured terminal).

Existing terminal settings are retained. The old widget `aur_helper` setting is
no longer used; pass `--aur-helper`, `yay` to package-menu itself if needed.
VirusTotal's local key remains at `~/.config/package-menu/virustotal.key`.
No preferences are silently rewritten and no Noctalia override is needed.

## Usage

Add `ajsem1337/system-menu:button` through bar settings, or open either panel:

```sh
noctalia msg panel-toggle ajsem1337/system-menu:menu
noctalia msg panel-toggle ajsem1337/system-menu:about
```

See [operations and privacy](OPERATIONS.md).

## Credits

MIT. Inspired by GNOME's [Logo Menu](https://github.com/Aryan20/Logomenu).

## AI assistance

**Made with AI.** Developed with AI assistance, including code, documentation and tests.
