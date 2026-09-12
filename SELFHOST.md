# Self-hosting this fork

This fork packages the repository's existing compiled `html/` directory as a static Nginx image. It does **not** rebuild the Vite/Framework7 source during image publication.

## Image

GHCR image:

```text
ghcr.io/rogerma12345/zhihu_web
```

Published images support:

- `linux/amd64`
- `linux/arm64`

`latest` is updated whenever the workflow actually publishes an image.

For an automatic upstream synchronization, the workflow also publishes an immutable-style upstream tag:

```text
upstream-<first-12-characters-of-upstream-SHA>
```

For a build triggered from a direct fork deployment change, or a forced rebuild with no new upstream commit, it publishes:

```text
fork-<first-12-characters-of-fork-commit-SHA>
```

## Why the application lives under `/zhihu_web/`

The existing Vite configuration uses `/zhihu_web/` as its base path, and the already-built files in `html/` reference assets below that path. The Docker image therefore preserves the same application base path instead of moving the application to `/`.

Nginx behavior is:

```text
/             -> 302 /zhihu_web/
/zhihu_web    -> 301 /zhihu_web/
/zhihu_web/   -> existing html/index.html
```

The application uses hash routing (`#!/...`), so Nginx does not provide a history-SPA fallback. Missing static files return a real `404`.

## Intended deployment

This image is intended for a trusted home/LAN HTTP deployment with no domain, HTTPS termination, or reverse proxy requirement.

Example run command for the user to execute on the Docker host:

```bash
docker run -d \
  --name zhihu-web \
  --restart unless-stopped \
  -p 8080:80 \
  ghcr.io/rogerma12345/zhihu_web:latest
```

Then open:

```text
http://192.168.2.X:8080/zhihu_web/
```

The container itself does not need the LAN host IP as configuration.

## Login and browser data

This fork does not add a login backend, Nginx API proxy, cookie proxy, token relay, or database. The existing browser-side Zhihu login flow remains unchanged:

```text
Browser -> GM_xmlhttpRequest -> Zhihu API
```

Login-related browser data is not stored in the Docker image or Nginx server. The server must not be given Zhihu phone numbers, passwords, SMS codes, cookies, access tokens, or refresh tokens.

## Upstream synchronization

The single workflow `.github/workflows/sync-ghcr.yml` handles both synchronization and image publication in the same workflow run.

For scheduled/manual upstream checks it:

1. fetches `zhihulite/zhihu_web` `main`;
2. compares the upstream HEAD with `.upstream-state`;
3. stops without building when nothing changed, unless the scheduled keepalive rule applies;
4. creates an upstream working-tree snapshot when the SHA changed;
5. checks for conflicts with fork-owned overlay paths;
6. synchronizes normal upstream files with `rsync --archive --delete` while preserving fork-owned files and all fork workflows;
7. builds and pushes the multi-architecture GHCR image from the current workspace;
8. only after a successful image publication, updates `.upstream-state` and pushes the synchronized fork commit.

This ordering means a failed GHCR build/push does not mark an upstream SHA as completed, so a later scheduled run can retry it.

Fork-managed paths are protected from upstream synchronization:

```text
.git/
.github/workflows/
Dockerfile
.dockerignore
deploy/
.upstream-state
SELFHOST.md
```

If upstream begins shipping a conflicting fork-overlay path such as `Dockerfile`, `.dockerignore`, `deploy/`, `.upstream-state`, or `SELFHOST.md`, automatic synchronization fails before copying files. The user must decide how to resolve that conflict.

Upstream `.github/workflows/` files are always excluded rather than synchronized, so the upstream GitHub Pages workflow cannot be restored automatically.

## Scheduled workflow and keepalive

The schedule runs daily at:

```text
27 3 * * *
```

This is 03:27 UTC.

On a public fork, GitHub may require the scheduled workflow to be enabled manually. In the repository's **Actions** tab, open **Sync upstream and publish GHCR** and use **Enable workflow** if GitHub shows that option.

If a scheduled run finds no upstream change and `.upstream-state` shows at least 30 days since `last_activity`, the workflow only refreshes `last_activity` and pushes:

```text
chore: keep upstream sync active
```

That keepalive does not build or publish an image and does not modify `html/` or deployment files. Pushes performed by `GITHUB_TOKEN` do not create a recursive workflow run. If GitHub still disables scheduled workflows after repository inactivity, the user must enable the workflow again manually.

## Manual workflow run

Open **Actions** -> **Sync upstream and publish GHCR** -> **Run workflow**.

The `force_build` input defaults to `false`:

- upstream changed: synchronize, build, publish, then commit the new state;
- upstream unchanged and `force_build=false`: finish without publishing;
- upstream unchanged and `force_build=true`: rebuild/publish the current fork state.

No PAT is required by this workflow. It uses the repository `GITHUB_TOKEN` with:

```yaml
permissions:
  contents: write
  packages: write
```

If repository rules, branch protection, organization policy, or package permissions block those operations, resolve that GitHub-side policy rather than adding a PAT to the workflow.

## GHCR visibility

A **Public** GHCR package can be pulled without package authentication. A **Private** package requires an authenticated client with permission to read the package. Package visibility is managed in GitHub; this workflow does not force the package to Public.

After the first successful publication, check the package settings and change visibility manually if anonymous LAN-host pulls are desired.

## User acceptance testing

Image runtime verification remains a user task. After publication, the user should verify the root redirect, `/zhihu_web/`, static assets, hash routes, iframe embedding, GM requests, Zhihu login, login persistence after refresh, and browser-side login persistence after a container restart.
