#!/usr/bin/env bash
# One entry point for running, demonstrating and testing AccessPath AI (macOS/Linux).
#   ./scripts/dev.sh setup | start | demo | test | lint | check | benchmark | logs | stop
set -euo pipefail
cd "$(dirname "$0")/.."
command="${1:-help}"; shift || true

secret() { python3 -c "import secrets,sys; print(secrets.token_urlsafe(int(sys.argv[1])))" "$1"; }

init_env() {
  if [ -f .env ]; then echo ".env already exists; keeping it."; return; fi
  sed -e "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$(secret 48)|" \
      -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(secret 18)|" .env.example > .env
  echo "Created .env with a random secret key and database password. Add AI keys there later (optional)."
}

wait_web() {
  for _ in $(seq 1 30); do
    docker compose exec -T web python manage.py check >/dev/null 2>&1 && return 0
    sleep 2
  done
}

case "$command" in
  setup)
    init_env
    docker compose up -d --build --renew-anon-volumes
    wait_web
    docker compose exec -T web python manage.py migrate
    docker compose exec -T web python manage.py install_axe_core \
      || echo "axe-core could not be downloaded; the keyboard checks still run."
    docker compose exec -T web python manage.py demo_setup "$@"
    docker compose exec -T web python manage.py check_setup
    echo; echo "Open http://127.0.0.1:8000/ and sign in with the demo account above." ;;
  start) docker compose up -d ;;
  demo) docker compose exec -T web python manage.py demo_setup "$@" ;;
  test) docker compose exec -T -e DJANGO_SETTINGS_MODULE=config.settings.test web python -m pytest -q "$@" ;;
  lint) docker compose exec -T web python -m ruff check . "$@" ;;
  check) docker compose exec -T web python manage.py check_setup ;;
  benchmark)
    if [ "$#" -eq 0 ]; then set -- --provider fixture --repeat 1; fi
    docker compose exec -T worker python manage.py run_benchmark "$@" ;;
  logs) docker compose logs -f worker ;;
  stop) docker compose stop ;;
  *) sed -n '2,3p' "$0" ;;
esac
