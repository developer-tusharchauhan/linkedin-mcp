"""LinkedIn automation routines used by the MCP tools."""

from __future__ import annotations

import json
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

from patchright.sync_api import Page

from linkedin_mcp.browser import BrowserError, BrowserSession

ANSWERS_FILE = Path.home() / ".linkedin-mcp" / "answers.json"
LOGIN_TIMEOUT_SECONDS = 600

JOB_TYPE_CODES = {
    "full_time": "F",
    "part_time": "P",
    "contract": "C",
    "temporary": "T",
    "internship": "I",
    "other": "O",
}
DATE_POSTED_CODES = {
    "day": "r86400",
    "week": "r604800",
    "month": "r2592000",
}
WORK_TYPE_CODES = {"remote": "2", "hybrid": "3", "onsite": "1"}


def first_text(page: Page, *objects) -> str:
    for selector in objects:
        loc = page.locator(selector).first
        if loc.count() > 0:
            try:
                return loc.inner_text(timeout=3000).strip()
            except Exception:
                continue
    return ""


def is_logged_in(page: Page) -> bool:
    if "linkedin.com" not in page.url:
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
    if "authwall" in page.url or "/login" in page.url:
        return False
    try:
        page.wait_for_selector(
            '[data-testid="primary-nav"], a[href*="/mynetwork"], a[href*="/jobs/"]',
            timeout=8000,
        )
        return True
    except Exception:
        return False


def ensure_logged_in(page: Page) -> None:
    if not is_logged_in(page):
        raise BrowserError(
            "Not signed in to LinkedIn. Call the `login` tool first (or on first use "
            "it will open a browser window for you to sign in)."
        )


def _close_modal_if_present(page: Page) -> None:
    try:
        close = page.locator('button[aria-label="Dismiss"]').first
        if close.count() > 0 and close.is_visible(timeout=1000):
            close.click(timeout=2000)
            page.wait_for_timeout(800)
    except Exception:
        pass


def login(session: BrowserSession, wait_seconds: int | None = None) -> dict:
    page = session.page
    timeout = LOGIN_TIMEOUT_SECONDS if wait_seconds is None else wait_seconds
    page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
    deadline = time.time() + timeout
    sessions_seen = 0
    while time.time() < deadline:
        if is_logged_in(page):
            return {"status": "ok", "already_logged_in": sessions_seen == 0}
        sessions_seen += 1
        page.wait_for_timeout(2000)
    raise BrowserError(
        "Timed out waiting for LinkedIn sign-in. Pass `wait_seconds` to allow more time."
    )


def check_session(session: BrowserSession) -> dict:
    logged = is_logged_in(session.page)
    return {"status": "ok" if logged else "logged_out"}


def create_post(session: BrowserSession, text: str) -> dict:
    page = session.page
    ensure_logged_in(page)
    page.goto("https://www.linkedin.com/feed/", wait_until="load")
    trigger = page.locator(
        'a[href*="sharebox"], a[aria-label="Start a post"], '
        'button[aria-label*="Start a post"], .share-box-feed-entry__trigger'
    ).first
    if trigger.count() == 0:
        raise BrowserError("Could not find the post composer trigger.")
    trigger.click()
    editor = page.locator(
        '.ql-editor[contenteditable="true"], div[contenteditable="true"][role="textbox"]'
    ).first
    editor.wait_for(state="visible", timeout=15000)
    editor.click()
    page.keyboard.insert_text(text)
    page.wait_for_timeout(500)
    post_btn = page.get_by_role("button", name="Post", exact=True)
    if post_btn.count() == 0 or not post_btn.is_enabled():
        raise BrowserError("Post button not found or disabled.")
    post_btn.click()
    try:
        page.wait_for_selector(".ql-editor", state="detached", timeout=15000)
    except Exception:
        pass
    return {"status": "posted", "preview": text[:300]}


