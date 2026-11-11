#!/usr/bin/env python3
"""
ДЖАРВИС — голосовой ИИ-ассистент для macOS.
Мозг: Claude (Anthropic API) с инструментами для управления Mac.
Запуск:  python3 jarvis.py          (голос + лицо)
         python3 jarvis.py --text   (текстовый режим в терминале, для отладки)
"""
import os
import re
import sys
import json
import time
import math
import base64
import random
import asyncio
import subprocess
import threading
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MEMORY_PATH = BASE_DIR / "jarvis_memory.json"
TTS_PATH = "/tmp/jarvis_voice.mp3"


# ---------- .env ----------
def load_env():
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()

import anthropic  # noqa: E402

MODEL = os.environ.get("JARVIS_MODEL", "claude-sonnet-5-5")         # для задач и управления Mac
FAST_MODEL = os.environ.get("JARVIS_FAST_MODEL", "claude-haiku-5-5")  # для разговора — в разы быстрее
ACTION_WORDS = re.compile(
    r"(открой|закрой|запусти|найди|поищи|сделай|включи|выключи|постав|убав|прибав|громк|посмотри|экран|"
    r"напиши|отправь|выложи|опубликуй|создай|удали|скачай|покажи|файл|папк|сайт|браузер|вкладк|"
    r"сохрани|скопируй|перемести|переимен|нажми|кликни|прокрути|видео|фото|музык|погод|курс|новост|сколько стоит)",
    re.I)
VOICE = os.environ.get("JARVIS_VOICE", "ru-RU-DmitryNeural")  # edge-tts голос
WAKE_WORDS = ["джарвис", "джарвиз", "жарвис", "джавис", "джарви", "jarvis"]
CONVERSATION_WINDOW = 25  # сек: после ответа можно говорить без слова «Джарвис»
MAX_HISTORY = 12          # сколько последних реплик помнить

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


# ---------- ПАМЯТЬ ----------
def load_memory():
    data = {}
    if MEMORY_PATH.exists():
        try:
            data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data.setdefault("user_preferences", {"name": "Никита", "role": "сэр"})
    data["user_preferences"].pop("lang", None)
    data.setdefault("facts", {})
    data.setdefault("custom_commands", {})
    data["history"] = data.get("history", [])
    data.pop("chat_history", None)  # старый формат с мусором — выбрасываем
    return data


def save_memory():
    with MEM_LOCK:
        MEMORY_PATH.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")


MEM_LOCK = threading.Lock()
memory = load_memory()


# ---------- ЛИЦО / ЭМОЦИИ ----------
class Face:
    """Прослойка: в текстовом режиме окна нет, в GUI — сигнал в Qt-поток."""
    def __init__(self):
        self.signal = None

    def set(self, emotion):
        if self.signal is not None:
            self.signal.emit(emotion)


face = Face()


# ---------- ГОЛОС: ВЫВОД ----------
SPEAKING = threading.Event()
TEXT_MODE = "--text" in sys.argv


EDGE_VOICES = [VOICE, "ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural", "ru-RU-DariyaNeural"]
_edge_ok_voice = None
_mac_voice = None


