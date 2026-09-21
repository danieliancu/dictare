"""Responsive smoke tests in a real browser (Playwright + Chromium).

    pip install -r requirements/dev.txt && python -m playwright install chromium
    pytest -m e2e

Checks every key page at phone, tablet and desktop widths for horizontal overflow,
the right navigation, and primary CTAs being inside the viewport.
"""

import os

import pytest

playwright = pytest.importorskip("playwright.sync_api")

# Playwright's sync API runs an event loop in this thread; Django's ORM is used only
# from fixtures before the browser starts.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

WIDTHS = [320, 375, 390, 430, 768, 1024, 1280, 1440]
MOBILE_MAX = 768
HEADER_BREAKPOINT = 960


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # browser binaries not installed
            pytest.skip(f"Chromium not available: {exc}")
        yield b
        b.close()


@pytest.fixture
def site(live_server, plans, accent, phrases):
    return live_server.url


def open_page(browser, url, width):
    page = browser.new_page(viewport={"width": width, "height": 900 if width > 800 else 800})
    page.goto(url)
    page.wait_for_load_state("networkidle")
    return page


def assert_no_horizontal_overflow(page, width):
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    assert scroll_width <= width, f"horizontal overflow: {scroll_width}px > {width}px"


def assert_in_viewport_x(page, selector, width):
    box = page.locator(selector).first.bounding_box()
    assert box is not None, f"{selector} not rendered"
    assert box["x"] >= 0 and box["x"] + box["width"] <= width + 1, f"{selector} off-screen"


@pytest.mark.parametrize("width", WIDTHS)
def test_homepage(browser, site, width):
    page = open_page(browser, site + "/", width)
    assert_no_horizontal_overflow(page, width)
    assert_in_viewport_x(page, ".hero__ctas .btn--primary", width)
    nav_visible = page.locator(".site-nav").is_visible()
    toggle_visible = page.locator("[data-nav-toggle]").is_visible()
    if width <= HEADER_BREAKPOINT:
        assert toggle_visible and not nav_visible
        page.click("[data-nav-toggle]")
        assert page.locator("#mobile-menu").is_visible()
    else:
        assert nav_visible and not toggle_visible
    assert page.locator(".phone").is_visible()
    page.close()


@pytest.mark.parametrize("width", WIDTHS)
def test_practice_session(browser, site, width):
    page = open_page(browser, site + "/practice/daily/", width)
    assert "/practice/session/" in page.url
    assert_no_horizontal_overflow(page, width)
    for selector in [
        "[data-play]",
        ".level-tabs",
        "textarea[name=answer]",
        ".answer button[type=submit]",
        "[data-reveal]",
    ]:
        assert page.locator(selector).first.is_visible(), selector
        assert_in_viewport_x(page, selector, width)
    submit = page.locator(".answer button[type=submit]").bounding_box()
    assert submit["height"] >= 44, "primary action must be touch friendly"

    page.fill("textarea[name=answer]", "hello there")
    page.click(".answer button[type=submit]")
    page.wait_for_selector(".result")
    assert_no_horizontal_overflow(page, width)
    assert page.locator(".transcript").is_visible()
    page.close()


@pytest.mark.parametrize("width", [375, 1280])
def test_logged_in_navigation(browser, site, user, width):
    page = open_page(browser, site + "/login/", width)
    page.fill("input[name=username]", user.email)
    page.fill("input[name=password]", "parola-sigura-123")
    page.click("form button[type=submit]")
    page.wait_for_load_state("networkidle")
    page.goto(site + "/progress/")
    assert_no_horizontal_overflow(page, width)
    bottom_nav = page.locator(".bottom-nav").is_visible()
    assert bottom_nav == (width <= MOBILE_MAX)
    page.close()
