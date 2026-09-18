"""Unit tests for the LinkedIn tool flows using a fake page, so the logic in
linkedin.py is exercised without a real browser or network.

Only the DOM regression suite in test_selectors.py needs a headless browser.
"""

import pytest

from linkedin_mcp import linkedin
from linkedin_mcp.browser import BrowserError

LOGIN_SEL = (
    '[data-testid="primary-nav"], a[href*="/mynetwork"], a[href*="/jobs/"]'
)
COMPOSE_TRIGGER = (
    'a[href*="sharebox"], a[aria-label="Start a post"], '
    'button[aria-label*="Start a post"], .share-box-feed-entry__trigger'
)
EDITOR_SEL = (
    '.ql-editor[contenteditable="true"], div[contenteditable="true"][role="textbox"]'
)
ARTICLES_SEL = (
    "article.feed-shared-update-v2, div[data-urn*='activity'], .occludable-update"
)
POST_MENU_SEL = 'button[aria-label*="control menu for post"]'
DELETE_ITEM_SEL = (
    "li.option-delete div[role='button'], "
    "li.feed-shared-control-menu__item.option-delete"
)
EDIT_ITEM_SEL = (
    "li.option-edit-share div[role='button'], "
    "li.feed-shared-control-menu__item.option-edit-share"
)
DELETE_DIALOG_SEL = ".feed-components-shared-decision-modal"
EDIT_MODAL_SEL = ".share-box-v2__modal"


def role_key(role, name, exact=True):
    return f"role={role}:name={name}:exact={exact}"


class _Noop:
    def count(self):
        return 0

    @property
    def first(self):
        return self

    @property
    def last(self):
        return self

    def nth(self, i):
        return self

    def all(self):
        return []

    def inner_text(self, *a, **k):
        return ""

    def get_attribute(self, *a, **k):
        return None

    def is_enabled(self):
        return False

    def is_visible(self, *a, **k):
        return False

    def click(self, *a, **k):
        raise AssertionError("clicked a missing element")

    def wait_for(self, *a, **k):
        raise AssertionError("waited for a missing element")

    def scroll_into_view_if_needed(self, *a, **k):
        raise AssertionError("scrolled a missing element")

    def locator(self, sel):
        return self

    def get_by_role(self, **k):
        return self


NOOP = _Noop()


class FakeEl:
    def __init__(self, page, text="", exists=True, enabled=True, visible=True,
                 attrs=None, on_click=None):
        self.page = page
        self.text = text
        self.exists = exists
        self.enabled = enabled
        self.visible = visible
        self.attrs = attrs or {}
        self.on_click = on_click
        self.clicked = 0

    def count(self):
        return 1 if self.exists else 0

    @property
    def first(self):
        return self

    @property
    def last(self):
        return self

    def nth(self, i):
        return self if self.exists else NOOP

    def all(self):
        return [self] if self.exists else []

    def inner_text(self, *a, **k):
        return self.text

    def get_attribute(self, name, *a, **k):
        return self.attrs.get(name)

    def is_enabled(self):
        return self.exists and self.enabled

    def is_visible(self, *a, **k):
        return self.exists and self.visible

    def click(self, *a, **k):
        if not self.exists:
            raise AssertionError("clicked a missing element")
        self.clicked += 1
        if self.on_click:
            self.on_click()

    def wait_for(self, state="visible", **k):
        if not self.exists:
            raise AssertionError(f"waited for state '{state}' on a missing element")

    def scroll_into_view_if_needed(self, *a, **k):
        if not self.exists:
            raise AssertionError("scrolled a missing element")

    def locator(self, sel):
        return FakeLocator(self.page, sel)

    def get_by_role(self, role=None, name=None, exact=None):
        return self.page.get_by_role(role=role, name=name, exact=exact)


