import getpass
import time
from pathlib import Path
from typing import TypedDict
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from playwright.sync_api import (
    BrowserContext,
    Download,
    Page,
    Playwright,
    sync_playwright,
)

from .config import settings

GOOGLE_ARCHIVE_URL_PART = "takeout.google.com/manage/archive"
GOOGLE_PASSWORD_PAGE_URL_PART = "accounts.google.com/v3/signin/challenge/pwd"


class PartInfo(TypedDict):
    """Type definition for part information dictionary."""

    part_number: int
    link: str
    downloaded: bool
    size: int | None


def detect_google_password_prompt(page: Page) -> bool:
    """
    Detect if Google is prompting for password re-verification.
    Checks URL directly since password pages load normally and are detectable by URL.
    """
    return GOOGLE_PASSWORD_PAGE_URL_PART in page.url


def prompt_for_password() -> None:
    """
    Prompt user for Google password and overwrite settings.google_pass.
    Handles cancellation gracefully without overwriting existing password.
    """
    try:
        password = getpass.getpass("Enter your Google password: ")
        if password:
            settings.google_pass = password  # Always overwrite when password provided
            print("Password set for this session.")
        else:
            print("Empty password entered. Using existing password if available.")
    except (EOFError, KeyboardInterrupt):
        print("Password prompt cancelled. Using existing password if available.")
        # Don't overwrite - keep existing password


def handle_password_prompt(page: Page, context_message: str = "") -> None:
    """
    Handle Google password prompt automatically using the stored password.
    """
    if len(context_message):
        context_message = " " + context_message

    if not settings.google_pass:
        print(
            f"Google password prompt detected{context_message}. Please enter your password in the browser."
        )
        input("Press Enter after entering password...")
        return

    print(
        f"Google password prompt detected{context_message}. Attempting automatic password entry..."
    )
    try:
        # Wait for password input field to be visible
        password_input = page.locator('input[type="password"]').first
        password_input.wait_for(state="visible", timeout=10000)

        # Clear any existing text and enter password with small delays
        password_input.click()
        page.keyboard.press("Control+a")  # Select all
        page.keyboard.press("Delete")  # Clear
        time.sleep(0.5)  # Small delay

        # Type password character by character with small delays
        for char in settings.google_pass:
            password_input.type(char)
            time.sleep(0.1)  # Small delay between characters

        time.sleep(0.5)  # Delay before submitting

        # Submit the form
        password_input.press("Enter")
        print(f"Password entered automatically{context_message}.")

        # Wait for page to fully load after authentication
        page.wait_for_load_state("networkidle", timeout=10000)
        time.sleep(2)  # Extra buffer for dynamic content

        # Check if we're still on password page (authentication failed)
        if detect_google_password_prompt(page):
            print(f"Automatic password entry failed{context_message}.")
            input("Press Enter after entering password manually...")
        elif detect_google_takeout_archive(page):
            print(f"Authentication successful{context_message}!")
        else:
            print(f"Page navigation unclear{context_message}. Please check browser.")
            input("Press Enter when ready to continue...")

    except Exception as e:
        print(f"Automatic password entry failed{context_message}: {e}")
        input("Press Enter after entering password manually...")


def detect_google_takeout_archive(page: Page) -> bool:
    """
    Detect if Google archive page is being shown.
    Checks URL first, and only waits for load state if navigating to ensure stability.
    """
    # First check if we're already on the archive page (no need to wait)
    if GOOGLE_ARCHIVE_URL_PART in page.url:
        return True

    # If not on archive page, wait for basic load completion before checking
    page.wait_for_load_state("load")
    return GOOGLE_ARCHIVE_URL_PART in page.url


