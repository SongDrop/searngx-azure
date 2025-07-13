def generate_setup(
    DOMAIN_NAME,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,  # Not used by default in SearxNG but kept for uniformity
    PORT
):
    base_domain = DOMAIN_NAME.split('.', 1)[-1] if DOMAIN_NAME.count('.') > 1 else DOMAIN_NAME
    searxng_dir = "/opt/searxng"
    searxng_image = "searxng/searxng:latest"

    script_template = f"""#!/bin/bash

set -e

# Validate DOMAIN_NAME is a proper FQDN
if [[ ! "{DOMAIN_NAME}" =~ ^[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}$ ]]; then
    echo "ERROR: {DOMAIN_NAME} is not a valid FQDN (e.g., {DOMAIN_NAME})"
    exit 1
fi

DOMAIN_NAME="{DOMAIN_NAME}"
ADMIN_EMAIL="{ADMIN_EMAIL}"
SEARXNG_DIR="{searxng_dir}"

echo "Updating system and installing dependencies..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y curl docker.io ufw nginx certbot python3-certbot-nginx

echo "Installing docker-compose..."
DOCKER_COMPOSE_VERSION="v2.24.5"
curl -SL https://github.com/docker/compose/releases/download/$DOCKER_COMPOSE_VERSION/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

echo "Enabling and starting Docker and Nginx services..."
systemctl enable docker
systemctl start docker
systemctl enable nginx
systemctl start nginx

echo "Creating SearxNG directory..."
mkdir -p "$SEARXNG_DIR"
cd "$SEARXNG_DIR" || exit 1

echo "Creating Docker Compose file for SearxNG..."
cat > docker-compose.yml <<EOF
version: "3"

services:
  searxng:
    image: {searxng_image}
    container_name: searxng
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ./settings.yml:/etc/searxng/settings.yml:ro
EOF

echo "Creating minimal settings.yml..."
cat > settings.yml <<'EOF'
server:
  base_url: https://{DOMAIN_NAME}

# Add additional settings or customize as needed
EOF

echo "Starting SearxNG container..."
docker-compose up -d

echo "Allowing HTTP, HTTPS, and SSH through UFW..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp

ufw status | grep -qw inactive && echo "Enabling UFW firewall..." && ufw --force enable
ufw reload || true

echo "Configuring Nginx reverse proxy for SearxNG..."

NGINX_CONF="/etc/nginx/sites-available/searxng"
cat > "$NGINX_CONF" <<EOF
server {{
    listen 80;
    server_name {DOMAIN_NAME};

    location /.well-known/acme-challenge/ {{
        root /var/www/certbot;
    }}

    location / {{
        proxy_pass http://localhost:{PORT}/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }}
}}
EOF

mkdir -p /var/www/certbot
ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/searxng

echo "Testing Nginx configuration..."
nginx -t

echo "Reloading Nginx..."
systemctl reload nginx

echo "Obtaining Let's Encrypt SSL certificate for {DOMAIN_NAME}..."
certbot --nginx -d {DOMAIN_NAME} --non-interactive --agree-tos --email {ADMIN_EMAIL} --redirect

echo "Reloading Nginx to apply SSL configuration..."
systemctl reload nginx

echo "SearxNG setup completed successfully!"

echo ""
echo "IMPORTANT DNS Records to configure for {DOMAIN_NAME}:"
echo "A Record: {DOMAIN_NAME} -> Your Server IP"
echo ""
echo "Access SearxNG at: https://{DOMAIN_NAME}/"
echo ""
echo "Please customize your SearxNG settings in {searxng_dir}/settings.yml as needed."
"""
    return script_template