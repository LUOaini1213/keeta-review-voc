# Dashboard preview and Pages publication

The aggregate dashboard is a self-contained HTML file. Its charts contain
market-level counts, issue shares and label-quality estimates. It does not load
individual reviews, reference rows, prompts or responses. Report, method and
source links point to GitHub, so the site needs no other repository files.

The **live dashboard** is at
<https://luoaini1213.github.io/keeta-review-voc/>.
The [first verified Pages release](https://github.com/LUOaini1213/keeta-review-voc/actions/runs/38193315517)
completed both build and deployment successfully on 2026-10-12, from reviewed
main commit `d240b7914194b04ad67f98a67ac9a9809d83f18d`. The public page and all
three navigation targets returned HTTP 200. Its 34,727-byte HTML matched the
approved dashboard exactly, with SHA-256
`5838506d55d5f0e16809e7ee61d644296f49cde35d2ac0303142cb0f164d5979`.

## Local preview

From the repository root, using the installed analysis dependencies:

```bash
python scripts/build_dashboard.py --check
python scripts/prepare_pages.py
python -m http.server 0 --bind 127.0.0.1 --directory build/pages
```

Open the loopback URL printed by the server (the OS selects an available port)
and stop the server when finished. Only the staged
directory is served. Downloading and opening `docs/dashboard.html` locally also
works. Preparation refuses a stale dashboard, unexpected output files and
symlinked output paths; it never copies or recursively cleans the repository.

## Artifact boundary

The Pages upload path is always `build/pages`. Its complete allowlist is:

- `index.html`: the freshly reproduced, committed aggregate dashboard.
- `.nojekyll`: an empty static-site marker.

The repository, `data/`, excerpts, per-review metadata or labels, local logs,
virtual environments and credentials are not copied into this directory.
Do not replace the workflow upload path with `.`, `docs/` or `data/`.
GitHub's upload action excludes hidden files, including the empty `.nojekyll`
marker. The published artifact therefore contains only `index.html`; the Actions
workflow does not run Jekyll.

PR and push runs reproduce the committed snapshot and stage/upload this
artifact with read-only repository permission. They never deploy. The release
job alone receives Pages and OpenID Connect write permissions.

## Release a future update

Initial activation is complete: Pages uses **GitHub Actions** as its publishing
source, and the repository Actions variable `KEETA_PAGES_ENABLED` is `true`.
For a future release:

- Review and merge the intended changes into `main`.
- Confirm the required `ci` checks succeeded for the intended main commit.
- Run **pages-preparation** manually on **main**, selecting `publish: true`.
  The workflow repeats the offline reproduction checks and publishes only
  after the build succeeds.

A PR, branch push or manual run on another branch cannot satisfy the release
condition. A manual run with publication disabled still builds the preview.
The workflow reads existing Pages configuration with `enablement: false`; it
does not enable the site or use a personal access token. If Pages is not
configured, the requested release fails rather than enabling it implicitly.

See GitHub's [custom Pages workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
for the artifact, deployment permissions and environment requirements.
