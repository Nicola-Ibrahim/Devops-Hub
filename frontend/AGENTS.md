# Frontend architecture

Follow root [AGENTS.md](../AGENTS.md). The Next.js dashboard consumes backend
contracts; it never provisions resources or decides authorization.

## Structure

- `src/app/` owns routes, layouts, server/client boundaries and the backend proxy.
- `src/components/` owns feature UI and local interaction state.
- `src/app/globals.css` owns shared visual tokens and global styles.
- Keep API shapes typed at their consumption boundary. Extract a shared component
  only after more than one feature needs the same behavior.
- Never edit or treat `.next/` as source.

## Invariants

- Show project/environment context, operation status and lease expiry explicitly.
  Queued, ready, failed, deleting and expired are distinct states.
- Backend authorization is authoritative. Guest mode uses clearly labeled demo
  data and cannot expose privileged actions or real credentials.
- Connection secrets never enter ordinary lists, logs or persistent browser
  storage; retrieve them only through an explicit authorized action.
- Every flow handles loading, empty, error, denied and retry states. Preserve form
  input after recoverable errors.
- Use semantic HTML, labels, keyboard navigation, visible focus, sufficient
  contrast, textual status cues and intentional narrow-screen layouts.

Use [frontend-development](../.agents/skills/frontend-development/SKILL.md) for
the implementation and verification procedure.
