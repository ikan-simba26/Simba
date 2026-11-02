"""The overwhelm index reads a page only if it may, and scores it only if it is one.

Every test here is against a server on this machine: a real browser and the real
pipeline, never a live site. What matters most is what must not happen. A page
robots.txt forbids is never opened, a robots.txt nobody could read is not
permission, and a firewall's refusal, which this model would call calm, is never
ranked.
"""

import concurrent.futures
import csv
import asyncio
import http.server
import threading
import urllib.error
from collections.abc import Iterator
from pathlib import Path

import pytest

from backend.estimator import page_model
from backend.estimator.page_features import PageFeatures
from tools.evaluation import overwhelm_index as index
from tools.evaluation.collect_corpus import UA
from tools.evaluation.overwhelm_index import Robots, Site
from tools.screen_site import USER_AGENT

BUSY = ("<!doctype html><title>A busy page</title><h1>Welcome</h1>"
        + "".join(f"<p><a href='/{n}'>A long link number {n} with several words</a></p>"
                  for n in range(60))
        + "<p>" + "Plain sentences about the service sit here. " * 60 + "</p>")


class Sites(http.server.BaseHTTPRequestHandler):
    """Pages by path, and a record of everything asked for."""

    pages: dict[str, tuple[int, str]] = {}
    asked: list[tuple[str, str, str]] = []

    def answer(self) -> None:
        Sites.asked.append((self.command, self.path, self.headers.get("User-Agent", "")))
        status, body = Sites.pages.get(self.path, (404, "not here"))
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type",
                         "text/plain" if self.path == "/robots.txt" else "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = do_HEAD = answer

    def log_message(self, *_: object) -> None:
        pass


@pytest.fixture
def host() -> Iterator[str]:
    Sites.pages, Sites.asked = {}, []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Sites)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.fixture
def model() -> page_model.PageModel:
    found = page_model.load()
    assert found is not None
    return found


