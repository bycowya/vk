import random
import re
import json
import os
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

with open("questions.json", "r", encoding="utf-8") as f:
    QUESTIONS = json.load(f)

TOKEN = os.environ.get("BOT_TOKEN")

vk_session = vk_api.VkApi(token=TOKEN)
longpoll = VkLongPoll(vk_session)
vk = vk_session.get_api()


def normalize(text):
    text = text.strip().lower()
    text = text.replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    return text


def ballov(n):
    n_abs = abs(n) % 100
    if 11 <= n_abs <= 19:
        word = "баллов"
    else:
        n_last = n_abs % 10
        if n_last == 1:
            word = "балл"
        elif 2 <= n_last <= 4:
            word = "балла"
        else:
            word = "баллов"
    return f"{n} {word}"


user_states = {}


def make_start_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("Начать", color=VkKeyboardColor.POSITIVE, payload={"command": "начать"})
    return keyboard


def make_question_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("Пропустить", color=VkKeyboardColor.SECONDARY, payload={"command": "пропустить"})
    keyboard.add_button("Завершить", color=VkKeyboardColor.NEGATIVE, payload={"command": "завершить"})
    return keyboard


def make_return_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("Вернуться к вопросу", color=VkKeyboardColor.SECONDARY, payload={"command": "вернуться"})
    keyboard.add_button("Пропустить", color=VkKeyboardColor.SECONDARY, payload={"command": "пропустить"})
    keyboard.add_button("Завершить", color=VkKeyboardColor.NEGATIVE, payload={"command": "завершить"})
    return keyboard


def send_message(user_id, text, keyboard=None):
    vk.messages.send(
        user_id=user_id,
        message=text,
        keyboard=keyboard.get_keyboard() if keyboard else None,
        random_id=random.randint(1, 2**31 - 1)
    )


def send_question(user_id):
    state = user_states[user_id]
    q = QUESTIONS[state["step"]]
    attachment = q.get("attachment_vk")
    vk.messages.send(
        user_id=user_id,
        message=q["text"],
        attachment=attachment,
        keyboard=make_question_keyboard().get_keyboard(),
        random_id=random.randint(1, 2**31 - 1)
    )


def send_greeting(user_id):
    send_message(
        user_id,
        "Привет! Я твой цифровой тренажер «Чтобы помнили». "
        "Я помогу тебе закрепить самые сложные темы Великой Отечественной войны "
        "для реального ЕГЭ по истории. Тебя ждет интерактивный квест. "
        "Ответь на все вопросы и проверь свои силы перед экзаменом. Поехали!",
        make_start_keyboard()
    )


def start_quest(user_id):
    user_states[user_id] = {"step": 0, "score": 0, "answered_wrong": False}
    send_question(user_id)


def finish_quest(user_id):
    state = user_states.get(user_id)
    if state:
        send_message(
            user_id,
            f"Квест завершён. Твой результат: {state['score']} из 17.",
            make_start_keyboard()
        )
        del user_states[user_id]
    else:
        send_message(
            user_id,
            "Квест завершён. Если хочешь пройти заново — нажми «Начать».",
            make_start_keyboard()
        )


def skip_question(user_id):
    state = user_states.get(user_id)
    if not state:
        return
    state["step"] += 1
    state["answered_wrong"] = False
    if state["step"] < len(QUESTIONS):
        send_message(
            user_id,
            f"Вопрос пропущен. Баллы не начислены. У вас {ballov(state['score'])}."
        )
        send_question(user_id)
    else:
        send_message(
            user_id,
            f"Вопрос пропущен. Баллы не начислены. У вас {ballov(state['score'])}.\n\n"
            f"Поздравляем, квест пройден! Твой результат: {state['score']} из 17.",
            make_start_keyboard()
        )
        del user_states[user_id]


def handle_answer(user_id, answer_text):
    state = user_states.get(user_id)
    if not state:
        return

    q = QUESTIONS[state["step"]]
    user_norm = normalize(answer_text)

    is_correct = False
    for variant in q["correct_variants"]:
        if user_norm == normalize(variant):
            is_correct = True
            break

    if is_correct:
        if not state["answered_wrong"]:
            state["score"] += 1
            state["step"] += 1
            state["answered_wrong"] = False

            if state["step"] < len(QUESTIONS):
                send_message(
                    user_id,
                    f"Правильно! У вас {ballov(state['score'])}."
                )
                send_question(user_id)
            else:
                send_message(
                    user_id,
                    f"Правильно! У вас {ballov(state['score'])}.\n\n"
                    f"Поздравляем, квест пройден! Твой результат: {state['score']} из 17.",
                    make_start_keyboard()
                )
                del user_states[user_id]
        else:
            state["step"] += 1
            state["answered_wrong"] = False

            if state["step"] < len(QUESTIONS):
                send_message(
                    user_id,
                    f"Правильно! Баллы не начислены, так как вы уже ошибались в этом вопросе. У вас {ballov(state['score'])}."
                )
                send_question(user_id)
            else:
                send_message(
                    user_id,
                    f"Правильно! Баллы не начислены, так как вы уже ошибались в этом вопросе. У вас {ballov(state['score'])}.\n\n"
                    f"Поздравляем, квест пройден! Твой результат: {state['score']} из 17.",
                    make_start_keyboard()
                )
                del user_states[user_id]
    else:
        state["answered_wrong"] = True
        send_message(
            user_id,
            f"Неправильно! Вам не будут начислены баллы. Вот пояснение исторической справки:\n\n{q['hint']}",
            make_return_keyboard()
        )


def main():
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_id = event.user_id
            text = event.text.strip()

            payload = None
            if hasattr(event, "payload") and event.payload:
                try:
                    payload = json.loads(event.payload)
                except Exception:
                    payload = None

            print(f"DEBUG: TEXT='{text}' | PAYLOAD={payload} | USER={user_id}", flush=True)

            command = text
            if not command and payload and "command" in payload:
                command = payload["command"]

            cmd_norm = command.strip().lower()

            if "начать" in cmd_norm or cmd_norm in ("start", "/start"):
                if user_id in user_states:
                    send_message(user_id, "Ты уже проходишь квест. Продолжай!")
                    send_question(user_id)
                else:
                    start_quest(user_id)
                continue

            if "завершить" in cmd_norm:
                finish_quest(user_id)
                continue

            if "пропустить" in cmd_norm:
                skip_question(user_id)
                continue

            if "вернуться" in cmd_norm:
                state = user_states.get(user_id)
                if state:
                    send_question(user_id)
                continue

            if user_id not in user_states:
                send_greeting(user_id)
                continue

            handle_answer(user_id, command)


if __name__ == "__main__":
    main()
