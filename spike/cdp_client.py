"""Connects to the Electron spike over CDP and drives the hidden view."""

from playwright.sync_api import sync_playwright


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")

        target_page = None
        for context in browser.contexts:
            for page in context.pages:
                if "example.com" in page.url:
                    target_page = page
                    break
            if target_page:
                break

        if target_page is None:
            raise RuntimeError("No page with URL containing 'example.com' found")

        print("Title:", target_page.title())

        links = target_page.query_selector_all("a")
        for link in links:
            print("Link text:", link.inner_text())

        if not links:
            raise RuntimeError("No links found on the page")

        links[0].click()
        target_page.wait_for_load_state()
        print("Resulting URL:", target_page.url)


if __name__ == "__main__":
    main()
