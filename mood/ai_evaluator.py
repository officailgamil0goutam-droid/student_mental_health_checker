import json
import os
from decouple import config


def _get_gemini_model():
    import google.generativeai as genai
    genai.configure(api_key=config('GEMINI_API_KEY'))
    return genai.GenerativeModel('gemini-2.5-flash')


def _build_prompt(checkin, journal_entries=None):
    journal_text = ''
    if journal_entries:
        entries = '\n'.join([
            f"- [{e.created_at.date()}] {e.title or 'Untitled'}: {e.content[:200]}"
            for e in journal_entries
        ])
        journal_text = f"\nRecent journal entries:\n{entries}"

    return f"""You are a compassionate mental health support assistant for university students.
Analyse this student's daily check-in and provide supportive, non-clinical feedback.

Today's check-in scores (1=worst, 5=best):
- Mood:    {checkin.mood_score}/5  ({checkin.get_mood_score_display()})
- Sleep:   {checkin.sleep_score}/5  ({checkin.get_sleep_score_display()})
- Stress:  {checkin.stress_score}/5  ({checkin.get_stress_score_display()})
- Social:  {checkin.social_score}/5  ({checkin.get_social_score_display()})
- Energy:  {checkin.energy_score}/5  ({checkin.get_energy_score_display()})
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


def _call_ai(prompt):
    model = _get_gemini_model()
    response = model.generate_content(prompt)
    return response.text


def _parse_response(raw):
    try:
        clean = raw.strip()
        if clean.startswith('```'):
            clean = '\n'.join(clean.split('\n')[1:])
        if clean.endswith('```'):
            clean = '\n'.join(clean.split('\n')[:-1])
        return json.loads(clean.strip())
    except Exception:
        return {
            'insight': 'We received your check-in. Thank you for taking the time to reflect today.',
            'risk_level': 'low',
            'risk_reason': '',
            'recommendations': [
                'Take a moment to breathe.',
                'Stay hydrated.',
                'Reach out if you need support.'
            ]
        }


def evaluate_checkin(checkin, recent_journals=None):
    try:
        result = _parse_response(_call_ai(_build_prompt(checkin, recent_journals)))
        checkin.ai_insight = json.dumps({
            'insight': result.get('insight', ''),
            'risk_level': result.get('risk_level', 'low'),
            'risk_reason': result.get('risk_reason', ''),
            'recommendations': result.get('recommendations', []),
        })
        checkin.ai_risk_flag = result.get('risk_level', 'low') == 'high'
        checkin.save()
        return result
    except Exception as e:
        print(f'AI evaluation failed: {e}')
        return None


def _build_chat_system_prompt(user):
    from django.utils import timezone
    from .models import DailyCheckIn, JournalEntry, Streak

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
                ai_ctx = f"\nAI evaluation: risk={ai_data.get('risk_level','low')}, insight={ai_data.get('insight','')}"
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
        pattern_ctx = f"\n7-day avg: mood={avg_mood:.1f}, stress={avg_stress:.1f}, checkins={len(checkins)}"

    streak_obj = Streak.objects.filter(user=user).first()
    streak_ctx = f"\nStreak: {streak_obj.current_streak} days" if streak_obj else ''

    mood = latest.mood_score if latest else 3
    if mood <= 2:
        tone = "Be extra gentle, warm and validating. Never push. Acknowledge pain first. Avoid toxic positivity."
    elif mood == 3:
        tone = "Be friendly and curious. Ask open questions. Help them reflect without pressure."
    else:
        tone = "Be warm, celebratory and encouraging. You can be a bit upbeat and playful."

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


def call_ai_chat(system_prompt, messages):
    try:
        model = _get_gemini_model()
        full_prompt = system_prompt + '\n\n' + '\n'.join([
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in messages
        ])
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        print(f'AI chat failed: {e}')
        return "I'm here with you. Something went wrong on my end — could you say that again?"