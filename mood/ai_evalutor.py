import json
from google import genai
from django.conf import settings
from .models import DailyCheckIn, MentalHealthScore
from django.utils import timezone

client = genai.Client(api_key=settings.GEMINI_API_KEY)


def evaluate_checkin(checkin, recent_journals=None):
    try:
        mood_map   = {1:'Very Low', 2:'Low', 3:'Neutral', 4:'Good', 5:'Great'}
        sleep_map  = {1:'Less than 4 hrs', 2:'4-6 hrs', 3:'6-7 hrs', 4:'7-8 hrs', 5:'8+ hrs'}
        stress_map = {1:'Very High', 2:'High', 3:'Moderate', 4:'Low', 5:'None'}
        social_map = {1:'Very isolated', 2:'Somewhat isolated', 3:'Neutral', 4:'Connected', 5:'Very connected'}
        energy_map = {1:'Exhausted', 2:'Tired', 3:'Okay', 4:'Energised', 5:'Very energised'}

        journal_context = ''
        if recent_journals:
            entries = []
            for j in recent_journals:
                entries.append(f"- [{j.created_at.date()}] {j.title or 'Untitled'}: {j.content[:200]}")
            if entries:
                journal_context = '\n\nRecent journal entries:\n' + '\n'.join(entries)

        prompt = f"""You are MindMate, a compassionate mental health support AI for university students.

A student has completed their daily check-in:
- Mood: {mood_map.get(checkin.mood_score, 'Unknown')}
- Sleep: {sleep_map.get(checkin.sleep_score, 'Unknown')}
- Stress: {stress_map.get(checkin.stress_score, 'Unknown')}
- Social connection: {social_map.get(checkin.social_score, 'Unknown')}
- Energy: {energy_map.get(checkin.energy_score, 'Unknown')}
- Note: "{checkin.mood_note or 'None'}"
- Mental health score: {round(checkin.mental_health_score or 0)}/100
{journal_context}

Respond ONLY with a valid JSON object (no markdown, no backticks):
{{
  "insight": "A warm, empathetic 2-3 sentence insight about their current state",
  "risk_level": "low",
  "risk_reason": "",
  "recommendations": ["recommendation 1", "recommendation 2", "recommendation 3"]
}}

risk_level must be exactly: "low", "medium", or "high"
- high: clear signs of crisis
- medium: mood <= 2 or stress >= 4
- low: otherwise"""

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        text = response.text.strip()

        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        text = text.strip()

        data = json.loads(text)

        checkin.ai_insight   = json.dumps(data)
        checkin.ai_risk_flag = data.get('risk_level') == 'high'
        checkin.save()

        _update_weekly_score(checkin.user)
        return data

    except Exception as e:
        print(f'AI evaluation failed: {e}')
        return None


def _update_weekly_score(user):
    try:
        today      = timezone.now().date()
        week_start = today - timezone.timedelta(days=today.weekday())
        checkins   = DailyCheckIn.objects.filter(user=user, date__gte=week_start)

        if not checkins.exists():
            return

        avg_mood   = sum(c.mood_score   for c in checkins) / checkins.count()
        avg_sleep  = sum(c.sleep_score  for c in checkins) / checkins.count()
        avg_stress = sum(c.stress_score for c in checkins) / checkins.count()
        avg_social = sum(c.social_score for c in checkins) / checkins.count()
        avg_energy = sum(c.energy_score for c in checkins) / checkins.count()
        overall    = ((avg_mood + avg_sleep + avg_stress + avg_social + avg_energy) / 25) * 100

        MentalHealthScore.objects.update_or_create(
            user=user,
            week_start=week_start,
            defaults={
                'avg_mood':      avg_mood,
                'avg_sleep':     avg_sleep,
                'avg_stress':    avg_stress,
                'avg_social':    avg_social,
                'avg_energy':    avg_energy,
                'overall_score': round(overall, 1),
            }
        )
    except Exception as e:
        print(f'Weekly score update failed: {e}')


def _build_chat_system_prompt(user):
    try:
        profile  = user.profile
        checkins = user.checkins.order_by('-date')[:5]
        journals = user.journal_entries.order_by('-created_at')[:3]

        checkin_summary = ''
        if checkins.exists():
            latest   = checkins.first()
            mood_map = {1:'Very Low', 2:'Low', 3:'Neutral', 4:'Good', 5:'Great'}
            checkin_summary = f"""
Latest check-in ({latest.date}):
- Mood: {mood_map.get(latest.mood_score, 'Unknown')}
- Score: {round(latest.mental_health_score or 0)}/100
- Note: "{latest.mood_note or 'None'}"
"""

        journal_summary = ''
        if journals.exists():
            entries = [f"- {j.title or 'Untitled'} ({j.created_at.date()}): {j.content[:150]}" for j in journals]
            journal_summary = '\nRecent journals:\n' + '\n'.join(entries)

        return f"""You are MindMate AI, a compassionate mental health companion for university students.

Student profile:
- Name: {user.first_name or user.username}
- University: {profile.university or 'Not specified'}
- Year: {profile.year_of_study or 'Not specified'}
- Subject: {profile.subject_area or 'Not specified'}
{checkin_summary}{journal_summary}

Your role:
- Be warm, empathetic, and non-judgmental
- Listen actively and validate feelings
- Offer practical, student-friendly coping strategies
- Never diagnose or replace professional help
- If the student seems in crisis, gently encourage professional support
- Keep responses concise (2-4 sentences)
- Use the student's name occasionally

Important: You are NOT a therapist. Always remind users to seek professional help for serious concerns."""

    except Exception as e:
        print(f'System prompt build failed: {e}')
        return "You are MindMate AI, a compassionate mental health companion. Be warm and supportive."


def call_ai_chat(system_prompt, messages):
    try:
        last_message = messages[-1]['content'] if messages else ''
        full_message = f"{system_prompt}\n\nStudent: {last_message}"

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=full_message
        )
        return response.text.strip()

    except Exception as e:
        print(f'AI chat failed: {e}')
        return "I'm here with you. Something went wrong on my end — could you say that again?"