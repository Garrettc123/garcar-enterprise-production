# 💰 Deploy Everything Money - Quick Start Guide

**Complete deployment of all revenue-generating systems in under 10 minutes**

## 🎯 Overview

This guide will deploy the complete Garcar Enterprise Production Stack with all revenue systems connected and operational.

## ⚡ One-Command Deployment

```bash
./scripts/deploy-everything-money.sh
```

That's it! The master orchestrator will:
1. ✅ Check prerequisites
2. ✅ Build Docker images
3. ✅ Deploy Kubernetes infrastructure
4. ✅ Deploy all revenue services
5. ✅ Configure networking
6. ✅ Verify health checks
7. ✅ Connect revenue systems
8. ✅ Display deployment summary

## 📋 Prerequisites

Before running the deployment, ensure you have:

- **Docker** (20.10+)
- **kubectl** configured with cluster access
- **Kubernetes cluster** (GKE, EKS, AKS, or minikube)
- **Git** (for cloning repository)

### Quick Install (Ubuntu/Debian)

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# Verify installations
docker --version
kubectl version --client
```

## 🚀 Deployment Methods

### Option 1: Kubernetes (Recommended for Production)

```bash
# Full deployment to Kubernetes
./scripts/deploy-everything-money.sh kubernetes

# Dry run (preview without deploying)
./scripts/deploy-everything-money.sh kubernetes true
```

### Option 2: Local Development

```bash
# Use Docker Compose for local development
cp .env.example .env
# Edit .env with your configuration
docker-compose up -d
```

### Option 3: GitHub Actions CI/CD

```bash
# Trigger automated deployment
git push origin main

# Or manually trigger workflow
gh workflow run deploy-production.yml
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file or configure Kubernetes secrets:

```bash
# Database
DB_HOST=postgres
DB_PORT=5432
DB_NAME=revenue_aggregator
DB_USER=postgres
DB_PASSWORD=your_secure_password

# Redis
REDIS_URL=redis://redis:6379

# JWT Authentication
JWT_SECRET=your_jwt_secret_min_32_chars

# Services
API_GATEWAY_PORT=5000
REVENUE_AGGREGATOR_PORT=8080
AI_AGENT_HUB_PORT=8081
```

### Kubernetes Secrets

```bash
# Create secrets manually
kubectl create secret generic garcar-secrets \
  --from-literal=db-password=YOUR_PASSWORD \
  --from-literal=jwt-secret=YOUR_JWT_SECRET \
  --from-literal=redis-password=YOUR_REDIS_PASSWORD \
  -n garcar-prod

# Or use the configuration script
./scripts/configure-secrets.sh
```

## 💸 Revenue Systems

The deployment automatically connects these revenue systems:

| System | Annual Potential | Status |
|--------|-----------------|--------|
| NWU Protocol | $98,500,000 | Active |
| Tree of Life System | $131,796 MRR | Active |
| MARS AI | $10,000,000 | Active |
| AI Orchestrator | $490,000 | Active |
| AI Business Platform | $946,000 | Active |

**Total Annual Potential: $110,067,796**

## 📊 Post-Deployment Verification

### Check Deployment Status

```bash
# View all pods
kubectl get pods -n garcar-prod

# Check service health
kubectl get svc -n garcar-prod

# View logs
kubectl logs -f deployment/revenue-aggregator -n garcar-prod
```

### Access Services

```bash
# Get service URLs
kubectl get ingress -n garcar-prod

# Port forward for local access
kubectl port-forward svc/api-gateway 5000:5000 -n garcar-prod
kubectl port-forward svc/revenue-aggregator 8080:8080 -n garcar-prod
kubectl port-forward svc/ai-agent-hub 8081:8081 -n garcar-prod
```

### Test API Endpoints

```bash
# Health check
curl http://localhost:5000/health

# Get current revenue
curl http://localhost:5000/api/revenue/current

# List AI agents
curl http://localhost:5000/api/agents
```

## 🔍 Monitoring

### View Metrics

