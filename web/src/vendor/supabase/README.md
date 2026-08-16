Everything under this directory is vendored, not ours: edit only to fix an import that fails to
resolve, to swap a Next.js router primitive for its react-router equivalent, or to delete an i18n
or feature-flag import and inline its fallback string. Restyling — colors, spacing, class names,
any visual change — happens in `web/src/components/`, never here.

Provenance and the full file list are in `web/NOTICE`.