def handle_download(
    download: Download, download_path: Path, expected_size: int | None = None
) -> None:
    """
    Handle the download process: wait for completion, save to path, verify size, and clean up.
    """
    print(f"Download object created. Filename: {download.suggested_filename}")

    # Wait for download to actually complete by accessing the path
    download_path_on_disk = download.path()
    print(f"Download completed (temporary save to: {download_path_on_disk})")

    # Save to our download directory with suggested filename
    print("Saving file to target location...")
    saved_path = download_path / download.suggested_filename
    download.save_as(str(saved_path))
    print(f"File saved to: {saved_path}")

    # Verify file size if expected size is provided
    if expected_size is not None:
        actual_size = saved_path.stat().st_size
        if actual_size != expected_size:
            print("WARNING: File size mismatch!")
            print(f"Expected: {expected_size} bytes")
            print(f"Actual: {actual_size} bytes")
            print("The download may be incomplete or corrupted.")
        else:
            print(f"✓ File size verified: {expected_size} bytes")

    # Remove the temporary file after successful save
    try:
        download_path_on_disk.unlink()
        print(f"Temporary file removed: {download_path_on_disk}")
    except Exception as e:
        print(f"Warning: Could not remove temporary file {download_path_on_disk}: {e}")


def prepare_archive_url(archive_url: str) -> str:
    """
    Ensure hl=en is set in the URL for consistent language.
    """
    parsed_url = urlparse(archive_url)
    query_params = parse_qs(parsed_url.query)
    query_params["hl"] = ["en"]
    new_query = urlencode(query_params, doseq=True)
    return urlunparse(parsed_url._replace(query=new_query))


def setup_browser_context(p: Playwright) -> tuple[BrowserContext, Page]:
    """
    Launch and configure the browser context for Google Takeout automation.
    """
    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-infobars",
    ]

    context = p.chromium.launch_persistent_context(
        user_data_dir=str(settings.user_data_dir),
        executable_path=settings.executable_path,
        headless=False,
        args=launch_args,
        accept_downloads=True,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Brave/128.0.0.0 Chrome/128.0.0.0 Safari/537.36",
    )

    page = context.new_page()
    return context, page


def ensure_archive_ready(page: Page, archive_url: str) -> None:
    """
    Ensure the page is on the Google Takeout archive page and handle authentication if needed.
    """
    if not detect_google_takeout_archive(page):
        page.goto(archive_url)
        print("Navigating to archive page.")

    if detect_google_password_prompt(page):
        handle_password_prompt(page, "during archive navigation")


def wait_for_user_confirmation(part_number: int) -> bool:
    """
    Give the user time to interrupt the download process before proceeding.
    Returns True if the user wants to continue, False if interrupted.
    """
    wait_seconds = 3
    try:
        print(
            f"Starting download #{part_number}. Waiting {wait_seconds} seconds (press Ctrl+C to stop)..."
        )
        time.sleep(wait_seconds)
        print("Continuing...")
        return True
    except KeyboardInterrupt:
        print("\nInterrupted during wait. Exiting...")
        return False


def extract_parts_info(page: Page) -> list[PartInfo]:
    """
    Extract information about all available parts from the archive page.
    Uses robust locators based on aria-labels and text content instead of dynamic CSS classes.
    Returns a list of dicts with part_number, link, downloaded status, and size.
    """
    parts: list[PartInfo] = []

    # Find all download links using aria-label (more stable than CSS classes)
    download_links = page.locator('a[aria-label^="Download"]').all()

    for link in download_links:
        # Extract part number from aria-label (e.g., "Download part 22 of 59" or "Download again part 21 of 59")
        aria_label = link.get_attribute("aria-label")
        if not aria_label:
            continue

        # Parse part number from aria-label
        try:
            # Split on "part " and take the next part, then split on space or " of"
            part_str = aria_label.split("part ")[1].split()[0]
            part_number = int(part_str)
        except (IndexError, ValueError):
            continue

        # Get the download URL
        href = link.get_attribute("href")
        if not href:
            continue

        # Check if already downloaded by looking for "Download started" text in the containing li
        # Use XPath to find the li ancestor and check its text content
        li_element = link.locator("xpath=ancestor::li[1]")
        li_text = li_element.text_content() or ""
        has_downloaded = "Download started" in li_text

        # Extract file size using XPath to find ancestor div with data-size
        size_element = link.locator("xpath=ancestor::div[@data-size]")
        size_str = (
            size_element.get_attribute("data-size")
            if size_element.count() > 0
            else None
        )
        size = int(size_str) if size_str else None

        parts.append(
            {
                "part_number": part_number,
                "link": href,
                "downloaded": has_downloaded,
                "size": size,
            }
        )

    # Sort by part number to ensure correct order
    parts.sort(key=lambda x: x["part_number"])
    return parts


