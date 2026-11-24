"""The halt email's recipient comes from config, and no address sits in the code.

WHY THIS FILE EXISTS
--------------------
`ops/halt.py` held a personal address as `DEFAULT_ALERT_TO`, in a public repository.
Removing it has one way to do harm: a machine that sets only the SMTP pair relied on
that default, and a halt alert that quietly stops arriving is the failure this module
exists to prevent. So the recipient falls back to the SMTP account, and these tests
pin both halves.

Nothing here opens a socket: `smtplib.SMTP` is replaced, and the root conftest blocks
the network in any case.
"""
import re
from pathlib import Path

import pytest

from ops import halt


class FakeSMTP:
    """Records what would have been sent."""

    sent: list = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


@pytest.fixture()
def configure(monkeypatch):
    """Set the alert config for one test, and catch anything it would send."""
    FakeSMTP.sent = []
    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)

    def _set(**values):
        monkeypatch.setattr(halt, "_cfg", lambda key, default=None: values.get(key, default))

    return _set


def test_no_personal_address_is_written_in_the_module():
    source = Path(halt.__file__).read_text()
    assert re.findall(r"[\w.+-]+@gmail\.com", source) == []


def test_the_configured_recipient_receives_the_alert(configure):
    configure(ALERT_EMAIL_TO="desk@example.invalid", ALERT_SMTP_USER="sender@example.invalid",
              ALERT_SMTP_PASS="synthetic-not-a-password")
    assert halt._email("subject", "body") is True
    assert FakeSMTP.sent[0]["To"] == "desk@example.invalid"


def test_with_no_recipient_the_alert_goes_to_the_smtp_account(configure):
    configure(ALERT_SMTP_USER="sender@example.invalid", ALERT_SMTP_PASS="synthetic-not-a-password")
    assert halt._email("subject", "body") is True
    assert FakeSMTP.sent[0]["To"] == "sender@example.invalid"


def test_with_no_smtp_pair_nothing_is_sent_and_the_reason_is_returned(configure):
    configure(ALERT_EMAIL_TO="desk@example.invalid")
    result = halt._email("subject", "body")
    assert result is not True and "not configured" in result
    assert FakeSMTP.sent == []
