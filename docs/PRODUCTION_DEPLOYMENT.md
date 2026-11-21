# Production deployment guide

AccessPath AI's normal `docker-compose.yml` is for local development and demos.
Use `config.settings.production` and `docker-compose.production.yml` only behind a
managed HTTPS gateway. The cloud platform, DNS and secrets are intentionally not
created by this repository.

## Required services

- A managed PostgreSQL database on a private network, with backups and point-in-time recovery.
- A managed Redis service on a private network, with TLS and authentication where available.
- Private object storage for screenshots and reports. Apply lifecycle deletion rules before accepting user data.
- A secret manager and KMS. Store `DJANGO_SECRET_KEY`, database credentials, Redis credentials, provider keys and repository tokens there; never in Git or a production `.env` file.
- A HTTPS load balancer that removes incoming `X-Forwarded-Proto`, sets it itself, validates the expected host names and forwards only to the `web` service.
- A separate evaluation-worker service. It is the only service allowed controlled outbound internet access.

## Production variables

Set these through the cloud secret manager or deployment platform:

```text
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=<unique random secret>
DJANGO_ALLOWED_HOSTS=app.example.edu
SECURE_HSTS_SECONDS=31536000
POSTGRES_*=<managed database values>
REDIS_URL=<private Redis URL>
CELERY_RESULT_BACKEND=<private Redis URL>
```

The production profile requires HSTS preload and all subdomains. Only use it after the
entire production domain is permanently HTTPS-only. Use a separate staging profile for
certificate and redirect testing.

## Service separation

| Service | Queue / role | Network access |
|---|---|---|
| `web` | Django and reports | Database, Redis, private object storage only |
| `browser-worker` | `default,evaluation` | Database, Redis, object storage, controlled public-web egress and approved AI providers |
| `repository-worker` | `repository` | Database, Redis, object storage and allowlisted Git hosts only |

Run browser workers with one Chromium evaluation at a time initially. Add workers
when queue age grows rather than increasing browser concurrency inside a container.

## Network rules

At the cloud firewall or egress proxy, deny browser-worker access to loopback,
private, link-local and cloud metadata addresses. Explicitly block `169.254.169.254`
and the provider-specific metadata address. Allow only DNS, HTTPS to approved public
sites and AI providers, and service-to-service private traffic.

The application also checks target manifests, but network enforcement is necessary to
protect against DNS rebinding and browser implementation issues.

## Deployment checklist

```text
[ ] Build immutable image and record its digest
[ ] Apply database migrations as one release job
[ ] Run python manage.py check --deploy
[ ] Verify /healthz/ and /readyz/
[ ] Confirm HTTPS redirect, secure cookies and strict host handling
[ ] Confirm database restore from a backup
[ ] Confirm object-storage lifecycle rule and private access
[ ] Confirm worker resource limits, queue routing and egress firewall
[ ] Confirm monitoring for errors, queue age, worker memory, provider 429s and spend
[ ] Run the deterministic benchmark after release
```

## Resource starting point

Start with two small web replicas and one browser worker with 1–2 vCPU and 2–4 GB
RAM. Keep browser-worker concurrency at one. Set cost caps for active browser workers,
AI calls per run and AI spend per user/team in the cloud account before public use.

## Verification

```bash
python manage.py check --deploy --settings=config.settings.production
docker compose -f docker-compose.production.yml config --quiet
```

Do not run `docker-compose.production.yml` as-is on a public host until managed
database, Redis, object storage, secret manager, HTTPS gateway and network controls
are supplied by the selected cloud platform.
