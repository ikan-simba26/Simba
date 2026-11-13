"""robots.txt, asked before the AI planner opens a website (2026-11-13), and
the words that mark a press as a change, now that the AI works on live sites.
A server on this machine plays every answer a site can give; nothing reaches
another computer."""

import asyncio
import http.server
import socketserver
import threading

import pytest

from backend.orchestrator import robots
from backend.orchestrator.loop import CHANGE_WORDS, Move, would_change
from backend.orchestrator.plan import Expectation, Operation, Target


def serve(status: int, body: str = "", content_type: str = "text/plain"):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *args):
            pass

    server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture
def remote(monkeypatch):
    """The local server, read as if it were someone else's site: the check
    skips this machine's own addresses, so the test points `LOCAL` elsewhere."""
    monkeypatch.setattr(robots, "LOCAL", ("never.local",))
    servers = []

    def make(status, body="", content_type="text/plain"):
        server = serve(status, body, content_type)
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}"
    yield make
    for server in servers:
        server.shutdown()


def allowed(address: str) -> bool:
    return asyncio.run(robots.allowed(address))


def test_a_disallowed_page_is_not_used(remote):
    site = remote(200, "User-agent: *\nDisallow: /private/\n")
    assert not allowed(f"{site}/private/form")
    assert allowed(f"{site}/public/form")


def test_a_rule_for_simba_is_heard(remote):
    site = remote(200, "User-agent: SIMBA\nDisallow: /\n\nUser-agent: *\nAllow: /\n")
    assert not allowed(f"{site}/anything")


def test_no_robots_txt_allows_everything(remote):
    assert allowed(f"{remote(404)}/train")


@pytest.mark.parametrize("status", [401, 403])
def test_a_refused_robots_txt_is_a_no(remote, status):
    assert not allowed(f"{remote(status)}/train")


def test_a_page_where_rules_should_be_is_no_rules(remote):
    # Pakistan Railways answers /robots.txt with its own HTML (EVALUATION.md,
    # 2026-11-12): that is a site with no rules, not a site that says no.
    site = remote(200, "<!DOCTYPE html><html><body>Home</body></html>", "text/html")
    assert allowed(f"{site}/train")


def test_a_site_that_does_not_answer_is_a_no(monkeypatch):
    monkeypatch.setattr(robots, "LOCAL", ("never.local",))
    # A port nothing listens on.
    assert not allowed("http://127.0.0.1:9/train")


def test_our_own_copies_are_never_asked():
    assert allowed("http://127.0.0.1:9/whatever")


def move(label: str) -> Move:
    return Move(instruction="", detail="", expect=Expectation(), fields=[], actions=[],
                operations=[Operation(kind="click", target=Target(role="button", label=label))])


@pytest.mark.parametrize("label", [
    "Apply now", "Send", "Sign up", "Create account", "Place order", "Order now",
    "Proceed to payment", "Subscribe", "Donate", "Save changes", "Delete my account",
    "Book", "Pay", "Submit", "Confirm", "Checkout",
])
def test_a_press_whose_words_change_something_is_a_change(label):
    assert CHANGE_WORDS.search(label), label
    assert would_change(move(label), object())


@pytest.mark.parametrize("label", [
    "Search", "Show more", "Next month", "Find trains", "Check Bill", "Look up",
    "Close", "Accept all cookies", "Menu", "Sending times",
])
def test_a_press_that_only_reads_is_not(label):
    assert not would_change(move(label), object()), label
