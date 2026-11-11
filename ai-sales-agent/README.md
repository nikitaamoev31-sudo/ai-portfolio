# AI Sales Agent — B2B Lead Generation & Cold Outreach

Autonomous AI agent that replaces three roles in cold outreach: **analyst, sales rep and assistant**.

## What it does
1. Takes a list of companies (`leads.csv`) and scrapes each company's website.
2. Uses an LLM (Gemini / OpenAI) to analyze the business: niche, services, audience.
3. Finds concrete places where an AI agent would help *this* company.
4. Writes a short personalized cold email (strict copywriting rules in `system_prompt.txt`).
5. Pushes ready emails into an outreach campaign via the **Instantly API** (`push_to_instantly.py`).

## Stack
Python · LLM API (Gemini, OpenAI) · crawl4ai / BeautifulSoup · pandas · REST API (Instantly) · Docker

## Run
```bash
cp .env.example .env          # add your API keys
cp leads.example.csv leads.csv
docker build -t ai-sales-agent .
docker run --env-file .env -v $(pwd)/leads.csv:/app/leads.csv ai-sales-agent
```

## Files
- `ai_lead_generation.py` — core pipeline: scrape → analyze → write email
- `ai_agency_conveyor.py` — batch "conveyor" mode with booking link in CTA
- `push_to_instantly.py` — upload generated leads/emails to Instantly campaign
- `system_prompt.txt` — copywriting prompt for the LLM
- `Dockerfile` — containerized run
