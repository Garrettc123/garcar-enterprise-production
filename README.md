# 🚀 Garcar Enterprise Production Stack

**Auto-Deployment System with Complete CI/CD Pipeline**

## 🎯 Overview

Production-ready enterprise stack featuring:
- **Revenue Aggregator**: Universal revenue tracking across all systems
- **AI Agent Network Hub**: Distributed agent orchestration
- **API Gateway**: Unified entry point with authentication & rate limiting
- **Auto-Deployment**: GitHub Actions CI/CD with Kubernetes

## 🏗️ Architecture

```
╭────────────────────╮
│  API Gateway (5000)   │
│  ├─ Authentication    │
│  ├─ Rate Limiting     │
│  └─ Load Balancing    │
╰────────┬───────────╯
         │
    ┌────┼────┐
    │         │
╭───┼──╮  ╭───┼───╮
│Revenue│  │AI Agent│
│ (8080) │  │  (8081) │
╰───┬───╯  ╰───┬────╯
    │         │
    └───┬─────┘
        │
   ╭────┼────╮
   │PostgreSQL│
   │  (5432)  │
   ╰─────────╯
```

## ⚡ Quick Start

### 💰 Deploy Everything Money (One Command)

```bash
./scripts/deploy-everything-money.sh
```

This master orchestrator deploys the complete revenue stack in under 10 minutes!

**See [QUICKSTART.md](QUICKSTART.md) for 5-minute getting started guide.**

**See [DEPLOY.md](DEPLOY.md) for detailed deployment guide.**

### Prerequisites
- Docker & Docker Compose
- Kubernetes cluster (or minikube for local)
- kubectl configured
- GitHub account with repository access

### 1️⃣ Configure Secrets

Add these secrets to your GitHub repository:

```bash
KUBECONFIG           # Base64 encoded kubeconfig
DB_PASSWORD          # PostgreSQL password
REDIS_PASSWORD       # Redis password
JWT_SECRET           # JWT signing secret (min 32 chars)
GRAFANA_PASSWORD     # Grafana admin password
ALLOWED_ORIGINS      # Comma-separated list of allowed CORS origins
SLACK_WEBHOOK_URL    # Slack notifications (optional)
PAGERDUTY_WEBHOOK    # PagerDuty alerts (optional)
PAGERDUTY_KEY        # PagerDuty routing key (optional)
```

**Note on CORS Configuration:**
The `ALLOWED_ORIGINS` environment variable controls which domains can access the API. 
For production, set this to your actual domain names (e.g., `https://api.garcar-enterprise.com,https://garcar-enterprise.com`). 
For development, use `http://localhost:3000,http://localhost:5000`.

### 2️⃣ Auto-Deploy

**Push to main branch:**
```bash
git push origin main
```

GitHub Actions will automatically:
1. ✅ Build Docker images
2. ✅ Run security scans
3. ✅ Deploy to Kubernetes
4. ✅ Run health checks
5. ✅ Execute performance tests

**Manual deployment:**
```bash
gh workflow run deploy-production.yml
```

### 3️⃣ Verify Deployment

```bash
# Check pods
kubectl get pods -n garcar-prod

# Check services
kubectl get svc -n garcar-prod

# View logs
kubectl logs -f deployment/revenue-aggregator -n garcar-prod
```

## 📦 Service Endpoints

| Service | Port | URL |
|---------|------|-----|
| API Gateway | 5000 | `https://api.garcar-enterprise.com` |
| Revenue Aggregator | 8080 | `https://revenue.garcar-enterprise.com` |
| AI Agent Hub | 8081 | `https://agents.garcar-enterprise.com` |
| Grafana | 3000 | `https://monitoring.garcar-enterprise.com` |
| Prometheus | 9090 | `https://prometheus.garcar-enterprise.com` |

## 📊 Monitoring

**Automated health checks every 15 minutes:**
- Service availability
- Response times
- Error rates
- Resource utilization

**Grafana Dashboards:**
- Revenue metrics
- Agent performance
- API gateway analytics
- System health

## 💾 Database Backups

**Automated daily backups at 2 AM UTC:**
- Full PostgreSQL dump
- Uploaded to S3 Glacier
- 30-day retention policy
- Point-in-time recovery

## 🔐 Security Features

- ✅ JWT authentication
- ✅ Rate limiting (100 req/15min)
- ✅ Helmet.js security headers
- ✅ Restricted CORS (configurable allowed origins)
- ✅ Automated vulnerability scanning
- ✅ Secrets encrypted with Kubernetes
- ✅ TLS/SSL with Let's Encrypt

## 📚 API Documentation

### Authentication
```bash
curl -X POST https://api.garcar-enterprise.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"secret"}'
```

### Get Revenue
```bash
curl https://api.garcar-enterprise.com/api/revenue/current \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### List AI Agents
```bash
curl https://api.garcar-enterprise.com/api/agents \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Money Dashboard (All Revenue Systems)
```bash
curl https://api.garcar-enterprise.com/api/money/dashboard \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Returns consolidated view of all revenue systems:
- Total annual potential: $110,067,796
- Active systems status
- Payout configuration
- Real-time statistics

## 🛠️ Development

**Local development:**
```bash
# Clone repository
git clone https://github.com/Garrettc123/garcar-enterprise-production
cd garcar-enterprise-production

# Setup environment
cp .env.example .env
# Edit .env with your values

# Start services
docker-compose up -d

# View logs
docker-compose logs -f
```

## 🐞 Troubleshooting

**Pods not starting:**
```bash
kubectl describe pod POD_NAME -n garcar-prod
kubectl logs POD_NAME -n garcar-prod
```

**Database connection issues:**
```bash
kubectl exec -it deploy/postgres -n garcar-prod -- psql -U postgres
```

**Check GitHub Actions:**
- Go to Actions tab in repository
- View workflow runs and logs

## 💼 Production Checklist

- [ ] Configure all GitHub secrets
- [ ] Update domain names in ingress.yaml
- [ ] Setup DNS records
- [ ] Configure SSL certificates
- [ ] Setup S3 bucket for backups
- [ ] Configure monitoring alerts
- [ ] Test disaster recovery
- [ ] Document runbooks

## 📈 Scaling

**Horizontal Pod Autoscaler (HPA):**
- Revenue Aggregator: 3-10 replicas
- AI Agent Hub: 2-8 replicas
- API Gateway: 3-10 replicas

**Auto-scales based on:**
- CPU utilization > 70%
- Memory utilization > 80%

## 🌟 Support

- **Documentation**: [docs.garcar-enterprise.com](https://docs.garcar-enterprise.com)
- **Issues**: [GitHub Issues](https://github.com/Garrettc123/garcar-enterprise-production/issues)
- **Email**: gwc2780@gmail.com

## 📝 License

Proprietary - Garcar Enterprise © 2026

---

**Built with ❤️ by Garrett Carrol**
**Deployed with 🚀 GitHub Actions**
