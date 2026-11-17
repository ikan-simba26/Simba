"""The site catalogue (2026-11-13): the shipped list, the person's additions,
addresses as people type them, and taught routines placed on their site."""

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from backend.orchestrator.catalogue import (
    CatalogueError, CatalogueStore, OTHER, address_in, clean_address, host_of, offered,
)

SHIPPED = Path(__file__).resolve().parents[2] / "data" / "catalogue.json"


def store(tmp_path: Path, sites: list | None = None) -> CatalogueStore:
    path = tmp_path / "catalogue.json"
    path.write_text(json.dumps({
        "genres": ["Travel", "Bills"],
        "sites": sites if sites is not None else [
            {"id": "rail", "name": "Railways", "address": "https://www.pakrailways.gov.pk/train",
             "genre": "Travel",
             "tasks": [{"label": "Train times", "goal": "Train times", "how": "built-in",
                        "flow": "railways"}]},
            {"id": "bill", "name": "Bill copy", "address": "http://127.0.0.1:5100",
             "genre": "Bills",
             "tasks": [{"label": "Bill", "goal": "Check my bill", "how": "ai"}]},
        ]}), encoding="utf-8")
    return CatalogueStore(path, tmp_path / "local.json")


# ------------------------------------------------------------ the shipped file

def test_the_shipped_catalogue_reads_whole():
    catalogue = CatalogueStore(SHIPPED, SHIPPED.parent / "no-such-local.json").load()
    # At least five genres with a site in them, as the advisor asked.
    used = {site.genre for site in catalogue.sites}
    assert len(used - {"Practice sites"}) >= 5
    assert len(catalogue.sites) >= 10
    # Every site has a task, and none was dropped as malformed.
    raw = json.loads(SHIPPED.read_text(encoding="utf-8"))
    assert len(catalogue.sites) == len(raw["sites"])
    assert all(site.tasks for site in catalogue.sites)
    # The three built-in flows are each reachable from the list.
    flows = {task.flow for site in catalogue.sites for task in site.tasks if task.flow}
    assert flows == {"registration", "billing", "railways"}


def test_no_shipped_site_is_daraz():
    # DECISIONS.md, 2026-11-13: robots.txt disallows its cart and checkout.
    catalogue = CatalogueStore(SHIPPED, SHIPPED.parent / "no-such-local.json").load()
    assert not any("daraz" in site.address for site in catalogue.sites)


# ------------------------------------------------------------ addresses

@pytest.mark.parametrize("typed, whole", [
    ("gov.uk/bank-holidays", "https://gov.uk/bank-holidays"),
    ("https://www.Daewoo.com.pk", "https://www.daewoo.com.pk/"),
    ("127.0.0.1:5100", "http://127.0.0.1:5100/"),
    ("  http://bill.pitc.com.pk/iescobill?x=1#top ", "http://bill.pitc.com.pk/iescobill?x=1"),
])
def test_an_address_as_typed_is_made_whole(typed, whole):
    assert clean_address(typed) == whole


@pytest.mark.parametrize("typed", [
    "", "hello", "14.382", "file:///C:/Windows", "javascript:alert(1)",
    "ftp://example.com", "trains to Karachi", "C:\\simba\\data",
])
def test_anything_else_is_not_an_address(typed):
    with pytest.raises(CatalogueError) as raised:
        clean_address(typed)
    assert raised.value.reason == "address"


@pytest.mark.parametrize("goal, address", [
    ("when is the next bank holiday on gov.uk", "https://gov.uk/"),
    ("www.daewoo.com.pk bus times to Multan", "https://www.daewoo.com.pk/"),
    ("check https://bill.pitc.com.pk/iescobill please.", "https://bill.pitc.com.pk/iescobill"),
    ("my bill is Rs 14.382, due soon", None),
    ("trains to Rawalpindi tomorrow", None),
    ("write to me at someone@example.com", None),
    ("e.g. a bus", None),
])
def test_an_address_written_in_a_goal_is_found(goal, address):
    assert address_in(goal) == address


def test_a_host_is_the_same_with_or_without_www_and_keeps_its_port():
    assert host_of("https://www.gov.uk/x") == host_of("http://gov.uk/") == "gov.uk"
    assert host_of("http://127.0.0.1:5100") != host_of("http://127.0.0.1:5000")


# ------------------------------------------------------------ the person's additions

def test_a_site_added_is_listed_after_the_shipped_ones(tmp_path):
    catalogue = store(tmp_path)
    added = catalogue.add("  My   clinic ", "clinic.example.pk/appointments", "Health")
    sites = catalogue.load().sites
    assert sites[-1] == added
    assert added.name == "My clinic"
    assert added.address == "https://clinic.example.pk/appointments"
    # Not one of the list's genres: it goes under Other, and Other is listed.
    assert added.genre == OTHER
    assert OTHER in catalogue.load().genres
    assert added.added and added.tasks == ()