def _open_recent_activity(page: Page) -> None:
    page.goto(
        "https://www.linkedin.com/in/me/recent-activity/all/", wait_until="load"
    )
    page.wait_for_timeout(4000)


def _find_post_card(page: Page, text_match: str):
    articles = page.locator(
        "article.feed-shared-update-v2, div[data-urn*='activity'], .occludable-update"
    )
    for i in range(articles.count()):
        try:
            text = articles.nth(i).inner_text() or ""
        except Exception:
            text = ""
        if text_match.lower() in text.lower():
            return articles.nth(i)
    return None


def _open_post_menu(page: Page, card) -> None:
    menu = card.locator('button[aria-label*="control menu for post"]').first
    if menu.count() == 0:
        raise BrowserError("Could not find the control menu for the post.")
    menu.scroll_into_view_if_needed()
    menu.click()
    page.wait_for_timeout(3000)


def _click_menu_item(page: Page, css: str) -> None:
    item = page.locator(css).first
    try:
        item.wait_for(state="attached", timeout=10000)
        item.click()
    except Exception:
        raise BrowserError("Could not find the requested control-menu item.")
    page.wait_for_timeout(2500)


def delete_post(session: BrowserSession, text_match: str, confirm: bool = False) -> dict:
    """Delete a LinkedIn post whose text contains `text_match`.

    With `confirm=False` (default) it only locates the post and returns a
    preview; pass `confirm=True` to actually delete it.
    """
    page = session.page
    ensure_logged_in(page)
    _open_recent_activity(page)
    card = _find_post_card(page, text_match)
    if card is None:
        raise BrowserError(f"No post found containing {text_match!r}.")
    preview = (card.inner_text() or "").strip()[:300]
    if not confirm:
        return {
            "status": "ready_to_delete",
            "post_preview": preview,
            "message": "Post matched but not deleted. Re-run with confirm=true to delete it.",
        }
    _open_post_menu(page, card)
    _click_menu_item(
        page,
        "li.option-delete div[role='button'], "
        "li.feed-shared-control-menu__item.option-delete",
    )
    dialog = page.locator(".feed-components-shared-decision-modal").last
    try:
        dialog.wait_for(state="visible", timeout=10000)
    except Exception:
        raise BrowserError("Could not find the delete confirmation dialog.")
    delete_btn = dialog.get_by_role("button", name="Delete", exact=True)
    if delete_btn.count() == 0:
        raise BrowserError("Could not find the 'Delete' confirmation button.")
    delete_btn.click()
    try:
        page.wait_for_selector(
            ".feed-components-shared-decision-modal", state="detached", timeout=15000
        )
    except Exception:
        pass
    return {"status": "deleted", "post_preview": preview}


def edit_post(session: BrowserSession, text_match: str, new_text: str) -> dict:
    """Replace the text of a LinkedIn post whose text contains `text_match`."""
    page = session.page
    ensure_logged_in(page)
    _open_recent_activity(page)
    card = _find_post_card(page, text_match)
    if card is None:
        raise BrowserError(f"No post found containing {text_match!r}.")
    old_preview = (card.inner_text() or "").strip()[:300]
    _open_post_menu(page, card)
    _click_menu_item(
        page,
        "li.option-edit-share div[role='button'], "
        "li.feed-shared-control-menu__item.option-edit-share",
    )
    editor = page.locator(
        ".share-box-v2__modal .ql-editor[contenteditable='true'], "
        ".share-box-v2__modal [contenteditable='true']"
    ).first
    try:
        editor.wait_for(state="visible", timeout=10000)
    except Exception:
        raise BrowserError("Could not find the post editor.")
    editor.click()
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    page.wait_for_timeout(300)
    page.keyboard.insert_text(new_text)
    page.wait_for_timeout(400)
    save_btn = page.get_by_role("button", name="Save", exact=True)
    if save_btn.count() == 0 or not save_btn.is_enabled():
        raise BrowserError("Save button not found or disabled.")
    save_btn.click()
    try:
        page.wait_for_selector(".share-box-v2__modal", state="detached", timeout=15000)
    except Exception:
        pass
    return {
        "status": "edited",
        "old_preview": old_preview,
        "new_preview": new_text[:300],
    }


