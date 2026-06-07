import json
import time

from decouple import config


DEFAULT_GEMINI_MODEL = 'gemini-2.5-flash-lite'
FALLBACK_GEMINI_MODELS = ('gemini-2.5-flash', 'gemini-2.0-flash')


def _get_client():
    from google import genai

    return genai.Client(api_key=config('GEMINI_API_KEY').strip())


def _get_models():
    configured = config('GEMINI_MODEL', default=DEFAULT_GEMINI_MODEL).strip()
    models = [configured, *FALLBACK_GEMINI_MODELS]
    return list(dict.fromkeys([model for model in models if model]))


def _is_rate_limit_error(error):
    return '429' in str(error) or 'RESOURCE_EXHAUSTED' in str(error)


def _friendly_checkin_fallback(checkin):
    recommendations = [
        'Take a short break and drink some water.',
        'Try a two-minute breathing exercise before your next task.',
    ]

    if checkin.stress_score <= 2:
        recommendations[0] = 'Pause for five minutes and write down the one thing that feels heaviest right now.'
    if checkin.sleep_score <= 2:
        recommendations[1] = 'Protect one small sleep habit tonight, like dimming screens before bed.'

    return {
        'insight': 'Thanks for checking in. Your responses suggest it may help to slow things down and focus on one manageable next step today.',
        'risk_level': 'low',
        'risk_reason': 'AI quota was unavailable, so this is a basic supportive fallback.',
        'recommendations': recommendations,
    }


# --- CORE AI CALLING LOGIC ---

def _call_gemini(prompt, retries=3):
    from google.genai import types

    client = _get_client()
    last_error = None

    for model in _get_models():
        for attempt in range(retries):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type='application/json',
                        max_output_tokens=1000,
                    ),
                )
                return response.text
            except Exception as e:
                last_error = e
                if _is_rate_limit_error(e):
                    print(f'[AI] Model {model} is rate limited or out of quota.')
                    break
                if attempt < retries - 1:
                    wait = attempt + 1
                    print(f'[AI] Gemini call failed on {model}. Retrying in {wait}s...')
                    time.sleep(wait)
                else:
                    raise e

    raise Exception(f'Gemini unavailable for all configured models: {last_error}')


def call_ai_chat(system_prompt, messages_list):
    from google.genai import types

    client = _get_client()

    try:
        history_for_gemini = []
        for msg in messages_list[:-1]:
            role = 'user' if msg['role'] == 'user' else 'model'
            history_for_gemini.append({
                'role': role,
                'parts': [{'text': msg['content']}],
            })

        last_message = messages_list[-1]['content']
        last_error = None

        for model in _get_models():
            try:
                chat = client.chats.create(
                    model=model,
                    config=types.GenerateContentConfig(system_instruction=system_prompt),
                    history=history_for_gemini,
                )
                response = chat.send_message(last_message)
                return response.text
            except Exception as e:
                last_error = e
                if _is_rate_limit_error(e):
                    print(f'[AI CHAT] Model {model} is rate limited or out of quota.')
                    continue
                raise e

        raise Exception(f'Gemini chat unavailable for all configured models: {last_error}')
    except Exception as e:
        import traceback

        if _is_rate_limit_error(e):
            return 'I am here with you. The AI service is out of quota right now, but you can try again in a little while.'
        print(f'[AI CHAT ERROR] {e}')
        traceback.print_exc()
        return 'I am here with you. Something went wrong. Could you say that again?'


# --- EVALUATOR LOGIC (FOR CHECK-INS) ---

def _build_prompt(checkin, journal_entries=None):
    journal_text = ''
    if journal_entries:
        entries = '\n'.join([
            f"- [{e.created_at.date()}] {e.title or 'Untitled'}: {e.content[:200]}"
            for e in journal_entries
        ])
        journal_text = f'\nRecent journal entries:\n{entries}'

    return f"""You are a compassionate mental health support assistant for university students.
Analyze this student's daily check-in and provide supportive, non-clinical feedback.

Today's check-in scores (1=worst, 5=best):
- Mood: {checkin.mood_score}/5 ({checkin.get_mood_score_display()})
- Sleep: {checkin.sleep_score}/5 ({checkin.get_sleep_score_display()})
- Stress: {checkin.stress_score}/5 ({checkin.get_stress_score_display()})
- Social: {checkin.social_score}/5 ({checkin.get_social_score_display()})
- Energy: {checkin.energy_score}/5 ({checkin.get_energy_score_display()})
- Overall computed score: {checkin.mental_health_score:.1f}/100
{f'- Note from student: "{checkin.mood_note}"' if checkin.mood_note else ''}
{journal_text}

Respond ONLY with a valid JSON object, no extra text:
{{
  "insight": "A warm 2-3 sentence paragraph acknowledging how they feel.",
  "risk_level": "low",
  "risk_reason": "",
  "recommendations": ["tip 1", "tip 2", "tip 3"]
}}

Risk level: low=scores mostly 3-5, medium=multiple 2s, high=any 1s or distressing note.""".strip()


