/**
 * API Gateway Unit Tests
 */

// Mock dependencies before requiring the app
jest.mock('redis', () => ({
  createClient: jest.fn(() => ({
    on: jest.fn(),
    connect: jest.fn(),
    quit: jest.fn(),
  })),
}));

jest.mock('http-proxy-middleware', () => ({
  createProxyMiddleware: jest.fn(() => (req, res, next) => next()),
}));

const request = require('supertest');

// Set env vars before loading app
process.env.JWT_SECRET = 'test-secret-key-for-unit-tests-min32chars';
process.env.NODE_ENV = 'test';

const app = require('../src/api-gateway/gateway');

describe('API Gateway', () => {
  describe('GET /health', () => {
    it('should return healthy status', async () => {
      const res = await request(app).get('/health');
      expect(res.statusCode).toBe(200);
      expect(res.body.status).toBe('healthy');
      expect(res.body.service).toBe('api-gateway');
      expect(res.body.version).toBe('1.0.0');
      expect(res.body.timestamp).toBeDefined();
    });
  });

  describe('GET /metrics', () => {
    it('should return prometheus metrics', async () => {
      const res = await request(app).get('/metrics');
      expect(res.statusCode).toBe(200);
      expect(res.text).toContain('api_gateway_up 1');
      expect(res.text).toContain('api_gateway_uptime_seconds');
    });
  });

  describe('POST /auth/login', () => {
    it('should return a JWT token with valid credentials', async () => {
      const res = await request(app)
        .post('/auth/login')
        .send({ username: 'admin', password: 'password' });
      expect(res.statusCode).toBe(200);
      expect(res.body.token).toBeDefined();
      expect(res.body.expiresIn).toBe('24h');
      expect(res.body.user.username).toBe('admin');
    });

    it('should return 401 without credentials', async () => {
      const res = await request(app)
        .post('/auth/login')
        .send({});
      expect(res.statusCode).toBe(401);
      expect(res.body.error).toBe('Invalid credentials');
    });
  });

  describe('Protected endpoints', () => {
    it('should return 401 without token', async () => {
      const res = await request(app).get('/api/revenue');
      expect(res.statusCode).toBe(401);
    });
  });

  describe('GET /nonexistent', () => {
    it('should return 404 for unknown routes', async () => {
      const res = await request(app).get('/nonexistent');
      expect(res.statusCode).toBe(404);
      expect(res.body.error).toBe('Endpoint not found');
    });
  });

  describe('OPTIONS (CORS)', () => {
    it('should return 200 for preflight requests', async () => {
      const res = await request(app)
        .options('/api/revenue')
        .set('Origin', 'http://localhost:3000');
      expect(res.statusCode).toBe(200);
      expect(res.headers['access-control-allow-origin']).toBe('*');
    });
  });
});
