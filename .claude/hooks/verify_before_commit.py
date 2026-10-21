"""Commit gate: check the message and run `make verify` before any agent commit.

Claude Code passes the pending Bash command as JSON on stdin. Exit code 2
blocks the command and shows stderr to the agent. Any other command passes.

Agent commits must use the form `git commit -m "<message>"` with a single -m,
so the message can be read and checked before the commit runs.
"""

import json
import os
import re
import shlex
import subprocess
import sys

MAX_LENGTH = 72
OPTIONAL_PREFIX = re.compile(r"^[a-z][a-z0-9-]*: ")
NOT_IMPERATIVE = {
    "added", "adding", "fixed", "fixing", "updated", "updating", "removed",
    "removing", "changed", "changing", "created", "creating", "implemented",
    "implementing", "refactored", "refactoring", "renamed", "moved",
}  # fmt: skip
ATTRIBUTION = ("co-authored-by", "signed-off-by", "generated with", "@anthropic.com")
SEPARATORS = {";", "&&", "||", "|", "&", "\n"}


def find_commit(command: str) -> list[str] | None:
    """Return the arguments after `git commit`, or None if there is no commit."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    tokens = list(lexer)
    segment: list[str] = []
    for token in [*tokens, ";"]:
        if token not in SEPARATORS:
            segment.append(token)
            continue
        if segment and segment[0] == "git":
            rest = segment[1:]
            while rest and rest[0].startswith("-"):
                rest = rest[2:] if rest[0] in ("-C", "-c") else rest[1:]
            if rest and rest[0] == "commit":
                return rest[1:]
        segment = []
    return None


def commit_message(args: list[str]) -> tuple[str | None, str | None]:
    """Return (message, None) for a single -m message, else (None, reason)."""
    messages = []
    for i, arg in enumerate(args):
        if arg in ("-F", "--file") or arg.startswith("--file="):
            return None, "use -m, not a message file"
        if arg in ("-m", "--message") or re.fullmatch(r"-[a-zA-Z]*m", arg):
            if i + 1 >= len(args):
                return None, "-m has no message"
            messages.append(args[i + 1])
        elif arg.startswith("--message="):
            messages.append(arg.split("=", 1)[1])
    if len(messages) != 1:
        return None, 'use exactly one -m "<message>"'
    if "$(" in messages[0] or "`" in messages[0]:
        return None, "write the message inline, not built from a command"
    return messages[0], None


def message_problems(message: str) -> list[str]:
    """Return every way the message breaks the commit conventions."""
    problems = []
    if "\n" in message:
        problems.append("must be a single line")
    if len(message) > MAX_LENGTH:
        problems.append(f"must be {MAX_LENGTH} characters or fewer")
    if not message.isascii():
        problems.append("must be plain ASCII (no emojis)")
    if any(marker in message.lower() for marker in ATTRIBUTION):
        problems.append("must not contain attribution or co-author lines")
    if message.rstrip().endswith("."):
        problems.append("must not end with a full stop")
    subject = OPTIONAL_PREFIX.sub("", message, count=1).strip()
    words = subject.split()
    if not words or not words[0][0].isupper():
        problems.append("must start with a capital letter")
    if len(words) < 2 or words[0].lower() == "wip":
        problems.append("must say what changed, not just 'Fix' or 'WIP'")
    if words and words[0].lower() in NOT_IMPERATIVE:
        problems.append("must use the imperative ('Add', not 'Added')")
    return problems


def main() -> int:
    command = json.load(sys.stdin).get("tool_input", {}).get("command", "")
    if not re.search(r"\bgit\b.*\bcommit\b", command, re.DOTALL):
        return 0
    try:
        args = find_commit(command)
    except ValueError:
        print("Commit blocked: could not read the command.", file=sys.stderr)
        return 2
    if args is None:
        return 0
    message, reason = commit_message(args)
    problems = [reason] if reason else message_problems(message)
    if problems:
        print("Commit blocked: message " + "; ".join(problems) + ".", file=sys.stderr)
        return 2
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    result = subprocess.run(
        ["make", "verify"], cwd=project_dir, capture_output=True, text=True
    )
    if result.returncode != 0:
        print("Commit blocked: make verify failed.", file=sys.stderr)
        print(result.stdout + result.stderr, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
