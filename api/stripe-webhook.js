const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);
const { Client } = require('@notionhq/client');
const notion = new Client({ auth: process.env.NOTION_API_KEY });
export const config = { api: { bodyParser: false } };
async function getRawBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(Buffer.from(chunk));
  return Buffer.concat(chunks);
}
export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).end();
  const buf = await getRawBody(req);
  const sig = req.headers['stripe-signature'];
  let event;
  try {
    event = stripe.webhooks.constructEvent(buf, sig, process.env.STRIPE_WEBHOOK_SECRET);
  } catch (e) {
    return res.status(400).send('Webhook Error: ' + e.message);
  }
  if (event.type === 'checkout.session.completed') {
    const s = event.data.object;
    await notion.pages.create({
      parent: { database_id: process.env.NOTION_DEALS_DB_ID },
      properties: {
        Name: { title: [{ text: { content: s.customer_email } }] },
        Email: { email: s.customer_email },
        Status: { select: { name: 'Paid' } },
        Amount: { number: s.amount_total / 100 },
        Product: { rich_text: [{ text: { content: s.metadata && s.metadata.product ? s.metadata.product : 'Garcar' } }] },
        StripeSession: { rich_text: [{ text: { content: s.id } }] },
        CreatedAt: { date: { start: new Date().toISOString() } }
      }
    });
    await fetch('https://api.github.com/repos/' + process.env.GITHUB_REPO + '/dispatches', {
      method: 'POST',
      headers: { Authorization: 'token ' + process.env.GITHUB_PAT, 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_type: 'provision-customer', client_payload: { email: s.customer_email, product: s.metadata ? s.metadata.product : '' } })
    });
  }
  res.json({ received: true });
}
