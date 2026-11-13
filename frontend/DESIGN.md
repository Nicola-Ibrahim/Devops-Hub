# Frontend design direction

This is the visual and interaction target for the developer dashboard, not evidence that a capability is implemented. Treat it as a starting point: tune the visual choices while designing a representative workspace shell and resource view, then carry the settled patterns through the dashboard. Keep component boundaries, security invariants, and frontend responsibilities in [AGENTS.md](AGENTS.md).

## Character and page hierarchy

- Use a restrained, professional palette: slate for structure and text, quiet cool neutrals for surfaces and dividers, and teal for primary actions, links, and selected states. Reserve strong colors for meaningful status or errors. Avoid decorative gradients, oversized display type, and excess shadow.
- Make the signed-in workspace feel like a practical tool: persistent project context and navigation, a compact top bar, a clear page title, then the most useful resource or activity content. Keep navigation labels and page headings direct.
- Keep the public landing page useful and compact. Explain what the platform currently supports, show a small, clearly labeled workspace example, and offer a direct sign-in or exploration path. Avoid marketing slogans, inflated promises, and long promotional sections.
- Prefer readable resource tables when scanning and comparison matter. Include the useful identifiers and context, status, and expiry; use stable column alignment and restrained row separators. On narrow screens, switch to a deliberate stacked summary or contained horizontal scroll with clear labels—never silently drop important fields.
- Use cards for focused forms, detail views, or small collections where each item needs its own actions. Keep primary actions visually distinct and destructive actions understated until confirmation is needed.

## Language and displayed data

- Describe only behavior verified in the current environment. Distinguish a request being accepted or queued from a resource being provisioned and ready. State target limits and unavailable capabilities plainly.
- Label guest, sample, mock, or illustrative content at the point of display. Do not let a sample status or action imply a live resource or working integration.
- Use concise, specific status text. Keep lifecycle states distinct, and pair color or icons with readable text. Explain the next useful action for pending, failed, expired, or unavailable states.
- Examples must be synthetic and secret-safe: use placeholders such as `postgresql://USER:REDACTED@HOST:5432/DB`, never a realistic password, token, or live endpoint. Do not show secrets in lists, activity examples, screenshots, or persistent UI; reveal connection details only within the authorized, explicit retrieval interaction.

## CSS tokens

Define shared visual choices as CSS custom properties in `src/app/globals.css`, grouped by purpose so a later visual pass can tune them centrally:

- **Color:** page canvas, surface, raised surface, primary and muted text, border, accent, accent hover, focus ring, and semantic success/warning/error/info foreground and background pairs.
- **Shape and depth:** small/medium/large radii, subtle border treatment, and one restrained elevation level.
- **Space and type:** a consistent spacing scale; body, label, caption, and heading sizes; readable line heights; and a monospace role for IDs or technical values.
- **Interaction:** minimum control height, focus-ring width/offset, and short transition duration.

Names should describe the role rather than a specific hue. Keep text and status colors legible on every intended surface; validate contrast when choosing final values. Avoid one-off literals for repeated UI roles. These categories are guidance, not fixed token values: tune them with the representative shell and resource view before treating the palette or scale as settled.

## Interaction, motion, and accessibility

- Give controls clear default, hover, focus-visible, active, disabled, and busy appearances. Preserve visible keyboard focus and make links, buttons, selects, and form fields easy to target.
- Make loading, empty, error, denied, pending, ready, expired, and retry states understandable without animation or color alone. Announce asynchronous results through suitable status or alert semantics; retain recoverable form input.
- Use semantic landmarks, ordered headings, associated labels, descriptive link text, and accessible names for icon-only controls. Keep dialogs keyboard operable and return focus to their opener.
- Keep layouts usable at narrow widths and zoom: allow content to reflow, prevent page-level horizontal overflow, and keep tables or technical strings reachable. Do not rely on hover to expose essential actions.
- Motion should be short and purposeful, such as a restrained transition on a state change or a small loading indicator. Avoid parallax, looping decoration, and motion that delays feedback. Honor `prefers-reduced-motion` by removing nonessential transitions and animation; never make status understandable only through movement.