class FakeLocator:
    def __init__(self, page, key):
        self.page = page
        self.key = key

    def _els(self):
        return self.page._els_for(self.key)

    def count(self):
        return len(self._els())

    @property
    def first(self):
        els = self._els()
        return els[0] if els else NOOP

    @property
    def last(self):
        els = self._els()
        return els[-1] if els else NOOP

    def nth(self, i):
        els = self._els()
        return els[i] if i < len(els) else NOOP

    def all(self):
        return list(self._els())

    def inner_text(self, *a, **k):
        els = self._els()
        return els[0].inner_text() if els else ""

    def get_attribute(self, name, *a, **k):
        els = self._els()
        return els[0].get_attribute(name) if els else None

    def is_enabled(self):
        els = self._els()
        return bool(els) and els[0].is_enabled()

    def is_visible(self, *a, **k):
        els = self._els()
        return bool(els) and els[0].is_visible()

    def click(self, *a, **k):
        els = self._els()
        if not els:
            raise AssertionError("clicked a missing element")
        els[0].click(*a, **k)

    def wait_for(self, state="visible", **k):
        els = self._els()
        if not els:
            raise AssertionError(f"waited for state '{state}' on a missing element")
        els[0].wait_for(state=state)

    def scroll_into_view_if_needed(self, *a, **k):
        els = self._els()
        if els:
            els[0].scroll_into_view_if_needed()


class FakeKeyboard:
    def __init__(self):
        self.typed = []
        self.pressed = []

    def insert_text(self, text):
        self.typed.append(text)

    def press(self, key):
        self.pressed.append(key)


class FakePage:
    def __init__(self, url="https://www.linkedin.com/feed/"):
        self.url = url
        self.registry = {}
        self.gotos = []
        self.waits = []
        self.keyboard = FakeKeyboard()

    def _els_for(self, key):
        v = self.registry.get(key)
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return [v]

    def set(self, key, el=None, **kw):
        self.registry[key] = el if el is not None else FakeEl(self, **kw)
        return self.registry[key]

    def set_multi(self, key, els):
        self.registry[key] = list(els)

    def set_role(self, role, name, el=None, exact=True, **kw):
        return self.set(role_key(role, name, exact), el=el, **kw)

    def remove(self, key):
        self.registry.pop(key, None)

    def clicked(self, key):
        v = self.registry.get(key)
        if isinstance(v, list):
            return sum(getattr(e, "clicked", 0) for e in v)
        return getattr(v, "clicked", 0) if v is not None else 0

    def locator(self, sel):
        return FakeLocator(self, sel)

    def get_by_role(self, role, name=None, exact=None):
        if name is None:
            return NOOP
        return FakeLocator(self, role_key(role, name, exact))

    def goto(self, url, wait_until=None):
        self.url = url
        self.gotos.append(url)

    def wait_for_timeout(self, ms):
        self.waits.append(ms)

    def wait_for_selector(self, sel, state=None, timeout=None):
        els = self._els_for(sel)
        present = bool(els)
        if state == "detached":
            if present:
                raise AssertionError(f"expected '{sel}' to be detached")
            return None
        if not present:
            raise AssertionError(f"waited for '{sel}' ({state}) but missing")
        return None


class FakeSession:
    def __init__(self, page):
        self.page = page


@pytest.fixture
def page():
    return FakePage()


@pytest.fixture
def session(page):
    pg = FakePage()
    return FakeSession(pg), pg


def logged_in_session():
    pg = FakePage()
    pg.set(LOGIN_SEL)
    return FakeSession(pg), pg


# ---------------------------------------------------------------- is_logged_in

def test_is_logged_in_when_nav_present(page):
    page.set(LOGIN_SEL)
    assert linkedin.is_logged_in(page) is True


def test_is_logged_in_false_on_authwall(page):
    page.url = "https://www.linkedin.com/authwall"
    assert linkedin.is_logged_in(page) is False


def test_is_logged_in_false_when_nav_missing(page):
    assert linkedin.is_logged_in(page) is False


def test_check_session_reports_logged_out(page):
    assert linkedin.check_session(FakeSession(page)) == {"status": "logged_out"}


def test_check_session_reports_ok(page):
    page.set(LOGIN_SEL)
    assert linkedin.check_session(FakeSession(page)) == {"status": "ok"}


# ---------------------------------------------------------------- first_text

def test_first_text_falls_back(page):
    page.set("first", text="one")
    assert linkedin.first_text(page, "missing-a", "first", "missing-b") == "one"


def test_first_text_empty_when_none(page):
    assert linkedin.first_text(page, "nothing", "nothing-else") == ""


# ---------------------------------------------------------------- create_post

def test_create_post_posts_text(session):
    session, pg = session
    pg.set(LOGIN_SEL)
    pg.set(COMPOSE_TRIGGER)
    pg.set(EDITOR_SEL)
    pg.set_role("button", "Post", enabled=True)
    result = linkedin.create_post(session, "Hello world")
    assert result["status"] == "posted"
    assert pg.keyboard.typed == ["Hello world"]


