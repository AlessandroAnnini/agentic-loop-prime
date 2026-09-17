from agentic_loop_prime.cli import main


def test_version(capsys) -> None:
    assert main(["version"]) == 0
    assert "0.1.0" in capsys.readouterr().out
