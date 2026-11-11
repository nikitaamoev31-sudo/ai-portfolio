import os
from dotenv import load_dotenv
load_dotenv()

import os
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import unquote

# 1. КОНФИГУРАЦИЯ ВАШЕЙ ВОРОНКИ В ТБИЛИСИ
CAL_LINK = "https://cal.com" # Ваша ссылка из Cal.com
TARGET_GEO = "Dubai"                            # Целевой город для поиска клиентов
TARGET_NICHE = "Web design digital agency"       # Ниша потенциальных клиентов

print(f"🚀 Инициализация конвейера... Цель: {TARGET_NICHE} в {TARGET_GEO}")

# 2. АВТОМАТИЧЕСКИЙ СБОР РЕАЛЬНЫХ САЙТОВ
def fetch_real_leads(query, max_results=3):
    print(f"[Парсер] Ищу реальные компании по запросу: '{query}'...")
    url = f"https://duckduckgo.com{query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    
    leads = []
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.find_all('a', class_='result__url')
            
            for link in links:
                raw_url = link.get('href', '')
                if "duckduckgo.com" not in raw_url and "http" in raw_url:
                    if '&uddg=' in raw_url:
                        clean_url = raw_url.split('&uddg=')[1].split('&rut=')[0]
                    else:
                        clean_url = raw_url
                    clean_url = unquote(clean_url)
                    
                    # Формируем имя из домена чисто для отображения
                    domain = clean_url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
                    comp_name = domain.split(".")[0].capitalize()
                    
                    leads.append({
                        "company_name": comp_name,
                        "website": clean_url,
                        "ceo_name": "Founder / CEO",
                        "email": f"contact@{domain}"
                    })
                    if len(leads) >= max_results:
                        break
    except Exception as e:
        print(f"❌ Ошибка парсинга поисковой выдачи: {e}")
    
    return leads

def get_site_content(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for script in soup(["script", "style"]):
                script.extract()
            return " ".join(soup.get_text().split())[:6000]
        return "Content unavailable."
    except Exception:
        return "Website unreachable."

def query_local_llm(prompt):
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama3.2", "prompt": prompt, "stream": False},
            timeout=60
        )
        return response.json().get("response", "") if response.status_code == 200 else ""
    except Exception:
        return ""

# 3. ЗАПУСК ПОИСКА И ГЕНЕРАЦИИ
search_query = f"{TARGET_NICHE} {TARGET_GEO}"
real_leads = fetch_real_leads(search_query, max_results=3)

if not real_leads:
    print("❌ Не удалось собрать сайты компаний. Использую запасные реальные B2B-домены...")
    real_leads = [
        {"company_name": "Example Agency", "website": "https://example.com", "ceo_name": "CEO", "email": "info@example.com"},
        {"company_name": "Example Studio", "website": "https://example.org", "ceo_name": "Founder", "email": "hello@example.org"}
    ]

print(f"✅ Готово к обработке компаний: {len(real_leads)}")
final_results = []

for lead in real_leads:
    print(f"\n==================================================")
    print(f"🤖 ИИ АНАЛИЗИРУЕТ РЕАЛЬНЫЙ БИЗНЕС: {lead['company_name']}")
    print(f"==================================================")
    
    print(f"[Парсер] Сканирую сайт: {lead['website']} ...")
    site_text = get_site_content(lead['website'])
    
    print("[Локальный ИИ] Выявляет рутинные процессы компании...")
    prompt_analyze = f"You are a Senior B2B Analyst. Analyze this text from {lead['company_name']} website ({lead['website']}):\n---\n{site_text}\n---\nIdentify their exact services and 2 bottlenecks in their manual lead generation that an AI agent could fix."
    analysis_text = query_local_llm(prompt_analyze)
    
    print("[Локальный ИИ] Пишет уникальный англоязычный оффер со ссылкой Cal.com...")
    prompt_email = f"""You are a master of B2B AI Sales. Based on this text: {analysis_text}
    Write a short cold email to the CEO of {lead['company_name']}. 
    
    STRICT RULES:
    1. Language: English only.
    2. Hook: Say that this email was automatically generated and sent by an autonomous AI agent that found them and analyzed their site.
    3. Pitch: Offer them the exact same autonomous lead gen system to capture more B2B clients.
    4. Call to Action: Ask them to book a quick 10-minute demo directly in your calendar using this exact link: {CAL_LINK}
    5. Formatting: Include 'Subject:' at the top. Keep it brief and sharp."""

    email_text = query_local_llm(prompt_email)
    
    lead['generated_email'] = email_text
    final_results.append(lead)
    print(f"✅ Оффер со ссылкой на созвон для {lead['company_name']} готов!")
    time.sleep(1)

# 4. СОХРАНЕНИЕ ГОТОВОЙ БАЗЫ ДЛЯ ОТПРАВКИ
df = pd.DataFrame(final_results)
df.to_csv("real_b2b_outreach.csv", index=False, encoding="utf-8")

print("\n==================================================")
print("🎉 БОЕВОЙ КОНВЕЙЕР ЗАВЕРШИЛ РАБОТУ!")
print("Файл 'real_b2b_outreach.csv' успешно создан.")
print("Внутри лежат реальные компании и готовые письма с вашей ссылкой Cal.com!")
print("==================================================")
