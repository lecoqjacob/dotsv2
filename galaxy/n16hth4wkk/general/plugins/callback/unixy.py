# -*- coding: utf-8 -*-
# Copyright (c) 2023, Al Bowles <@akatch>
# Copyright (c) 2012-2014, Michael DeHaan <michael.dehaan@gmail.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

# Make coding more python3-ish
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
    name: unixy
    type: stdout
    author: Al Bowles (@akatch)
    short_description: condensed Ansible output
    description:
      - Consolidated Ansible output in the style of LINUX/UNIX startup logs.
    extends_documentation_fragment:
      - default_callback
    requirements:
      - set as stdout in configuration
"""

from os.path import basename
from ansible import constants as C
from ansible import context
from ansible.module_utils.common.text.converters import to_text
from ansible.utils.color import colorize, hostcolor
from ansible.plugins.callback.default import CallbackModule as CallbackModule_default
from ansible.utils.color import stringc

COLOR_ANDROMEDA = C.COLOR_DEBUG
COLOR_ANDROMEDA_TASK = C.COLOR_VERBOSE
COLOR_ANDROMEDA_INCLUDE = C.COLOR_SKIP

COLOR_INCLUDE = C.COLOR_SKIP


class CallbackModule(CallbackModule_default):

    """
    Design goals:
    - Print consolidated output that looks like a *NIX startup log
    - Defaults should avoid displaying unnecessary information wherever possible

    TODOs:
    - Only display task names if the task runs on at least one host
    - Add option to display all hostnames on a single line in the appropriate result color (failures may have a separate line)
    - Consolidate stats display
    - Don't show play name if no hosts found
    """

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "stdout"
    CALLBACK_NAME = "n16hth4wkk.general.unixy"

    def andromeda_title(
        self,
        text,
        newline=True,
        text_color=None,
        title="[ANDROMEDA]: ",
        title_color=COLOR_ANDROMEDA,
    ):
        self._display.display(title, color=title_color, newline=False)
        self._display.display("\t%s" % text, color=text_color, newline=newline)

    def andromeda_display(
        self,
        text,
        stderr=None,
        tabbed=False,
        newline=True,
        text_color=None,
    ):
        msg = "%s" % text
        if tabbed:
            msg = "  %s" % text

        self._display.display(msg, color=text_color, newline=newline, stderr=stderr)

    def _run_is_verbose(self, result):
        return (
            self._display.verbosity > 0 or "_ansible_verbose_always" in result._result
        ) and "_ansible_verbose_override" not in result._result

    def _get_task_display_name(self, task):
        self.task_display_name = None
        display_name = task.get_name().strip().split(" : ")

        task_display_name = display_name[-1]
        if task_display_name.startswith("include"):
            return
        else:
            self.task_display_name = task_display_name

    def _preprocess_result(self, result):
        self.delegated_vars = result._result.get("_ansible_delegated_vars", None)
        self._handle_exception(result._result, use_stderr=self.get_option("display_failed_stderr"))
        self._handle_warnings(result._result)

    def _process_result_output(self, result, msg, show_host=True):
        if show_host:
            task_host = result._host.get_name()
            task_result = "=> %s %s" % (task_host, msg)
        else:
            task_result = "=> %s" % msg

        if self._run_is_verbose(result):
            task_result = "%s %s: %s" % (
                task_host,
                msg,
                self._dump_results(result._result, indent=4),
            )
            return task_result

        if self.delegated_vars:
            task_delegate_host = self.delegated_vars["ansible_host"]
            task_result = "%s -> %s %s" % (task_host, task_delegate_host, msg)

        if result._result.get("msg") and result._result.get("msg") != "All items completed":
            task_result += " | msg: " + to_text(result._result.get("msg"))

        if result._result.get("stdout"):
            task_result += " | stdout: " + result._result.get("stdout")

        if result._result.get("stderr"):
            task_result += " | stderr: " + result._result.get("stderr")

        return task_result

    # ================================================================================================================== #
    # v2_on_* methods
    # ================================================================================================================== #

    def v2_on_file_diff(self, result):
        if result._task.loop and "results" in result._result:
            for res in result._result["results"]:
                if "diff" in res and res["diff"] and res.get("changed", False):
                    diff = self._get_diff(res["diff"])
                    if diff:
                        self._display.display(diff)
        elif (
            "diff" in result._result
            and result._result["diff"]
            and result._result.get("changed", False)
        ):
            diff = self._get_diff(result._result["diff"])
            if diff:
                self._display.display(diff)

    # ================================================================================================================== #
    # v2_runner_on_* methods
    # ================================================================================================================== #

    def v2_runner_on_unreachable(self, result):
        self._preprocess_result(result)

        msg = "unreachable"
        display_color = C.COLOR_UNREACHABLE
        task_result = self._process_result_output(result, msg)

        self.andromeda_display(
            "  " + task_result,
            text_color=display_color,
            stderr=self.get_option("display_failed_stderr"),
        )

    def v2_runner_on_ok(self, result, msg="ok", display_color=C.COLOR_OK):
        if result._task.no_log:
            return

        self._preprocess_result(result)
        result_was_changed = "changed" in result._result and result._result["changed"]

        if result_was_changed:
            msg = "done"
            item_value = self._get_item_label(result._result)

            if item_value:
                msg += " | item: %s" % (item_value,)

            display_color = C.COLOR_CHANGED
            task_result = self._process_result_output(result, msg)
        elif self.get_option("display_ok_hosts"):
            task_result = self._process_result_output(result, msg)

        self.andromeda_display(task_result, text_color=display_color, tabbed=True)

    def v2_runner_on_failed(self, result, ignore_errors=False):
        self._preprocess_result(result)
        display_color = C.COLOR_ERROR
        msg = "failed"
        item_value = self._get_item_label(result._result)
        if item_value:
            msg += " | item: %s" % (item_value,)

        task_result = self._process_result_output(result, msg)
        self.andromeda_display(
            "  " + task_result,
            text_color=display_color,
            stderr=self.get_option("display_failed_stderr"),
        )

    def v2_runner_on_skipped(self, result, ignore_errors=False):
        if self.get_option("display_skipped_hosts"):
            self._preprocess_result(result)
            display_color = C.COLOR_SKIP
            msg = "skipped"
            task_result = self._process_result_output(result, msg)
            self._display.display("  " + task_result, display_color)
        else:
            return

    # ================================================================================================================== #
    # v2_runner_item_on_* methods
    # ================================================================================================================== #

    def v2_runner_item_on_skipped(self, result):
        self.v2_runner_on_skipped(result)

    def v2_runner_item_on_failed(self, result):
        self.v2_runner_on_failed(result)

    def v2_runner_item_on_ok(self, result):
        self.v2_runner_on_ok(result)

    # ================================================================================================================== #
    # v2_playbook_on_* methods
    # ================================================================================================================== #

    def v2_playbook_on_start(self, playbook):
        msg = "Running playbook file %s"

        if context.CLIARGS["check"] and self.get_option("check_mode_markers"):
            msg += " in check mode"

        self.andromeda_title(msg % stringc(basename(playbook._file_name), C.COLOR_CHANGED))

        # show CLI arguments
        if self._display.verbosity > 3:
            if context.CLIARGS.get("args"):
                self._display.display(
                    "Positional arguments: %s" % " ".join(context.CLIARGS["args"]),
                    color=C.COLOR_VERBOSE,
                    screen_only=True,
                )

            for argument in (a for a in context.CLIARGS if a != "args"):
                val = context.CLIARGS[argument]
                if val:
                    self._display.vvvv("%s: %s" % (argument, val))

    def v2_playbook_on_play_start(self, play):
        name = play.get_name().strip()
        if play.check_mode and self.get_option("check_mode_markers"):
            if name and play.hosts:
                msg = "Executing [%s] (in check mode) on hosts: %s -" % (name, ",".join(play.hosts))
            else:
                msg = "Executing in check mode"
        else:
            if name and play.hosts:
                msg = "Executing [%s] on hosts: [%s]" % (name, ",".join(play.hosts))
            else:
                msg = "Executing..."

        self.andromeda_title(msg)

    def v2_playbook_on_task_start(self, task, is_conditional):
        if task.no_log:
            return

        self._get_task_display_name(task)
        if self.task_display_name is None:
            return

        msg = self.task_display_name
        if task.check_mode and self.get_option("check_mode_markers"):
            msg += " (check mode)..."
        else:
            msg += "..."

        self.andromeda_title(
            msg,
            title="[ANDROMEDA TASK]: ",
            title_color=COLOR_ANDROMEDA_TASK,
        )

    def v2_playbook_on_handler_task_start(self, task):
        self._get_task_display_name(task)
        if self.task_display_name is not None:
            if task.check_mode and self.get_option("check_mode_markers"):
                self._display.display("%s (via handler in check mode)... " % self.task_display_name)
            else:
                self._display.display("%s (via handler)... " % self.task_display_name)

    def v2_playbook_on_no_hosts_matched(self):
        self._display.display("  No hosts found!", color=C.COLOR_DEBUG)

    def v2_playbook_on_no_hosts_remaining(self):
        self._display.display("  Ran out of hosts!", color=C.COLOR_ERROR)

    def v2_playbook_on_include(self, included_file):
        msg = "%s for %s" % (
            included_file._filename,
            ", ".join([h.name for h in included_file._hosts]),
        )

        label = self._get_item_label(included_file._vars)
        if label:
            msg += " => (item=%s)" % label

        self.andromeda_title(
            msg,
            title="[ANDROMEDA INCLUDE]: ",
            text_color=COLOR_ANDROMEDA_INCLUDE,
            title_color=COLOR_ANDROMEDA_INCLUDE,
        )

    def v2_runner_retry(self, result):
        msg = "  Retrying... (%d of %d)" % (result._result["attempts"], result._result["retries"])
        if self._run_is_verbose(result):
            msg += "Result was: %s" % self._dump_results(result._result)
        self._display.display(msg, color=C.COLOR_DEBUG)

    def v2_playbook_on_stats(self, stats):
        self._display.display("\n- Play recap -", screen_only=True)

        hosts = sorted(stats.processed.keys())
        for h in hosts:
            # TODO how else can we display these?
            t = stats.summarize(h)

            self._display.display(
                "  %s : %s %s %s %s %s %s"
                % (
                    hostcolor(h, t),
                    colorize("ok", t["ok"], C.COLOR_OK),
                    colorize("changed", t["changed"], C.COLOR_CHANGED),
                    colorize("unreachable", t["unreachable"], C.COLOR_UNREACHABLE),
                    colorize("failed", t["failures"], C.COLOR_ERROR),
                    colorize("rescued", t["rescued"], C.COLOR_OK),
                    colorize("ignored", t["ignored"], C.COLOR_WARN),
                ),
                screen_only=True,
            )

            self._display.display(
                "  %s : %s %s %s %s %s %s"
                % (
                    hostcolor(h, t, False),
                    colorize("ok", t["ok"], None),
                    colorize("changed", t["changed"], None),
                    colorize("unreachable", t["unreachable"], None),
                    colorize("failed", t["failures"], None),
                    colorize("rescued", t["rescued"], None),
                    colorize("ignored", t["ignored"], None),
                ),
                log_only=True,
            )
        if stats.custom and self.get_option("show_custom_stats"):
            self._display.banner("CUSTOM STATS: ")
            # per host
            # TODO: come up with 'pretty format'
            for k in sorted(stats.custom.keys()):
                if k == "_run":
                    continue
                self._display.display(
                    "\t%s: %s"
                    % (k, self._dump_results(stats.custom[k], indent=1).replace("\n", ""))
                )

            # print per run custom stats
            if "_run" in stats.custom:
                self._display.display("", screen_only=True)
                self._display.display(
                    "\tRUN: %s"
                    % self._dump_results(stats.custom["_run"], indent=1).replace("\n", "")
                )
            self._display.display("", screen_only=True)