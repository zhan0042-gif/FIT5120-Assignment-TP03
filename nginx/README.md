# Nginx

The production reverse proxy is **host nginx on the EC2 instance**, not a container. It terminates TLS, enforces the shared-password gate, serves the three static frontend builds, and proxies the API to the backend container.

**The live configuration is `/etc/nginx/sites-enabled/default` on the server.** It is not a file in this directory and it is not version-controlled — this README is the record of what it contains. Editing it means editing that file over SSM and reloading; back it up first (`sudo cp /etc/nginx/sites-enabled/default /tmp/nginx-default.bak.$(date +%F)`).

## Layout

| Path | Serves | Backing directory |
| ---------------- | ---------------------------------------------- | ------------------- |
| `/` | Current build (I3) | `/var/www/html` |
| `/i1/` | Archived Iteration 1 build | `/var/www/html/i1` |
| `/i2/` | Archived Iteration 2 build | `/var/www/html/i2` |
| `/api/` | FastAPI, via `proxy_pass http://127.0.0.1:8000` | backend container |

`proxy_pass` has no URI part, so the full original URI is passed through unchanged — `/api/v1/households` reaches the backend as `/api/v1/households`.

## Authentication

`auth_basic "Restricted"` and `auth_basic_user_file /etc/nginx/.htpasswd` are set at **server** level, so every location block inherits the gate without repeating the directive. Adding `auth_basic` inside `location /i1/` would be redundant, and its absence there is not a gap.

This is the detail that is easiest to get wrong in both directions, so it is worth stating plainly: nginx location blocks **do** inherit server-level directives. A new location under this server is gated by default.

The gate is a single shared password for the whole site, including both archives. It is a "keep the prototype private" control, not per-user authentication.

## Static routing

Each frontend build is an SPA, so every location needs its own fallback or a deep link resolves against the wrong build:

```nginx
location / {
    try_files $uri $uri/ /index.html;
}
location /i1/ {
    try_files $uri $uri/ /i1/index.html;
}
location /i2/ {
    try_files $uri $uri/ /i2/index.html;
}
```

Two things follow from this that are easy to miss:

- **A location without its own `try_files` inherits nothing useful here.** The fallback is a literal path, and the obvious fallback `/index.html` is the *current* build, so `/i1/plan` on a refresh would serve the I3 shell rather than the I1 app. Each archive needs its own line.
- **Matching is by longest prefix, not file order.** Three prefix locations coexist without ordering concerns; there are no regex locations in this config.

## Adding another archive

Build the frozen commit with a matching asset base and an injected `<base>` tag, then copy it in and add one location block:

```bash
git worktree add --detach /tmp/i3-build <sha>
cd /tmp/i3-build/frontend && npm ci && npx vite build --base=/i3/
perl -i -pe 's{<head>}{<head>\n    <base href="/i3/" />}' dist/index.html
sudo mkdir -p /var/www/html/i3 && sudo cp -r dist/. /var/www/html/i3/
```

Both the `--base` flag and the `<base>` tag are required and they do different jobs: `--base` rewrites asset URLs, and the `<base>` tag is what the router reads to derive its history base. Vite's `--base` alone does not change routing, because vue-router does not read `BASE_URL` from the build.

Then add the location block, back up the config, and reload:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

`deploy.sh` copies each new build into `/var/www/html` with `cp -r dist/.` — an overwrite-copy that does not delete. The archive subdirectories are therefore untouched by a normal deploy, which is what keeps them frozen.

## Security notes

Tracked as T21 in the threat model. The archive paths are gated like everything else, and the residual risk is only that the shared gate is exactly as strong as it is for the main site.

The explicit probe is `curl -s -o /dev/null -w '%{http_code}\n' https://cubesix.me/i1/`, which must print `401`.
