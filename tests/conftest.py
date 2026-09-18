import pathlib

import pytest
from patchright.sync_api import sync_playwright

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture(scope="session")
def page(browser):
    ctx = browser.new_context()
    pg = ctx.new_page()
    yield pg
    ctx.close()


@pytest.fixture
def load(page):
    def _load(name: str):
        page.goto((FIXTURES / name).as_uri(), wait_until="domcontentloaded")
        page.wait_for_timeout(100)
        return page

    return _load