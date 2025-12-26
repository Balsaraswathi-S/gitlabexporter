#!/bin/bash
# GitLab Monitoring Stack - Amazon Linux 2023 EC2 Deployment Script

set -e

echo "=========================================="
echo "GitLab Monitoring Stack - EC2 Deployment"
echo "=========================================="
echo ""

# Update system
echo "📦 Updating system packages..."
sudo dnf update -y

# Install Docker
echo "🐳 Installing Docker..."
sudo dnf install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# Install Docker Compose
echo "📦 Installing Docker Compose..."
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
docker-compose --version

# Create application directory
echo "📁 Creating application directory..."
mkdir -p ~/gitlab-monitoring
cd ~/gitlab-monitoring

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "1. Upload your monitoring files to ~/gitlab-monitoring/"
echo "2. Run: docker-compose up -d"
echo "3. Configure security group to allow ports:"
echo "   - 3000 (Grafana)"
echo "   - 9090 (Prometheus)"
echo "   - 9200 (GitLab Exporter)"
echo ""
echo "Note: You may need to logout and login again for Docker group to take effect."
echo "      Or run: newgrp docker"


