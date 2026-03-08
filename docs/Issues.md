Here is a complete record of every issue encountered and fix applied during this session.
ChessEcon Dashboard — Issues & Fixes Log
Issue 1 — Black pieces invisible on dark squares
Root cause: Black pieces were rendered in #1a1a2e (near-black), which was indistinguishable from the dark board background (#141c21).
Fix: Changed black piece color to vivid gold #E8B400 (filled Unicode symbols ♚♛♜♝♞♟) with a dark drop-shadow. Gold is visible on both cream and brown squares.
File changed: frontend/client/src/components/ChessBoard.tsx
Issue 2 — White pieces invisible on light squares
Root cause: White pieces were initially set to #FFFFFF (white), which was invisible on cream squares (#F0D9B5). A subsequent attempt using navy #1B2A6B was too dark on brown squares. A -webkit-text-stroke approach made pieces appear grey/muddy.
Fix: White pieces (hollow Unicode symbols ♔♕♖♗♘♙) are rendered in dark navy #1a2744. The hollow outline of the Unicode symbol is clearly visible on both cream and brown squares. A subtle white drop-shadow adds depth.
File changed: frontend/client/src/components/ChessBoard.tsx
Issue 3 — Board square colors too dark (original dark theme)
Root cause: The CSS classes chess-square-light and chess-square-dark used near-black values (#141c21 and similar) from the original dark terminal theme, making the board unreadable.
Fix: Changed to classic chess board colors — cream #F0D9B5 for light squares and warm brown #B58863 for dark squares.
File changed: frontend/client/src/index.css
Issue 4 — Docker build not picking up source changes
Root cause: Files were copied to chessecon/frontend/src/components/ but the Vite Docker config (vite.docker.config.ts) uses root: "client", meaning it reads from chessecon/frontend/client/src/. The wrong directory was targeted.
Fix: Identified the correct path from vite.docker.config.ts. All file copies must go to chessecon/frontend/client/src/ (not frontend/src/).
Command to verify: docker exec chessecon-app grep -o "chess-square-light[^}]*}" /app/backend/static/assets/index-*.css
Issue 5 — Browser serving cached old CSS (304 Not Modified)
Root cause: After Docker rebuild, the browser loaded the old index-ezKtz3Zw.css from cache because the filename hash had not changed (Vite produces the same hash when output bytes are identical).
Fix: Open the app in an Incognito/Private window, or enable "Disable cache" in DevTools Network tab before reloading.
Issue 6 — Board completely blank on initial load
Root cause: An earlier attempt used position: absolute with inset: "1.75rem 0 0 0" on the board div, but the Panel component's root element did not have position: relative in the right context, so the board rendered outside the visible area.
Fix: Rewrote ChessBoard to use a pure flex layout (width: 100%; height: 100%) that fills its container naturally, removing all absolute positioning.
File changed: frontend/client/src/components/ChessBoard.tsx
Issue 7 — Black horizontal lines appearing on the board during simulation
Root cause: The board used a CSS class chess-board with display: grid but the container had overflow: hidden cutting rows unevenly. Combined with flex: 1 on the board panel, grid row heights became fractional and borders bled through as visible lines.
Fix: Moved all grid styles inline (display: grid, gridTemplateColumns, gridTemplateRows, overflow: hidden) directly on the board div, eliminating the CSS class dependency and ensuring clean row boundaries.
File changed: frontend/client/src/components/ChessBoard.tsx
Issue 8 — Board stretching vertically during first 2–3 simulations
Root cause: The board panel used flex: 1 which caused it to grow to fill all remaining vertical space in the left column. As the wallet history chart appeared below and the page layout expanded, the left column grew taller and the board stretched with it.
Fix: Replaced flex: 1 with aspectRatio: "1 / 1" and flexShrink: 0 on the board panel container. The board height is now always derived from its width — it is a strict square at all times regardless of surrounding layout changes.
File changed: frontend/client/src/pages/Home.tsx
Summary of files changed
File
Changes
frontend/client/src/components/ChessBoard.tsx
Piece colors, layout rewrite, inline grid styles
frontend/client/src/index.css
Square colors (#F0D9B5 / #B58863)
frontend/client/src/pages/Home.tsx
Board panel aspect-ratio fix, agent cards layout
Docker rebuild command (run after copying all three files)
Bash
docker compose down
docker compose build --no-cache chessecon
PORT=8006 docker compose up chessecon