def find_part_to_download(parts_info: list[PartInfo], part_number: int) -> PartInfo:
    """
    Find the part information for a specific part number.
    Raises ValueError if the part is not found.
    """
    for part in parts_info:
        if part["part_number"] == part_number:
            return part

    available_parts = [p["part_number"] for p in parts_info]
    raise ValueError(
        f"Fatal error: Part {part_number} not found in available parts. "
        f"Available parts: {available_parts}"
    )


def download_files(
    page: Page,
    download_path: Path,
    start_part: int,
    archive_url: str,
    skip_downloaded: bool = False,
) -> None:
    """
    Download files sequentially starting from the specified part.
    """
    i = start_part
    while True:
        print("\n=== Download Start ===")

        if not wait_for_user_confirmation(i):
            return

        ensure_archive_ready(page, archive_url)

        # Extract parts information
        parts_info = extract_parts_info(page)
        if not parts_info:
            print("No parts found. Verify authentication.")
            continue

        # Find the part to download
        part_to_download = find_part_to_download(parts_info, i)

        print(f"Downloading file {i} of {len(parts_info)}...")
        if part_to_download["size"]:
            print(f"File size: {part_to_download['size']} bytes")

        # Skip already downloaded parts if requested
        if part_to_download["downloaded"]:
            print(f"Note: Part {i} has already been downloaded previously.")
            if skip_downloaded:
                print(f"Skipping download of Part {i}.")
                i += 1
                continue

        print(f"Clicking download link of Part {i}...")
        try:
            # Click the specific link for this part
            link_element = page.locator(f'a[href="{part_to_download["link"]}"]')
            link_element.click()
            print("Download initiated...")

            # Wait a few seconds and check if password prompt appeared
            time.sleep(3)

            if detect_google_password_prompt(page):
                handle_password_prompt(page, "after download click")

            # Now wait for the actual download to start
            with page.expect_download(
                timeout=10000
            ) as download_info:  # 10 second timeout
                print("Waiting for download to start...")

            download = download_info.value
            expected_size = part_to_download["size"]
            handle_download(download, download_path, expected_size)
            i += 1  # Success, move to next file

        except Exception as e:
            print(f"Failed to download file {i}: {e}, retrying...")
            continue

        # Check if we've downloaded all files
        if i > max(p["part_number"] for p in parts_info):
            break

    print(f"\nAll downloads complete! Files saved to: {download_path}")


def download_takeout_archive(
    archive_url: str, start_part: int = 1, skip_downloaded: bool = False
) -> None:
    """
    Navigate to Google Takeout archive page, wait for login, then download files sequentially.
    Downloads happen directly in the browser with proper authentication.
    """
    archive_url = prepare_archive_url(archive_url)

    if GOOGLE_ARCHIVE_URL_PART not in archive_url:
        raise ValueError("Invalid archive URL. Must be a Google Takeout URL.")

    download_path = settings.download_path
    user_data_dir = settings.user_data_dir

    # Ensure directories exist
    download_path.mkdir(parents=True, exist_ok=True)
    user_data_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context, page = setup_browser_context(p)

        try:
            download_files(
                page, download_path, start_part, archive_url, skip_downloaded
            )
        except KeyboardInterrupt:
            print("\nInterrupted. Exiting...")
            return  # Exit cleanly without trying to close browser
        except Exception as e:
            print(f"Process failed: {e}")
            raise
        finally:
            # Only close if not already handled by KeyboardInterrupt
            try:
                print("Closing browser...")
                context.close()
                print("Browser closed.")
            except Exception:
                pass  # Already handled or browser already closed
