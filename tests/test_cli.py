from envcheck import cli


def test_version_command(capsys):
    exit_code = cli.main(["version"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == "0.1.0"


def test_demo_runs_end_to_end_and_prints_a_report(capsys):
    exit_code = cli.main(["demo"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "envcheck report" in captured.out
    assert "trust_score" in captured.out


def test_demo_fail_under_triggers_a_nonzero_exit_when_trust_score_is_low(capsys):
    exit_code = cli.main(["demo", "--fail-under", "0.99"])

    assert exit_code == 1


def test_demo_fail_under_stays_zero_when_trust_score_clears_the_bar(capsys):
    exit_code = cli.main(["demo", "--fail-under", "0.5"])

    assert exit_code == 0