def test_a_site_added_never_touches_the_shipped_file(tmp_path):
    catalogue = store(tmp_path)
    before = catalogue.path.read_text(encoding="utf-8")
    catalogue.add("Clinic", "clinic.example.pk", "Bills")
    assert catalogue.path.read_text(encoding="utf-8") == before
    assert catalogue.local.exists()


@pytest.mark.parametrize("name, address, reason", [
    ("", "example.com", "name"),
    ("Mine", "not an address", "address"),
    ("Again", "pakrailways.gov.pk/train", "listed"),
])
def test_a_site_that_cannot_be_added_says_why(tmp_path, name, address, reason):
    with pytest.raises(CatalogueError) as raised:
        store(tmp_path).add(name, address, "Travel")
    assert raised.value.reason == reason


def test_the_added_list_has_an_end(tmp_path):
    catalogue = store(tmp_path)
    for n in range(30):
        catalogue.add(f"Site {n}", f"site{n}.example.com", "Travel")
    with pytest.raises(CatalogueError) as raised:
        catalogue.add("One more", "more.example.com", "Travel")
    assert raised.value.reason == "full"


def test_an_added_site_can_be_taken_off_and_a_shipped_one_cannot(tmp_path):
    catalogue = store(tmp_path)
    added = catalogue.add("Clinic", "clinic.example.pk", "Bills")
    assert catalogue.remove(added.id)
    assert not catalogue.remove("rail")
    assert [site.id for site in catalogue.load().sites] == ["rail", "bill"]


def test_forget_me_clears_the_added_sites(tmp_path):
    catalogue = store(tmp_path)
    catalogue.add("Clinic", "clinic.example.pk", "Bills")
    catalogue.clear()
    assert [site.id for site in catalogue.load().sites] == ["rail", "bill"]
    catalogue.clear()  # twice is harmless


# ------------------------------------------------------------ damaged files

def test_a_damaged_row_is_one_site_fewer(tmp_path):
    catalogue = store(tmp_path, sites=[
        {"id": "ok", "name": "OK", "address": "example.com", "genre": "Travel", "tasks": []},
        {"id": "bad", "name": "Bad", "address": "javascript:alert(1)", "genre": "Travel"},
        {"id": "noname", "name": "  ", "address": "example.org"},
        "not even a row",
        {"id": "ok", "name": "Duplicate id", "address": "example.net"},
        {"id": "flowless", "name": "Flowless", "address": "example.io",
         "tasks": [{"label": "x", "goal": "x", "how": "built-in", "flow": "nope"},
                   {"label": "y", "goal": "y", "how": "magic"}]},
    ])
    sites = catalogue.load().sites
    assert [site.id for site in sites] == ["ok", "flowless"]
    assert sites[1].tasks == ()


def test_an_unreadable_file_is_an_empty_list(tmp_path):
    path = tmp_path / "catalogue.json"
    path.write_text("{not json", encoding="utf-8")
    assert CatalogueStore(path, tmp_path / "local.json").load().sites == []


# ------------------------------------------------------------ taught routines

@dataclass
class Routine:
    id: str
    label: str
    start: str


def test_a_taught_routine_is_a_task_on_the_site_it_was_taught_on(tmp_path):
    catalogue = store(tmp_path).load()
    sites = offered(catalogue, [Routine("r1", "My bill", "http://127.0.0.1:5100/"),
                                Routine("r2", "Elsewhere", "https://nowhere.example/")])
    bill = next(site for site in sites if site.id == "bill")
    assert bill.tasks[-1].how == "taught"
    assert bill.tasks[-1].routine == "r1"
    # Not on the railways site, and the unlisted one is a tile only.
    rail = next(site for site in sites if site.id == "rail")
    assert all(task.how != "taught" for task in rail.tasks)
    assert len(sites) == 2


# ------------------------------------------------------- a site named in words

def shipped_store() -> CatalogueStore:
    return CatalogueStore(SHIPPED, SHIPPED.parent / "no-such-local.json")


@pytest.mark.parametrize("goal, site_id", [
    ("find me the price of the book alchemist on readings book", "readings"),
    ("Order the book Sapiens from Readings bookshop", "readings"),
    ("look up Allama Iqbal on Wikipedia", "wikipedia"),
    ("search for a bicycle on OLX", "olx"),
])
def test_a_goal_that_names_a_listed_site_is_for_that_site(goal, site_id):
    found = shipped_store().named_in(goal)
    assert found is not None and found.id == site_id


@pytest.mark.parametrize("goal", [
    "Trains from Lahore to Karachi tomorrow",
    "hello",
    "compare readings and olx for this book",   # two sites: not decided here
])
def test_a_goal_that_names_no_single_site_is_for_none(goal):
    assert shipped_store().named_in(goal) is None
