const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);
const { Client } = require('@notionhq/client');
const notion = new Client({ auth: process.env.NOTION_API_KEY });
export const config = { api: { bodyParser: false } };

const processedEventIds = new Set();

async function getRawBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(Buffer.from(chunk));
  return Buffer.concat(chunks);
}

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).end();
  if (!process.env.STRIPE_WEBHOOK_SECRET || !process.env.STRIPE_SECRET_KEY) {
    return res.status(503).send('Webhook not configured');
  }
  const buf = await getRawBody(req);
  const sig = req.headers['stripe-signature'];
  let event;
  try {
    event = stripe.webhooks.constructEvent(buf, sig, process.env.STRIPE_WEBHOOK_SECRET);
  } catch (e) {
    return res.status(400).send('Webhook Error');
  }
  if (processedEventIds.has(event.id)) {
    return res.json({ received: true, duplicate: true });
  }
  if (event.type === 'checkout.session.completed') {
    const s = event.data.object;
    if (process.env.NOTION_API_KEY && process.env.NOTION_DEALS_DB_ID) {
      await notion.pages.create({
        parent: { database_id: process.env.NOTION_DEALS_DB_ID },
        properties: {
          Name: { title: [{ text: { content: s.customer_email || 'unknown' } }] },
          Email: { email: s.customer_email },
          Status: { select: { name: 'Paid' } },
          Amount: { number: (s.amount_total || 0) / 100 },
          Product: { rich_text: [{ text: { content: s.metadata && s.metadata.product ? s.metadata.product : 'Garcar' } }] },
          StripeSession: { rich_text: [{ text: { content: s.id } }] },
          StripeEvent: { rich_text: [{ text: { content: event.id } }] },
          CreatedAt: { date: { start: new Date().toISOString() } }
        }
      });
    }
    if (process.env.GITHUB_REPO && process.env.GITHUB_PAT) {
      await fetch('https://api.github.com/repos/' + process.env.GITHUB_REPO + '/dispatches', {
        method: 'POST',
        headers: { Authorization: 'token ' + process.env.GITHUB_PAT, 'Content-Type': 'application/json' },
        body: JSON.stringify({ event_type: 'provision-customer', client_payload: { email: s.customer_email, product: s.metadata ? s.metadata.product : '', stripe_event_id: event.id } })
      });
    }
  }
  processedEventIds.add(event.id);
  res.json({ received: true, event_id: event.id });
}
