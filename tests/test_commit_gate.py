"""Harness checks for the commit gate hook. They cover no AC or INV rule."""

import importlib.util
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / ".claude/hooks/verify_before_commit.py"
spec = importlib.util.spec_from_file_location("verify_before_commit", HOOK)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


@pytest.mark.parametrize(
    "message",
    [
        "Add make verify, CI workflow, commit gate and package skeleton",
        "generator: Add seeded event generation",
        "Fix typo",
        "Add " + "x" * 68,  # exactly 72 characters
    ],
)
def test_good_messages_pass(message):
    assert gate.message_problems(message) == []


@pytest.mark.parametrize(
    ("message", "problem"),
    [
        ("Add thing\n\nMore detail", "single line"),
        ("Add " + "x" * 69, "72 characters"),
        ("Add rocket \U0001f680", "plain ASCII"),
        ("Add thing Co-Authored-By: Claude <noreply@anthropic.com>", "attribution"),
        ("Add thing.", "full stop"),
        ("add thing", "capital letter"),
        ("generator: add thing", "capital letter"),
        ("Fix", "say what changed"),
        ("WIP on generator", "say what changed"),
        ("Added the generator", "imperative"),
    ],
)
def test_bad_messages_are_rejected(message, problem):
    assert any(problem in p for p in gate.message_problems(message))


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ('git commit -m "Add thing"', ("Add thing", None)),
        ('git -C repo commit -am "Add thing"', ("Add thing", None)),
        ('make verify && git commit --message="Add thing"', ("Add thing", None)),
        ('git commit -m "Add thing" -m "Body"', (None, "exactly one -m")),
        ("git commit", (None, "exactly one -m")),
        ("git commit -F msg.txt", (None, "message file")),
        ('git commit -m "$(cat <<EOF\nAdd thing\nEOF\n)"', (None, "inline")),
    ],
)
def test_commit_message_is_read_from_command(command, expected):
    message, reason = gate.commit_message(gate.find_commit(command))
    assert message == expected[0]
    assert (reason is None) if expected[1] is None else expected[1] in reason


@pytest.mark.parametrize(
    "command", ["ls", "git log --grep commit", "git status", "echo commit"]
)
def test_non_commit_commands_are_ignored(command):
    assert gate.find_commit(command) is None
