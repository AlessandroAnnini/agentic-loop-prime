"""al-prime command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agentic_loop_prime import __version__
from agentic_loop_prime.schedule import next_frame, prompt_block
from agentic_loop_prime.telemetry import (
    OpenTelemetryListener,
    configure_telemetry,
    flush_telemetry,
)


def main(argv: list[str] | None = None) -> int:
    configure_telemetry()
    parser = argparse.ArgumentParser(
        prog="al-prime",
        description="Agentic Loop Prime — goal-loop harness for new software",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"agentic-loop-prime {__version__}",
    )
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("version", help="Print package version")

    p_next = sub.add_parser("next", help="Frame the next DELEGATE or STOP")
    p_next.add_argument(
        "--memory",
        default="memory",
        help="Memory directory (default: ./memory)",
    )
    p_next.add_argument("--brief-dir", default=None, help="Brief folder (read-only)")
    p_next.add_argument("--app-dir", default=None, help="Product app directory")
    p_next.add_argument(
        "--loop-budget",
        type=int,
        default=None,
        help="Reset loop remaining (omit to continue)",
    )
    p_next.add_argument(
        "--prompt",
        action="store_true",
        help="Print a copy-paste Resume block",
    )
    p_next.add_argument(
        "--autonomous",
        action="store_true",
        help="Least HITL: auto-sign charter/brief, skip open_questions (sticky)",
    )

    p_done = sub.add_parser("done", help="Close the open frame (log + clear lock)")
    p_done.add_argument(
        "--memory",
        default="memory",
        help="Memory directory (default: ./memory)",
    )
    p_done.add_argument(
        "--transition-id",
        default=None,
        help="Must match run-state.lock (default: the open lock)",
    )
    gate = p_done.add_mutually_exclusive_group(required=True)
    gate.add_argument("--pass", dest="outcome", action="store_const", const=True)
    gate.add_argument("--fail", dest="outcome", action="store_const", const=False)

    p_init = sub.add_parser("init", help="Create a slim studio (memory, brief, app, skills)")
    p_init.add_argument(
        "dir",
        nargs="?",
        default=".",
        help="Studio root (default: .)",
    )
    p_init.add_argument("--memory", default="memory", help="Memory directory")
    p_init.add_argument("--brief-dir", default="brief", help="Brief folder")
    p_init.add_argument("--app-dir", default="app", help="Product app directory")
    p_init.add_argument(
        "--force",
        action="store_true",
        help="Fill missing seed files only",
    )

    p_change = sub.add_parser(
        "request-change",
        help="Queue a post-ship change or reopen a live feature",
    )
    p_change.add_argument("--memory", default="memory", help="Memory directory")
    p_change.add_argument(
        "--intent",
        default="",
        help="One-line change intent (creates a new backlog feature)",
    )
    p_change.add_argument(
        "--feature-id",
        default="",
        help="Reopen an existing feature into designing",
    )
    p_change.add_argument("--name", default="", help="Display name for a new feature")
    p_change.add_argument(
        "--surface",
        default="cli",
        choices=["ui", "cli", "api", "library"],
    )
    p_change.add_argument(
        "--bump",
        default="patch",
        choices=["patch", "minor", "major"],
    )

    p_unatt = sub.add_parser(
        "unattended",
        help="Outer loop until human STOP or AGENT_NEEDED",
    )
    p_unatt.add_argument("--memory", default="memory", help="Memory directory")
    p_unatt.add_argument("--brief-dir", default=None, help="Brief folder")
    p_unatt.add_argument("--app-dir", default=None, help="Product app directory")
    p_unatt.add_argument(
        "--loop-budget",
        type=int,
        default=None,
        help="Reset loop remaining on the first turn only",
    )
    p_unatt.add_argument(
        "--autonomous",
        action="store_true",
        help="Pass --autonomous to each next (sticky)",
    )
    p_unatt.add_argument("--max-turns", type=int, default=50)
    p_unatt.add_argument(
        "--agent-cmd",
        default="",
        help=(
            "Command does the write; Prime closes. "
            "Env: ALP_PROMPT_FILE, ALP_ACTION_JSON, ALP_POLICY_FILE"
        ),
    )

    p_upd = sub.add_parser(
        "update", help="Refresh pin and overwrite prime-* plus support skills"
    )
    p_upd.add_argument("--studio", default=".", help="Studio root (default: .)")
    p_upd.add_argument("--kit", default=None, help="Kit checkout (default: this package)")

    p_doc = sub.add_parser("doctor", help="Check studio health and print next command")
    p_doc.add_argument("--studio", default=".", help="Studio root (default: .)")
    p_doc.add_argument("--kit", default=None, help="Kit checkout (unused; accepted)")

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if args.cmd in (None, "version"):
        print(f"agentic-loop-prime {__version__}")
        return 0
    if args.cmd == "next":
        return _cmd_next(args)
    if args.cmd == "done":
        return _cmd_done(args)
    if args.cmd == "init":
        return _cmd_init(args)
    if args.cmd == "request-change":
        return _cmd_request_change(args)
    if args.cmd == "unattended":
        return _cmd_unattended(args)
    if args.cmd == "update":
        return _cmd_update(args)
    if args.cmd == "doctor":
        return _cmd_doctor(args)
    parser.print_help()
    return 2


def _cmd_next(args: argparse.Namespace) -> int:
    from agentic_loop_prime.context import ProgramContext

    memory = Path(args.memory)
    brief = Path(args.brief_dir) if args.brief_dir else None
    app = Path(args.app_dir) if args.app_dir else None
    tel = OpenTelemetryListener()
    try:
        action = next_frame(
            memory,
            brief_dir=brief,
            app_dir=app,
            loop_budget=args.loop_budget,
            telemetry=tel,
            autonomous=bool(args.autonomous),
        )
        print(action.format_text())
        if args.prompt:
            ctx = ProgramContext(memory_dir=memory)
            print()
            print(prompt_block(action, ctx, ctx.program_state), end="")
        if action.kind == "STOP":
            return 2
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    finally:
        flush_telemetry()


def _cmd_done(args: argparse.Namespace) -> int:
    from agentic_loop_prime.done import CloseError, close_frame

    tel = OpenTelemetryListener()
    try:
        result = close_frame(
            Path(args.memory),
            passed=bool(args.outcome),
            transition_id=args.transition_id,
            telemetry=tel,
        )
        print(result.format_text())
        return 0
    except CloseError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    finally:
        flush_telemetry()


def _cmd_init(args: argparse.Namespace) -> int:
    from agentic_loop_prime.init import InitError, init_studio

    tel = OpenTelemetryListener()
    try:
        result = init_studio(
            Path(args.dir),
            memory=args.memory,
            brief_dir=args.brief_dir,
            app_dir=args.app_dir,
            force=bool(args.force),
            telemetry=tel,
        )
        print(result.format_text())
        return 0
    except InitError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    finally:
        flush_telemetry()


def _cmd_request_change(args: argparse.Namespace) -> int:
    from agentic_loop_prime.request_change import RequestChangeError, request_change

    try:
        result = request_change(
            Path(args.memory),
            intent=str(args.intent or ""),
            feature_id=str(args.feature_id or ""),
            name=str(args.name or ""),
            surface=str(args.surface or "cli"),
            bump=str(args.bump or "patch"),
        )
    except RequestChangeError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    print(result.format_text())
    return 0


def _cmd_unattended(args: argparse.Namespace) -> int:
    from agentic_loop_prime.unattended import run_unattended

    brief = Path(args.brief_dir) if args.brief_dir else None
    app = Path(args.app_dir) if args.app_dir else None
    return run_unattended(
        Path(args.memory),
        brief_dir=brief,
        app_dir=app,
        loop_budget=args.loop_budget,
        autonomous=bool(args.autonomous),
        max_turns=int(args.max_turns),
        agent_cmd=str(args.agent_cmd or ""),
    )


def _cmd_update(args: argparse.Namespace) -> int:
    from agentic_loop_prime.studio import StudioError, update_studio

    tel = OpenTelemetryListener()
    kit = Path(args.kit) if args.kit else None
    try:
        result = update_studio(Path(args.studio), kit=kit, telemetry=tel)
        print(result.format_text())
        return 0
    except StudioError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    finally:
        flush_telemetry()


def _cmd_doctor(args: argparse.Namespace) -> int:
    from agentic_loop_prime.studio import doctor_studio

    tel = OpenTelemetryListener()
    kit = Path(args.kit) if args.kit else None
    try:
        result = doctor_studio(Path(args.studio), kit=kit, telemetry=tel)
        print(result.format_text())
        return 0 if result.ok else 1
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    finally:
        flush_telemetry()
