# Documentation publishing

The canonical product URL is <https://deepagentlabs.io/control-tower/>, with
[documentation](https://deepagentlabs.io/control-tower/docs/) and
[use cases](https://deepagentlabs.io/control-tower/usecases/).

This repository owns the product page, images, guides and use cases. The
`deepagentlabs.github.io` workflow builds and publishes them with the same
shared theme used by Lens, Sidecar, Chaos, Evals and MCP. A scheduled website
build picks up source updates daily; maintainers can dispatch the website's
**Website and repository docs** workflow to publish immediately after a merge.

This repository's **Docs** workflow validates both shared builds and uploads a
product preview artifact. It does not deploy an independent project Pages site.
This keeps the existing website navigation, product URL and theme consistent.

The shared builder discovers guides and groups them by reader task. Historical
`/control-tower/docs/docs/...` links remain as redirects to the corresponding
canonical guides.