def _gather_text(page: Page, selectors: str) -> list[str]:
    out = []
    for item in page.locator(selectors).all():
        text = (item.inner_text() or "").strip()
        if text:
            out.append(text)
    return out


def _section_paragraphs(loc) -> list[str]:
    return [
        (p.inner_text() or "").strip()
        for p in loc.locator("p").all()
        if (p.inner_text() or "").strip()
    ]


_PRONOUNS = {"He/Him", "She/Her", "They/Them"}


def get_my_profile(session: BrowserSession) -> dict:
    page = session.page
    ensure_logged_in(page)
    page.goto("https://www.linkedin.com/in/me/", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    topcard = page.locator('[id$="QsTopcard"]').first
    name = ""
    headline = ""
    if topcard.count():
        name = first_text(topcard, "h2")
        for text in _section_paragraphs(topcard):
            if text in _PRONOUNS:
                continue
            headline = text
            break
    about = ""
    about_sec = page.locator('[id$="QsAbout"]').first
    if about_sec.count():
        about = "\n".join(_section_paragraphs(about_sec))
    experience = _gather_text(
        page,
        "[id$='QsExperience'] li, [id='experience'] li, "
        "section#experience li, li[data-section-name='experience']",
    )
    education = _gather_text(
        page,
        "[id$='QsEducation'] li, [id='education'] li, "
        "section#education li, li[data-section-name='education']",
    )
    skills = _gather_text(
        page,
        "[id$='QsSkills'] li, [id='skills'] li, section#skills .pvs-entity, "
        "#skills + * .pvs-entity",
    )
    return {
        "name": name,
        "headline": headline,
        "about": about,
        "experience": experience[:20],
        "education": education[:20],
        "skills": skills[:50],
    }


def _click_pencil(page: Page, section_selectors: list[str]) -> bool:
    for section_sel in section_selectors:
        section = page.locator(section_sel).first
        if section.count() == 0:
            continue
        pencils = section.locator('button[aria-label*="Edit"], a[aria-label*="Edit"]')
        for i in range(pencils.count()):
            candidate = pencils.nth(i)
            if candidate.is_visible():
                candidate.click()
                return True
    return False


def _fill_field_by_label(page: Page, label_text: str, value: str, container=None) -> bool:
    scope = container if container is not None else page
    try:
        label = scope.locator(f'label:has-text("{label_text}")').first
        if label.count() == 0:
            return False
        target_id = label.get_attribute("for")
        if target_id:
            field = scope.locator(f'[id="{target_id}"]').first
        else:
            field = label.locator("input, textarea").first
        if field.count() == 0:
            return False
        field.click()
        field.fill(value)
        return True
    except Exception:
        return False


def _fill_editor(page: Page, value: str, container=None) -> bool:
    scope = container if container is not None else page
    editor = scope.locator(
        '.ql-editor[contenteditable="true"], [contenteditable="true"].ql-editor, textarea'
    ).first
    if editor.count() == 0:
        return False
    editor.click()
    page.keyboard.insert_text(value)
    return True


def _click_save(page: Page) -> str | None:
    for sel in [
        'button[type="submit"].artdeco-button--primary',
        ".artdeco-modal__buttons button.artdeco-button--primary",
        'button.artdeco-button--primary:has-text("Save")',
    ]:
        btn = page.locator(sel).first
        if btn.count() > 0 and btn.is_visible():
            btn.click()
            return "saved"
    return None


def update_headline(session: BrowserSession, headline: str) -> dict:
    page = session.page
    ensure_logged_in(page)
    page.goto("https://www.linkedin.com/in/me/", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    if not _click_pencil(
        page, ["section.top-card-layout", ".top-card-layout", "div[class*='top-card']"]
    ):
        raise BrowserError("Could not find the edit control for the intro card.")
    page.wait_for_timeout(1200)
    if not _fill_field_by_label(page, "Headline", headline):
        raise BrowserError("Could not locate the Headline input in the editor.")
    status = _click_save(page)
    page.wait_for_timeout(1000)
    return {"status": status or "unknown", "headline": headline}


def update_about(session: BrowserSession, about: str) -> dict:
    page = session.page
    ensure_logged_in(page)
    page.goto("https://www.linkedin.com/in/me/", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    if not _click_pencil(page, ["section#about", "#about"]):
        raise BrowserError("Could not find the edit control for the About section.")
    page.wait_for_timeout(1200)
    if not _fill_editor(page, about):
        raise BrowserError("Could not locate the About editor.")
    status = _click_save(page)
    page.wait_for_timeout(1000)
    return {"status": status or "unknown", "about_preview": about[:300]}


def _add_entry(session: BrowserSession, entry_type: str, values: dict) -> dict:
    page = session.page
    ensure_logged_in(page)
    page.goto("https://www.linkedin.com/in/me/", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    triggers = [
        f'button[aria-label*="Add {entry_type}"], a[aria-label*="Add {entry_type}"]',
        f'button[aria-label*="Add new {entry_type}"]',
    ]
    add_btn = page.locator(", ".join(triggers)).first
    clicked = False
    if add_btn.count() > 0:
        add_btn.first.click()
        clicked = True
    else:
        for sel in [
            f'a[href*="forms/position/new"]',
            f'a[href*="forms/education/new"]',
            f"button.artdeco-button:has-text('Add')",
        ]:
            el = page.locator(sel).first
            if el.count() > 0:
                el.click()
                clicked = True
                break
    if not clicked:
        raise BrowserError(f"Could not find the 'Add {entry_type}' control.")
    modal = page.locator(".artdeco-modal, div[role='dialog']").last
    modal_head = modal if modal.count() > 0 else page
    page.wait_for_timeout(1200)
    labels = {
        "experience": [
            ("Title", "title"),
            ("Company name", "company"),
            ("Employment type", "employment_type"),
            ("Location", "location"),
            ("Description", "description"),
        ],
        "education": [
            ("School", "school"),
            ("Degree", "degree"),
            ("Field of study", "field_of_study"),
            ("Description", "description"),
        ],
    }
    filled: list[str] = []
    missing: list[str] = []
    for label_text, key in labels[entry_type]:
        if key not in values or not values[key]:
            continue
        ok = False
        if label_text == "Description":
            ok = _fill_editor(page, values[key], container=modal_head)
        else:
            ok = _fill_field_by_label(page, label_text, values[key], container=modal_head)
        (filled if ok else missing).append(label_text)
    for date_label, key in [
        (("Start date", "Start"), "start"),
        (("End date", "End"), "end"),
    ]:
        if key in values and values[key]:
            set_ok = False
            for lab in date_label:
                if _fill_field_by_label(page, lab, values[key], container=modal_head):
                    set_ok = True
                    break
            (filled if set_ok else missing).append(date_label[0])
    status = _click_save(page)
    page.wait_for_timeout(1500)
    return {
        "status": status or "unknown",
        "entry_type": entry_type,
        "filled_fields": filled,
        "unset_fields": missing,
    }


def update_experience(
    session: BrowserSession,
    title: str,
    company: str,
    start: str = "",
    end: str = "",
    description: str = "",
    employment_type: str = "",
    location: str = "",
) -> dict:
    return _add_entry(
        session,
        "experience",
        {
            "title": title,
            "company": company,
            "start": start,
            "end": end,
            "description": description,
            "employment_type": employment_type,
            "location": location,
        },
    )


def update_education(
    session: BrowserSession,
    school: str,
    degree: str = "",
    field_of_study: str = "",
    start: str = "",
    end: str = "",
    description: str = "",
) -> dict:
    return _add_entry(
        session,
        "education",
        {
            "school": school,
            "degree": degree,
            "field_of_study": field_of_study,
            "start": start,
            "end": end,
            "description": description,
        },
    )


def search_jobs(
    session: BrowserSession,
    keywords: str,
    location: str = "",
    date_posted: str = "",
    job_type: str = "",
    work_setting: str = "",
    limit: int = 10,
) -> dict:
    page = session.page
    ensure_logged_in(page)
    params: dict[str, str] = {"keywords": keywords, "location": location}
    if date_posted in DATE_POSTED_CODES:
        params["f_TPR"] = DATE_POSTED_CODES[date_posted]
    if job_type in JOB_TYPE_CODES:
        params["f_JT"] = JOB_TYPE_CODES[job_type]
    if work_setting in WORK_TYPE_CODES:
        params["f_WT"] = WORK_TYPE_CODES[work_setting]
    url = "https://www.linkedin.com/jobs/search/?" + urllib.parse.urlencode(params)
    page.goto(url, wait_until="domcontentloaded")
    try:
        page.wait_for_selector(
            ".jobs-search-results__list-item, ul.jobs-search__results-list li", timeout=15000
        )
    except Exception:
        raise BrowserError("No job results found on the search page.")
    results: list[dict] = []
    items = page.locator(".jobs-search-results__list-item, ul.jobs-search__results-list li")
    for i in range(min(items.count(), limit)):
        item = items.nth(i)
        title_sel = item.locator(
            ".job-card-list__title, .job-card-container__link, .job-card-list__title--link"
        ).first
        title = (title_sel.inner_text() or "").strip() if title_sel.count() else ""
        href = ""
        if title_sel.count():
            href = title_sel.get_attribute("href") or ""
        company = first_text(
            item,
            ".job-card-container__primary-description",
            ".job-card-list__company-name",
        )
        location_text = first_text(item, ".job-card-container__metadata-item", ".job-card-container__metadata-wrapper")
        item_id = item.get_attribute("data-occludable-job-id") or ""
        job_id = item_id
        if not job_id:
            job_id = (href.split("/jobs/view/")[-1].split("?")[0] if "/jobs/view/" in href else "")
        results.append(
            {
                "title": title,
                "company": company,
                "location": location_text,
                "url": href,
                "job_id": job_id,
            }
        )
    return {"count": len(results), "jobs": results}


def get_job_details(session: BrowserSession, url: str) -> dict:
    page = session.page
    ensure_logged_in(page)
    page.goto(url, wait_until="domcontentloaded")
    try:
        page.wait_for_selector("#job-details, .job-details-jobs-unified-top-card", timeout=20000)
    except Exception:
        pass
    title = first_text(
        page,
        ".job-details-jobs-unified-top-card__job-title",
        ".job-details-jobs-unified-top-card__title",
        "h1",
    )
    company = first_text(
        page,
        ".job-details-jobs-unified-top-card__company-name",
        ".job-details-jobs-unified-top-card__primary-description-container",
    )
    location = first_text(
        page,
        ".job-details-jobs-unified-top-card__bullet",
        ".job-details-jobs-unified-top-card__location",
    )
    description = first_text(page, "#job-details .jobs-description-content__text", "#job-details")
    criteria: list[str] = []
    for el in page.locator(".job-criteria__item, .job-insight").all():
        text = (el.inner_text() or "").strip()
        if text:
            criteria.append(text)
    return {
        "url": url,
        "title": title,
        "company": company,
        "location": location,
        "description": description[:2000],
        "criteria": criteria[:20],
    }


def _collect_apply_questions(page: Page) -> list[dict]:
    dialog = page.locator(".job-details-apply-modal, div[role='dialog']").last
    scope = dialog if dialog.count() > 0 else page
    questions: list[dict] = []
    handled: set[str] = set()
    for field in scope.locator("input, textarea, select").all():
        if not field.is_visible():
            continue
        try:
            field_id = field.get_attribute("id") or ""
        except Exception:
            field_id = ""
        if field_id in handled:
            continue
        handled.add(field_id)
        label_text = ""
        if field_id:
            try:
                label_text = scope.locator(f'label[for="{field_id}"]').inner_text(timeout=1000).strip()
            except Exception:
                label_text = ""
        if not label_text:
            label_text = field.get_attribute("aria-label") or ""
        if not label_text:
            label_text = field.get_attribute("placeholder") or ""
        questions.append({"field": field_id or label_text, "question": label_text})
    return questions


def _load_answers() -> dict:
    try:
        return json.loads(ANSWERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _apply_step(page: Page, confirm: bool, answers: dict) -> tuple[bool, list[dict]]:
    dialog = page.locator(".job-details-apply-modal, div[role='dialog']").last
    scope = dialog if dialog.count() > 0 else page
    questions = _collect_apply_questions(page)
    unanswered = []
    filled = 0
    for q in questions:
        value = ""
        for q_key in q["question"].lower().split():
            for answer_key, answer_value in answers.items():
                if answer_key.lower() in q["question"].lower() or answer_key.lower() in q_key:
                    value = str(answer_value)
                    break
            if value:
                break
        if not value and q["field"]:
            value = answers.get(q["field"], "")
        if value:
            try:
                field = scope.locator(f'[id="{q["field"]}"]').first
                field.fill(value)
                filled += 1
            except Exception:
                unanswered.append(q)
        else:
            unanswered.append(q)
    next_btn = None
    for btn in scope.locator("footer button.artdeco-button--primary, button.artdeco-button--primary").all():
        text = (btn.inner_text() or "").strip().lower()
        if "next" in text or "review" in text:
            next_btn = btn
            break
    submit_btn = None
    for btn in scope.locator("footer button.artdeco-button--primary, button.artdeco-button--primary").all():
        text = (btn.inner_text() or "").strip().lower()
        if "submit application" in text or "submit" in text:
            submit_btn = btn
            break
    if submit_btn is not None:
        if unanswered:
            return False, unanswered
        if confirm:
            submit_btn.click()
            return True, []
        return False, [{"field": "__final__", "question": "Ready to submit application (pass confirm=true)"}]
    if next_btn is not None:
        if unanswered:
            return False, unanswered
        next_btn.click()
        return True, []
    return False, unanswered


def easy_apply(session: BrowserSession, url: str, dry_run: bool = True, confirm: bool = False) -> dict:
    page = session.page
    ensure_logged_in(page)
    page.goto(url, wait_until="domcontentloaded")
    try:
        apply_btn = page.locator(
            'button[aria-label*="Easy Apply"], button:has-text("Easy Apply")'
        ).first
        apply_btn.wait_for(state="visible", timeout=20000)
    except Exception:
        return {
            "status": "unavailable",
            "message": "No Easy Apply button found (job likely redirects to an external site).",
        }
    apply_btn.click()
    page.wait_for_timeout(1500)
    answers = {} if dry_run else _load_answers()
    steps = 0
    visited_url = page.url
    while steps < 15:
        ok, unanswered = _apply_step(page, confirm, answers)
        if not ok:
            if unanswered and unanswered[0].get("field") == "__final__":
                return {
                    "status": "ready_to_submit",
                    "message": "All fields can be answered. Re-run with confirm=true to submit.",
                }
            return {
                "status": "needs_user_input",
                "questions": unanswered,
                "hint": "Fill ~/.linkedin-mcp/answers.json with values for these questions, then retry.",
            }
        steps += 1
        page.wait_for_timeout(1200)
        if page.url != visited_url:
            break
    try:
        page.wait_for_selector(
            ".artdeco-toast-item, [data-test-id='apply-form-success'], [class*='post-apply']",
            timeout=10000,
        )
    except Exception:
        pass
    return {
        "status": "submitted" if confirm else "inspected",
        "steps_processed": steps,
        "message": "Application submitted." if confirm else "Form flow inspected without submitting.",
    }