def test_create_post_raises_when_trigger_missing(session):
    session, pg = session
    pg.set(LOGIN_SEL)
    with pytest.raises(BrowserError, match="composer trigger"):
        linkedin.create_post(session, "Hello")


def test_create_post_raises_when_post_button_disabled(session):
    session, pg = session
    pg.set(LOGIN_SEL)
    pg.set(COMPOSE_TRIGGER)
    pg.set(EDITOR_SEL)
    pg.set_role("button", "Post", enabled=False)
    with pytest.raises(BrowserError, match="Post button"):
        linkedin.create_post(session, "Hello")


# ---------------------------------------------------------------- delete_post

def test_delete_post_ready_to_delete_without_confirm(session):
    session, pg = session
    pg.set(LOGIN_SEL)
    pg.set_multi(ARTICLES_SEL, [
        FakeEl(pg, text="A friendly Meta moment about AI"),
        FakeEl(pg, text="Some other post"),
    ])
    result = linkedin.delete_post(session, "Meta moment")
    assert result["status"] == "ready_to_delete"
    assert "Meta moment" in result["post_preview"]
    assert pg.clicked(POST_MENU_SEL) == 0
    assert pg.clicked(DELETE_ITEM_SEL) == 0
    assert pg.clicked(DELETE_DIALOG_SEL) == 0


def test_delete_post_confirmed_flow(session):
    session, pg = session
    pg.set(LOGIN_SEL)
    pg.set_multi(ARTICLES_SEL, [
        FakeEl(pg, text="A friendly Meta moment about AI"),
    ])
    pg.set(POST_MENU_SEL)
    pg.set(DELETE_ITEM_SEL)
    dialog = pg.set(DELETE_DIALOG_SEL)
    confirm = pg.set_role("button", "Delete")
    confirm.on_click = lambda: pg.remove(DELETE_DIALOG_SEL)
    result = linkedin.delete_post(session, "Meta moment", confirm=True)
    assert result["status"] == "deleted"
    assert confirm.clicked == 1


def test_delete_post_raises_when_no_match(session):
    session, pg = session
    pg.set(LOGIN_SEL)
    pg.set_multi(ARTICLES_SEL, [FakeEl(pg, text="Unrelated content")])
    with pytest.raises(BrowserError, match="No post found"):
        linkedin.delete_post(session, "Meta moment", confirm=True)


def test_delete_post_fails_when_dialog_never_appears(session):
    session, pg = session
    pg.set(LOGIN_SEL)
    pg.set_multi(ARTICLES_SEL, [FakeEl(pg, text="A Meta moment post")])
    pg.set(POST_MENU_SEL)
    pg.set(DELETE_ITEM_SEL)
    with pytest.raises(BrowserError, match="delete confirmation dialog"):
        linkedin.delete_post(session, "Meta moment", confirm=True)


# ---------------------------------------------------------------- edit_post

def test_edit_post_replaces_text(session):
    session, pg = session
    pg.set(LOGIN_SEL)
    pg.set_multi(ARTICLES_SEL, [FakeEl(pg, text="Old content to edit")])
    pg.set(POST_MENU_SEL)
    pg.set(EDIT_ITEM_SEL)
    pg.set(
        f"{EDIT_MODAL_SEL} .ql-editor[contenteditable='true'], "
        f"{EDIT_MODAL_SEL} [contenteditable='true']"
    )
    pg.set_role("button", "Save", enabled=True)
    result = linkedin.edit_post(session, "Old content", "Brand new text")
    assert result["status"] == "edited"
    assert result["old_preview"].startswith("Old content")
    assert result["new_preview"] == "Brand new text"
    assert pg.keyboard.typed == ["Brand new text"]


def test_edit_post_raises_when_editor_missing(session):
    session, pg = session
    pg.set(LOGIN_SEL)
    pg.set_multi(ARTICLES_SEL, [FakeEl(pg, text="Old content to edit")])
    pg.set(POST_MENU_SEL)
    pg.set(EDIT_ITEM_SEL)
    with pytest.raises(BrowserError, match="post editor"):
        linkedin.edit_post(session, "Old content", "New text")


def test_edit_post_raises_when_no_match(session):
    session, pg = session
    pg.set(LOGIN_SEL)
    pg.set_multi(ARTICLES_SEL, [FakeEl(pg, text="Unrelated content")])
    with pytest.raises(BrowserError, match="No post found"):
        linkedin.edit_post(session, "Old content", "New text")