"""Accounts provider method for bounded, on-demand signup email verification.

No mailbox daemon, password copy, message mutation, or inference provider is created.
"""
import argparse
import email.policy
import imaplib
import json
import re
import time
from datetime import datetime, timezone
from email.parser import BytesParser
from email.utils import getaddresses, parseaddr
from html.parser import HTMLParser
from pathlib import Path

PROVIDER = "gmail-verification"


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def verification_from_message(raw, *, sender_domain, recipient, code_length):
    message = BytesParser(policy=email.policy.default).parsebytes(raw)
    sender = parseaddr(str(message.get("From", "")))[1].rsplit("@", 1)[-1].lower()
    if sender != sender_domain and not sender.endswith("." + sender_domain):
        return None
    recipients = {address.lower() for _, address in getaddresses(message.get_all("To", []))}
    if recipient.lower() not in recipients:
        return None
    texts = []
    for part in message.walk():
        if part.get_content_type() not in ("text/plain", "text/html"):
            continue
        if part.get_content_disposition() == "attachment":
            continue
        text = part.get_content()
        if part.get_content_type() == "text/html":
            parser = PlainHTML()
            parser.feed(text)
            text = " ".join(parser.parts)
        texts.append(text)
    codes = set(re.findall(r"(?<!\d)(\d{%d})(?!\d)" % code_length, "\n".join(texts)))
    return next(iter(codes)) if len(codes) == 1 else None


def run(context, operation, arguments):
    if operation not in ("inventory", "qualify", "verification_code"):
        raise ValueError("Unsupported mailbox verification operation")
    reference = context.account["metadata"]["credential_ref"]
    if operation == "inventory":
        return {"capabilities": ["verification_code"], "credential_ref": reference,
                "network_probe_performed": False}
    domain = str(arguments.get("sender_domain", "")).lower()
    after = arguments.get("after")
    digits = arguments.get("code_length", 6)
    if operation == "verification_code":
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", domain) or "." not in domain:
            raise ValueError("An exact sender domain is required")
        if type(after) not in (int, float) or not time.time() - 900 <= after <= time.time() + 30:
            raise ValueError("A signup request timestamp within fifteen minutes is required")
        if type(digits) is not int or not 4 <= digits <= 8:
            raise ValueError("Verification code length must be four to eight digits")
    credential = context.reader.read(reference, fresh=False)["value"]
    context.used_credentials.add(reference)
    address = credential["gmail_address"]
    client = None
    try:
        client = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=15)
        client.login(address, credential["gmail_app_password"])
        status, _ = client.select("INBOX", readonly=True)
        if status != "OK":
            raise RuntimeError("Verification mailbox selection failed")
        if operation == "qualify":
            return {"status": "authenticated", "protocol": "IMAP4_SSL", "message_reads": 0}
        since = datetime.fromtimestamp(after, timezone.utc).strftime("%d-%b-%Y")
        status, values = client.uid("search", None, '(SINCE "%s" FROM "%s")' % (since, domain))
        if status != "OK":
            raise RuntimeError("Verification sender search failed")
        for uid in reversed((values[0].split() if values and values[0] else [])[-10:]):
            status, parts = client.uid("fetch", uid, "(INTERNALDATE BODY.PEEK[]<0.65536>)")
            if status != "OK":
                continue
            for part in parts:
                if not isinstance(part, tuple):
                    continue
                match = re.search(rb'INTERNALDATE "([^"]+)"', part[0])
                if not match:
                    continue
                received = datetime.strptime(match.group(1).decode("ascii"), "%d-%b-%Y %H:%M:%S %z").timestamp()
                if received < after or received > time.time() + 30:
                    continue
                code = verification_from_message(part[1], sender_domain=domain,
                                                 recipient=address, code_length=digits)
                if code:
                    return {"status": "ready", "code": code, "message_uid": uid.decode("ascii"),
                            "received_at": received, "sender_domain": domain}
        return {"status": "pending", "sender_domain": domain, "mailbox_mutated": False}
    finally:
        if client:
            try:
                client.logout()
            except (OSError, imaplib.IMAP4.error):
                pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controller-config", default="/state/accounts.json")
    parser.add_argument("--account", default="mailbox.verification.evanbronitskiy")
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--credential-ref")
    parser.add_argument("--operation", choices=("inventory", "qualify", "verification_code"), default="inventory")
    parser.add_argument("--sender-domain")
    parser.add_argument("--after", type=float)
    parser.add_argument("--code-length", type=int, default=6)
    args = parser.parse_args()
    from networks.integrations.accounts.controller_service import ControllerAccountsRuntime
    from accounts_and_secrets.provider_methods import retain_method
    runtime = ControllerAccountsRuntime(json.loads(Path(args.controller_config).read_text()))
    if args.install:
        if not args.credential_ref:
            parser.error("--install requires an existing --credential-ref")
        existing = None
        try:
            existing = runtime.reader.read_account(args.account, fresh=False)
        except KeyError:
            pass
        if existing and existing["provider"] != PROVIDER:
            raise ValueError("Account belongs to another provider")
        retain_method(runtime.reader, provider=PROVIDER, source=Path(__file__).read_text(),
                      allowed_hosts=["imap.gmail.com"], operations=["inventory", "qualify", "verification_code"])
        if not existing or existing.get("metadata", {}).get("credential_ref") != args.credential_ref:
            runtime.reader.put_account({"id": args.account, "provider": PROVIDER,
                "label": "Owned-mail signup verification capability (not a new vendor account)",
                "state": "configured", "expected_revision": existing["revision"] if existing else 0,
                "request_id": "mailbox-verification-install-" + str(int(time.time())),
                "metadata": {"credential_ref": args.credential_ref, "purpose": "platform-signup-verification"}})
    result = runtime.providers.run(args.account, args.operation,
        {"sender_domain": args.sender_domain, "after": args.after, "code_length": args.code_length})
    if args.operation == "qualify" and result["result"].get("status") == "authenticated":
        current = runtime.reader.read_account(args.account, fresh=False)
        runtime.reader.put_account({"id": args.account, "provider": PROVIDER,
            "expected_revision": current["revision"], "state": "authenticated",
            "request_id": "mailbox-verification-qualified-" + str(int(time.time())),
            "observations": {"qualification": {"protocol": "IMAP4_SSL", "observed_at": time.time(),
                                              "message_reads": 0}}})
    print(json.dumps(result))


if __name__ == "__main__":
    main()
