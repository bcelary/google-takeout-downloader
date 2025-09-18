# Google Takeout Downloader

A tool for downloading Google Takeout archives that uses the archive page view (`takeout.google.com/manage/archive`) to download files one by one. The initial login requires manual authentication (including 2FA when prompted), but subsequent re-authentication prompts can be handled automatically when `GOOGLE_PASS` is configured (via `.env` file or `--prompt-password` flag). The tool verifies file sizes upon completion but cannot check integrity since Google doesn't provide checksums.

## Setup

1. Ensure Python 3.10 or later is installed.
2. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
3. Create virtual environment: `uv venv`
4. Activate venv: `source .venv/bin/activate` (Windows: `.venv\Scripts\activate`)
5. Install dependencies: `uv sync`, for development: `uv sync --extra dev`
6. Install Playwright browsers: `playwright install`

## Usage

Download files from a Google Takeout archive page:

```bash
# Basic usage
takeout-download "https://takeout.google.com/manage/archive/..."

# Start from a specific part (useful for resuming downloads)
takeout-download --start-part 2 "https://takeout.google.com/manage/archive/..."

# Prompt for password upfront (secure override of .env)
takeout-download --prompt-password "https://takeout.google.com/manage/archive/..."

# With custom options
takeout-download --executable-path /path/to/browser --download-path /custom/downloads "https://takeout.google.com/manage/archive/..."
```

The tool will:
- Launch a browser and navigate to the archive URL (with `?hl=en` for English interface)
- Show browser for manual login (complete 2FA if prompted)
- Wait for user confirmation that the archive page is visible
- Download all files sequentially directly in the browser (may require password prompt on first download)
- Save files to the download directory and print their locations

### Environment Variables

Optional: Set environment variables in `.env` file to customize behavior. Copy `.env.sample` to `.env` and modify as needed:

```
EXECUTABLE_PATH=/path/to/chrome/executable  # Optional: uses default browser if not set
DOWNLOAD_PATH=./takeout-downloads  # this is the default setting if not set
USER_DATA_DIR=./takeout-profile  # this is the default setting if not set
GOOGLE_PASS=your_google_password  # Optional: enables automatic password entry for re-authentication
```

**Note:** The `.env` file is automatically loaded when running the tool. Never commit your actual `.env` file to version control.

### Direct Execution

Run directly: `python -m src.takeout_automation.main <CLI command args>`

## Development

Run all checks: `uv run mypy src/ && uv run ruff check src/ --fix && uv run black src/ && uv run pytest`

Individual commands:
- Type check: `mypy src/`
- Lint: `uv run ruff check src/ tests/`
- Format: `uv run black src/ tests/`
- Test: `pytest`

## Prerequisites

- Python >= 3.10
- uv for dependency management
