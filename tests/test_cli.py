"""Tests for the CLI argument/param handling (no network)."""

import pytest

from trading_bot.cli import _parse_sets, main


def test_parse_sets_coerces_by_param_kind():
    out = _parse_sets(["window=14", "oversold=25.5", "allow_short=true"], "rsi")
    assert out == {"window": 14, "oversold": 25.5, "allow_short": True}
    assert isinstance(out["window"], int)
    assert isinstance(out["oversold"], float)
    assert isinstance(out["allow_short"], bool)


def test_parse_sets_bool_false_variants():
    out = _parse_sets(["allow_short=false"], "rsi")
    assert out["allow_short"] is False


def test_parse_sets_rejects_bad_format():
    with pytest.raises(SystemExit):
        _parse_sets(["notakeyvalue"], "rsi")


def test_list_command_runs(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert "ma_crossover" in out and "pairs" in out


def test_backtest_unknown_strategy_exits():
    with pytest.raises(SystemExit):
        main(["backtest", "--strategy", "nope", "--symbols", "AAPL"])