def _parse_response(raw):
    try:
        clean = raw.strip()
        if '```' in clean:
            lines = [l for l in clean.split('\n') if not l.strip().startswith('```')]
            clean = '\n'.join(lines).strip()
        return json.loads(clean)
    except Exception as e:
        print(f'[AI] Parse failed: {e}')
        return None


def evaluate_checkin(checkin, recent_journals=None):
    try:
        prompt = _build_prompt(checkin, recent_journals)
        raw = _call_gemini(prompt)
        result = _parse_response(raw)
    except Exception as e:
        print(f'[EVAL ERROR] {e}')
        result = _friendly_checkin_fallback(checkin)

    if result:
        checkin.ai_insight = json.dumps(result)
        checkin.ai_risk_flag = result.get('risk_level') == 'high'
        checkin.save()
        return result
    return None


# --- CHAT SYSTEM PROMPT BUILDER ---

def _build_chat_system_prompt(user):
    from .models import DailyCheckIn, JournalEntry, Streak

    profile = getattr(user, 'profile', None)
    if profile and not profile.ai_personalization:
        return f"""You are MindMate, a compassionate AI mental health companion for university students.
Keep responses to 2-4 sentences max.
Never diagnose or give clinical advice.
If crisis is mentioned, gently suggest appropriate emergency or crisis support.

User: {user.first_name or user.username}"""

    latest = DailyCheckIn.objects.filter(user=user).first()
    checkin_ctx = ''
    ai_ctx = ''
    if latest:
        checkin_ctx = f"""
Today's check-in ({latest.date}):
- Mood: {latest.mood_score}/5 ({latest.get_mood_score_display()})
- Sleep: {latest.sleep_score}/5 ({latest.get_sleep_score_display()})
- Stress: {latest.stress_score}/5 ({latest.get_stress_score_display()})
- Social: {latest.social_score}/5 ({latest.get_social_score_display()})
- Energy: {latest.energy_score}/5 ({latest.get_energy_score_display()})
- Overall: {latest.mental_health_score:.1f}/100
{f'- Note: "{latest.mood_note}"' if latest.mood_note else ''}"""
        if latest.ai_insight:
            try:
                ai_data = json.loads(latest.ai_insight)
                ai_ctx = f"\nAI evaluation: risk={ai_data.get('risk_level', 'low')}, insight={ai_data.get('insight', '')}"
            except Exception:
                pass

    journals = JournalEntry.objects.filter(user=user).order_by('-created_at')[:5]
    journal_ctx = ''
    if journals:
        journal_ctx = '\nRecent journals:\n' + '\n'.join([
            f"- [{e.created_at.date()}] {e.mood_tag or ''} {e.title or 'Untitled'}: {e.content[:150]}"
            for e in journals
        ])

    checkins = DailyCheckIn.objects.filter(user=user).order_by('-date')[:7]
    pattern_ctx = ''
    if len(checkins) > 1:
        avg_mood = sum(c.mood_score for c in checkins) / len(checkins)
        avg_stress = sum(c.stress_score for c in checkins) / len(checkins)
        pattern_ctx = f'\n7-day avg: mood={avg_mood:.1f}, stress={avg_stress:.1f}, checkins={len(checkins)}'

    streak_obj = Streak.objects.filter(user=user).first()
    streak_ctx = f'\nStreak: {streak_obj.current_streak} days' if streak_obj else ''

    mood = latest.mood_score if latest else 3
    if mood <= 2:
        tone = 'Be extra gentle, warm and validating. Never push. Acknowledge pain first. Avoid toxic positivity.'
    elif mood == 3:
        tone = 'Be friendly and curious. Ask open questions. Help them reflect without pressure.'
    else:
        tone = 'Be warm, celebratory and encouraging. You can be a bit upbeat and playful.'

    return f"""You are MindMate, a compassionate AI mental health companion for university students.
You are having a follow-up conversation after a daily check-in.

Tone: {tone}

Rules:
- Keep responses to 2-4 sentences max
- Always end with one follow-up question
- Never diagnose or give clinical advice
- If crisis is mentioned, gently suggest Samaritans: 116 123
- Reference their data naturally, don't recite it robotically

User: {user.first_name or user.username}
{checkin_ctx}{ai_ctx}{journal_ctx}{pattern_ctx}{streak_ctx}"""
