# GAR-425: CRM Setup Guide

## Recommended Stack: HubSpot Free + Zapier

### Step 1: HubSpot Setup
1. Go to https://app.hubspot.com and create a free account
2. Create a Pipeline: Settings > CRM > Pipelines > New Pipeline
   - Stages: New Lead, Contacted, Qualified, Proposal Sent, Won, Lost
3. Create custom properties:
   - `lead_source` (dropdown: Landing Page, LinkedIn, Cold Outreach, Referral)
   - `automation_score` (number 0-100)
   - `monthly_manual_hours` (number)

### Step 2: Zapier Connections

#### Zap 1: Website Form -> HubSpot
- Trigger: Typeform/Google Forms new submission
- Action 1: HubSpot > Create Contact
- Action 2: HubSpot > Add to nurture sequence
- Action 3: Slack > Post notification

#### Zap 2: LinkedIn Lead Gen Form -> HubSpot
- Trigger: LinkedIn Lead Gen new lead
- Action: HubSpot > Create Contact with source=LinkedIn

#### Zap 3: Calendly Booked -> HubSpot
- Trigger: Calendly > New Event Created
- Action: HubSpot > Update Contact stage to "Qualified"

#### Zap 4: Stripe Payment -> HubSpot
- Trigger: Stripe > Payment Succeeded
- Action: HubSpot > Move contact to "Won"
- Action 2: Trigger onboarding webhook (GAR-429)

### Step 3: Lead Source Tags
| Source | HubSpot Tag | Nurture Sequence |
|--------|------------|------------------|
| Landing page | web_organic | standard_7day |
| LinkedIn post | linkedin_organic | linkedin_variant |
| Cold outreach | cold_email | objection_focused |
| Referral | referral | fast_track_3day |

### Step 4: Weekly P&L Report (Zapier Scheduled)
- Trigger: Zapier > Schedule > Every Monday 8 AM CT
- Action: Stripe > Get charges (past week)
- Action: Google Sheets > Append row
- Action: Email > Send weekly summary to gwc2780@gmail.com
