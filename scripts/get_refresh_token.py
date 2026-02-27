"""
Generate a Google Ads API Refresh Token.

Usage:
    python scripts/get_refresh_token.py

You will need your Client ID and Client Secret from Google Cloud Console.
A browser window will open for you to authorize the app.
The refresh token will be printed to the console.
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/adwords"]


def main():
    client_id = input("Client ID: ").strip()
    client_secret = input("Client Secret: ").strip()

    if not client_id or not client_secret:
        print("Error: Both Client ID and Client Secret are required.")
        return

    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
    )

    credentials = flow.run_local_server(port=8080)

    print("\n" + "=" * 60)
    print("SUCCESS! Copy this Refresh Token:")
    print("=" * 60)
    print(f"\n{credentials.refresh_token}\n")
    print("=" * 60)
    print("Paste it in Settings > Google Ads > Refresh Token")


if __name__ == "__main__":
    main()
