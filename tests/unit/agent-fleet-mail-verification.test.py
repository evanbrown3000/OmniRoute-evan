import importlib.util
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

source = Path(__file__).resolve().parents[2] / "scripts/ops/agent-fleet/mail_verification.py"
spec = importlib.util.spec_from_file_location("mail_verification", str(source))
mail = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mail)


def message(body="Verification code: 123456", sender="login@deepseek.com", recipient="owner@example.test"):
    return ("From: %s\r\nTo: %s\r\nContent-Type: text/plain\r\n\r\n%s" %
            (sender, recipient, body)).encode()


class MailVerificationTests(unittest.TestCase):
    def test_extracts_only_the_selected_recipient_and_real_sender_domain(self):
        args = dict(sender_domain="deepseek.com", recipient="owner@example.test", code_length=6)
        self.assertEqual(mail.verification_from_message(message(), **args), "123456")
        self.assertIsNone(mail.verification_from_message(message(sender="login@deepseek.com.attacker.test"), **args))
        self.assertIsNone(mail.verification_from_message(message(recipient="other@example.test"), **args))
        self.assertIsNone(mail.verification_from_message(message(body="Codes 123456 and 654321"), **args))

    def test_decodes_html_without_returning_the_whole_mail(self):
        raw = (b"From: verify@mail.deepseek.com\r\nTo: owner@example.test\r\n"
               b"Content-Type: text/html\r\n\r\n<p>Your code is <b>123456</b></p>")
        self.assertEqual(mail.verification_from_message(raw, sender_domain="deepseek.com",
                         recipient="owner@example.test", code_length=6), "123456")

    def context(self):
        value = {"gmail_address": "owner@example.test", "gmail_app_password": "fixture-private-password"}
        reader = SimpleNamespace(read=lambda *args, **kwargs: {"value": value})
        return SimpleNamespace(reader=reader, account={"id": "mailbox", "metadata": {}},
            method={"recipes": {"mailboxes": {"mailbox": {"credential_ref": "owned-mail"}}}},
            used_credentials=set())

    def test_inventory_does_not_read_credentials_or_connect(self):
        context = self.context()
        context.reader.read = lambda *args, **kwargs: self.fail("inventory read private material")
        with patch.object(mail.imaplib, "IMAP4_SSL", side_effect=AssertionError("network probe")):
            self.assertFalse(mail.run(context, "inventory", {})["network_probe_performed"])

    def test_rejects_broad_or_stale_search_before_connecting(self):
        with patch.object(mail.imaplib, "IMAP4_SSL", side_effect=AssertionError("network probe")):
            for args in [{"sender_domain": "*", "after": time.time()},
                         {"sender_domain": "deepseek.com", "after": 0},
                         {"sender_domain": "deepseek.com", "after": time.time(), "code_length": 30}]:
                with self.assertRaises(ValueError):
                    mail.run(self.context(), "verification_code", args)

    def test_reads_only_bounded_new_verification_mail_and_always_logs_out(self):
        now = time.time()
        received = mail.datetime.fromtimestamp(now, mail.timezone.utc).strftime("%d-%b-%Y %H:%M:%S %z")
        class Client:
            def __init__(self): self.calls = []
            def list(self): return "OK", []
            def login(self, *args): self.calls.append(("login",))
            def select(self, folder, readonly=False):
                self.calls.append(("select", folder, readonly)); return "OK", []
            def uid(self, op, *args):
                self.calls.append((op,) + args)
                if op == "search": return "OK", [b"1"]
                return "OK", [(('1 (INTERNALDATE "%s")' % received).encode(), message())]
            def logout(self): self.calls.append(("logout",))
        client = Client()
        with patch.object(mail.imaplib, "IMAP4_SSL", return_value=client):
            result = mail.run(self.context(), "verification_code", {"sender_domain": "deepseek.com", "after": now})
        self.assertEqual(result["code"], "123456")
        self.assertIn(("select", "INBOX", True), client.calls)
        self.assertIn(("fetch", b"1", "(INTERNALDATE BODY.PEEK[]<0.65536>)"), client.calls)
        self.assertEqual(client.calls[-1], ("logout",))
        self.assertNotIn("fixture-private-password", str(result))

    def test_discovers_only_special_use_folders_including_localized_junk(self):
        client = SimpleNamespace(list=lambda: ("OK", [
            b'(\\All) "/" "[Gmail]/All Mail"',
            b'(\\Junk) "/" "[Gmail]/Localized-Junk"',
            b'(\\HasNoChildren) "/" "Unrelated private label"']))
        self.assertEqual(mail.verification_mailboxes(client),
                         ["INBOX", '"[Gmail]/All Mail"', '"[Gmail]/Localized-Junk"'])


if __name__ == "__main__":
    unittest.main()
