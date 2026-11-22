#!/usr/bin/env bash
# Те же проверки, что в triage.py, но стандартными утилитами Linux —
# так ищут на сервере, где нет Python и нужных библиотек.
# Запуск: bash playbook.sh   (из папки проекта, после python gen_logs.py)
set -euo pipefail
cd "$(dirname "$0")/logs"

echo "== 1. Сколько 5xx по эндпоинтам за день"
awk '$9 >= 500 {print $6, $7, $9}' access.log | tr -d '"' | sort | uniq -c | sort -rn

echo "== 2. 5xx по минутам на POST /api/checkout (видно окно инцидента)"
grep '"POST /api/checkout' access.log | awk '$9 >= 500 {print substr($4, 14, 5)}' | sort | uniq -c

echo "== 3. Ошибки приложения по тексту (что именно падает)"
jq -r 'select(.level == "ERROR") | .msg' app.log | sort | uniq -c | sort -rn

echo "== 4. Топ IP по неудачным входам"
grep 'login failure' auth.log | grep -o 'ip=[^ ]*' | sort | uniq -c | sort -rn | awk 'NR <= 3'

echo "== 5. Самые медленные ответы: секунды, эндпоинт, request_id"
awk '{for (i = 1; i <= NF; i++) { if ($i ~ /^rt=/) rt = substr($i, 4); if ($i ~ /^rid=/) rid = substr($i, 5) }
      print rt, $7, rid}' access.log | sort -rn | awk 'NR <= 5'

echo "== 6. Тикет клиента u0215: всё, что не INFO"
jq -c 'select(.user == "u0215" and .level != "INFO")' app.log
