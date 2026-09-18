"""DOM regression tests.

These pin the current (2026) LinkedIn page structure so that when LinkedIn
redesigns its markup again, the test suite fails loudly and the broken
selectors are surfaced before a release instead of after.

Selectors under test are copied verbatim from the tools in linkedin.py so any
selector drift breaks a test.
"""

import pytest

pytestmark = pytest.mark.browser


def test_login_nav_selector(load):
    page = load("feed.html")
    assert page.locator('[data-testid="primary-nav"]').count() >= 1
    assert (
        page.locator(
            '[data-testid="primary-nav"], a[href*="/mynetwork"], a[href*="/jobs/"]'
        ).count()
        >= 1
    )


def test_composer_trigger_selector(load):
    page = load("feed.html")
    assert (
        page.locator(
            'a[href*="sharebox"], a[aria-label="Start a post"], '
            'button[aria-label*="Start a post"], .share-box-feed-entry__trigger'
        ).count()
        >= 1
    )


def test_activity_control_menu_button(load):
    page = load("activity.html")
    assert page.locator(
        "article.feed-shared-update-v2, div[data-urn*='activity'], .occludable-update"
    ).count() >= 1
    assert page.locator('button[aria-label*="control menu for post"]').count() >= 1


def test_menu_items_only_after_open(load):
    """Dropdown items for edit/delete must be absent while the menu is closed
    and present once it is open (they are lazily rendered)."""
    closed = load("activity.html")
    assert closed.locator(
        "li.option-delete, li.feed-shared-control-menu__item.option-delete"
    ).count() == 0
    assert closed.locator(
        "li.option-edit-share, li.feed-shared-control-menu__item.option-edit-share"
    ).count() == 0
    open_ = load("menu_open.html")
    assert open_.locator(
        "li.option-delete, li.feed-shared-control-menu__item.option-delete"
    ).count() >= 1
    assert open_.locator(
        "li.option-edit-share, li.feed-shared-control-menu__item.option-edit-share"
    ).count() >= 1


def test_control_menu_labels(load):
    page = load("menu_open.html")
    assert page.locator(
        '.feed-shared-control-menu__headline:has-text("Edit post")'
    ).count() >= 1
    assert page.locator(
        '.feed-shared-control-menu__headline:has-text("Delete post")'
    ).count() >= 1


def test_delete_dialog_selector(load):
    page = load("delete_dialog.html")
    dialog = page.locator(".feed-components-shared-decision-modal").first
    assert dialog.count() >= 1
    assert dialog.get_by_role("button", name="Delete", exact=True).count() == 1
    assert dialog.get_by_role("button", name="Cancel", exact=True).count() == 1


def test_profile_section_selectors(load):
    page = load("profile.html")
    assert page.locator('[id$="QsTopcard"]').count() >= 1
    assert page.locator('[id$="QsAbout"]').count() >= 1
    assert page.locator('[aria-label="Edit about"]').count() >= 1


def test_profile_name_headline_about_content(load):
    """The exact extraction heuristics used by get_my_profile must return the
    real profile values against the captured page."""
    page = load("profile.html")
    topcard = page.locator('[id$="QsTopcard"]').first
    assert topcard.locator("h2").first.inner_text().strip() == "Tushar Chauhan"
    paragraphs = [
        (p.inner_text() or "").strip()
        for p in topcard.locator("p").all()
        if (p.inner_text() or "").strip()
    ]
    headlines = [t for t in paragraphs if t not in ("He/Him", "She/Her", "They/Them") and "|" in t]
    assert headlines and "Backend Engineer" in headlines[0]
    about = page.locator('[id$="QsAbout"]').first
    about_texts = [
        (p.inner_text() or "").strip()
        for p in about.locator("p").all()
        if (p.inner_text() or "").strip()
    ]
    assert about_texts and about_texts[0].startswith("Senior Software Engineer")