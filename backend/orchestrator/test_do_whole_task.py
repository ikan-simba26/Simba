"""The pieces of 2026-11-17 that need no browser: one item unless asked, the
kept details' boxes, booking numbers, and which words make a goal "do" something."""

from backend.orchestrator import bookings, cards, profile
from backend.orchestrator.llm_loop import DOING_GOAL, goal_words


def test_one_item_unless_the_goal_says_more() -> None:
    assert not cards.goal_wants_many("order me an alchemist book")
    assert not cards.goal_wants_many("Book a bus ticket from Lahore to Karachi on 21 November")
    assert cards.goal_wants_many("order 2 copies of the alchemist")
    assert cards.goal_wants_many("book 3 tickets")
    assert cards.goal_wants_many("two books please")


def test_add_and_checkout_words() -> None:
    assert cards.ADD_WORDS.search("Add to Cart")
    assert cards.CHECKOUT_WORDS.search("Proceed to checkout")
    assert not cards.ADD_WORDS.search("Search")


def test_a_box_is_matched_to_the_detail_it_wants() -> None:
    assert profile.kind_of("Passenger Name") == "name"
    assert profile.kind_of("Enter Your Phone #") == "phone"
    assert profile.kind_of("CNIC") == "cnic"
    assert profile.kind_of("Email Address") == "email"
    assert profile.kind_of("City") == "city"
    # A sign-in, a card and a code are never kept as details.
    assert profile.kind_of("Password") is None
    assert profile.kind_of("User name") is None
    assert profile.kind_of("Card number") is None
    assert profile.kind_of("Search") is None


def test_the_details_are_kept_encrypted_and_never_in_the_clear(tmp_path) -> None:
    store = profile.ProfileVault(tmp_path / "profile.json")
    if not store.available:
        return  # not Windows: nothing is kept, as for the sign-in vault
    store.put("phone", "03001234567")
    assert store.get("phone") == "03001234567"
    assert "03001234567" not in (tmp_path / "profile.json").read_text(encoding="utf-8")
    assert store.forget() and store.get("phone") is None


def test_a_booking_keeps_what_was_chosen_but_not_who_you_are(tmp_path) -> None:
    from shared.schema import Detail

    store = bookings.BookingStore(tmp_path / "bookings.json")
    store.add("Book a bus ticket", "https://daewoo.com.pk/x",
              [Detail(label="Seat", value="Window, row 3"), Detail(label="Phone", value="0300"),
               Detail(label="Amount", value="Rs 4,500")], "Booking no DW-123456")
    [kept] = store.all()
    assert kept.number == "DW-123456"
    assert kept.amount == "Rs 4,500"
    assert [line.label for line in kept.lines] == ["Seat", "Amount"]
    assert "0300" not in (tmp_path / "bookings.json").read_text(encoding="utf-8")


def test_what_a_goal_is_about() -> None:
    assert goal_words("Order me an alchemist book") == ["alchemist"]
    assert DOING_GOAL.search("order me an alchemist book")
    assert not DOING_GOAL.search("find the price of Atomic Habits")
