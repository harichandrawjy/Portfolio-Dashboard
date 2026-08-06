#!/usr/bin/env bash
#
# Bring a fresh Linux VM to the point where DEPLOY.md step 1 can run.
#
# DEPLOY.md starts at `git clone` and assumes Docker is installed and ports 80
# and 443 are reachable. On a free-tier VM neither is true, and the reasons are
# provider-specific enough to be worth automating rather than documenting:
#
#   Docker      not installed on any stock image
#   Firewall    Oracle's images ship an INPUT chain ending in a blanket REJECT;
#               GCP blocks at the VPC level instead, which this script cannot
#               fix from inside the box (it prints the command)
#   Swap        the frontend build (rollup + tailwind oxide) OOMs on a 1 GB
#               box, and both GCP e2-micro and Oracle's AMD micro are 1 GB
#
# Deliberately does NOT clone the repo or deploy — DEPLOY.md already covers
# that and it works. Safe to re-run; every step is a no-op if already done.
#
#   sudo bash scripts/bootstrap-host.sh
#
set -euo pipefail

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }
warn() { printf '\033[33m    ! %s\033[0m\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }

# Compose 2.24 is the floor: docker-compose.prod.yml relies on the !override
# and !reset tags, and older Compose ignores them silently — which is how the
# database ends up published on every interface with nothing in any log.
MIN_COMPOSE=2.24.0

# --------------------------------------------------------------------------
# Which cloud is this? Only used to print the right console instructions —
# nothing below branches on it.
# --------------------------------------------------------------------------
CLOUD=unknown
if curl -fsS -m 2 -H 'Metadata-Flavor: Google' \
     http://metadata.google.internal/computeMetadata/v1/instance/id >/dev/null 2>&1; then
  CLOUD=gcp
elif curl -fsS -m 2 -H 'Authorization: Bearer Oracle' \
     http://169.254.169.254/opc/v2/instance/ >/dev/null 2>&1; then
  CLOUD=oracle
fi

PUBLIC_IP=$(curl -fsS -m 5 https://api.ipify.org 2>/dev/null || echo "")

say "Host: $(. /etc/os-release && echo "$PRETTY_NAME") on $(uname -m) — cloud: $CLOUD"
[ -n "$PUBLIC_IP" ] && info "public IP: $PUBLIC_IP"

# --------------------------------------------------------------------------
# Swap — before Docker, so the very first build already has it.
# --------------------------------------------------------------------------
say "Swap"
mem_kb=$(awk '/^MemTotal:/{print $2}' /proc/meminfo)
swap_kb=$(awk '/^SwapTotal:/{print $2}' /proc/meminfo)
info "RAM $((mem_kb / 1024)) MB, swap $((swap_kb / 1024)) MB"

if [ "$mem_kb" -ge 2000000 ]; then
  info "2 GB+ of RAM — the frontend build has headroom, skipping"
elif [ "$swap_kb" -ge 512000 ]; then
  info "swap already present, skipping"
elif [ -e /swapfile ]; then
  warn "/swapfile exists but is not active — leaving it alone, check it by hand"
else
  info "under 2 GB and no swap: adding 2 GB at /swapfile so 'npm run build' survives"
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  info "done — 2 GB swap active and persisted to /etc/fstab"
fi

# --------------------------------------------------------------------------
# Host firewall.
#
# Docker's published ports are DNAT'ed in nat/PREROUTING and then traverse
# FORWARD, not INPUT — so in principle Oracle's INPUT REJECT does not block
# them. In practice it is inconsistent across images, the rules cost nothing,
# and anything bound directly to the host later needs them anyway. Restarting
# Docker at the end is the part that actually matters: persisting iptables
# rewrites the table and drops Docker's chains until it re-inserts them.
# --------------------------------------------------------------------------
say "Host firewall (ports 80, 443)"

if command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
  info "firewalld is running (Oracle Linux / RHEL family)"
  firewall-cmd --permanent --add-service=http  >/dev/null
  firewall-cmd --permanent --add-service=https >/dev/null
  firewall-cmd --reload >/dev/null
  info "http + https allowed permanently"

elif command -v iptables >/dev/null 2>&1; then
  # Insert BEFORE the first REJECT/DROP rather than appending. Appending puts
  # the ACCEPT after the blanket REJECT where it can never match, and the
  # hardcoded "-I INPUT 6" from every blog post is wrong the moment an image
  # ships a different number of preceding rules.
  pos=$(iptables -L INPUT --line-numbers -n 2>/dev/null \
        | awk '$2=="REJECT" || $2=="DROP" {print $1; exit}')
  if [ -n "$pos" ]; then
    info "INPUT chain rejects by default at rule $pos — inserting above it"
  else
    info "INPUT chain has no blanket REJECT — appending"
  fi

  changed=0
  for port in 80 443; do
    if iptables -C INPUT -p tcp --dport "$port" -m state --state NEW -j ACCEPT 2>/dev/null; then
      info "port $port already allowed"
      continue
    fi
    if [ -n "$pos" ]; then
      iptables -I INPUT "$pos" -p tcp --dport "$port" -m state --state NEW -j ACCEPT
    else
      iptables -A INPUT -p tcp --dport "$port" -m state --state NEW -j ACCEPT
    fi
    info "port $port allowed"
    changed=1
  done

  if [ "$changed" -eq 1 ]; then
    if command -v netfilter-persistent >/dev/null 2>&1; then
      netfilter-persistent save >/dev/null
      info "saved via netfilter-persistent"
    elif [ -d /etc/iptables ]; then
      iptables-save > /etc/iptables/rules.v4
      info "saved to /etc/iptables/rules.v4"
    elif command -v apt-get >/dev/null 2>&1; then
      warn "iptables-persistent is not installed — rules would vanish on reboot"
      DEBIAN_FRONTEND=noninteractive apt-get update -qq
      DEBIAN_FRONTEND=noninteractive apt-get install -y -qq iptables-persistent >/dev/null
      netfilter-persistent save >/dev/null
      info "installed iptables-persistent and saved"
    else
      warn "could not persist iptables rules — they will not survive a reboot"
    fi
  fi
else
  info "no iptables or firewalld — nothing to open on the host"
fi

# UFW is disabled on Oracle images and OCI's own docs advise against enabling
# it; say so rather than leaving someone to discover it after a lockout.
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q '^Status: active'; then
  warn "ufw is ACTIVE. Oracle advises against it and it can conflict with Docker's chains."
  warn "If 80/443 stay unreachable: sudo ufw allow 80/tcp && sudo ufw allow 443/tcp"
fi

# --------------------------------------------------------------------------
# Docker
# --------------------------------------------------------------------------
say "Docker"
if command -v docker >/dev/null 2>&1; then
  info "already installed: $(docker --version)"
  docker_was_present=1
else
  info "installing via get.docker.com (works on both arm64 and x86_64)"
  curl -fsSL https://get.docker.com | sh >/dev/null
  info "installed: $(docker --version)"
  docker_was_present=0
fi

systemctl enable --now docker >/dev/null 2>&1 || true

# Persisting iptables above rewrites the filter table and wipes Docker's
# chains until the daemon re-adds them. Restart so published ports work now
# rather than after the next reboot.
if [ "${changed:-0}" -eq 1 ] && [ "$docker_was_present" -eq 1 ]; then
  info "restarting Docker so it re-inserts its chains over the new rules"
  systemctl restart docker
fi

compose_ver=$(docker compose version --short 2>/dev/null || echo "")
if [ -z "$compose_ver" ]; then
  warn "the 'docker compose' plugin is missing — docker-compose.prod.yml cannot be used"
  exit 1
fi
if [ "$(printf '%s\n%s\n' "$MIN_COMPOSE" "$compose_ver" | sort -V | head -1)" != "$MIN_COMPOSE" ]; then
  warn "Compose $compose_ver is older than $MIN_COMPOSE."
  warn "The !override / !reset tags would be IGNORED — Postgres would end up"
  warn "published on every interface and the API would bypass Caddy and TLS."
  exit 1
fi
info "Compose $compose_ver — supports the !override / !reset tags"

# Docker group, so the deploy does not need sudo on every command.
if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != root ]; then
  if id -nG "$SUDO_USER" | tr ' ' '\n' | grep -qx docker; then
    info "$SUDO_USER is already in the docker group"
  else
    usermod -aG docker "$SUDO_USER"
    warn "added $SUDO_USER to the docker group — log out and back in for it to apply"
  fi
fi

# --------------------------------------------------------------------------
say "Host is ready. Remaining steps are outside this box:"
cat <<EOF

  1. Open 80/443 at the CLOUD level — the host firewall above is only half of it.
EOF
case "$CLOUD" in
  oracle) cat <<EOF
     Oracle: Networking > Virtual Cloud Networks > your VCN > Security Lists >
     Default Security List > Add Ingress Rules. Two rules, stateful:
       Source 0.0.0.0/0, IP Protocol TCP, Destination Port Range 80
       Source 0.0.0.0/0, IP Protocol TCP, Destination Port Range 443
EOF
  ;;
  gcp) cat <<EOF
     GCP, from a machine with gcloud:
       gcloud compute instances add-tags <INSTANCE> --tags=http-server,https-server --zone=<ZONE>
     (the default-allow-http / default-allow-https rules key off those tags)
EOF
  ;;
  *) cat <<EOF
     Whatever your provider calls its network firewall: allow TCP 80 and 443
     from 0.0.0.0/0.
EOF
  ;;
esac
cat <<EOF

  2. Point the hostname at ${PUBLIC_IP:-this box's public IP} and confirm it
     resolves BEFORE deploying — Caddy's certificate challenge fails otherwise,
     and Let's Encrypt rate-limits repeated failures:

       getent hosts <your-host>      # must print ${PUBLIC_IP:-the IP above}

  3. Then follow DEPLOY.md from step 1 (git clone).

EOF
