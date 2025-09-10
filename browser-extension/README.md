
# WFH Monitoring Browser Extension

This browser extension provides detailed website tracking and browser activity monitoring for the WFH monitoring system.

## Features

- **Real-time tab tracking**: URL, title, and tab switching events
- **Page interaction monitoring**: Clicks, keystrokes, scrolling
- **Navigation events**: Page loads, redirects, tab close/open
- **Activity analysis**: Time spent on each website
- **Local storage fallback**: Works even when agent is offline
- **Privacy-focused**: No actual keystroke content captured

## Installation

### Chrome/Edge Installation

1. **Download the extension folder** to your computer
2. **Open Chrome/Edge** and go to `chrome://extensions/` (or `edge://extensions/`)
3. **Enable Developer Mode** (toggle in top-right)
4. **Click "Load unpacked"** and select the `browser-extension` folder
5. **Pin the extension** to toolbar for easy access

### Firefox Installation

1. **Open Firefox** and go to `about:debugging`
2. **Click "This Firefox"**
3. **Click "Load Temporary Add-on"**
4. **Select the `manifest.json`** file from the extension folder

## Configuration

The extension automatically connects to the Python agent on `http://localhost:8001`.

### Agent Setup

Make sure your Python agent is running with the updated code that includes the extension server.

### Verification

1. **Click the extension icon** in your browser toolbar
2. **Check connection status** - should show "Connected to agent"
3. **Browse some websites** to generate test data
4. **Check the popup** to see event counts and activity

## Data Collected

### Tab Events
- Tab activation (switching between tabs)
- Tab updates (navigation, page loads)
- Tab creation and closure
- Window focus changes

### Page Interactions
- Click events (element type and position)
- Keyboard activity (key types, not content)
- Scroll events
- Page visibility changes

### Website Analytics
- Time spent on each website
- Page load times
- Activity patterns

## Privacy & Security

- **No personal data**: Keystrokes are categorized, not recorded
- **Local processing**: Data processed locally before sending
- **Secure transmission**: HTTPS communication with agent
- **User control**: Easy to disable or uninstall

## Troubleshooting

### Extension Not Connecting

1. **Check agent is running**: Verify Python agent shows "Browser extension server ready"
2. **Check port availability**: Ensure port 8001 is not blocked
3. **Test connection**: Click "Test Connection" in extension popup
4. **Check console**: Open browser DevTools to see error messages

### No Data Appearing

1. **Verify extension permissions**: Check that all permissions are granted
2. **Check popup statistics**: Should show increasing event counts
3. **Test with simple browsing**: Navigate between a few websites
4. **Check stored events**: Extension popup shows locally stored events

### Firefox Issues

- Firefox may require additional permissions for local server communication
- Use `about:config` to set `security.mixed_content.block_active_content` to `false` if needed

## Development

### Building for Production

1. **Update manifest.json**: Remove developer-specific permissions
2. **Add icons**: Place icon files in `icons/` folder
3. **Test thoroughly**: Verify on all target browsers
4. **Package**: Create ZIP file for distribution

### Chrome Web Store Publishing

1. **Create developer account**: Register with Google
2. **Package extension**: Create ZIP file of extension folder
3. **Upload and submit**: Follow Chrome Web Store guidelines
4. **Handle review process**: Address any feedback from Google

## Support

- Check browser console for error messages
- Verify Python agent logs for connection issues
- Test with minimal browsing activity first
- Contact system administrator for agent configuration issues
