import argparse
import getpass
import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def prompt_for_password() -> None:
    """
    Prompt user for Google password and set it in environment.
    Handles cancellation gracefully without overwriting existing password.
    """
    try:
        password = getpass.getpass("Enter your Google password: ")
        if password:
            os.environ["GOOGLE_PASS"] = password  # Set in environment for the session
            print("Password set for this session.")
        else:
            print("Empty password entered. Using existing password if available.")
    except (EOFError, KeyboardInterrupt):
        print("Password prompt cancelled. Using existing password if available.")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Google Takeout Automation")
    parser.add_argument(
        "url",
        help="Google Takeout archive URL",
    )
    parser.add_argument(
        "--executable-path",
        help="Path to browser executable (overrides EXECUTABLE_PATH env var)",
    )
    parser.add_argument(
        "--download-path",
        help="Path to download directory (overrides DOWNLOAD_PATH env var)",
    )
    parser.add_argument(
        "--user-data-dir",
        help="Path to user data directory (overrides USER_DATA_DIR env var)",
    )
    parser.add_argument(
        "--start-part",
        type=int,
        default=1,
        help="Part number to start downloading from (default: 1)",
    )
    parser.add_argument(
        "--skip-downloaded",
        action="store_true",
        help="Skip parts that have already been downloaded (default: False)",
    )
    parser.add_argument(
        "--prompt-password",
        action="store_true",
        help="Prompt for Google password upfront instead of when needed (default: False)",
    )

    args = parser.parse_args()

    # Set environment variables from CLI arguments
    if args.executable_path:
        os.environ["EXECUTABLE_PATH"] = args.executable_path
    if args.download_path:
        os.environ["DOWNLOAD_PATH"] = args.download_path
    if args.user_data_dir:
        os.environ["USER_DATA_DIR"] = args.user_data_dir

    # Handle password prompting if requested
    if args.prompt_password:
        prompt_for_password()

    # Run the extraction and download process
    from .exporter import download_takeout_archive

    download_takeout_archive(args.url, args.start_part, args.skip_downloaded)


if __name__ == "__main__":
    main()
