"""MCP server entrypoint — registers all LinkedIn tools and runs over stdio."""

from __future__ import annotations

import sys

from mcp.server.mcpserver import MCPServer

from linkedin_mcp.browser import BrowserError, BrowserSession
from linkedin_mcp import linkedin as li

mcp = MCPServer("linkedin")


@mcp.tool()
def login(wait_seconds: int | None = None) -> dict:
    """Open a headed LinkedIn sign-in window (first-time use or re-login).

    Args:
        wait_seconds: Max seconds to wait for manual sign-in (default: 600).
    """
    try:
        with BrowserSession(headless=False, timeout_ms=300_000) as session:
            return li.login(session, wait_seconds)
    except BrowserError as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def check_session() -> dict:
    """Return whether the persisted LinkedIn session is still valid."""
    try:
        with BrowserSession() as session:
            return li.check_session(session)
    except BrowserError as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def create_post(text: str) -> dict:
    """Publish a post to the authenticated user's LinkedIn feed.

    Args:
        text: The full text of the post to publish.
    """
    try:
        with BrowserSession() as session:
            return li.create_post(session, text)
    except BrowserError as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def get_my_profile() -> dict:
    """Return the authenticated user's full profile: name, headline, about, experience, education, skills."""
    try:
        with BrowserSession() as session:
            return li.get_my_profile(session)
    except BrowserError as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def update_headline(headline: str) -> dict:
    """Replace the profile headline with new text.

    Args:
        headline: The new headline string to set.
    """
    try:
        with BrowserSession() as session:
            return li.update_headline(session, headline)
    except BrowserError as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def update_about(about: str) -> dict:
    """Replace the profile About / Summary section.

    Args:
        about: The new About text.
    """
    try:
        with BrowserSession() as session:
            return li.update_about(session, about)
    except BrowserError as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def update_experience(
    title: str,
    company: str,
    start: str = "",
    end: str = "",
    description: str = "",
    employment_type: str = "",
    location: str = "",
) -> dict:
    """Add a new experience entry to the profile.

    Args:
        title: Job title.
        company: Company / organisation name.
        start: Start date label (e.g. "Jan 2023" or "2023-01-01").
        end: End date label (leave blank for present role).
        description: Role description.
        employment_type: One of full_time, part_time, contract, temporary, internship, other.
        location: Location string.
    """
    try:
        with BrowserSession() as session:
            return li.update_experience(
                session,
                title=title,
                company=company,
                start=start,
                end=end,
                description=description,
                employment_type=employment_type,
                location=location,
            )
    except BrowserError as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def update_education(
    school: str,
    degree: str = "",
    field_of_study: str = "",
    start: str = "",
    end: str = "",
    description: str = "",
) -> dict:
    """Add a new education entry to the profile.

    Args:
        school: School or university name.
        degree: Degree (e.g. "Bachelor of Science").
        field_of_study: Field of study (e.g. "Computer Science").
        start: Start year or date string.
        end: End year or date string.
        description: Description / notes.
    """
    try:
        with BrowserSession() as session:
            return li.update_education(
                session,
                school=school,
                degree=degree,
                field_of_study=field_of_study,
                start=start,
                end=end,
                description=description,
            )
    except BrowserError as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def search_jobs(
    keywords: str,
    location: str = "",
    date_posted: str = "",
    job_type: str = "",
    work_setting: str = "",
    limit: int = 10,
) -> dict:
    """Search LinkedIn jobs and return structured results.

    Args:
        keywords: Job search keywords (e.g. "Senior Data Engineer").
        location: Location filter (e.g. "New York").
        date_posted: One of 'day', 'week', 'month'.
        job_type: One of full_time, part_time, contract, temporary, internship, other.
        work_setting: One of remote, hybrid, onsite.
        limit: Max results to return (default 10).
    """
    try:
        with BrowserSession() as session:
            return li.search_jobs(
                session,
                keywords=keywords,
                location=location,
                date_posted=date_posted,
                job_type=job_type,
                work_setting=work_setting,
                limit=limit,
            )
    except BrowserError as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def get_job_details(url: str) -> dict:
    """Fetch full details for a specific LinkedIn job listing URL.

    Args:
        url: Full LinkedIn job URL (e.g. https://www.linkedin.com/jobs/view/1234567890).
    """
    try:
        with BrowserSession() as session:
            return li.get_job_details(session, url)
    except BrowserError as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def easy_apply(url: str, dry_run: bool = True, confirm: bool = False) -> dict:
    """Inspect or submit an Easy Apply job application.

    Args:
        url: LinkedIn job URL containing an Easy Apply button.
        dry_run: If True, inspect the form fields and return unanswered questions without submitting.
                 Must be False for the application to actually be submitted.
        confirm: Must be True alongside dry_run=False to actually submit. Extra safety gate.
    """
    try:
        with BrowserSession() as session:
            return li.easy_apply(session, url, dry_run=dry_run, confirm=confirm)
    except BrowserError as e:
        return {"status": "error", "message": str(e)}


def _install_browsers() -> None:
    sys.argv = ["patchright", "install", "chromium"]
    from patchright.__main__ import main as patchright_main

    patchright_main()


def main() -> None:
    if "--install-browsers" in sys.argv:
        _install_browsers()
        return
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()