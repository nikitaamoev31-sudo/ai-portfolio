import csv
import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("INSTANTLY_API_KEY")
CAMPAIGN_ID = os.getenv("INSTANTLY_CAMPAIGN_ID")
CSV_PATH = os.path.expanduser("~/Desktop/ai_agency/massive_b2b_500.csv")

if not API_KEY or not CAMPAIGN_ID:
    print("❌ Ошибка: проверьте INSTANTLY_API_KEY и INSTANTLY_CAMPAIGN_ID в .env")
    exit(1)

# Точный официальный URL поддомена API
url = "https://api.instantly.ai/api/v2/leads/add"
headers = {
    "Authorization": "Bearer " + API_KEY.strip(),
    "Content-Type": "application/json"
}

leads_to_push = []

with open(CSV_PATH, mode="r", encoding="utf-8") as f:
    reader = list(csv.DictReader(f))
    for row in reader:
        email = row.get("email") or row.get("Email") or row.get("contact_email") or ""
        company = row.get("company_name") or row.get("Company") or row.get("company") or ""
        first_name = row.get("first_name") or row.get("Name") or ""
        pitch = row.get("AI Generated Cold Email") or row.get("generated_email") or row.get("pitch") or ""

        if email and "@" in email:
            leads_to_push.append({
                "email": email.strip(),
                "first_name": first_name.strip(),
                "company_name": company.strip(),
                "custom_variables": {
                    "ai_pitch": pitch.strip()
                }
            })

# Ограничиваем ровно 210 контактами под лимит тарифа
batch_limit = 210
upload_batch = leads_to_push[:batch_limit]
print(f"📊 Отправляем {len(upload_batch)} лидов из {len(leads_to_push)} найденных...")

payload = {
    "campaign_id": CAMPAIGN_ID.strip(),
    "leads": upload_batch,
    "skip_if_in_workspace": False
}

resp = requests.post(url, headers=headers, json=payload)

if resp.status_code == 200 or resp.status_code == 201:
    print("🎉 УСПЕХ! 210 лидов успешно загружены в кампанию!")
    print(f"Ответ сервера: {resp.json()}")
else:
    print(f"❌ Ошибка API ({resp.status_code}):")
    print(resp.text[:400])