def surveyed(sites, model, into: Path, **options):
    """On a thread of its own: a sync Playwright session holds this one."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, index.survey(
            tuple(sites), model, into, pause_s=options.pop("pause_s", 0), **options)).result()


def site(host: str, path: str = "/") -> Site:
    return Site("A site", index.UTILITY, f"{host}{path}", "To test with")


def features(**values: float) -> PageFeatures:
    base = dict(interactive=5, links=20, inferred=0, text_density=1.0, max_depth=8, overlays=0,
                form_fields=0, dead_link_ratio=0.0, reading_grade=8.0, controls=25, dead_links=0,
                characters=800, viewport_characters=800, words=120, sentences=8, syllables=200)
    return PageFeatures(**{**base, **values})


# --- the list ----------------------------------------------------------------


def test_the_list_is_about_forty_across_all_seven_kinds() -> None:
    assert 38 <= len(index.SITES) <= 44
    assert {s.category for s in index.SITES} == {
        index.GOVERNMENT, index.UTILITY, index.UNIVERSITY, index.BANK, index.TELECOM,
        index.TRANSPORT, index.HEALTH}
    assert all(s.why and s.url.startswith("https://") for s in index.SITES)


def test_no_site_appears_twice() -> None:
    assert len({s.url for s in index.SITES}) == len(index.SITES)
    assert len({s.name for s in index.SITES}) == len(index.SITES)


def test_only_main_pages_and_never_a_sign_in() -> None:
    for entry in index.SITES:
        assert not index.SIGN_IN.search(entry.url.split("/", 3)[-1]), entry.url
        assert entry.url.count("/") == 3 and entry.url.endswith("/"), entry.url


def test_the_page_is_fetched_as_the_agent_robots_was_read_for() -> None:
    assert UA == USER_AGENT
    assert index.VIEWPORT == {"width": 1280, "height": 800}


# --- robots.txt --------------------------------------------------------------


def test_a_disallowed_page_is_never_opened(host: str, model, tmp_path: Path) -> None:
    Sites.pages = {"/robots.txt": (200, "User-agent: *\nDisallow: /"), "/": (200, BUSY)}

    rows, _ = surveyed([site(host)], model, tmp_path)

    assert rows[0]["status"] == "skipped"
    assert "disallowed" in rows[0]["note"]
    assert "/" not in [path for _, path, _ in Sites.asked]


def test_a_rule_for_this_agent_alone_counts(host: str, model, tmp_path: Path) -> None:
    Sites.pages = {"/robots.txt": (200, "User-agent: SIMBA-screener\nDisallow: /\n"),
                   "/": (200, BUSY)}

    rows, _ = surveyed([site(host)], model, tmp_path)

    assert rows[0]["status"] == "skipped"


def test_no_robots_file_means_no_rules_stated(host: str, model, tmp_path: Path) -> None:
    Sites.pages = {"/": (200, BUSY)}

    rows, _ = surveyed([site(host)], model, tmp_path)

    assert rows[0]["status"] == "scored", rows[0]
    assert "no robots.txt" in rows[0]["note"]


@pytest.mark.parametrize("code", [401, 403])
def test_a_refused_robots_file_is_a_no(host: str, model, tmp_path: Path, code: int) -> None:
    Sites.pages = {"/robots.txt": (code, "no"), "/": (200, BUSY)}

    rows, _ = surveyed([site(host)], model, tmp_path)

    assert rows[0]["status"] == "skipped"
    assert "/" not in [path for _, path, _ in Sites.asked]


def test_a_server_in_trouble_is_not_permission(host: str, model, tmp_path: Path) -> None:
    """RFC 9309: unreachable means assume the worst. The screener's own fetch
    reads this as no rules at all when it cannot read the file."""
    Sites.pages = {"/robots.txt": (503, "down"), "/": (200, BUSY)}

    rows, _ = surveyed([site(host)], model, tmp_path)

    assert rows[0]["status"] == "skipped"
    assert "unreachable" in rows[0]["note"]
    assert "/" not in [path for _, path, _ in Sites.asked]


def test_a_file_python_could_not_reach_gets_a_try_in_the_browser(
    host: str, model, tmp_path: Path,
) -> None:
    """An incomplete certificate chain stops `urllib` and not Chromium."""
    Sites.pages = {"/robots.txt": (200, "User-agent: *\nAllow: /\n"), "/": (200, BUSY)}

    def fails(_: str):
        return None, "(could not fetch robots.txt: CERTIFICATE_VERIFY_FAILED)"

    rows, _ = surveyed([site(host)], model, tmp_path, fetch=fails)

    assert rows[0]["status"] == "scored", rows[0]


def test_nothing_reachable_at_all_is_a_skip(model, tmp_path: Path) -> None:
    def fails(_: str):
        return None, "(could not fetch robots.txt: timed out)"

    rows, _ = surveyed([site("http://127.0.0.1:1")], model, tmp_path, fetch=fails)

    assert rows[0]["status"] == "skipped"
    assert "unreachable" in rows[0]["note"]


def test_an_http_error_from_the_screener_does_not_stop_the_run() -> None:
    def forbids(url: str):
        raise urllib.error.HTTPError(url, 403, "Forbidden", None, None)

    assert index.from_python("https://example.org/", forbids) == Robots(
        False, "robots.txt refused: HTTP 403")


# --- one visit ---------------------------------------------------------------


def test_one_visit_nothing_sent_and_a_picture_of_the_frozen_size(
    host: str, model, tmp_path: Path,
) -> None:
    Sites.pages = {"/robots.txt": (200, "User-agent: *\nAllow: /\n"), "/": (200, BUSY)}

    rows, _ = surveyed([site(host)], model, tmp_path)

    row = rows[0]
    assert row["status"] == "scored", row
    assert [path for _, path, _ in Sites.asked if path == "/"] == ["/"]
    assert {method for method, _, _ in Sites.asked} == {"GET"}
    assert {agent for _, _, agent in Sites.asked} == {USER_AGENT}
    assert row["layout_width"] == 1280

    from struct import unpack

    png = (tmp_path / row["screenshot"]).read_bytes()
    assert unpack(">II", png[16:24]) == (1280, 800)


def test_a_score_has_all_it_was_asked_for(host: str, model, tmp_path: Path) -> None:
    Sites.pages = {"/": (200, BUSY)}

    row = surveyed([site(host)], model, tmp_path)[0][0]

    for name in page_model.FEATURES:
        assert name in row
    assert 1 <= row["rating"] <= 5
    assert 0 <= row["score"] <= 1
    assert row["page_band"] in (1, 2, 3)
    assert row["simba_level"] in (2, 3)
    assert row["sha256"]


def test_one_broken_site_does_not_stop_the_rest(host: str, model, tmp_path: Path) -> None:
    Sites.pages = {"/good": (200, BUSY)}
    dead = Site("Dead", index.BANK, "http://127.0.0.1:1/", "Refuses connections")

    def no_rules(_: str):
        from urllib.robotparser import RobotFileParser

        parser = RobotFileParser()
        parser.parse([])
        return parser, "(no robots.txt: HTTP 404)"

    rows, _ = surveyed([dead, site(host, "/good")], model, tmp_path, fetch=no_rules)

    assert [row["status"] for row in rows] == ["failed", "scored"]


# --- what is not a page ------------------------------------------------------


@pytest.mark.parametrize("status, body", [
    (403, BUSY),
    (500, BUSY),
    (200, "<title>Just a moment...</title><p>Checking your browser before you continue.</p>"),
    (200, "<title>Attention Required! | Cloudflare</title><p>You have been blocked.</p>"),
    (200, "<title>Request Rejected</title><p>The requested URL was rejected.</p>"),
    (200, "<title>Access Denied</title><p>You don't have permission.</p>"),
    (200, "<title>Welcome</title>"),
])
def test_a_refusal_is_failed_never_ranked(
    host: str, model, tmp_path: Path, status: int, body: str,
) -> None:
    """The model would call each of these calm: short, plain, few links."""
    Sites.pages = {"/": (status, body)}

    rows, _ = surveyed([site(host)], model, tmp_path)

    assert rows[0]["status"] == "failed", rows[0]
    assert index.ranked(rows) == []
    assert list(tmp_path.glob("*.png")) == []


def test_a_redirect_to_sign_in_is_failed(host: str, model, tmp_path: Path) -> None:
    Sites.pages = {"/": (200, "<meta http-equiv=refresh content='0;url=/login'>"),
                   "/login": (200, BUSY)}

    rows, _ = surveyed([site(host)], model, tmp_path)

    assert rows[0]["status"] == "failed", rows[0]
    assert "sign-in" in rows[0]["note"]


@pytest.mark.parametrize("path", ["/login", "/Sign-In", "/portal/login.aspx", "/sso/start"])
def test_sign_in_addresses_are_seen(path: str) -> None:
    assert index.SIGN_IN.search(path)


@pytest.mark.parametrize("path", ["/", "/blogin-news", "/authors", "/designing"])
def test_other_addresses_are_not(path: str) -> None:
    assert not index.SIGN_IN.search(path)


def test_a_real_page_with_an_error_in_its_later_words_is_kept() -> None:
    """Only the top of a page is read for a refusal: a bank's page can say 404
    somewhere and still be a page."""
    text = "Welcome to the bank. " * 40 + "Call 404 for help."
    row = {"interactive": 20, "links": 60, "characters": 5000}

    assert index.not_a_page(200, "A bank", text, "https://bank.example/", row) is None


# --- the numbers -------------------------------------------------------------


def test_simba_level_comes_from_the_rules_and_a_calm_page_is_still_two(model) -> None:
    calm = {**features(text_density=0.1, links=2, interactive=1).as_dict()}

    row = index.judged(calm, model)

    assert row["page_band"] == 1, row
    assert row["simba_level"] == 2


def test_a_heavy_page_starts_at_three(model) -> None:
    heavy = features(text_density=12.0, links=400, interactive=120).as_dict()

    row = index.judged(heavy, model)

    assert row["page_band"] == 3
    assert row["simba_level"] == 3


def test_a_score_past_the_corpus_is_said_to_be() -> None:
    ranges = index.corpus_ranges()
    row = features(links=int(ranges["links"][1]) + 1).as_dict()

    assert "links" in index.outside(row, ranges)


def test_a_page_inside_the_corpus_is_not_flagged() -> None:
    ranges = index.corpus_ranges()
    row = {name: (low + high) / 2 for name, (low, high) in ranges.items()}

    assert index.outside(row, ranges) == []


def test_urdu_share_reads_letters_only() -> None:
    assert index.urdu_share("") == 0
    assert index.urdu_share("hello 123") == 0
    assert index.urdu_share("پاکستان") == 1
    assert index.urdu_share("پاک ab") == pytest.approx(0.6)


def scored(name: str, category: str, rating: float, reasons: list[str], band: int = 2) -> dict:
    return {"site": name, "category": category, "status": "scored", "rating": rating, "score": 0.5,
            "page_band": band, "simba_level": max(2, band), "reasons": reasons, "urdu_share": 0.0,
            "outside_corpus": []}


def missed(name: str, category: str, status: str = "failed") -> dict:
    return {"site": name, "category": category, "status": status, "note": "HTTP 403"}


def test_ranked_most_first_ties_by_name_and_only_what_was_scored() -> None:
    rows = [scored("B", "x", 3.0, []), missed("Z", "x"), scored("A", "x", 3.0, []),
            scored("C", "x", 4.0, [])]

    assert [row["site"] for row in index.ranked(rows)] == ["C", "A", "B"]


def test_a_category_mean_counts_only_scored_pages() -> None:
    rows = [scored("A", "Banks", 4.0, [], band=3), scored("B", "Banks", 3.0, []),
            missed("C", "Banks"), scored("D", "Health", 2.0, []), missed("E", "Telecoms")]

    groups = index.by_category(rows)

    assert groups[0] == {"category": "Banks", "listed": 3, "scored": 2, "mean": 3.5, "heavy": 1}
    assert [group["category"] for group in groups] == ["Banks", "Health", "Telecoms"]
    assert groups[2]["mean"] is None


def test_common_reasons_ignore_a_links_count() -> None:
    rows = [scored("A", "x", 3, ["many links (240)", "a lot of text on screen"]),
            scored("B", "x", 3, ["many links (88)", "a lot of text on screen"]),
            scored("C", "x", 3, ["many links (9)"]), missed("D", "x")]

    assert index.common_reasons(rows) == [("many links", 3), ("a lot of text on screen", 2)]


def full_row(name: str, rating: float, band: int) -> dict:
    row = scored(name, "Banks", rating, ["many links (240)"], band)
    return {**row, **{feature: 1 for feature in page_model.FEATURES}, "url": "https://x.example/",
            "final_url": "https://x.example/", "title": "پاکستان", "http_status": 200,
            "screenshot": "x.png", "sha256": "abc"}


def test_the_csv_is_ranked_and_keeps_urdu(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"

    index.write_csv([full_row("Low", 2.0, 1), missed("Gone", "Banks"), full_row("High", 4.0, 3)],
                    path)

    with path.open(encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
    assert [(row["rank"], row["site"]) for row in rows] == [("1", "High"), ("2", "Low")]
    assert rows[0]["reason_1"] == "many links (240)" and rows[0]["reason_2"] == ""
    assert rows[0]["title"] == "پاکستان"


def test_the_report_names_what_was_missed_and_its_limits(model) -> None:
    rows = [full_row("High", 4.0, 3), missed("Gone", "Banks", "skipped")]
    recorded = {"taken_at": "2026-11-02T18:00:00+05:00", "chromium": "1",
                "git": {"commit": "abc", "branch": "eval/overwhelm-index"}}

    words = index.report(rows, model, recorded)

    assert "**Gone** (skipped): HTTP 403" in words
    assert "prediction" in words
    assert "15 raters" in words and "first screen" in words
    assert model.version in words
