/**
 * Universal API Gateway - Production Ready
 * Garcar Enterprise
 */

const express = require('express');
const rateLimit = require('express-rate-limit');
const helmet = require('helmet');
const jwt = require('jsonwebtoken');
const redis = require('redis');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();
const PORT = process.env.PORT || 5000;

// Redis client for caching and rate limiting
const redisClient = redis.createClient({
  host: process.env.REDIS_HOST || 'localhost',
  port: process.env.REDIS_PORT || 6379,
  password: process.env.REDIS_PASSWORD
});

redisClient.on('connect', () => {
  console.log('Connected to Redis');
});

redisClient.on('error', (err) => {
  console.error('Redis error:', err);
});

// Security middleware
app.use(helmet());
app.use(express.json());

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests per windowMs
  message: 'Too many requests from this IP'
});

app.use('/api/', limiter);

// CORS
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Authorization');
  if (req.method === 'OPTIONS') {
    return res.sendStatus(200);
  }
  next();
});

// JWT Authentication Middleware
const authenticateToken = (req, res, next) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];
  
  if (!token) {
    return res.status(401).json({ error: 'Access token required' });
  }
  
  jwt.verify(token, process.env.JWT_SECRET, (err, user) => {
    if (err) {
      return res.status(403).json({ error: 'Invalid token' });
    }
    req.user = user;
    next();
  });
};

// Logging middleware
app.use((req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    const duration = Date.now() - start;
    console.log(`${req.method} ${req.path} ${res.statusCode} ${duration}ms`);
  });
  next();
});

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'api-gateway',
    version: '1.0.0',
    timestamp: new Date().toISOString()
  });
});

// Readiness check
app.get('/ready', (req, res) => {
  // Check if dependencies are ready
  res.json({
    status: 'ready',
    service: 'api-gateway',
    dependencies: {
      redis: redisClient.connected ? 'connected' : 'disconnected'
    }
  });
});

// Metrics endpoint for Prometheus
app.get('/metrics', (req, res) => {
  res.set('Content-Type', 'text/plain');
  res.send(`
# HELP api_gateway_requests_total Total number of requests
# TYPE api_gateway_requests_total counter
api_gateway_requests_total 0

# HELP api_gateway_up Service up status
# TYPE api_gateway_up gauge
api_gateway_up 1
  `.trim());
});

// Service proxies
const services = {
  revenue: {
    target: 'http://revenue-aggregator-service:8080',
    pathRewrite: { '^/api/revenue': '/revenue' }
  },
  agents: {
    target: 'http://ai-agent-hub-service:8081',
    pathRewrite: { '^/api/agents': '' }
  }
};

// Proxy endpoints
app.use('/api/revenue', authenticateToken, createProxyMiddleware(services.revenue));
app.use('/api/agents', authenticateToken, createProxyMiddleware(services.agents));

// Public endpoints (no auth required)
app.use('/public/revenue', createProxyMiddleware({
  target: 'http://revenue-aggregator-service:8080',
  pathRewrite: { '^/public/revenue': '/revenue/current' }
}));

// Money Dashboard - Consolidated view of all revenue systems
app.get('/api/money/dashboard', authenticateToken, async (req, res) => {
  try {
    const dashboard = {
      timestamp: new Date().toISOString(),
      totalAnnualPotential: 110067796,
      systems: [
        {
          name: 'NWU Protocol',
          status: 'active',
          annualPotential: 98500000,
          endpoint: 'http://nwu-protocol:8000/api/revenue/current'
        },
        {
          name: 'Tree of Life System',
          status: 'active',
          mrr: 131796,
          annualPotential: 1581552,
          endpoint: 'https://tree-of-life-system.vercel.app/api/subscriptions/mrr'
        },
        {
          name: 'MARS AI',
          status: 'active',
          annualPotential: 10000000,
          endpoint: 'http://mars-ai:3000/api/revenue'
        },
        {
          name: 'AI Orchestrator',
          status: 'active',
          annualPotential: 490000,
          endpoint: 'http://ai-orchestrator:8001/api/health'
        },
        {
          name: 'AI Business Platform',
          status: 'active',
          annualPotential: 946000,
          endpoint: 'http://ai-business-platform:3001/api/v1/status'
        }
      ],
      payouts: {
        paypal: {
          email: 'gwc2780@gmail.com',
          percentage: 70
        },
        ethereum: {
          address: '0x5C92DCa91ac3251c17c94d69E93b8784fE8dcd30',
          percentage: 30
        },
        threshold: 1000
      },
      stats: {
        activeSystems: 5,
        totalRevenue: 0, // Would be fetched from database in production
        pendingPayouts: 0
      }
    };

    res.json(dashboard);
  } catch (error) {
    console.error('Error fetching money dashboard:', error);
    res.status(500).json({ error: 'Failed to fetch dashboard data' });
  }
});

// Authentication endpoints
app.post('/auth/login', async (req, res) => {
  const { username, password } = req.body;

  // TODO: Implement proper authentication
  // This is a placeholder
  if (username && password) {
    const token = jwt.sign(
      { username, role: 'user' },
      process.env.JWT_SECRET || 'default-secret-change-me',
      { expiresIn: '24h' }
    );

    return res.json({
      token,
      expiresIn: '24h',
      user: { username, role: 'user' }
    });
  }

  res.status(401).json({ error: 'Invalid credentials' });
});

// Error handling
app.use((err, req, res, next) => {
  console.error('Error:', err);
  res.status(500).json({
    error: 'Internal server error',
    message: process.env.NODE_ENV === 'development' ? err.message : undefined
  });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: 'Endpoint not found' });
});

// Start server
const server = app.listen(PORT, '0.0.0.0', () => {
  console.log(`API Gateway listening on port ${PORT}`);
  console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM received, closing server...');
  server.close(() => {
    console.log('Server closed');
    redisClient.quit();
    process.exit(0);
  });
});

// Export for testing
module.exports = app;