```bash
# Prometheus metrics
kubectl port-forward svc/prometheus 9090:9090 -n garcar-prod
# Open http://localhost:9090

# Grafana dashboards
kubectl port-forward svc/grafana 3000:3000 -n garcar-prod
# Open http://localhost:3000
# Default: admin/admin
```

### Check Logs

```bash
# All services
kubectl logs -f -l app=garcar -n garcar-prod

# Specific service
kubectl logs -f deployment/api-gateway -n garcar-prod

# Database logs
kubectl logs -f deployment/postgres -n garcar-prod
```

## 🐞 Troubleshooting

### Pods Not Starting

```bash
# Describe pod for events
kubectl describe pod POD_NAME -n garcar-prod

# Check pod logs
kubectl logs POD_NAME -n garcar-prod

# Check previous logs if crashed
kubectl logs POD_NAME -n garcar-prod --previous
```

### Database Connection Issues

```bash
# Test database connection
kubectl exec -it deploy/postgres -n garcar-prod -- psql -U postgres

# Check database tables
kubectl exec -it deploy/postgres -n garcar-prod -- psql -U postgres -d revenue_aggregator -c "\dt"
```

### Service Not Accessible

```bash
# Check service endpoints
kubectl get endpoints -n garcar-prod

# Test internal connectivity
kubectl exec -it deploy/api-gateway -n garcar-prod -- curl http://revenue-aggregator:8080/health
```

### Image Pull Errors

```bash
# Check image pull secrets
kubectl get secrets -n garcar-prod

# Pull images manually
docker pull garcar-api-gateway:latest
docker pull garcar-revenue-aggregator:latest
docker pull garcar-ai-agent-hub:latest
```

## 🔄 Rollback

If something goes wrong, rollback to previous version:

```bash
# Rollback all services
./scripts/rollback.sh all

# Rollback specific service
./scripts/rollback.sh revenue-aggregator

# Manual rollback
kubectl rollout undo deployment/revenue-aggregator -n garcar-prod
```

## 📈 Scaling

### Manual Scaling

```bash
# Scale revenue aggregator
kubectl scale deployment revenue-aggregator --replicas=5 -n garcar-prod

# Scale AI agent hub
kubectl scale deployment ai-agent-hub --replicas=4 -n garcar-prod
```

### Auto-Scaling (HPA)

Horizontal Pod Autoscaler is automatically configured:

- **Revenue Aggregator**: 3-10 replicas (CPU > 70%)
- **AI Agent Hub**: 2-8 replicas (CPU > 70%)
- **API Gateway**: 3-10 replicas (CPU > 70%)

## 🔐 Security Checklist

- [ ] Update default passwords in secrets
- [ ] Configure JWT secret (min 32 characters)
- [ ] Enable network policies
- [ ] Configure TLS/SSL certificates
- [ ] Setup firewall rules
- [ ] Enable audit logging
- [ ] Configure RBAC policies
- [ ] Scan images for vulnerabilities

## 📚 Additional Resources

- **Full Documentation**: See [README.md](README.md)
- **Launch Guide**: See [LAUNCH.md](LAUNCH.md)
- **Architecture**: See [docs/architecture.md](docs/architecture.md)
- **API Documentation**: See [docs/api.md](docs/api.md)

## 💬 Support

- **Issues**: [GitHub Issues](https://github.com/Garrettc123/garcar-enterprise-production/issues)
- **Email**: gwc2780@gmail.com
- **Documentation**: [docs.garcar-enterprise.com](https://docs.garcar-enterprise.com)

## 🎉 Success!

Once deployment completes, you'll see:

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🎉 SUCCESS! ALL REVENUE SYSTEMS DEPLOYED! 🎉              ║
║                                                              ║
║   💰 Total Annual Potential: $110,067,796                   ║
║   🚀 All Services: OPERATIONAL                              ║
║   💸 Revenue Tracking: ACTIVE                               ║
║   🤖 AI Agents: ONLINE                                      ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

**Your revenue systems are now live and generating money! 💰**

---

*Built with ❤️ by Garrett Carrol | Garcar Enterprise © 2026*
