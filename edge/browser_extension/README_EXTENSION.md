# Browser Extension (Manifest V3)

## Capabilities
- Popup-triggered page image scan
- DOM image candidate filtering with limits
- Optional overlay badges
- Options page for mode and scan settings
- Backend fallback inference path

## Architecture
- `background.ts`: runtime messaging and tab command dispatch
- `content.ts`: page scan execution and overlay rendering
- `domScanner.ts`: candidate collection and anti-rescan cache
- `popup/*`: scan UX and summary
- `options/*`: persistent settings controls

## Runtime Modes
- `local`: use local extension runtime (if integrated)
- `backend`: always call backend
- `auto`: attempt local, fallback to backend

## Security Practices
- Minimal default permissions
- Optional host permissions
- No destructive DOM mutations (overlay-only)
- Local storage for settings and recent results
