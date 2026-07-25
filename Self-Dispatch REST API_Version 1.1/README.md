# Self-Dispatch Desktop GUI (Dell / Lenovo)

Python `tkinter` app that fronts vendor self-dispatch APIs. It keeps everything in one file (`app.py`) so it is easy to turn into an `.exe` with PyInstaller (or similar). The current build uses local sample payloads for Dell and mock data for Lenovo so you can exercise the UI with no network calls.

## Features
- Vendor picker (Dell or Lenovo) with username/password login.
- Dashboard listing claims for the authenticated user; simple text filter.
- Warranty checker dialog (service tag / serial).
- Make-claim form with Dell rules (>=1 and <=8 attachments).
- Attachments uploaded as base64 in the payload to mirror Dell’s API.

## Run locally (PyQt)
```bash
cd "/Users/prmikey/Downloads/Self-Dispatch REST API_Version 1.1"
python -m pip install pyqt5 requests
python app.py
```
Requires Python 3.9+ and PyQt5. On macOS you may need `python3` instead of `python`.

## Where to plug real APIs
- `app.py`:
  - `DellTechDirectClient.login`: replace the mock token with the real OAuth2 call.
  - `DellTechDirectClient.list_claims`: call Dell inquiry endpoint; keep the filter hook.
  - `DellTechDirectClient.check_warranty`: call the real warranty/inquiry API using `service_tag`.
  - `DellTechDirectClient.create_claim`: POST `final_payload` to the Dell dispatch endpoint with the bearer token; payload already merges UI data and encoded attachments.
  - `LenovoClient` methods follow the same shape; swap stubs for Lenovo endpoints.
- The UI already validates Dell’s attachment count; adjust `AttachmentManager` if Lenovo has different rules.

## Using the bundled samples
- The app reads `Self-Dispatch REST API_Sample Payloads/Inquiry Response Payload.json` to populate the dashboard when you log in as Dell.
- `Dispatch Request Payload - Parts.json` seeds claim creation so you can see the final JSON in the success dialog without calling the network.

## Packaging to .exe
- Example with PyInstaller:
  ```bash
  python -m pip install pyinstaller
  pyinstaller --onefile --name SelfDispatch app.py
  ```
  Keep the `Self-Dispatch REST API_Sample Payloads` folder next to the binary if you want the mock data available after packaging.
