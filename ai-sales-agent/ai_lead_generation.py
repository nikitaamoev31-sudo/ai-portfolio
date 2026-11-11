import os
from dotenv import load_dotenv
load_dotenv()

import os
import pandas as pd
import requests
from bs4 import BeautifulSoup

test_leads = [
    {
        "company_name": "Digital Alpha Agency", 
        "website": "https://example-digital-agency.com", 
        "ceo_name": "John Doe", 
        "email": "john@digitalalpha.com"
    },
    {
        "company_name": "Apex Marketing Hub", 
        "website": "https://example-apex-marketing.net", 
        "ceo_name": "Sarah Connor", 
        "email": "s.connor@apex.net"
    }
]

def get_site_content(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for script in soup(["script", "style"]):
                script.extract()
            text = soup.get_text(separator=' ')
            return " ".join(text.split())[:8000]
        return "Website content unavailable."
    except Exception:
        return "Website unreachable."

def query_local_llm(prompt):
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama3.2", "prompt": prompt, "stream": False},
            timeout=60
        )
        if response.status_code == 200:
            return response.json().get("response", "")
        return f"Ollama Error: Status {response.status_code}"
    except Exception as e:
        return f"Connection to Ollama failed: {e}"

final_results = []

for lead in test_leads:
    print(f"\n==================================================")
    print(f"🤖 AI SALES AGENT PROCESSING: {lead['company_name']}")
    print(f"==================================================")
    
    print("[Parser] Scraping potential client's website...")
    site_text = get_site_content(lead['website'])
    
    print("[Local AI] Analyzing business model and conversion bottlenecks...")
    prompt_analyze = f"""You are a Senior B2B Business Analyst at an AI Automation Agency.
    Analyze this text scraped from the website of {lead['company_name']} ({lead['website']}):
    ---
    {site_text}
    ---
    Identify what they do, who their target audience is, and find at least 2 manual lead generation or sales processes that can be automated using our AI agents to save them time and increase their revenue."""
    
    analysis_text = query_local_llm(prompt_analyze)
    
    print("[Local AI] Generating a killer cold outreach email in English...")
    prompt_email = f"""You are the world's best Cold B2B Outreach Specialist selling AI B2B solutions.
    Based on this business analysis:
    {analysis_text}
    
    Write a highly-personalized cold outreach email to the CEO.
    Prospect Info: Name: {lead['ceo_name']}, Company: {lead['company_name']}, Email: {lead['email']}.
    
    CRITICAL EMAIL RULES:
    1. Write the entire response (Subject and Body) ONLY in English.
    2. Create a short, catchy, and intriguing Subject Line (3-5 words), e.g., "AI Lead Generation for {lead['company_name']}".
    3. The first sentence must prove we researched their business specifically (mention their niche or services).
    4. Include this exact powerful hook: "This very email was automatically generated and sent by my autonomous AI agent. It found your company, analyzed your website, and crafted this message tailored to your specific business bottlenecks." (This shows the product in action!).
    5. Offer to build them the exact same autonomous AI lead generation pipeline that will find clients and generate personalized pitches for them 24/7.
    6. Keep it short, sharp, professional, and completely free of fluff.
    7. Call to Action (CTA): Propose a brief 10-minute Zoom call to show a live demo of our AI agent working on their competitors."""

    email_text = query_local_llm(prompt_email)
    
    lead['generated_email'] = email_text
    final_results.append(lead)
    print(f"✅ English cold pitch for {lead['company_name']} is ready!")

print("\n[Export] Saving results to B2B database...")
df = pd.DataFrame(final_results)
df.to_csv("ai_outreach_results.csv", index=False, encoding="utf-8")

print("\n==================================================")
print("🎉 COLD OUTREACH CONVEYOR COMPLETED SUCCESSFULLY!")
print("The file 'ai_outreach_results.csv' has been generated in pure English.")
print("==================================================")