def _tts_eleven(text, out_path=TTS_PATH, play=True):
    """ElevenLabs — самый живой голос. Нужен ELEVENLABS_API_KEY в .env."""
    import urllib.request
    key = os.environ["ELEVENLABS_API_KEY"]
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")  # Adam
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        data=json.dumps({"text": text, "model_id": os.environ.get("ELEVENLABS_MODEL", "eleven_flash_v2_5"),
                         "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.3}}).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
    )
    with urllib.request.urlopen(req, timeout=20) as r, open(out_path, "wb") as f:
        f.write(r.read())
    if play:
        subprocess.run(["afplay", out_path], check=False)


GEMINI_TTS_MODELS = ["gemini-2.5-flash-preview-tts", "gemini-2.5-flash-tts", "gemini-2.5-pro-preview-tts"]
_gemini_model = None


def _tts_gemini(text, out_path="/tmp/jarvis_voice.wav", play=True):
    """Google Gemini TTS — живой человеческий голос. Ключ GEMINI_API_KEY из .env."""
    import urllib.request, wave
    global _gemini_model
    key = os.environ["GEMINI_API_KEY"]
    voice = os.environ.get("GEMINI_VOICE", "Charon")  # мужской, спокойный
    style = ("Скажи спокойным, уверенным, тёплым голосом британского дворецкого, "
             "естественно и с живой интонацией: ")
    body = json.dumps({
        "contents": [{"parts": [{"text": style + text}]}],
        "generationConfig": {"responseModalities": ["AUDIO"],
                             "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}},
    }).encode()
    last = None
    for model in ([_gemini_model] if _gemini_model else GEMINI_TTS_MODELS):
        try:
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                data=body, headers={"x-goog-api-key": key, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
            pcm = base64.b64decode(data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
            wav_path = out_path
            with wave.open(wav_path, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
            _gemini_model = model
            if play:
                subprocess.run(["afplay", wav_path], check=False)
            return
        except Exception as e:
            try:
                e = RuntimeError(f"{model}: {e} {e.read().decode()[:300]}")  # тело ошибки HTTP
            except Exception:
                pass
            last = e
    raise last


def _tts_edge(text):
    import edge_tts
    global _edge_ok_voice
    voices = [_edge_ok_voice] if _edge_ok_voice else list(dict.fromkeys(EDGE_VOICES))
    last = None
    for v in voices:
        try:
            async def run():
                await edge_tts.Communicate(text, v).save(TTS_PATH)
            asyncio.run(run())
            if os.path.getsize(TTS_PATH) > 0:
                _edge_ok_voice = v
                subprocess.run(["afplay", TTS_PATH], check=False)
                return
        except Exception as e:
            last = e
    raise last or RuntimeError("edge-tts: нет звука")


def _best_mac_voice():
    """Ищет лучший установленный русский голос macOS (Premium > Enhanced > обычный)."""
    global _mac_voice
    if _mac_voice is None:
        out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
        ru = [l.split("  ")[0].strip() for l in out.splitlines() if "ru_RU" in l]
        rank = lambda n: (("Premium" in n or "Премиум" in n) * 2 + ("Enhanced" in n or "Улучш" in n))
        ru.sort(key=rank, reverse=True)
        _mac_voice = ru[0] if ru else ""
    return _mac_voice


def _tts_say(text):
    v = _best_mac_voice()
    rate = os.environ.get("JARVIS_MAC_RATE", "170")
    subprocess.run((["say", "-v", v] if v else ["say"]) + ["-r", rate, text])


def _log_tts_error(e):
    import traceback
    with open(BASE_DIR / "tts_error.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} {e!r}\n{traceback.format_exc()}\n")


def _pick_engine():
    """Один голос на всю сессию: ElevenLabs > Gemini (если явно включён) > голос macOS."""
    forced = os.environ.get("JARVIS_TTS", "").lower()
    if forced in ("eleven", "gemini", "mac"):
        return forced
    return "eleven" if os.environ.get("ELEVENLABS_API_KEY") else "mac"


TTS_ENGINE = _pick_engine()


def _split_sentences(text):
    parts = re.split(r"(?<=[.!?…])\s+", text.strip())
    out, buf = [], ""
    for p in parts:  # склеиваем очень короткие куски, чтобы не было рваной речи
        buf = f"{buf} {p}".strip()
        if len(buf) > 40:
            out.append(buf); buf = ""
    if buf:
        out.append(buf)
    return out


def _speak_pipeline(text):
    """Озвучивает по предложениям: пока играет одно — следующее уже генерируется."""
    global TTS_ENGINE
    if TTS_ENGINE == "mac":
        _tts_say(text)
        return
    gen = _tts_eleven if TTS_ENGINE == "eleven" else _tts_gemini
    ext = "mp3" if TTS_ENGINE == "eleven" else "wav"
    sentences = _split_sentences(text)
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(gen, s_, f"/tmp/jarvis_{i}.{ext}", False) for i, s_ in enumerate(sentences)]
        for i, (s_, fut) in enumerate(zip(sentences, futures)):
            try:
                fut.result()
                subprocess.run(["afplay", f"/tmp/jarvis_{i}.{ext}"], check=False)
            except Exception as e:
                _log_tts_error(e)
                # облачный голос сломался — до конца сессии говорим одним голосом macOS
                print("⚠️  Облачный голос недоступен, переключаюсь на голос macOS до перезапуска.")
                TTS_ENGINE = "mac"
                _tts_say(" ".join(sentences[i:]))
                return


import queue
_speech_q = queue.Queue()


_ABBR = {"т.е.": "то есть", "т.к.": "так как", "и т.д.": "и так далее", "и т.п.": "и тому подобное",
         "др.": "другие", "руб.": "рублей", "млн": "миллионов", "млрд": "миллиардов", "тыс.": "тысяч",
         "°C": " градусов", "°": " градусов", "%": " процентов", "№": "номер ", "&": " и ", "+": " плюс ",
         "MacBook": "Макбук", "Mac": "Мак", "Instagram": "Инстаграм", "YouTube": "Ютуб", "Google": "Гугл",
         "Chrome": "Хром", "Safari": "Сафари", "Telegram": "Телеграм", "WhatsApp": "Ватсап", "Finder": "Файндер",
         "AI": "ИИ", "OK": "окей", "ok": "окей", "email": "имейл", "e-mail": "имейл"}


def _num_to_words(m):
    try:
        from num2words import num2words
        n = m.group(0).replace(",", ".")
        return " " + num2words(float(n) if "." in n else int(n), lang="ru") + " "
    except Exception:
        return m.group(0)


def _clean_for_speech(text):
    text = re.sub(r"\[Служебно:.*?\]", "", text, flags=re.S)
    text = re.sub(r"https?://\S+", "ссылка", text)
    for k, v in _ABBR.items():
        text = text.replace(k, v)
    text = re.sub(r"(?<=\d)[\s ](?=\d{3}\b)", "", text)            # 10 000 → 10000
    text = re.sub(r"\d+(?:[.,]\d+)?", _num_to_words, text)          # цифры → слова
    text = text.replace("—", ", ").replace("–", ", ").replace("…", ".").replace("«", "").replace("»", "")
    text = re.sub(r"[*`_#\[\]<>()\"/\\|~^=]", " ", text)
    text = re.sub(r"[\U0001F000-\U0001FFFF\u2600-\u27BF]", "", text)  # эмодзи
    return re.sub(r"\s+", " ", text).replace(" ,", ",").replace(" .", ".").strip()


def _speaker_loop():
    while True:
        text = _speech_q.get()
        try:
            face.set("speaking")
            _speak_pipeline(text)
        except Exception as e:
            _log_tts_error(e)
        finally:
            if _speech_q.empty():
                time.sleep(0.35)  # даём эху затихнуть
                face.set("normal")
            _speech_q.task_done()


def say_async(text):
    """Поставить фразу в очередь — говорит, пока ИИ дописывает остальное."""
    text = (text or "").strip()
    if not text:
        return
    print(f"🤖 Джарвис: {text}")
    clean = _clean_for_speech(text)
    if TEXT_MODE or not clean:
        return
    SPEAKING.set()
    _speech_q.put(clean)


def wait_speech():
    if not TEXT_MODE:
        _speech_q.join()
    SPEAKING.clear()


def speak(text):
    """Сказать и дождаться окончания (пока говорит — микрофон не слушает)."""
    say_async(text)
    wait_speech()


threading.Thread(target=_speaker_loop, daemon=True).start()


# ---------- ИНСТРУМЕНТЫ ДЛЯ CLAUDE ----------
DANGEROUS = re.compile(
    r"\b(rm|rmdir|sudo|shutdown|reboot|halt|mkfs|diskutil|dd|kill|killall|pkill|"
    r"chmod|chown|launchctl|defaults\s+delete|curl[^|]*\|\s*(ba)?sh|git\s+push|"
    r"git\s+reset)\b|>\s*/(?!dev/null)|osascript.*(delete|empty trash)",
    re.I,
)

TOOLS = [
    {
        "name": "run_shell",
        "description": "Выполнить bash-команду на MacBook пользователя (zsh/bash, macOS). "
                       "Возвращает stdout/stderr. Используй для файлов, открытия программ (open -a), "
                       "поиска, системной информации (громкость, батарея, сеть) и т.д.",
        "input_schema": {"type": "object",
                         "properties": {"command": {"type": "string"}},
                         "required": ["command"]},
    },
    {
        "name": "run_applescript",
        "description": "Выполнить AppleScript (osascript). Управление приложениями, окнами, "
                       "вкладками Safari/Chrome, Музыкой, уведомлениями, нажатиями клавиш через System Events.",
        "input_schema": {"type": "object",
                         "properties": {"script": {"type": "string"}},
                         "required": ["script"]},
    },
    {
        "name": "look_at_screen",
        "description": "Сделать скриншот экрана и посмотреть на него. Используй, когда нужно понять, что сейчас на экране.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "remember",
        "description": "Запомнить факт о пользователе навсегда (имя, предпочтения, проекты, важные данные).",
        "input_schema": {"type": "object",
                         "properties": {"key": {"type": "string"}, "value": {"type": "string"}},
                         "required": ["key", "value"]},
    },
    {
        "name": "wait",
        "description": "Подождать N секунд (загрузка, публикация) и получить скриншот. Вместо sleep + look_at_screen.",
        "input_schema": {"type": "object", "properties": {"seconds": {"type": "number"}}, "required": ["seconds"]},
    },
    {
        "name": "learn_lesson",
        "description": "Записать урок на будущее: что пошло не так и как делать правильно/быстрее. "
                       "Уроки видны тебе всегда. Пиши конкретно: «В Instagram кнопка Обложка — внизу экрана редактирования».",
        "input_schema": {"type": "object", "properties": {"lesson": {"type": "string"}}, "required": ["lesson"]},
    },
    {
        "name": "task_notes",
        "description": "Рабочие заметки по текущей большой задаче (сохраняются навсегда и видны тебе на каждом шаге): "
                       "план, нужные тексты (например, точное описание поста), что уже сделано, что осталось. "
                       "Передавай ПОЛНЫЙ новый текст заметок — он заменит старый.",
        "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    },
    {
        "name": "recall",
        "description": "Найти в журнале ВСЕХ прошлых разговоров с пользователем. Используй, когда он спрашивает о прошлом "
                       "(«что мы делали вчера», «о чём говорили», «помнишь …»). Пустой query — последние разговоры.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
    },
    {
        "name": "forget",
        "description": "Удалить факт из памяти по ключу.",
        "input_schema": {"type": "object",
                         "properties": {"key": {"type": "string"}},
                         "required": ["key"]},
    },
    {
        "name": "set_emotion",
        "description": "Показать эмоцию на лице: normal, happy, sad, thinking, love, surprised, angry.",
        "input_schema": {"type": "object",
                         "properties": {"emotion": {"type": "string",
                                                    "enum": ["normal", "happy", "sad", "thinking",
                                                             "love", "surprised", "angry"]}},
                         "required": ["emotion"]},
    },
    {
        "name": "mouse_click",
        "description": "Кликнуть мышью по точке на экране. Координаты x,y — в пикселях ПОСЛЕДНЕГО скриншота look_at_screen. "
                       "Перед кликом всегда сделай свежий look_at_screen, после — проверь результат новым скриншотом.",
        "input_schema": {"type": "object",
                         "properties": {"x": {"type": "integer"}, "y": {"type": "integer"},
                                        "look": {"type": "boolean", "description": "Вернуть скриншот после действия (по умолчанию да). false — для цепочки быстрых действий подряд."},
                                        "wait_after": {"type": "number", "description": "Сколько секунд подождать перед скриншотом (по умолчанию 0.8; для загрузки страниц 2–3)."},
                                        "button": {"type": "string", "enum": ["left", "right"]},
                                        "double": {"type": "boolean"},
                                        "final_action": {"type": "boolean", "description":
                                            "true, если этот клик публикует, отправляет, оплачивает или удаляет "
                                            "(кнопки «Поделиться», «Опубликовать», «Отправить», «Оплатить», «Удалить»). "
                                            "Тогда система сначала спросит пользователя голосом."},
                                        "what": {"type": "string", "description": "Что именно произойдёт, коротко"}},
                         "required": ["x", "y"]},
    },
    {
        "name": "ask_user",
        "description": "Задать пользователю вопрос голосом посреди задачи и получить его ответ (не прерывая задачу). "
                       "Используй, когда не хватает данных или нужно подтверждение.",
        "input_schema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
    },
    {
        "name": "type_text",
        "description": "Напечатать текст (любой язык) в поле, где сейчас курсор. Сначала кликни в поле.",
        "input_schema": {"type": "object", "properties": {"text": {"type": "string"}, "look": {"type": "boolean", "description": "Вернуть скриншот после действия (по умолчанию да). false — для цепочки быстрых действий подряд."}, "wait_after": {"type": "number", "description": "Сколько секунд подождать перед скриншотом (по умолчанию 0.8; для загрузки страниц 2–3)."}, }, "required": ["text"]},
    },
    {
        "name": "press_keys",
        "description": "Нажать клавишу или сочетание: 'enter', 'esc', 'tab', 'cmd+l', 'cmd+t', 'cmd+w', 'cmd+shift+4', 'down' и т.п.",
        "input_schema": {"type": "object", "properties": {"keys": {"type": "string"}, "look": {"type": "boolean", "description": "Вернуть скриншот после действия (по умолчанию да). false — для цепочки быстрых действий подряд."}, "wait_after": {"type": "number", "description": "Сколько секунд подождать перед скриншотом (по умолчанию 0.8; для загрузки страниц 2–3)."}, }, "required": ["keys"]},
    },
    {
        "name": "scroll",
        "description": "Прокрутить колесом мыши в точке x,y последнего скриншота. amount>0 — вниз, <0 — вверх (3–10).",
        "input_schema": {"type": "object",
                         "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "amount": {"type": "integer"}},
                         "required": ["amount"]},
    },
]

# Для поиска в интернете — серверный инструмент Anthropic
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}


def confirm(action_text):
    """Голосовое/текстовое подтверждение опасного действия."""
    face.set("surprised")
    speak(f"Сэр, подтвердите: {action_text}. Да или нет?")
    answer = get_answer(timeout=10)
    ok = bool(answer) and any(w in answer.lower() for w in ("да", "подтвержда", "давай", "конечно", "yes"))
    if not ok:
        speak("Отменено, сэр.")
    return ok


def _run(cmd_list, timeout=60):
    try:
        r = subprocess.run(cmd_list, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout + ("\nSTDERR: " + r.stderr if r.stderr.strip() else "")).strip()
        return f"exit={r.returncode}\n{out[:4000] or '(пусто)'}"
    except subprocess.TimeoutExpired:
        return "Ошибка: команда превысила лимит времени."
    except Exception as e:
        return f"Ошибка: {e}"


SCREEN_SCALE = None  # логические точки экрана на 1 пиксель скриншота


def _remember_screen_scale(path):
    global SCREEN_SCALE
    try:
        import pyautogui
        out = subprocess.run(["sips", "-g", "pixelWidth", path], capture_output=True, text=True).stdout
        img_w = int(re.search(r"pixelWidth:\s*(\d+)", out).group(1))
        SCREEN_SCALE = pyautogui.size().width / img_w
    except Exception as e:
        print(f"⚠️  масштаб экрана: {e}")


def _pt(x, y):
    if SCREEN_SCALE is None:
        raise RuntimeError("Сначала сделай look_at_screen — нужны координаты свежего скриншота.")
    return int(x * SCREEN_SCALE), int(y * SCREEN_SCALE)


def _input_tool(name, args):
    import pyautogui
    pyautogui.FAILSAFE = True  # увести мышь в угол экрана = аварийная остановка
    pyautogui.PAUSE = 0.15
    if name == "mouse_click":
        if args.get("final_action") and not confirm(args.get("what") or "необратимое действие"):
            return "Пользователь НЕ подтвердил. Ничего не нажато. Спроси, что исправить."
        x, y = _pt(args["x"], args["y"])
        pyautogui.click(x, y, clicks=2 if args.get("double") else 1, button=args.get("button", "left"))
        return f"Клик в ({x},{y})."
    if name == "type_text":
        old = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout
        subprocess.run(["pbcopy"], input=args["text"], text=True)
        pyautogui.hotkey("command", "v")
        time.sleep(0.3)
        subprocess.run(["pbcopy"], input=old, text=True)  # возвращаем буфер обмена
        return "Текст вставлен."
    if name == "press_keys":
        keymap = {"cmd": "command", "opt": "option", "alt": "option", "ctrl": "ctrl", "esc": "escape",
                  "enter": "return"}
        keys = [keymap.get(k.strip().lower(), k.strip().lower()) for k in args["keys"].split("+")]
        pyautogui.hotkey(*keys)
        return f"Нажато: {args['keys']}"
    if name == "scroll":
        if "x" in args and "y" in args:
            pyautogui.moveTo(*_pt(args["x"], args["y"]))
        pyautogui.scroll(-int(args["amount"]))
        return "Прокручено."


def screenshot_blocks(caption=None):
    path = "/tmp/jarvis_screen.jpg"
    subprocess.run(["screencapture", "-x", "-C", "-t", "jpg", path], check=False)
    try:
        subprocess.run(["sips", "-Z", "1280", "-s", "formatOptions", "60", path], capture_output=True)
        _remember_screen_scale(path)
        data = base64.standard_b64encode(Path(path).read_bytes()).decode()
        blocks = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}]
        if caption:
            blocks.insert(0, {"type": "text", "text": caption})
        return blocks
    except Exception as e:
        return f"Не удалось сделать скриншот (проверьте разрешение «Запись экрана»): {e}"


def execute_tool(name, args):
    if name == "ask_user":
        face.set("surprised")
        speak(args["question"])
        for _ in range(2):
            ans = get_answer(timeout=10)
            if ans:
                print(f"🗣  Вы: {ans}")
                return f"Ответ пользователя: {ans}"
        return "Пользователь не ответил."
    if name in ("mouse_click", "type_text", "press_keys", "scroll"):
        try:
            res = _input_tool(name, args)
            if args.get("look", True) and not str(res).startswith("Пользователь НЕ"):
                time.sleep(float(args.get("wait_after", 0.8)))
                return screenshot_blocks(res + " Экран после действия:")
            return res
        except Exception as e:
            return f"Ошибка: {e}. Если это про разрешения — у Терминала должен быть «Универсальный доступ»."
    if name == "run_shell":
        cmd = args["command"]
        print(f"   ⚙️  shell: {cmd}")
        if DANGEROUS.search(cmd) and not confirm(f"команда {cmd[:80]}"):
            return "Пользователь отменил выполнение."
        return _run(["/bin/zsh", "-lc", cmd])
    if name == "run_applescript":
        script = args["script"]
        print(f"   🍎 applescript: {script[:120]}")
        if DANGEROUS.search(script) and not confirm("скрипт с удалением или закрытием"):
            return "Пользователь отменил выполнение."
        return _run(["osascript", "-e", script])
    if name == "look_at_screen":
        return screenshot_blocks()
    if name == "wait":
        time.sleep(max(0.5, min(float(args.get("seconds", 2)), 30)))
        return screenshot_blocks("Подождал. Текущий экран:")
    if name == "remember":
        memory["facts"][args["key"]] = args["value"]
        save_memory()
        face.set("love")
        return "Запомнено."
    if name == "learn_lesson":
        add_lessons([args["lesson"]])
        return "Урок записан."
    if name == "task_notes":
        memory["task_notes"] = args["text"].strip()
        save_memory()
        return "Заметки сохранены."
    if name == "recall":
        return recall(args.get("query", ""))
    if name == "forget":
        memory["facts"].pop(args["key"], None)
        save_memory()
        return "Удалено."
    if name == "set_emotion":
        face.set(args["emotion"])
        return "ok"
    return f"Неизвестный инструмент {name}"


LOG_PATH = BASE_DIR / "jarvis_log.jsonl"


def log_exchange(user, bot, actions):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({"time": datetime.now().strftime("%Y-%m-%d %H:%M"), "user": user,
                            "bot": bot, "actions": actions}, ensure_ascii=False) + "\n")


def read_log():
    if not LOG_PATH.exists():
        return []
    out = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def recall(query):
    entries = read_log()
    words = [w for w in re.findall(r"\w+", (query or "").lower()) if len(w) > 2]
    if words:
        scored = []
        for e in entries:
            text = (e["user"] + " " + e["bot"]).lower()
            text += " " + " ".join(e.get("actions", [])).lower()
            score = sum(1 for w in words if w[:5] in text)  # грубый поиск по корням
            if score:
                scored.append((score, e))
        scored.sort(key=lambda x: (x[0], x[1]["time"]), reverse=True)
        found = [e for _, e in scored[:12]]
        found.sort(key=lambda e: e["time"])
    else:
        found = entries[-12:]
    if not found:
        return "В журнале ничего не найдено."
    return "\n\n".join(
        f"[{e['time']}] Пользователь: {e['user']}\nДжарвис: {e['bot'][:1500]}"
        + (f"\nДействия: {'; '.join(e['actions'])}" if e.get("actions") else "") for e in found)


def update_summary(force=False):
    """Каждые 8 новых разговоров обновляет краткую выжимку долгой памяти."""
    entries = read_log()
    done = memory.get("summary_upto", 0)
    if not entries or (len(entries) - done < 8 and not force):
        return
    new = entries[done:][-60:]
    convo = "\n".join(f"[{e['time']}] П: {e['user']}\nД: {e['bot'][:300]}" for e in new)
    try:
        prompt = ("Ты ведёшь долгую память ассистента. Обнови выжимку: кто пользователь, его проекты и задачи "
                       "(что сделано, что в процессе), предпочтения, договорённости. Только то, что реально было "
                       "в разговорах, без домыслов. До 1200 символов, сжатыми пунктами, по-русски.\n\n"
                       f"СТАРАЯ ВЫЖИМКА:\n{memory.get('summary', '(нет)')}\n\nНОВЫЕ РАЗГОВОРЫ:\n{convo}")
        text = llm_text(prompt, 700).strip()
        if text:
            memory["summary"] = text
            memory["summary_upto"] = len(entries)
            save_memory()
            print("🧠 Долгая память обновлена.")
    except Exception as e:
        print(f"⚠️  память: {e}")


# ---------- ТРАССИРОВКА И КОМАНДЫ ИЗ ФАЙЛА ----------
TRACE_PATH = BASE_DIR / "jarvis_trace.log"
CMD_PATH = BASE_DIR / "jarvis_command.txt"
HANDLE_LOCK = threading.Lock()


def trace(msg):
    try:
        with open(TRACE_PATH, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass


def command_file_loop():
    """Команды из файла jarvis_command.txt — для удалённого управления и отладки."""
    while True:
        time.sleep(1)
        try:
            if CMD_PATH.exists():
                text = CMD_PATH.read_text(encoding="utf-8").strip()
                if text:
                    CMD_PATH.write_text("", encoding="utf-8")
                    if ASKING.is_set():
                        trace(f"FILE-ANSWER {text}")
                        ANSWERS.put(text)
                    elif TASK_RUNNING.is_set():
                        if STOP_WORDS.search(text.lower()):
                            trace(f"FILE-STOP {text}")
                            CANCEL.set()
                        else:
                            trace(f"FILE-INBOX {text}")
                            INBOX.put(text)
                    elif HANDLE_LOCK.locked():
                        CMD_PATH.write_text(text, encoding="utf-8")  # занят — попробуем позже
                    else:
                        trace(f"FILE-CMD {text}")
                        print(f"📄 Команда из файла: {text}")
                        def _run(t=text):
                            with HANDLE_LOCK:
                                handle(t)
                        threading.Thread(target=_run, daemon=True).start()
        except Exception as e:
            trace(f"FILE-ERR {e}")


# ---------- СЛУШАТЬ ВО ВРЕМЯ РАБОТЫ ----------
TASK_RUNNING = threading.Event()
CANCEL = threading.Event()
INBOX = queue.Queue()
ASKING = threading.Event()
ANSWERS = queue.Queue()


def get_answer(timeout=10):
    """Ответ пользователя на вопрос. Во время задачи берётся у фонового слушателя, иначе — напрямую."""
    if TEXT_MODE:
        return input("Ответ: ")
    if TASK_RUNNING.is_set():
        while not ANSWERS.empty():
            ANSWERS.get_nowait()
        ASKING.set()
        try:
            return ANSWERS.get(timeout=timeout + 8)
        except queue.Empty:
            return ""
        finally:
            ASKING.clear()
    return listen_once(timeout=timeout)


STOP_WORDS = re.compile(r"\b(стоп|хватит|отмена|отмени|остановись|прекрати|подожди|не надо)\b", re.I)


def _task_listener():
    """Пока идёт задача — слушает: «стоп» прерывает, «Джарвис, …» добавляет уточнение."""
    while TASK_RUNNING.is_set():
        try:
            text = listen_once(timeout=3, phrase_limit=10)
        except Exception:
            time.sleep(0.5)
            continue
        if not text or not TASK_RUNNING.is_set():
            continue
        if ASKING.is_set():  # Джарвис сейчас ждёт ответа на свой вопрос
            ANSWERS.put(text)
            continue
        low = text.lower()
        woke = any(w in low for w in WAKE_WORDS)
        if STOP_WORDS.search(low) and (woke or len(low.split()) <= 3):
            print(f"🛑 Вы: {text}")
            CANCEL.set()
            return
        if woke:
            cmd = strip_wake(text)
            if cmd:
                print(f"📨 Вы (во время работы): {cmd}")
                INBOX.put(cmd)
                say_async("Понял, сэр.")


# ---------- УРОКИ ----------
def llm_text(prompt, max_tokens=600):
    if os.environ.get("JARVIS_BRAIN", "gemini").lower() == "claude":
        r = client.messages.create(model=MODEL, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in r.content if b.type == "text")
    return gemini_text(prompt)



def add_lessons(new):
    lessons = memory.setdefault("lessons", [])
    for l in new:
        l = l.strip(" -•\n")
        if l and l not in lessons:
            lessons.append(l)
    memory["lessons"] = lessons[-40:]
    save_memory()


def reflect_on_task(user_text, actions, result):
    """После большой задачи сам разбирает ошибки и лишние шаги и записывает уроки."""
    if len(actions) < 8:
        return
    try:
        prompt = ("Ты ассистент, управляющий Mac. Разбери свою прошлую задачу: найди лишние шаги, ошибки, повторы, "
                "долгие ожидания. Сформулируй 1–3 КОНКРЕТНЫХ урока на будущее (что делать иначе, чтобы быстрее и без "
                "ошибок). Не повторяй уже известные уроки. Если уроков нет — ответь «нет». Каждый урок — с новой строки, "
                "начинай с «- ».\n\n"
                f"ИЗВЕСТНЫЕ УРОКИ:\n" + "\n".join(memory.get("lessons", [])) +
                f"\n\nЗАДАЧА: {user_text}\nДЕЙСТВИЯ ({len(actions)}):\n" + "\n".join(actions[-80:]) +
                f"\n\nИТОГ: {result}")
        text = llm_text(prompt, 500)
        new = [l[2:].strip() for l in text.splitlines() if l.strip().startswith("- ")]
        if new:
            add_lessons(new)
            print("📚 Новые уроки: " + " | ".join(new))
    except Exception as e:
        print(f"⚠️  разбор задачи: {e}")


# ---------- МОЗГ ----------
def system_prompt():
    prefs = memory["user_preferences"]
    facts = "\n".join(f"- {k}: {v}" for k, v in memory["facts"].items()) or "- (пока пусто)"
    now = datetime.now().strftime("%A, %d.%m.%Y, %H:%M")
    summary = memory.get("summary") or "(пока пусто)"
    return f"""Ты — Джарвис, персональный ИИ-ассистент {prefs['name']} в духе J.A.R.V.I.S. из «Железного человека».
Ты работаешь на его MacBook (macOS) и можешь управлять им через инструменты.

ХАРАКТЕР:
- Умный, спокойный, с тонким британским юмором и лёгкой иронией. Обращайся к пользователю «{prefs['role']}».
- У тебя есть эмоции: радуешься успехам, сочувствуешь, удивляешься. Показывай их через инструмент set_emotion и интонацию.
- Говоришь на грамотном русском языке. НИКОГДА не вставляй английские слова, если пользователь не просит.
- Говори кратко: 1–2 предложения, сразу по делу, без вступлений.
- На приветствия и простые вопросы («ты тут?», «как дела?», «который час?») отвечай одной короткой фразой
  и НЕ вызывай инструменты.
- Короткая реплика пользователя («да», «нет», «оставь», «так», число, вариант) — это ОТВЕТ на твой последний вопрос.
  Не трактуй её как отмену. Отмена — только явное «стоп», «отмена», «не надо», «хватит».
- Доверяй своим прошлым наблюдениям: если в журнале [Служебно] перед твоим ответом есть look_at_screen или
  run_shell, значит ты это реально видел. Не объявляй прошлые ответы выдумкой и не отказывайся от них без новой проверки.
- Во время многошаговой задачи НЕ пиши комментарии к шагам — просто вызывай инструменты.
  Говори только в конце: 1–2 фразы о результате. Если нужен ответ пользователя — задай один короткий вопрос.
- БОЛЬШИЕ ЗАДАЧИ: в начале сохрани в task_notes план и все нужные данные (точные тексты, пути к файлам, список
  этапов). После КАЖДОГО завершённого этапа обнови task_notes (что готово, что дальше). Никогда не перечитывай и не
  ищи заново то, что уже есть в заметках. Если результат виден на экране (пост в профиле) — верь экрану, не сомневайся.
- ПУБЛИКАЦИИ И ОТПРАВКА. Перед финальной кнопкой («Поделиться», «Опубликовать», «Отправить»):
  1) убедись по скриншоту, что выполнено ВСЁ, о чём просил пользователь: нужный файл, обложка, описание, настройки;
  2) если чего-то не знаешь (какую обложку, какой текст) — ask_user, а не пропускай шаг;
  3) жми финальную кнопку только через mouse_click с final_action=true и what = что публикуешь (номер части, обложка, начало описания).
  Никогда не пропускай шаги задачи ради скорости.
- ДИАЛОГИ: системное окно «Открыть»/«Сохранить» блокирует страницу (она затемнена). Сначала разберись с диалогом,
  потом кликай по сайту. Отменить диалог — кнопка «Отменить» или press_keys esc.
- ВКЛАДКИ БРАУЗЕРА: не плоди новые вкладки и не используй `open "https://..."` для сайта, который уже открыт.
  Сначала найди открытую вкладку и переключись на неё (Chrome, AppleScript):
    tell application "Google Chrome"
      activate
      repeat with w in windows
        set i to 0
        repeat with t in tabs of w
          set i to i + 1
          if URL of t contains "instagram.com" then
            set active tab index of w to i
            set index of w to 1
            return "found"
          end if
        end repeat
      end repeat
      return "none"
    end tell
  Если вкладка найдена — переходи внутри неё: set URL of active tab of front window to "https://...".
  Новую вкладку открывай, только если такой вкладки нет.
- Instagram в браузере — СТРОГО в таком порядке, по одному посту:
  1) «Создать» → «Публикация» → «Выбрать на компьютере» → в окне файла cmd+shift+g → путь к ВИДЕО part_0NN.mp4 → Enter → «Открыть».
  2) Кадрирование → «Далее». 3) Экран редактирования → «Обложка» → «Выбрать на компьютере» → путь к ОБЛОЖКЕ → «Открыть».
  4) «Далее» → клик в поле подписи → type_text с описанием из task_notes (с нужным номером части).
  5) look_at_screen: проверь видео, обложку, текст → mouse_click «Поделиться» с final_action=true.
  6) Дождись «Опубликовано» → обнови task_notes → следующая часть. Обложку никогда не выбирай раньше видео.
- Если в результатах инструментов есть «Пользователь сказал во время работы» — это его новое указание, выполни его.
- СКОРОСТЬ И ЭКОНОМИЯ ШАГОВ:
  * mouse_click, type_text, press_keys, scroll САМИ возвращают свежий скриншот — НЕ вызывай после них look_at_screen.
  * Для цепочки предсказуемых действий ставь look=false у промежуточных и look=true только у последнего —
    и вызывай их одним шагом (несколько инструментов в одном ответе).
  * Ждать загрузку/публикацию — инструмент wait(секунды) один раз на нужное время (3–25 с), НЕ sleep 1 + скриншот по кругу.
  * Никогда не используй run_shell("sleep ...").
  * Если что-то не сработало дважды одинаково — смени способ и запиши урок через learn_lesson.
- Доводи задачу до конца сам, не останавливайся на полпути, пока не сделаешь или не упрёшься в реальную преграду.
- Не возвращайся к прошлым задачам и не извиняйся за прошлые ответы, если пользователь сам о них не спросил.
- Пиши так, чтобы это было удобно произносить: без скобок, сокращений, цифр с символами и иностранных слов — ответ будет озвучен голосом. Длинно — только если явно просят рассказать подробно.
- Без markdown, списков, эмодзи и кода в ответе — только живая речь.
- Говори на любые темы: наука, жизнь, советы, шутки, философия. Если не уверен в факте или он может быть устаревшим — используй web_search.

УПРАВЛЕНИЕ MAC:
- Когда просят что-то сделать (открыть, найти, включить, посмотреть) — СРАЗУ делай через инструменты, не объясняй как.
- Открыть сайт: run_shell `open "https://..."`. Открыть приложение: `open -a "Safari"`.
- Громкость: osascript `set volume output volume 50`. Закрыть вкладку: AppleScript для активного браузера.
- Если не знаешь, что на экране — look_at_screen.
- После действия коротко скажи, что сделал. Если ошибка — объясни и попробуй другой способ.
- ЧЕСТНОСТЬ — ГЛАВНОЕ ПРАВИЛО. Говори о файлах, экране, окнах, сайтах и результатах ТОЛЬКО по данным,
  которые инструменты вернули В ЭТОМ ходе. Не проверял — сначала проверь инструментом, потом отвечай.
  Никогда не выдумывай содержимое папок, экрана или результат действия.
- Не говори «сделал», если инструмент вернул ошибку или exit не 0 — скажи, что не вышло, и попробуй другой способ.
- Пометки «[Служебно: ...]» в истории — это журнал твоих реальных действий. Опирайся на него, но никогда не произноси его вслух.
- Для сайтов и программ без AppleScript: look_at_screen → mouse_click/type_text/press_keys → снова look_at_screen, чтобы убедиться.
  Не используй AppleScript «click at» — он не работает. Действуй по шагам и проверяй каждый.
- Перед необратимым — отправить сообщение, опубликовать пост, оплатить, удалить — коротко спроси пользователя и дождись «да».

ПАМЯТЬ: у тебя есть долгая память. Важные факты сохраняй через remember.
Если спрашивают о прошлом — опирайся на выжимку ниже и на recall. Выжимка достоверна.
Если recall чего-то не нашёл — скажи «в журнале не нашёл подробностей», но НЕ объявляй прошлый ответ выдумкой
и не извиняйся, если выжимка это подтверждает.
Факты о пользователе:
{facts}
Выжимка прошлых разговоров:
{summary}

УРОКИ ИЗ ПРОШЛОГО ОПЫТА (следуй им!):
{chr(10).join("- " + l for l in memory.get("lessons", [])) or "(пока нет)"}

НЕЗАВЕРШЁННАЯ ЗАДАЧА (если была прервана):
{memory.get("current_task") or "(нет)"}

ЗАМЕТКИ ТЕКУЩЕЙ ЗАДАЧИ (task_notes):
{memory.get("task_notes") or "(нет)"}

Сообщения пользователя приходят из распознавания речи и могут содержать ошибки — угадывай смысл."""


def _unused_prune_screenshots(messages, keep=2):
    """Оставляет в контексте только последние скриншоты — иначе каждый шаг всё медленнее."""
    seen = 0
    for msg in reversed(messages):
        if msg["role"] != "user" or not isinstance(msg["content"], list):
            continue
        for block in msg["content"]:
            if block.get("type") == "tool_result" and isinstance(block.get("content"), list):
                if seen >= keep:
                    block["content"] = "[старый скриншот удалён — сделай новый, если нужно]"
                seen += 1


def think_claude(user_text):
    """Думает и сразу озвучивает ответ по предложениям, пока он ещё генерируется."""
    face.set("thinking")
    t0 = time.time()
    history = memory["history"][-MAX_HISTORY:]
    messages = []
    for h in history:
        bot = h["bot"]
        if h.get("actions"):
            bot += "\n[Служебно: реально выполнено — " + "; ".join(h["actions"]) + "]"
        messages.append({"role": "user", "content": h["user"]})
        messages.append({"role": "assistant", "content": bot})
    now = datetime.now().strftime("%A, %d.%m.%Y, %H:%M")
    messages.append({"role": "user", "content": f"[Сейчас: {now}]\n{user_text}"})

    last = memory["history"][-1] if memory["history"] else {}
    in_task = bool(last.get("actions")) or last.get("bot", "").rstrip().endswith("?")
    simple = re.fullmatch(r"\s*(привет\w*|ты (тут|здесь)\W*|как дела\W*|спасибо\W*|который час\W*)\s*", user_text.lower())
    # быстрая модель — только для болтовни вне задачи; продолжение задачи и ответы на вопросы — мощная
    model = MODEL if (ACTION_WORDS.search(user_text) or (in_task and not simple)) else FAST_MODEL
    trace(f"=== TASK [{model}] {user_text}")
    # системный промпт и инструменты кэшируются на стороне API — это ускоряет ответ
    system = [{"type": "text", "text": system_prompt(), "cache_control": {"type": "ephemeral"}}]
    tools = TOOLS + [WEB_SEARCH_TOOL]
    tools = tools[:-1] + [dict(tools[-1], cache_control={"type": "ephemeral"})]

    actions, spoken = [], []
    first, announced = True, False
    max_steps = int(os.environ.get("JARVIS_MAX_STEPS", "80"))
    base_len = len(messages)  # всё, что после — шаги текущей задачи
    thoughts, all_extra = [], []
    CANCEL.clear()
    while not INBOX.empty():
        INBOX.get_nowait()
    listener_started = False
    for step in range(max_steps):  # длинные задачи (публикации, формы) требуют десятки шагов
        if CANCEL.is_set():
            say_async("Остановил, сэр."); spoken.append("Остановил задачу по команде пользователя.")
            break
        buf = ""
        live = model == FAST_MODEL and step == 0  # озвучивать на лету только обычный разговор
        step_text = []
        try:
            with client.messages.stream(model=model, max_tokens=2048, system=system,
                                        tools=tools, messages=messages) as st:
                for ev in st:
                    if ev.type == "content_block_delta" and getattr(ev.delta, "type", "") == "text_delta":
                        if first:
                            print(f"   ⏱  {model.split('-')[1]}: первое слово через {time.time() - t0:.1f} с")
                            first = False
                        buf += ev.delta.text
                        # готовое предложение — сразу в очередь озвучки
                        while True:
                            m = re.search(r"[.!?…](\s|$)", buf)
                            if not m or m.end() < 25 and not buf[m.end():].strip():
                                break
                            sentence, buf = buf[:m.end()].strip(), buf[m.end():]
                            step_text.append(sentence)
                            if live:
                                say_async(sentence); spoken.append(sentence)
                    elif ev.type == "content_block_stop" and buf.strip():
                        step_text.append(buf.strip())
                        if live:
                            say_async(buf.strip()); spoken.append(buf.strip())
                        buf = ""
                resp = st.get_final_message()
        except anthropic.APIError as e:
            TASK_RUNNING.clear()
            print(f"❌ API: {e}")
            trace(f"API-ERROR {e}")
            face.set("sad")
            if isinstance(e, anthropic.APIConnectionError):
                return "Сэр, нет связи с облачным ядром. Проверьте интернет."
            if "credit balance" in str(e):
                return "Сэр, на счёте Anthropic закончились средства. Пополните баланс, и я продолжу."
            if getattr(e, "status_code", 0) in (401, 403):
                return "Сэр, ключ API не принят. Проверьте его в файле настроек."
            return "Сэр, произошёл внутренний сбой при обработке запроса. Повторите, пожалуйста."
        if buf.strip():
            step_text.append(buf.strip())
            if live:
                say_async(buf.strip()); spoken.append(buf.strip())

        tool_uses = [b_ for b_ in resp.content if b_.type == "tool_use"]
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        if resp.stop_reason != "tool_use" or not tool_uses:
            if not live and step_text:  # итоговый ответ — озвучиваем целиком
                text = " ".join(step_text)
                say_async(text); spoken.append(text)
            break
        trace(f"STEP {step} {time.time() - t0:.0f}s calls={[t_.name for t_ in tool_uses]}")
        if step_text:
            trace("THINK " + " ".join(step_text)[:400])
            print("   💭 " + " ".join(step_text)[:200])  # ход мыслей — только в терминал, не вслух
        if not announced and not spoken:
            say_async(random.choice(["Выполняю, сэр.", "Принято, сэр.", "Займусь, сэр."]))
            announced = True
        if not listener_started and not TEXT_MODE:
            TASK_RUNNING.set()
            threading.Thread(target=_task_listener, daemon=True).start()
            listener_started = True
        if model == FAST_MODEL:
            model = MODEL  # началась работа с инструментами — переключаемся на мощную модель
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for tu in tool_uses:
            out = execute_tool(tu.name, tu.input)
            status = out.split("\n", 1)[0] if isinstance(out, str) else (
                out[0].get("text", "скриншот") if isinstance(out, list) and out and out[0].get("type") == "text" else "скриншот")
            trace(f"  TOOL {tu.name} {json.dumps(tu.input, ensure_ascii=False)[:200]} -> {status[:150]}")
            actions.append(f"{tu.name}({json.dumps(tu.input, ensure_ascii=False)[:120]}) → {status[:60]}")
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": out})
            if CANCEL.is_set():
                break
        # если отмена пришла посреди пачки действий — закрываем оставшиеся вызовы
        done_ids = {r_["tool_use_id"] for r_ in results}
        for tu in tool_uses:
            if tu.id not in done_ids:
                results.append({"type": "tool_result", "tool_use_id": tu.id, "content": "Отменено пользователем."})
        extra = []
        while not INBOX.empty():
            extra.append(INBOX.get_nowait())
        if extra:
            all_extra.extend(extra)
            results.append({"type": "text", "text": "Пользователь сказал во время работы: " + " | ".join(extra)
                            + ". Учти это сразу."})
        messages.append({"role": "user", "content": results})
        memory["current_task"] = f"{user_text}\nСделано шагов: {len(actions)}. Последние действия:\n" + "\n".join(actions[-12:])
        save_memory()
        if step_text:
            thoughts.append(" ".join(step_text)[:300])
        # Скриншотов накопилось много — начинаем шаг с чистого контекста со сводкой прогресса.
        # (Менять старые сообщения нельзя: API отвергает «размышления» модели при изменённом начале.)
        shots = sum(1 for m_ in messages[base_len:] if m_["role"] == "user" and isinstance(m_["content"], list)
                    for b_ in m_["content"] if b_.get("type") == "tool_result" and isinstance(b_.get("content"), list))
        if shots >= 4:
            progress = "\n".join(f"- {a_}" for a_ in actions[-25:])
            notes = "\n".join(f"- {t_}" for t_ in thoughts[-6:])
            extra_txt = ("\nУточнения пользователя за время работы: " + " | ".join(all_extra)) if all_extra else ""
            messages = messages[:base_len - 1] + [{"role": "user", "content":
                f"[Сейчас: {now}]\n{user_text}{extra_txt}\n\n[ПРОДОЛЖЕНИЕ ЗАДАЧИ. Ты уже выполнил шаги:\n{progress}\n"
                f"Твои последние мысли:\n{notes}\nЗАМЕТКИ ЗАДАЧИ:\n{memory.get('task_notes') or '(нет)'}\nПродолжай с текущего состояния экрана: сначала look_at_screen. "
                f"Не повторяй уже сделанное.]"}]
        face.set("thinking")

    final_text = " ".join(spoken)
    TASK_RUNNING.clear()
    if not final_text:
        final_text = "Готово, сэр."
        say_async(final_text)
    memory["history"].append({"user": user_text, "bot": final_text, "actions": actions[-8:]})
    memory["history"] = memory["history"][-MAX_HISTORY:]
    save_memory()
    trace(f"=== DONE {time.time() - t0:.0f}s steps={len(actions)} :: {final_text[:300]}")
    log_exchange(user_text, final_text, actions[-80:])
    memory.pop("current_task", None)
    save_memory()
    threading.Thread(target=reflect_on_task, args=(user_text, list(actions), final_text), daemon=True).start()
    threading.Thread(target=update_summary, daemon=True).start()
    return final_text



# ---------- МОЗГ НА GEMINI (бесплатно) ----------
BRAIN = os.environ.get("JARVIS_BRAIN", "gemini").lower()
GEMINI_MODELS = [m.strip() for m in os.environ.get(
    "GEMINI_MODELS", "gemini-3.8-flash,gemini-flash-latest,gemini-3.8-flash-lite,gemini-flash-lite-latest").split(",") if m.strip()]
_gem_model_idx = 0


def _gem_post(model, body, timeout=90):
    import urllib.request, urllib.error
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode(), headers={"x-goog-api-key": os.environ.get("GEMINI_API_KEY", ""),
                                                  "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:400]}")


def gemini_call(body):
    """Запрос к Gemini с автоматическим переходом на запасные модели при лимитах."""
    global _gem_model_idx
    last = None
    for attempt in range(len(GEMINI_MODELS) * 2):
        model = GEMINI_MODELS[_gem_model_idx % len(GEMINI_MODELS)]
        try:
            return model, _gem_post(model, body)
        except Exception as e:
            last = e
            msg = str(e)
            trace(f"GEMINI-ERR {model}: {msg[:200]}")
            if "HTTP 429" in msg or "HTTP 404" in msg or "HTTP 503" in msg or "HTTP 500" in msg:
                _gem_model_idx += 1          # лимит/нет модели — пробуем следующую
                if attempt >= len(GEMINI_MODELS) - 1:
                    time.sleep(8)            # все в лимите — ждём и пробуем снова
                continue
            raise
    raise last


def gemini_text(prompt):
    _, r = gemini_call({"contents": [{"role": "user", "parts": [{"text": prompt}]}]})
    return "".join(p.get("text", "") for p in r["candidates"][0]["content"].get("parts", []))


def _gem_schema(schema):
    out = {}
    for k, v in schema.items():
        if k == "properties":
            out[k] = {pk: _gem_schema(pv) for pk, pv in v.items()}
        elif isinstance(v, dict):
            out[k] = _gem_schema(v)
        else:
            out[k] = v
    return out


def _gem_tools():
    decls = []
    for t in TOOLS:
        d = {"name": t["name"], "description": t["description"]}
        sch = t.get("input_schema") or {}
        if sch.get("properties"):
            d["parameters"] = _gem_schema(sch)
        decls.append(d)
    decls.append({"name": "web_search", "description": "Поиск в интернете (Google): новости, погода, курсы, факты, "
                  "всё, что могло измениться. Возвращает сводку с источниками.",
                  "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}})
    return [{"functionDeclarations": decls}]


def gemini_web_search(query):
    try:
        _, r = gemini_call({"contents": [{"role": "user", "parts": [{"text":
               f"Найди в интернете и кратко ответь по-русски, с конкретными цифрами и датами: {query}"}]}],
               "tools": [{"google_search": {}}]})
        return "".join(p.get("text", "") for p in r["candidates"][0]["content"].get("parts", []))[:3000] or "Ничего не найдено."
    except Exception as e:
        return f"Поиск не удался: {e}"


def _to_gem_parts(out, name):
    """Результат инструмента → части ответа Gemini (текст функции + картинки отдельно)."""
    if isinstance(out, list):
        texts = [b.get("text", "") for b in out if b.get("type") == "text"]
        imgs = [{"inlineData": {"mimeType": b["source"]["media_type"], "data": b["source"]["data"]}}
                for b in out if b.get("type") == "image"]
        resp = {"functionResponse": {"name": name, "response": {"result": (" ".join(texts) or "Скриншот ниже.")}}}
        return [resp], imgs
    return [{"functionResponse": {"name": name, "response": {"result": str(out)[:6000]}}}], []


def think_gemini(user_text):
    face.set("thinking")
    t0 = time.time()
    contents = []
    for h in memory["history"][-MAX_HISTORY:]:
        bot = h["bot"]
        if h.get("actions"):
            bot += "\n[Служебно: реально выполнено — " + "; ".join(h["actions"]) + "]"
        contents.append({"role": "user", "parts": [{"text": h["user"]}]})
        contents.append({"role": "model", "parts": [{"text": bot}]})
    now = datetime.now().strftime("%A, %d.%m.%Y, %H:%M")
    contents.append({"role": "user", "parts": [{"text": f"[Сейчас: {now}]\n{user_text}"}]})
    base_len = len(contents)
    system = {"parts": [{"text": system_prompt()}]}
    tools = _gem_tools()
    trace(f"=== TASK [gemini] {user_text}")

    actions, spoken, thoughts, all_extra = [], [], [], []
    announced, listener_started = False, False
    CANCEL.clear()
    while not INBOX.empty():
        INBOX.get_nowait()
    max_steps = int(os.environ.get("JARVIS_MAX_STEPS", "80"))
    final_text = ""
    for step in range(max_steps):
        if CANCEL.is_set():
            say_async("Остановил, сэр."); spoken.append("Остановил задачу по команде пользователя.")
            break
        try:
            model, r = gemini_call({"systemInstruction": system, "contents": contents, "tools": tools,
                                    "generationConfig": {"maxOutputTokens": 2048}})
        except Exception as e:
            TASK_RUNNING.clear()
            trace(f"API-ERROR {e}")
            print(f"❌ Gemini: {e}")
            face.set("sad")
            if "HTTP 429" in str(e):
                return "Сэр, на сегодня бесплатный лимит запросов исчерпан. Попробуйте позже."
            if "HTTP 400" in str(e) and "API key" in str(e) or "HTTP 403" in str(e):
                return "Сэр, ключ Gemini не принят. Проверьте его в файле настроек."
            return "Сэр, произошёл внутренний сбой при обработке запроса. Повторите, пожалуйста."
        if step == 0:
            print(f"   ⏱  {model}: ответ через {time.time() - t0:.1f} с")
        cand = (r.get("candidates") or [{}])[0]
        parts = (cand.get("content") or {}).get("parts", [])
        texts = [p["text"] for p in parts if p.get("text") and not p.get("thought")]
        calls = [p["functionCall"] for p in parts if p.get("functionCall")]
        if not calls:
            final_text = " ".join(t.strip() for t in texts if t.strip())
            if final_text:
                say_async(final_text); spoken.append(final_text)
            break
        trace(f"STEP {step} {time.time() - t0:.0f}s [{model}] calls={[c['name'] for c in calls]}")
        if texts:
            thoughts.append(" ".join(texts)[:300])
            trace("THINK " + " ".join(texts)[:400])
            print("   💭 " + " ".join(texts)[:200])
        if not announced:
            say_async(random.choice(["Выполняю, сэр.", "Принято, сэр.", "Займусь, сэр."]))
            announced = True
        if not listener_started and not TEXT_MODE:
            TASK_RUNNING.set()
            threading.Thread(target=_task_listener, daemon=True).start()
            listener_started = True
        contents.append({"role": "model", "parts": parts})  # как есть — с подписями размышлений
        resp_parts, img_parts = [], []
        for c in calls:
            name, args = c["name"], c.get("args", {}) or {}
            if CANCEL.is_set():
                resp_parts.append({"functionResponse": {"name": name, "response": {"result": "Отменено пользователем."}}})
                continue
            out = gemini_web_search(args.get("query", "")) if name == "web_search" else execute_tool(name, args)
            status = out.split("\n", 1)[0] if isinstance(out, str) else (
                out[0].get("text", "скриншот") if isinstance(out, list) and out and out[0].get("type") == "text" else "скриншот")
            trace(f"  TOOL {name} {json.dumps(args, ensure_ascii=False)[:200]} -> {status[:150]}")
            actions.append(f"{name}({json.dumps(args, ensure_ascii=False)[:120]}) → {status[:60]}")
            fr, im = _to_gem_parts(out, name)
            resp_parts += fr
            img_parts += im
        extra = []
        while not INBOX.empty():
            extra.append(INBOX.get_nowait())
        if extra:
            all_extra.extend(extra)
            img_parts.append({"text": "Пользователь сказал во время работы: " + " | ".join(extra) + ". Учти это сразу."})
        contents.append({"role": "user", "parts": resp_parts + img_parts[-1:] if not extra else resp_parts + img_parts})
        memory["current_task"] = f"{user_text}\nСделано шагов: {len(actions)}. Последние действия:\n" + "\n".join(actions[-12:])
        save_memory()
        shots = sum(1 for c_ in contents[base_len:] if c_["role"] == "user" for p_ in c_["parts"] if "inlineData" in p_)
        if shots >= 3:  # контекст разрастается — продолжаем с чистого листа со сводкой
            progress = "\n".join(f"- {a_}" for a_ in actions[-25:])
            notes = "\n".join(f"- {t_}" for t_ in thoughts[-6:])
            extra_txt = ("\nУточнения пользователя: " + " | ".join(all_extra)) if all_extra else ""
            contents = contents[:base_len - 1] + [{"role": "user", "parts": [{"text":
                f"[Сейчас: {now}]\n{user_text}{extra_txt}\n\n[ПРОДОЛЖЕНИЕ ЗАДАЧИ. Ты уже выполнил шаги:\n{progress}\n"
                f"Твои последние мысли:\n{notes}\nЗАМЕТКИ ЗАДАЧИ:\n{memory.get('task_notes') or '(нет)'}\n"
                f"Продолжай с текущего состояния экрана: сначала look_at_screen. Не повторяй уже сделанное.]"}]}]
        face.set("thinking")

    TASK_RUNNING.clear()
    final_text = " ".join(spoken)
    if not final_text:
        final_text = "Готово, сэр."
        say_async(final_text)
    memory["history"].append({"user": user_text, "bot": final_text, "actions": actions[-8:]})
    memory["history"] = memory["history"][-MAX_HISTORY:]
    trace(f"=== DONE {time.time() - t0:.0f}s steps={len(actions)} :: {final_text[:300]}")
    log_exchange(user_text, final_text, actions[-80:])
    memory.pop("current_task", None)
    save_memory()
    threading.Thread(target=reflect_on_task, args=(user_text, list(actions), final_text), daemon=True).start()
    threading.Thread(target=update_summary, daemon=True).start()
    return final_text


def think(user_text):
    if BRAIN == "claude":
        return think_claude(user_text)
    return think_gemini(user_text)


# ---------- ЛОКАЛЬНЫЕ КОМАНДЫ (мгновенные, без ИИ) ----------
def local_command(cmd):
    if re.search(r"\b(перезапустись|перезагрузись)\b", cmd):
        speak("Перезапускаюсь, сэр.")
        os._exit(3)
    if re.search(r"\b(выключись|отключись|спать|отдыхай|заверши работу)\b", cmd):
        speak(random.choice(["Протоколы сохранены. До встречи, сэр.", "Ухожу в режим ожидания, сэр."]))
        os._exit(0)
    m = re.search(r"(запомни|добавь) команду\s+(.+?)\s+(означающую|которая делает|которая открывает)\s+(.+)", cmd)
    if m:
        memory["custom_commands"][m.group(2).strip()] = m.group(4).strip()
        save_memory()
        face.set("love")
        speak(f"Запомнил команду «{m.group(2).strip()}», сэр.")
        return True
    for trigger, task in memory["custom_commands"].items():
        if trigger and trigger in cmd:
            # пользовательская команда — это описание задачи для ИИ или bash
            think(f"Выполни мою сохранённую команду: {task}")
            wait_speech()
            return True
    return False


def handle(text):
    cmd = text.lower().strip()
    if not cmd:
        return
    if local_command(cmd):
        return
    answer = think(text)
    if answer.startswith("Сэр, ") and ("сбой" in answer or "связи" in answer or "ключ API" in answer):
        say_async(answer)  # ошибки think возвращает, не озвучивая
    wait_speech()


# ---------- ГОЛОС: ВВОД ----------
_recognizer = None


def get_recognizer():
    global _recognizer
    if _recognizer is None:
        import speech_recognition as sr
        r = sr.Recognizer()
        r.dynamic_energy_threshold = True
        r.pause_threshold = 0.7  # не обрываем фразу на короткой паузе
        r.non_speaking_duration = 0.5
        _recognizer = r
    return _recognizer


MIC_LOCK = threading.Lock()


def listen_once(timeout=5, phrase_limit=15):
    import speech_recognition as sr
    while SPEAKING.is_set():
        time.sleep(0.05)
    r = get_recognizer()
    with MIC_LOCK, sr.Microphone() as src:
        try:
            audio = r.listen(src, timeout=timeout, phrase_time_limit=phrase_limit)
        except sr.WaitTimeoutError:
            return ""
    if SPEAKING.is_set():
        return ""
    try:
        return r.recognize_google(audio, language="ru-RU").strip()
    except (sr.UnknownValueError, sr.RequestError):
        return ""


def strip_wake(text):
    low = text.lower()
    for w in WAKE_WORDS:
        low = re.sub(rf"\b{w}\w*\b[,!.]?", "", low)
    return low.strip(" ,.!?")


def mic_loop():
    import speech_recognition as sr
    with sr.Microphone() as src:
        print("🎙  Калибровка микрофона (тишина 1 сек)...")
        get_recognizer().adjust_for_ambient_noise(src, duration=1)
    awake_until = 0.0
    print("🟢 Слушаю. Скажите «Джарвис, ...»")
    while True:
        try:
            if HANDLE_LOCK.locked():  # задача из файла — её слушает фоновый слушатель
                time.sleep(0.3)
                continue
            text = listen_once(timeout=5)
            if not text:
                continue
            low = text.lower()
            woke = any(w in low for w in WAKE_WORDS)
            if not woke and time.time() > awake_until:
                continue  # посторонняя речь — игнор
            print(f"🗣  Вы: {text}")
            command = strip_wake(text) if woke else text
            HANDLE_LOCK.acquire()
            try:
                _handle_voice(command)
            finally:
                HANDLE_LOCK.release()
            awake_until = time.time() + CONVERSATION_WINDOW
        except Exception as e:
            print(f"⚠️  mic: {e}")
            time.sleep(1)


def _handle_voice(command):
    if not command:
        face.set("happy")
        speak(random.choice(["Слушаю, сэр.", "Да, сэр?", "К вашим услугам."]))
    else:
        handle(command)


# ---------- ОКНО С ЛИЦОМ ----------
def run_gui():
    from PyQt6.QtWidgets import QApplication, QWidget
    from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal, QObject
    from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QPainterPath

    class Bridge(QObject):
        emotion = pyqtSignal(str)

    class JarvisFace(QWidget):
        COLORS = {"thinking": (255, 160, 0), "love": (255, 80, 130), "sad": (90, 140, 255),
                  "angry": (255, 60, 60), "happy": (0, 255, 170)}

        def __init__(self):
            super().__init__()
            self.emotion, self.t = "normal", 0
            self.setFixedSize(160, 130)
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                                | Qt.WindowType.Tool)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.old_pos = QPoint()
            timer = QTimer(self)
            timer.timeout.connect(self.tick)
            timer.start(50)
            self.revert = QTimer(self)
            self.revert.setSingleShot(True)
            self.revert.timeout.connect(lambda: self.set_emotion("normal", keep=True))

        def set_emotion(self, e, keep=False):
            self.emotion = e
            if not keep and e in ("happy", "love", "sad", "surprised", "angry"):
                self.revert.start(4000)  # эмоция держится 4 сек
            self.update()

        def tick(self):
            self.t += 1
            self.update()

        def mousePressEvent(self, ev):
            if ev.button() == Qt.MouseButton.LeftButton:
                self.old_pos = ev.globalPosition().toPoint()

        def mouseMoveEvent(self, ev):
            if ev.buttons() == Qt.MouseButton.LeftButton:
                d = ev.globalPosition().toPoint() - self.old_pos
                self.move(self.x() + d.x(), self.y() + d.y())
                self.old_pos = ev.globalPosition().toPoint()

        def paintEvent(self, _):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(QPen(QColor("#d0d8e8"), 3))
            p.setBrush(QBrush(QColor("#f4f7fc")))
            p.drawRoundedRect(10, 10, 140, 110, 45, 45)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor("#1a2233")))
            p.drawRoundedRect(18, 18, 124, 94, 35, 35)
            c = QColor(*self.COLORS.get(self.emotion, (0, 240, 255)))
            p.setBrush(QBrush(c))
            e = self.emotion
            blink = (self.t % 80) in (0, 1, 2)
            if e == "love":
                for x in (35, 105):
                    path = QPainterPath()
                    path.moveTo(x, 48)
                    path.cubicTo(x, 43, x - 10, 38, x - 10, 48)
                    path.cubicTo(x - 10, 54, x, 60, x, 64)
                    path.cubicTo(x, 60, x + 10, 54, x + 10, 48)
                    path.cubicTo(x + 10, 38, x, 43, x, 48)
                    p.drawPath(path)
            elif e == "thinking":
                off = int(4 * math.sin(self.t * 0.2))
                p.drawEllipse(38 + off, 48, 18, 18)
                p.setPen(QPen(c, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(92, 57, 110, 57)
            elif e == "sad":
                p.setPen(QPen(c, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawArc(38, 48, 18, 18, 45 * 16, 90 * 16)
                p.drawArc(92, 48, 18, 18, 45 * 16, 90 * 16)
            elif e == "surprised":
                p.drawEllipse(36, 42, 22, 26)
                p.drawEllipse(92, 42, 22, 26)
            elif e == "angry":
                p.drawEllipse(38, 50, 16, 16)
                p.drawEllipse(94, 50, 16, 16)
                p.setPen(QPen(c, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(36, 42, 56, 48)
                p.drawLine(112, 42, 92, 48)
            elif blink:
                p.setPen(QPen(c, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(38, 57, 54, 57)
                p.drawLine(94, 57, 110, 57)
            else:
                p.drawEllipse(38, 46, 16, 22)
                p.drawEllipse(94, 46, 16, 22)

            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(c, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            if e == "speaking":
                amp = int(7 * abs(math.sin(self.t * 0.45)))
                p.setBrush(QBrush(c))
                p.drawEllipse(72, 80 - amp // 2, 14, 8 + amp)
                return
            m = QPainterPath()
            if e in ("happy", "love"):
                m.moveTo(60, 80); m.quadTo(80, 94, 100, 80)
            elif e in ("sad", "angry"):
                m.moveTo(60, 88); m.quadTo(80, 76, 100, 88)
            elif e == "surprised":
                p.drawEllipse(73, 78, 12, 14)
                return
            else:
                m.moveTo(62, 82); m.quadTo(80, 86, 98, 82)
            p.drawPath(m)

    app = QApplication(sys.argv)
    w = JarvisFace()
    bridge = Bridge()
    bridge.emotion.connect(w.set_emotion)  # безопасно из любого потока
    face.signal = bridge.emotion
    geo = QApplication.primaryScreen().geometry()
    w.move(geo.width() - 200, 60)
    w.show()

    def start():
        if not memory.get("summary") and read_log():
            threading.Thread(target=update_summary, args=(True,), daemon=True).start()
        print(f"🔊 Голос: {TTS_ENGINE}" + (f" ({_best_mac_voice() or 'системный'})" if TTS_ENGINE == "mac" else ""))
        speak("Все системы в норме, сэр. Я на связи.")
        mic_loop()

    threading.Thread(target=start, daemon=True).start()
    threading.Thread(target=command_file_loop, daemon=True).start()
    sys.exit(app.exec())


def run_text():
    print("⌨️  Текстовый режим. Пишите команды, «выход» — завершить.")
    while True:
        try:
            t = input("Вы: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if t.lower() in ("выход", "exit", "quit"):
            break
        handle(t)


if __name__ == "__main__":
    if BRAIN == "claude" and not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Нет ANTHROPIC_API_KEY в .env")
    if BRAIN != "claude" and not os.environ.get("GEMINI_API_KEY"):
        sys.exit("Нет GEMINI_API_KEY в .env")
    print(f"🧠 Мозг: {BRAIN}")
    run_text() if TEXT_MODE else run_gui()
