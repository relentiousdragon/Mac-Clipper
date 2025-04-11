# Mac-Clipper
Clipboard Manager for Mac OS, Copy and Paste whenever you need them, customizable hotkeys, pins, image pastes and more!

## Features
- **Clipboard History**: Automatically saves text and image clipboard entries.
- **Global Hotkey**: Quickly toggle the app using a customizable hotkey (default: `⌘ + ⌥ + V`).
- **Search**: Search through your clipboard history.
- **Pin Items**: Pin important clipboard entries to keep them from being removed.
- **Dark/Light Mode**: Automatically adapts to your system theme or can be manually set.
- **Launch at Login**: Option to start the app automatically when you log in (Enabled by Default).

## How to Use
1. **Launch the App**: Run the app and grant accessibility permissions when prompted.
2. **Toggle Visibility**: Use the default hotkey `⌘ + ⌥ + V` to show or hide the app.
3. **Search**: Use the search bar to filter clipboard entries.
4. **Paste**: Click on an item or use the arrow keys to navigate and press `Enter` to paste it into the active application.
5. **Right-Click Menu**: Right-click on an item to copy, paste, pin, or delete it.
6. **Preferences**: Access preferences by clicking the gear icon to customize settings like the hotkey, theme, and more.

## Requirements
- macOS
- Python 3.9 or later

### Required Python Packages
The following Python packages are required to run the app:
- `PyQt6`
- `pyobjc-framework-Quartz`

Install the required packages using:
```bash
pip install -r requirements.txt
```

## How to Build
To build the app using PyInstaller, follow these steps:

1. **Install PyInstaller**:
   ```bash
   pip install pyinstaller
   ```

2. **Run PyInstaller**:
   Use the provided `Mac Clipper.spec` file to build the app:
   ```bash
   python3 -m PyInstaller "Mac Clipper.spec" --noconfirm
   ```

3. **Locate the Built App**:
   After the build process completes, the app will be located in the `dist/Mac Clipper.app` directory.

## Accessibility Permissions
Mac Clipper requires accessibility permissions to listen for global hotkeys. If permissions are not granted, the app will not function correctly. You can enable these permissions in:
`System Settings > Privacy & Security > Accessibility`.

## License
This project is licensed under the GNU 3.0 License. See the `LICENSE` file for details.


<a href="https://www.flaticon.com/free-icons/paste" title="paste icons">Paste icons created by Pixel perfect - Flaticon</a>
