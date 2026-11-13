# Operations and privacy

## Launching applications

System Menu is a launcher, not a package manager. Packages and Task Manager start
only the application configured by the user. The plugin does not query package
catalogs, invoke pacman/sudo/AUR helpers, install software or maintain security
scanner configuration. The separately installed application owns those actions.

- **Direct:** executes `[program, ...arguments]`, detached, without a terminal.
- **In configured terminal:** executes `[terminal, ...terminal_args,
  ...terminal_exec_args, program, ...arguments]`, detached. For terminals requiring
  one command string, an explicit advanced option encodes the child command as
  one POSIX-quoted argument; the terminal is responsible for parsing those quotes.
- **Desktop entry:** a small Python helper executes `gtk-launch ID.desktop`; the installed desktop
  entry controls Exec, Terminal, Flatpak wrapping and D-Bus activation. Command
  argument settings are inactive in this mode. A nonzero gtk-launch exit is
  reported, not retried via another provider. The helper starts gtk-launch in a
  separate session with standard input/output/error at `/dev/null`, so GUI apps
  do not inherit short-lived capture pipes or Noctalia's captured-job timeout group.
- **Terminal:** executes `[terminal, ...terminal_args]` without a child command.

All launches use direct argument arrays. There is no widget-level shell parsing, automatic
sudo, install prompt, provider fallback or network lookup. Program paths may use
`~/`; other argument strings are literal. Programs are checked for availability
before launching. Runtime failures inside a detached application are that
application’s responsibility; accepting a launch does not prove the app is healthy.

## About This System

The native About panel runs `python3 collect.py` only on opening/refresh.
It reads local OS/hardware information using `fastfetch`, `lsblk`, standard
system commands and readable system files. Missing information is omitted or
reported as unavailable. No sudo, live resource polling or external network is
used. Copy Information writes the displayed system report to the clipboard.

The widget version is read from the installed `plugin.toml` and shown at the
bottom of About, including while system information is loading or unavailable.
Distribution icons are resolved locally, with the bundled fallback retained.

## Package workflow

The previous bundled workflow now lives in the independent, optional
[package-menu repository](https://github.com/ajsem1337/package-menu). Its package
operations, reports, dependencies and local configuration are documented there.
