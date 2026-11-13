import contextlib
import hashlib
import io
import json
import shlex
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "system-menu/packages"))
import app


def package(name="example", kind="repo", source="cachyos-v3"):
    return {"id": f"{source}/{name}", "name": name, "source": source, "version": "1.0-1", "kind": kind}


@contextlib.contextmanager
def preview_catalog(record, mode="summary"):
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "catalog.json"
        database.write_text(json.dumps({record["id"]: record}))
        (database.parent / "preview-mode").write_text(mode)
        yield database


def render_preview(database, record):
    with contextlib.redirect_stdout(io.StringIO()) as output:
        app.preview(database, record["id"])
    return output.getvalue()


class PackageMenuTests(unittest.TestCase):
    def setUp(self):
        helper = patch.object(app, "AUR_HELPER", "paru")
        helper.start()
        self.addCleanup(helper.stop)

    def test_custom_helper_is_used_for_aur_search_install_and_update(self):
        for helper in ("paru", "yay", "/opt/my helper/bin/custom-helper"):
            with self.subTest(helper=helper):
                app.configure_helper(helper)
                with patch.object(app, "capture", return_value="aur/example 1.0\n    Example\n") as capture:
                    self.assertEqual(app.catalog("aur", "example")[0]["name"], "example")
                self.assertEqual(capture.call_args.args[0], [helper, "-Ssa", "--color", "never", "--", "example"])
                self.assertEqual(app.transaction_command("install", [package(kind="aur", source="aur")]),
                                 [helper, "-S", "--needed", "--aur", "--", "example"])
                self.assertEqual(app.update_command(), [helper, "-Syu"])
                self.assertEqual(app.transaction_command("install", [package()])[0:2], ["sudo", "pacman"])
                self.assertEqual(app.transaction_command("remove", [package(kind="installed")])[0:2], ["sudo", "pacman"])

    def test_helper_cli_and_callback_commands_preserve_executable_as_one_argument(self):
        helper = "/opt/helper with spaces;$(literal)/yay"
        with patch.object(app, "main") as main:
            app.run(["--aur-helper", helper])
            main.assert_called_once_with()
        command = app.frontend_command("--preview", "/tmp/catalog.json")
        self.assertEqual(shlex.split(shlex.join(command)), command)
        self.assertEqual(command[3:5], ["--aur-helper", helper])
        with patch.object(app, "capture", return_value=""), patch.object(app.subprocess, "run", return_value=subprocess.CompletedProcess([], 130, "")) as run:
            app.picker([], "Install", merged=True)
        args = run.call_args.args[0]
        for option in ("--bind=start:", "--preview=", "--bind=shift-left:"):
            self.assertTrue(any(arg.startswith(option) and shlex.quote(helper) in arg for arg in args))

    def test_helper_validation_rejects_empty_control_characters_and_options(self):
        for value in ("", "  ", "--noconfirm", "bad\ncommand", "bad\x00command", "bad\x7fcommand"):
            with self.subTest(value=value), self.assertRaises(app.Error):
                app.configure_helper(value)
        with self.assertRaises(app.Error):
            app.run(["--aur-helper"])

    def test_custom_helper_is_executed_without_shell_parsing(self):
        with tempfile.TemporaryDirectory() as directory:
            helper = Path(directory) / "helper with spaces;literal"
            helper.write_text("#!/bin/sh\nprintf 'aur/example 1.0\\n    Example\\n'\n")
            helper.chmod(0o700)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                app.run(["--aur-helper", str(helper), "--list", "aur", "example"])
        self.assertEqual(json.loads(output.getvalue())[0]["name"], "example")

    def test_update_action_uses_helper_without_extra_confirmation_or_success_pause(self):
        app.configure_helper("yay")
        selection = ("", "", [{"id": "update"}])
        with patch.object(app, "picker", side_effect=[selection, None]), patch.object(app, "confirm", side_effect=AssertionError("no duplicate prompt")), patch.object(app.subprocess, "call", return_value=0) as call, patch.object(app, "pause") as pause:
            app.main()
        call.assert_called_once_with(["yay", "-Syu"])
        pause.assert_not_called()
        self.assertNotIn("--noconfirm", call.call_args.args[0])

    def test_update_error_is_displayed_and_paused(self):
        selection = ("", "", [{"id": "update"}])
        with patch.object(app, "picker", side_effect=[selection, None]), patch.object(app.subprocess, "call", return_value=7), patch.object(app, "pause") as pause, contextlib.redirect_stdout(io.StringIO()) as output:
            app.main()
        self.assertIn("System update stopped (exit 7)", output.getvalue())
        pause.assert_called_once_with()

    def test_missing_custom_helper_does_not_fall_back_or_block_repo_commands(self):
        app.configure_helper("missing-custom-helper")
        records = [package(kind="aur", source="aur")]
        with patch.object(app, "confirm", return_value=True), patch.object(app.subprocess, "call", side_effect=FileNotFoundError("missing helper")) as call, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(FileNotFoundError):
                app.perform("install", records)
        call.assert_called_once_with(["missing-custom-helper", "-S", "--needed", "--aur", "--", "example"])
        self.assertEqual(app.transaction_command("install", [package()])[0:2], ["sudo", "pacman"])

    def filter_records(self, records, query):
        result = subprocess.run(["fzf", *app.search_options(), "--filter=" + query],
                                input=app.picker_rows(sorted(records, key=app.source_order)), text=True, capture_output=True)
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return [line.split("\t", 1)[0] for line in result.stdout.splitlines()]

    def test_real_fzf_steam_matches_names_not_descriptions_sources_or_fuzzy_letters(self):
        records = [package("binutils"), package("some-tool-example-am"),
                   package("unrelated", source="steam"), package("steam-devices"), package("steam")]
        records[0]["description"] = "Steam tools"
        self.assertEqual(self.filter_records(records, "steam"),
                         ["cachyos-v3/steam", "cachyos-v3/steam-devices"])

    def test_real_fzf_keeps_source_groups_not_description_length(self):
        records = [package("steam", source="cachyos"), package("steam", source="multilib")]
        records[0]["description"] = "Long description " * 30
        self.assertEqual(self.filter_records(records, "STEAM"), ["multilib/steam", "cachyos/steam"])

    def test_real_fzf_groups_sources_and_sorts_names_alphabetically(self):
        records = [package("steam-z", kind="aur", source="aur"),
                   package("steam-z", source="cachyos"), package("steam-z", source="multilib"),
                   package("steam-a", source="multilib"), package("steam-a", kind="aur", source="aur")]
        self.assertEqual(self.filter_records(records, "steam"),
                         ["multilib/steam-a", "multilib/steam-z", "cachyos/steam-z", "aur/steam-a", "aur/steam-z"])

    def test_aur_rpc_search_is_name_only_and_marks_installed(self):
        response = io.BytesIO(json.dumps({"type": "search", "results": [
            {"Name": "steam-test", "Version": "1", "Description": "Test"},
            {"Name": "other", "Version": "1", "Description": "steam"}]}).encode())
        with patch.object(app.urllib.request, "urlopen", return_value=response) as send:
            records = app.aur_search("steam", {"steam-test"})
        self.assertTrue(send.call_args.args[0].endswith("/steam?by=name"))
        self.assertEqual([record["id"] for record in records], ["aur/steam-test"])
        self.assertEqual(records[0]["state"], "installed")

    def test_merged_search_preserves_previous_selections_and_reports_aur_failure(self):
        records = [package("steam"), package("old-aur-selection", kind="aur", source="aur")]
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            database = directory / "catalog.json"
            database.write_text(json.dumps({record["id"]: record for record in records}))
            (directory / "installed.json").write_text("[]")
            (directory / "header.txt").write_text("SOURCE PACKAGE")
            with patch.object(app.time, "sleep"), patch.object(app, "aur_search", side_effect=OSError("offline")), contextlib.redirect_stdout(io.StringIO()) as output:
                app.merged_search(database, "steam")
            self.assertIn("cachyos-v3/steam", output.getvalue())
            self.assertIn("old-aur-selection", output.getvalue())
            self.assertIn("aur/old-aur-selection", json.loads(database.read_text()))
            self.assertIn("AUR unavailable", (directory / "status.txt").read_text())

    def test_mixed_install_keeps_exact_targets_and_existing_aur_gate(self):
        records = [package("repo-package", source="multilib"), package("aur-package", kind="aur", source="aur")]
        self.assertEqual(app.transaction_commands("install", records), [
            ["sudo", "pacman", "-S", "--needed", "--", "multilib/repo-package"],
            ["paru", "-S", "--needed", "--aur", "--", "aur-package"]])
        with self.assertRaises(app.Error):
            app.transaction_commands("install", [package("steam"), package("steam", kind="aur", source="aur")])

    def test_merged_search_adds_aur_and_keeps_short_queries_local(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            database = directory / "catalog.json"
            record = package("steam", source="multilib")
            database.write_text(json.dumps({record["id"]: record}))
            (directory / "installed.json").write_text('["steam-test"]')
            (directory / "header.txt").write_text("SOURCE PACKAGE")
            with patch.object(app.time, "sleep"), patch.object(app, "aur_search", return_value=[package("steam-test", kind="aur", source="aur")]) as search, contextlib.redirect_stdout(io.StringIO()) as output:
                app.merged_search(database, "s")
                search.assert_not_called()
                app.merged_search(database, "steam")
                search.assert_called_once_with("steam", {"steam-test"})
            lookup = json.loads(database.read_text())
            self.assertIn("multilib/steam", lookup)
            self.assertIn("aur/steam-test", lookup)
            self.assertIn("aur/steam-test", output.getvalue())

    def test_install_picker_automatically_reloads_both_sources(self):
        with patch.object(app, "capture", return_value="steam\n"), patch.object(app.subprocess, "run", return_value=subprocess.CompletedProcess([], 130, "")) as run:
            app.picker([package("steam")], "Install", merged=True)
        args = run.call_args.args[0]
        self.assertIn("--id-nth=1", args)
        self.assertIn("--no-sort", args)
        self.assertTrue(any("change:reload-sync(" in arg for arg in args))
        self.assertNotIn("--expect=alt-a,alt-r,alt-t", args)

    def test_failed_repo_transaction_does_not_start_aur_transaction(self):
        records = [package("repo-package"), package("aur-package", kind="aur", source="aur")]
        with patch.object(app, "confirm", return_value=True), patch.object(app.subprocess, "call", return_value=1) as call, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(app.Error):
                app.perform("install", records)
        self.assertEqual(call.call_count, 1)

    def test_real_fzf_searches_full_names_and_treats_query_literally(self):
        record = package("very-long-package-name-beyond-column-steam")
        self.assertEqual(self.filter_records([record], "steam"), [record["id"]])
        self.assertEqual(self.filter_records([record], "steam | binutils"), [])

    def test_colored_rows_keep_ids_plain_and_sources_distinct(self):
        records = [package("steam", source="multilib"), package("steam-test", source="cachyos"),
                   package("steam-test", kind="aur", source="aur")]
        records[0]["state"] = "installed"
        with patch.object(app, "theme_options", return_value=[]):
            rows = app.picker_rows(records).splitlines()
        fields = [row.split("\t") for row in rows]
        self.assertEqual([row[0] for row in fields], [record["id"] for record in records])
        self.assertTrue(all("\033[1;" in row[1] for row in fields))
        self.assertEqual(len({row[2].split("m", 1)[0] for row in fields}), 3)
        self.assertIn("[Installed]", rows[0])
        self.assertIn("--ansi", app.search_options())

    def test_third_party_sources_get_stable_automatic_colors(self):
        sources = ("chaotic-aur", "omarchy", "garuda", "my-new-repository")
        colors = {source: app.source_color(source, "repo", {}) for source in sources}
        self.assertEqual(len(set(colors.values())), len(sources))
        for source, color in colors.items():
            self.assertRegex(color, r"^#[0-9a-f]{6}$")
            self.assertEqual(app.source_color(source.upper(), "repo", {}), color)
        self.assertNotEqual(colors["chaotic-aur"], app.source_color("aur", "aur", {}))
        self.assertNotEqual(colors["chaotic-aur"], app.source_color("extra", "repo", {}))

    def test_source_colors_do_not_depend_on_visible_rows(self):
        records = [package("test", source=source) for source in ("chaotic-aur", "garuda", "omarchy")]
        with patch.object(app, "theme_options", return_value=[]):
            together = [row.split("\t")[2] for row in app.picker_rows(records).splitlines()]
            separately = [app.picker_rows([record]).split("\t")[2] for record in records]
        self.assertEqual(together, separately)

    def test_installed_list_hides_state_column_but_search_keeps_it(self):
        record = package("steam", kind="installed", source="multilib")
        record["state"] = "installed"
        with patch.object(app.subprocess, "run", return_value=subprocess.CompletedProcess([], 130, "")) as run:
            app.picker([record], "Installed", show_state=False)
            args = run.call_args.args[0]
            header = next(arg for arg in args if arg.startswith("--header="))
            self.assertNotIn("STATE", header)
            self.assertNotIn("[Installed]", run.call_args.kwargs["input"])
            app.picker([record], "Search")
            header = next(arg for arg in run.call_args.args[0] if arg.startswith("--header="))
            self.assertIn("STATE", header)
            self.assertIn("[Installed]", run.call_args.kwargs["input"])

    def test_browse_shows_state_only_when_searching_for_install(self):
        with patch.object(app, "catalog", return_value=[]), patch.object(app, "picker", return_value=None) as picker, contextlib.redirect_stdout(io.StringIO()):
            for action in ("remove", "downgrade", "install"):
                app.browse(action)
                self.assertEqual(picker.call_args.kwargs["show_state"], action == "install")

    def test_picker_preserves_original_ids_for_preview_and_multiselection(self):
        records = [package("steam"), package("steam-devices")]
        result = subprocess.CompletedProcess([], 0, "steam\n\n" + app.picker_rows(records) + "\n")
        with patch.object(app.subprocess, "run", return_value=result) as run:
            selected = app.picker(records, "Test")
        self.assertEqual(selected, ("steam", "", records))
        self.assertIn("--no-hscroll", run.call_args.args[0])
        self.assertIn("--no-separator", run.call_args.args[0])
        self.assertTrue(any("shift-left:transform(" in arg and "shift-right:transform(" in arg
                            for arg in run.call_args.args[0]))
        self.assertNotIn("--no-input", run.call_args.args[0])
        self.assertTrue(any(arg.endswith(" {1}") for arg in run.call_args.args[0]))
        header = next(arg for arg in run.call_args.args[0] if arg.startswith("--header="))
        self.assertIn("Alt+P preview · Alt+T Traur audit", header)
        self.assertNotIn("A–Z per source", header)

    def test_preview_resize_moves_divider_in_both_directions_and_stops_at_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preview-size"
            path.write_text("48")
            self.assertEqual(app.resize_preview(path, 5), "change-preview-window(right,53%,wrap)+refresh-preview")
            self.assertEqual(app.resize_preview(path, -5), "change-preview-window(right,48%,wrap)+refresh-preview")
            for _ in range(20):
                app.resize_preview(path, 5)
            self.assertEqual(path.read_text(), "75")
            for _ in range(20):
                app.resize_preview(path, -5)
            self.assertEqual(path.read_text(), "25")

    def test_main_menu_has_no_search_input(self):
        with patch.object(app.subprocess, "run", return_value=subprocess.CompletedProcess([], 130, "")) as run:
            app.main()
        self.assertIn("--no-input", run.call_args.args[0])
        self.assertIn("--disabled", run.call_args.args[0])
        self.assertFalse(any(arg.startswith("--prompt=") for arg in run.call_args.args[0]))

    def test_main_menu_does_not_include_pacseek(self):
        with patch.object(app, "picker", return_value=None) as picker:
            app.main()
        self.assertNotIn("pacseek", [record["id"] for record in picker.call_args.args[0]])

    def test_orphan_cleanup_is_directly_below_installed(self):
        with patch.object(app, "picker", return_value=None) as picker:
            app.main()
        actions = [record["id"] for record in picker.call_args.args[0]]
        self.assertEqual(actions[actions.index("remove") + 1], "orphans")

    def test_console_clear_is_terminal_only(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            app.clear_console()
            self.assertEqual(output.getvalue(), "")
            with patch.object(output, "isatty", return_value=True):
                app.clear_console()
            self.assertEqual(output.getvalue(), "\033[2J\033[3J\033[H")

    def test_pause_keeps_results_until_acknowledged_then_clears(self):
        with patch.object(app, "clear_console") as clear:
            def acknowledge(prompt):
                clear.assert_not_called()
                return ""
            with patch("builtins.input", side_effect=acknowledge):
                app.pause()
            clear.assert_called_once_with()

    def test_search_preserves_sources_priority_and_descriptions(self):
        records = app.parse_search("cachyos-v3/example 2.0-1 [installed]\n    Fast example\nextra/example 1.0-1\n    Another build\n", "repo")
        self.assertEqual([record["id"] for record in records], ["cachyos-v3/example", "extra/example"])
        self.assertEqual(records[0]["state"], "installed")
        self.assertEqual(records[1]["description"], "Another build")

    def test_installed_origin_uses_real_field_not_aur_guess(self):
        output = "Installed From  : cachyos-v3\nName            : example\nVersion         : 1.0\nDescription     : One\n\nInstalled From  : None\nName            : foreign\nVersion         : 2.0\nDescription     : Two\n"
        records = app.parse_installed(output)
        self.assertEqual(records[0]["source"], "cachyos-v3")
        self.assertEqual(records[1]["source"], "local/unknown")

    def installed_catalog(self, installed, repositories="", aur=()):
        with patch.object(app, "capture", side_effect=[installed, repositories]), patch.object(app, "aur_info", return_value=set(aur)):
            return app.catalog("installed")

    def test_installed_missing_and_empty_origin_are_unresolved_not_aur_guesses(self):
        for origin in ("", "Installed From  : \n", "Installed From  : None\n"):
            records = app.parse_installed(origin + "Name            : local-bin\nVersion         : 1.0\n")
            self.assertEqual(records[0]["source"], "local/unknown")

    def test_installed_sources_resolve_all_repositories_before_aur(self):
        output = ("Name            : anydesk-bin\nVersion         : 1\n\n"
                  "Name            : mingw-w64-binutils\nVersion         : 2.47-1.1\n\n"
                  "Name            : custom-tool\nVersion         : 1\n\n"
                  "Installed From  : omarchy\nName            : visual-studio-code-bin\nVersion         : 1\n")
        repos = ("extra mingw-w64-binutils 2.47-1\n"
                 "cachyos-extra-v3 mingw-w64-binutils 2.47-1.1\n"
                 "new-repo custom-tool 2\n")
        with patch.object(app, "capture", side_effect=[output, repos]) as capture, patch.object(app, "aur_info", return_value={"anydesk-bin"}) as info:
            records = app.catalog("installed")
        self.assertEqual([r["source"] for r in records], ["aur", "cachyos-extra-v3", "new-repo", "omarchy"])
        info.assert_called_once_with(["anydesk-bin"])
        self.assertEqual([call.args[0] for call in capture.call_args_list], [["pacman", "-Qi"], ["pacman", "-Sl"]])
        self.assertTrue(all(r["kind"] == "installed" and r["id"] == "installed/" + r["name"] for r in records))
        self.assertIn("version differs", records[2]["source_detail"])
        self.assertNotIn("source_detail", records[3])

    def test_installed_repo_ties_follow_pacman_priority_not_alphabetical_order(self):
        output = "Name            : example\nVersion         : 1.0-1\n"
        for repositories in ("z-repo example 1.0-1\na-repo example 1.0-1\n",
                             "z-repo example 2.0-1\na-repo example 3.0-1\n"):
            records = self.installed_catalog(output, repositories)
            self.assertEqual(records[0]["source"], "z-repo")

    def test_installed_recorded_origin_is_not_overwritten_by_current_availability(self):
        output = ("Installed From  : removed-repo\nName            : example\nVersion         : 1\n\n"
                  "Name            : foreign\nVersion         : 1\n")
        records = self.installed_catalog(output, "extra example 1\n", {"foreign"})
        self.assertEqual([r["source"] for r in records], ["removed-repo", "aur"])

    def test_installed_recorded_origins_need_no_lookup(self):
        with patch.object(app, "capture", return_value="Installed From  : extra\nName            : example\n") as capture, patch.object(app.urllib.request, "urlopen") as send:
            self.assertEqual(app.catalog("installed")[0]["source"], "extra")
        capture.assert_called_once_with(["pacman", "-Qi"])
        send.assert_not_called()

    def test_installed_unmatched_local_bin_and_git_packages_stay_unknown(self):
        output = "Name            : local-bin\nVersion         : 1\n\nName            : local-git\nVersion         : 1\n"
        records = self.installed_catalog(output)
        self.assertEqual([r["source"] for r in records], ["local/unknown", "local/unknown"])
        self.assertIn("No recorded origin", records[0]["source_detail"])

    def test_installed_aur_failure_preserves_repos_and_removal(self):
        output = "Name            : repo-tool\nVersion         : 1\n\nName            : aur-tool\nVersion         : 1\n"
        for error in (OSError("offline"), ValueError("bad JSON"), app.Error("invalid response")):
            with patch.object(app, "capture", side_effect=[output, "extra repo-tool 1\n"]), patch.object(app, "aur_info", side_effect=error), contextlib.redirect_stderr(io.StringIO()) as warning:
                records = app.catalog("installed")
            self.assertEqual([r["source"] for r in records], ["extra", "local/unknown"])
            self.assertIn("AUR source lookup unavailable", warning.getvalue())
            self.assertIn("AUR lookup unavailable", records[1]["source_detail"])
            self.assertEqual(app.transaction_command("remove", records), ["sudo", "pacman", "-Rns", "--", "repo-tool", "aur-tool"])

    def test_installed_repo_failure_does_not_misclassify_packages_as_aur(self):
        with patch.object(app, "capture", side_effect=["Name            : example\n", app.Error("missing database")]), patch.object(app, "aur_info") as info, contextlib.redirect_stderr(io.StringIO()):
            records = app.catalog("installed")
        info.assert_not_called()
        self.assertEqual(records[0]["source"], "local/unknown")
        self.assertIn("missing database", records[0]["source_detail"])

    def test_installed_aur_is_last_yellow_and_remains_an_installed_selection(self):
        records = [package("aur-bin", "installed", "aur"), package("repo-bin", "installed", "extra"),
                   package("cachy-bin", "installed", "cachyos"), package("local-bin", "installed", "local/unknown")]
        self.assertEqual(self.filter_records(records, "-bin"),
                         ["extra/repo-bin", "local/unknown/local-bin", "cachyos/cachy-bin", "aur/aur-bin"])
        self.assertEqual(app.source_color("aur", "installed", {}), app.source_color("aur", "aur", {}))
        self.assertIn("AUR ", app.picker_rows(records, show_state=False))
        self.assertEqual(app.transaction_command("remove", records[:1]), ["sudo", "pacman", "-Rns", "--", "aur-bin"])

    def test_installed_preview_explains_inferred_source_and_uses_pacman_qi(self):
        record = package("example", "installed", "aur")
        record["source_detail"] = "Exact package name found in AUR; installation origin was not recorded."
        with preview_catalog(record, "details") as database, patch.object(app, "preview_aur"), patch.object(app, "capture", return_value="Installed metadata") as capture:
            output = render_preview(database, record)
        capture.assert_called_once_with(["pacman", "-Qi", "--", "example"])
        self.assertIn(record["source_detail"], output)

    def test_aur_preview_summary_details_and_session_cache(self):
        record = package(kind="aur", source="aur")
        item = {"Name": "example", "Version": "1.0-1", "Description": "A useful tool", "Maintainer": "alice",
                "NumVotes": 248, "Popularity": 2.003, "License": ["MIT"], "Depends": ["glibc"],
                "URL": "https://example.org", "LastModified": 1700000000, "MakeDepends": ["gcc"]}
        with preview_catalog(record) as database, patch.object(app, "aur_info", return_value={"example": item}) as info:
            summary = render_preview(database, record)
            self.assertTrue(all(value in summary for value in ("alice", "248", "2.003", "MIT", "glibc", "Alt+D", "Alt+B")))
            self.assertTrue(all(value not in summary for value in ("Source:", "https://", "Modified", "gcc", "safe")))
            self.assertEqual(summary.splitlines()[0], "example")
            self.assertEqual(summary.count("1.0-1"), 1)
            self.assertEqual(app.preview_mode(database, "details"), "refresh-preview")
            details = render_preview(database, record)
            self.assertTrue(all(value in details for value in ("https://example.org", "Modified", "gcc")))
            app.preview_mode(database, "details")
            self.assertEqual(render_preview(database, record), summary)
        info.assert_called_once_with(["example"])

    def test_aur_recipe_uses_split_base_is_cached_and_never_executed(self):
        record = package(kind="aur", source="aur")
        recipe = b'pkgname=example\n# never execute\ntouch /not-executed\n\x1b[31mtext\x00\n'
        with preview_catalog(record, "recipe") as database, patch.object(app, "aur_info", return_value={"example": {"PackageBase": "split-base"}}), patch.object(app.urllib.request, "urlopen", return_value=io.BytesIO(recipe)) as send, patch.object(app, "capture") as capture:
            output = render_preview(database, record)
            self.assertIn("touch /not-executed", output)
            self.assertIn("read-only", output)
            self.assertNotIn("\x1b", output)
            self.assertNotIn("\x00", output)
            self.assertEqual(render_preview(database, record), output)
            self.assertEqual(send.call_count, 1)
            self.assertTrue(send.call_args.args[0].endswith("plain/PKGBUILD?h=split-base"))
            capture.assert_not_called()

    def test_aur_preview_handles_orphans_old_installed_versions_and_flags(self):
        record = package(kind="installed", source="aur")
        local = "Description     : Installed description\nDepends On      : installed-dep\nInstall Date    : Local date\n"
        with preview_catalog(record) as database, patch.object(app, "aur_info", return_value={"example": {"Maintainer": None, "Version": "2.0-1", "OutOfDate": 1, "Depends": ["remote-dep"]}}), patch.object(app, "capture", return_value=local) as capture:
            output = render_preview(database, record)
        self.assertTrue(all(value in output for value in ("Orphaned", "out-of-date", "AUR version", "2.0-1")))
        self.assertIn("Description     : Installed description", output)
        self.assertNotIn("Install Date", output)
        self.assertNotIn("remote-dep", output)
        self.assertLess(output.index("Installed description"), output.index("Maintainer"))
        capture.assert_called_once_with(["pacman", "-Qi", "--", "example"])

    def test_aur_preview_uses_pacman_columns_wrapping_and_zero_statistics(self):
        record = package(kind="aur", source="aur")
        item = {"Description": "A long package description " * 5, "NumVotes": 0, "Popularity": 0,
                "Depends": ["glibc", "a-long-dependency-name", "another-dependency"]}
        with preview_catalog(record) as database, patch.object(app, "aur_info", return_value={"example": item}), patch.dict(app.os.environ, FZF_PREVIEW_COLUMNS="48"):
            output = render_preview(database, record)
        fields = output.splitlines()[1:-2]
        self.assertTrue(all(len(line) <= 48 for line in fields))
        self.assertTrue(all(line[16:18] == ": " or line.startswith(" " * 18) for line in fields))
        self.assertIn("Votes           : 0", output)
        self.assertIn("Popularity      : 0", output)
        self.assertIn("Licenses        : None", output)
        self.assertIn("Depends On      : glibc  a-long-dependency-name", output)

    def test_installed_aur_keeps_pacman_metadata_when_network_is_unavailable(self):
        record = package(kind="installed", source="aur")
        local = "Name            : example\nInstalled Size  : 42 KiB\nRequired By     : other\n"
        with preview_catalog(record) as database, patch.object(app, "aur_info", side_effect=OSError("offline")), patch.object(app, "capture", return_value=local) as capture:
            output = render_preview(database, record)
        self.assertEqual(output.splitlines()[0], "example")
        self.assertIn("Installed Size  : 42 KiB", output)
        self.assertIn("Required By     : other", output)
        self.assertIn("AUR preview unavailable: offline", output)
        capture.assert_called_once_with(["pacman", "-Qi", "--", "example"])

    def test_repo_preview_default_and_full_details_share_the_same_metadata(self):
        info = ("Name            : example\nVersion         : 1.0-1\nDescription     : Useful package\n"
                "Licenses        : MIT\nDepends On      : glibc\nInstalled Size  : 42 KiB\n"
                "Packager        : Alice\nArchitecture    : x86_64\nURL             : https://example.org\n"
                "Groups          : utils\nConflicts With  : old-tool\nReplaces        : older-tool\n"
                "Build Date      : yesterday\nOptional Deps   : extra-tool\n")
        for kind, operation in (("repo", "-Si"), ("installed", "-Qi")):
            record = package(kind=kind, source="extra")
            with preview_catalog(record) as database, patch.object(app, "capture", return_value=info) as capture:
                compact = render_preview(database, record)
                self.assertEqual(compact.splitlines()[0], "example")
                self.assertEqual(compact.count("1.0-1"), 1)
                self.assertTrue(all(value in compact for value in ("Useful package", "MIT", "glibc", "42 KiB", "Alice", "Alt+D full details")))
                self.assertTrue(all(value not in compact for value in ("Architecture", "URL", "Groups", "Conflicts", "Replaces", "Build Date", "Optional Deps", "Alt+B")))
                app.preview_mode(database, "details")
                full = render_preview(database, record)
                expected = app.parse_info(info)
                expected.pop("Name")
                self.assertEqual(app.parse_info(full), expected)
                self.assertIn("Alt+D compact view", full)
                target = record["name"] if kind == "installed" else record["id"]
                capture.assert_called_with(["pacman", operation, "--", target])
                app.preview_mode(database, "details")
                self.assertEqual(render_preview(database, record), compact)

    def test_aur_and_repo_previews_share_field_order_in_search_and_installed(self):
        info = "Version         : 1.0-1\nDescription     : Useful package\nURL             : https://example.org\nLicenses        : MIT\nDepends On      : glibc\n"
        metadata = {"Version": "1.0-1", "Description": "Useful package", "URL": "https://example.org",
                    "License": ["MIT"], "Depends": ["glibc"], "Maintainer": "alice"}
        common = ["Version", "Description", "URL", "Licenses", "Depends On"]
        for kind, source in [("repo", "extra"), ("aur", "aur"), ("installed", "extra"), ("installed", "aur")]:
            record = package(kind=kind, source=source)
            with self.subTest(kind=kind, source=source), preview_catalog(record, "details") as database, patch.object(app, "capture", return_value=info), patch.object(app, "aur_info", return_value={"example": metadata}):
                output = render_preview(database, record)
            fields = app.parse_info(output)
            self.assertEqual([key for key in fields if key in common], common)
            self.assertEqual({key: fields[key] for key in common}, app.parse_info(info))

    def test_aur_preview_errors_are_not_security_verdicts(self):
        record = dict(package(kind="aur", source="aur"), description="Cached description")
        for response in (OSError("offline"), {}, {"example": {"LastModified": "invalid"}}):
            with preview_catalog(record, "details") as database, patch.object(app, "aur_info", **({"side_effect": response} if isinstance(response, Exception) else {"return_value": response})):
                output = render_preview(database, record)
            self.assertIn("Cached description", output)
            self.assertIn("preview unavailable", output)
            self.assertNotIn("Trusted", output)

    def test_preview_mode_binding_does_not_exit_or_change_selections(self):
        with patch.object(app.subprocess, "run", return_value=subprocess.CompletedProcess([], 130, "")) as run:
            app.picker([package()], "Test")
        self.assertTrue(any("alt-d:transform(" in arg and "alt-b:transform(" in arg for arg in run.call_args.args[0]))
        with preview_catalog(package()) as database, self.assertRaises(app.Error):
            app.preview_mode(database, "invalid")

    def test_aur_info_batches_exact_names_and_includes_split_packages(self):
        names = [f"example-{index}" for index in range(101)] + ["libc++"]
        responses = [io.BytesIO(json.dumps({"type": "multiinfo", "results": [{"Name": "example-0"}]}).encode()),
                     io.BytesIO(json.dumps({"type": "multiinfo", "results": [{"Name": "libc++", "PackageBase": "libcxx"}]}).encode())]
        with patch.object(app.urllib.request, "urlopen", side_effect=responses) as send:
            self.assertEqual(set(app.aur_info(names)), {"example-0", "libc++"})
        self.assertEqual(send.call_count, 2)
        for call, expected in zip(send.call_args_list, (names[:100], names[100:])):
            url = app.urllib.parse.urlsplit(call.args[0])
            self.assertEqual(url.path, "/rpc/v5/info")
            self.assertEqual(app.urllib.parse.parse_qs(url.query), {"arg[]": expected})

    def test_aur_info_empty_list_does_not_use_network(self):
        with patch.object(app.urllib.request, "urlopen") as send:
            self.assertEqual(app.aur_info([]), {})
        send.assert_not_called()

    def test_aur_info_rejects_invalid_and_unrequested_results(self):
        for data in ([], {"type": "error", "results": []}, {"type": "multiinfo", "results": "bad"},
                     {"type": "multiinfo", "results": [{}]}, {"type": "multiinfo", "results": [{"Name": "other"}]}):
            with patch.object(app.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(data).encode())):
                with self.assertRaises(app.Error):
                    app.aur_info(["example"])

    def test_multiselect_install_keeps_exact_repo_targets_and_confirmation(self):
        command = app.transaction_command("install", [package("one"), package("two", source="extra")])
        self.assertEqual(command, ["sudo", "pacman", "-S", "--needed", "--", "cachyos-v3/one", "extra/two"])
        self.assertNotIn("--noconfirm", command)

    def test_aur_delegates_to_existing_paru_integration(self):
        command = app.transaction_command("install", [package(kind="aur", source="aur")])
        self.assertEqual(command, ["paru", "-S", "--needed", "--aur", "--", "example"])
        self.assertNotIn("--makepkg", command)
        self.assertNotIn("--skipreview", command)

    def test_duplicate_source_choice_and_option_injection_are_rejected(self):
        for records in [[package(), package(source="extra")], [package("--noconfirm")]]:
            with self.assertRaises(app.Error):
                app.transaction_command("install", records)

    def test_accidental_select_all_cannot_install_the_whole_catalog(self):
        with self.assertRaises(app.Error):
            app.transaction_command("install", [package(f"package-{index}") for index in range(51)])

    def test_remove_accepts_only_installed_and_keeps_dependency_checks(self):
        with self.assertRaises(app.Error):
            app.transaction_command("remove", [package()])
        self.assertEqual(app.transaction_command("remove", [package(kind="installed")]),
                          ["sudo", "pacman", "-Rns", "--", "example"])

    def test_orphan_catalog_only_contains_unused_dependencies(self):
        records = [package("unused", "installed"), package("explicit", "installed")]
        with patch.object(app, "capture", return_value="unused\n") as capture, patch.object(app, "installed_catalog", return_value=records):
            self.assertEqual(app.catalog("orphans"), records[:1])
        capture.assert_called_once_with(["pacman", "-Qdtq"], empty_ok=True)

    def test_empty_orphans_stay_in_their_list_without_prompt_or_transaction(self):
        selection = ("", "", [{"id": "orphans"}])
        with patch.object(app, "picker", side_effect=[selection, None, None]) as picker, patch.object(app, "capture", return_value=""), patch.object(app, "installed_catalog") as installed, patch.object(app, "pause") as pause, patch.object(app.subprocess, "call") as call, contextlib.redirect_stdout(io.StringIO()):
            app.main()
        call.assert_not_called()
        pause.assert_not_called()
        installed.assert_not_called()
        orphan_view = picker.call_args_list[1]
        self.assertEqual(orphan_view.args[0], [])
        self.assertIn("No orphaned", orphan_view.kwargs["keys"])

    def test_orphan_removal_rechecks_selection_and_preserves_native_confirmation(self):
        records = [package("unused", "installed")]
        with patch.object(app, "orphan_names", return_value={"unused"}), patch.object(app, "confirm", side_effect=AssertionError("no extra confirmation")), patch.object(app.subprocess, "call", return_value=0) as call, contextlib.redirect_stdout(io.StringIO()):
            app.perform("orphans", records)
        call.assert_called_once_with(["sudo", "pacman", "-Rns", "--", "unused"])
        self.assertNotIn("--noconfirm", call.call_args.args[0])
        with patch.object(app, "orphan_names", return_value=set()), patch.object(app.subprocess, "call") as call, self.assertRaises(app.Error):
            app.perform("orphans", records)
        call.assert_not_called()

    def test_orphan_query_errors_do_not_turn_into_removals(self):
        with patch.object(app, "capture", side_effect=app.Error("query failed")), patch.object(app.subprocess, "call") as call, self.assertRaises(app.Error):
            app.perform("orphans", [package("unused", "installed")])
        call.assert_not_called()

    def test_downgrade_is_cache_only_and_does_not_edit_ignore_policy(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(app, "capture", return_value=directory + "\n"):
            command = app.transaction_command("downgrade", [package(kind="installed")])
        self.assertIn("--cached-only", command)
        self.assertIn("--ignore=never", command)
        self.assertIn("--pacman-cache=" + directory, command)
        self.assertNotIn("--latest", command)

    def test_enter_is_not_confirmation(self):
        with patch("builtins.input", return_value=""):
            self.assertFalse(app.confirm("Install?"))

    def test_cancelled_package_selection_does_not_run_any_operation(self):
        with patch.object(app, "catalog", return_value=[]), patch.object(app, "picker", return_value=None), patch.object(app.subprocess, "call") as call, contextlib.redirect_stdout(io.StringIO()):
            app.browse("install")
        call.assert_not_called()

    def test_package_operations_have_no_duplicate_confirmation(self):
        with patch.object(app, "confirm", side_effect=AssertionError("no duplicate prompt")), patch.object(app.subprocess, "call", return_value=0) as call, contextlib.redirect_stdout(io.StringIO()):
            app.perform("install", [package()])
        call.assert_called_once_with(["sudo", "pacman", "-S", "--needed", "--", "cachyos-v3/example"])

    def test_successful_operations_reload_the_same_list_and_keep_the_query(self):
        for action, mode in [("install", "repos"), ("remove", "installed"), ("downgrade", "installed"), ("orphans", "orphans")]:
            record = package(kind="repo" if action == "install" else "installed")
            selection = ("systemd", "", [record])
            with self.subTest(action=action), patch.object(app, "catalog", return_value=[record]) as catalog, patch.object(app, "picker", side_effect=[selection, None]) as picker, patch.object(app, "perform") as perform, patch.object(app, "pause") as pause, contextlib.redirect_stdout(io.StringIO()):
                app.browse(action)
            perform.assert_called_once_with(action, [record])
            pause.assert_not_called()
            self.assertEqual([call.args for call in catalog.call_args_list], [(mode, ""), (mode, "systemd")])
            self.assertEqual(picker.call_count, 2)
            self.assertEqual(picker.call_args_list[0].args[1], picker.call_args_list[1].args[1])
            self.assertEqual(picker.call_args_list[1].args[2], "systemd")

    def test_failed_operation_waits_then_restores_the_same_list(self):
        record = package()
        selection = ("systemd", "", [record])
        with patch.object(app, "catalog", return_value=[record]), patch.object(app, "picker", side_effect=[selection, None]) as picker, patch.object(app, "perform", side_effect=app.Error("operation failed")) as perform, patch.object(app, "pause") as pause, contextlib.redirect_stdout(io.StringIO()) as output:
            app.browse("install")
        self.assertIn("operation failed", output.getvalue())
        pause.assert_called_once_with("Find & install")
        self.assertEqual(picker.call_count, 2)
        self.assertEqual(picker.call_args.args[2], "systemd")
        perform.assert_called_once()  # Redisplaying the list must not retry.

    def test_removing_last_orphan_keeps_the_empty_orphan_screen(self):
        record = package(kind="installed")
        with patch.object(app, "catalog", side_effect=[[record], []]), patch.object(app, "picker", side_effect=[("", "", [record]), None]) as picker, patch.object(app, "perform"), patch.object(app, "pause") as pause, contextlib.redirect_stdout(io.StringIO()):
            app.browse("orphans")
        self.assertEqual(picker.call_count, 2)
        self.assertEqual(picker.call_args.args[0], [])
        self.assertIn("No orphaned", picker.call_args.kwargs["keys"])
        pause.assert_not_called()

    def test_failed_package_operation_is_displayed_and_paused(self):
        selection = ("", "", [{"id": "install"}])
        with patch.object(app, "picker", side_effect=[selection, None]), patch.object(app, "browse", side_effect=app.Error("Package operation stopped (exit 1)")), patch.object(app, "pause") as pause, contextlib.redirect_stdout(io.StringIO()) as output:
            app.main()
        self.assertIn("Package operation stopped (exit 1)", output.getvalue())
        pause.assert_called_once_with()

    def test_vt_hash_is_local_and_digests_are_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "binary"
            path.write_bytes(b"test bytes")
            self.assertEqual(app.file_digest(str(path)), hashlib.sha256(b"test bytes").hexdigest())
        self.assertEqual(app.file_digest("A" * 64), "a" * 64)

    def test_empty_virustotal_input_returns_without_another_enter(self):
        selection = ("", "", [{"id": "vt"}])
        with patch.object(app, "picker", side_effect=[selection, None]), patch("builtins.input", return_value="") as input_, patch.object(app, "pause") as pause, patch.object(app, "vt_lookup") as lookup, contextlib.redirect_stdout(io.StringIO()):
            app.main()
        input_.assert_called_once()
        pause.assert_not_called()
        lookup.assert_not_called()

    def test_displayed_virustotal_report_waits_but_cancel_does_not(self):
        for displayed in (False, True):
            with self.subTest(displayed=displayed), patch.object(app, "picker", side_effect=[("", "", [{"id": "vt"}]), None]), patch.object(app, "virustotal", return_value=displayed), patch.object(app, "pause") as pause:
                app.main()
            self.assertEqual(pause.call_count, int(displayed))

    def test_virustotal_invalid_input_shows_error_then_waits(self):
        selection = ("", "", [{"id": "vt"}])
        with patch.object(app, "picker", side_effect=[selection, None]), patch("builtins.input", return_value="/nonexistent/virustotal-test-file"), patch.object(app, "pause") as pause, contextlib.redirect_stdout(io.StringIO()) as output:
            app.main()
        self.assertIn("STOP:", output.getvalue())
        pause.assert_called_once_with()

    def test_vt_is_get_by_hash_not_file_upload(self):
        response = io.BytesIO(json.dumps({"data": {"attributes": {"last_analysis_stats": {"malicious": 1}}}}).encode())
        with patch.object(app.urllib.request, "urlopen", return_value=response) as send:
            data = app.vt_lookup("a" * 64, "secret")
        request = send.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)
        self.assertEqual(data["last_analysis_stats"]["malicious"], 1)
        self.assertNotIn("secret", request.full_url)

    def test_vt_unknown_and_rate_limit_are_not_clean(self):
        for code in [404, 429]:
            error = urllib.error.HTTPError("https://example.invalid", code, "error", {}, None)
            with patch.object(app.urllib.request, "urlopen", side_effect=error):
                if code == 404:
                    self.assertIsNone(app.vt_lookup("a" * 64, "secret"))
                else:
                    with self.assertRaises(app.Error):
                        app.vt_lookup("a" * 64, "secret")

    def test_api_key_file_is_private(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(app, "VT_KEY", Path(directory) / "key"):
            app.save_vt_key("a" * 64)
            self.assertEqual(app.VT_KEY.stat().st_mode & 0o777, 0o600)

    def test_malicious_traur_report_is_shown_not_mislabeled_as_no_result(self):
        report = {"tier": "Malicious", "status": "complete", "signals": []}
        with patch.object(app, "capture", return_value=json.dumps(report)), contextlib.redirect_stdout(io.StringIO()) as output:
            app.audit([package(kind="aur", source="aur")])
        self.assertIn("Malicious", output.getvalue())
        self.assertNotIn("NO VALID AUDIT RESULT", output.getvalue())

    def test_audit_is_manual_skips_repo_origins_and_rejects_incomplete_reports(self):
        with patch.object(app, "capture") as capture, contextlib.redirect_stdout(io.StringIO()):
            app.audit([package(), package(kind="installed", source="extra")])
        capture.assert_not_called()
        for result in ({"tier": "Trusted", "status": "incomplete", "signals": []}, [], {"tier": "Ok", "status": "complete", "signals": "invalid"}):
            with patch.object(app, "capture", return_value=json.dumps(result)) as capture, patch.object(app.subprocess, "call") as install, contextlib.redirect_stdout(io.StringIO()) as output:
                app.audit([package(kind="aur", source="aur")])
            self.assertEqual(capture.call_args.args[0], ["traur", "scan", "example", "--json"])
            self.assertIn("NO VALID AUDIT RESULT", output.getvalue())
            install.assert_not_called()


if __name__ == "__main__":
    unittest.main()
