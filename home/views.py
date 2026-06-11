from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from mood.models import DailyCheckIn, JournalEntry, Streak
from django.db.models import Avg
from datetime import timedelta
from django.utils import timezone

def home(request):
    return render(request, "home/home.html")

@login_required(login_url='/accounts/login/')
def dashboard(request):
    user = request.user
    now = timezone.now()
    entries = DailyCheckIn.objects.filter(user=user).order_by('-date')

    # Avg stats
    avg_stress = entries.aggregate(Avg('stress_score'))['stress_score__avg']
    avg_sleep  = entries.aggregate(Avg('sleep_score'))['sleep_score__avg']
    avg_mood   = entries.aggregate(Avg('mood_score'))['mood_score__avg']

    # Total check-ins
    total_checkins = entries.count()

    # Recent 3 entries
    recent_entries = entries[:3]

    # Streak
    try:
        streak_obj = Streak.objects.get(user=user)
        streak = streak_obj.current_streak
        longest_streak = streak_obj.longest_streak
    except:
        streak = 0
        longest_streak = 0

    # Weekly score
    week_start = now.date() - timedelta(days=7)
    week_entries = entries.filter(date__gte=week_start)
    weekly_score = None
    latest_score = None
    score_status = "Complete your first check-in"
    if week_entries.exists():
        avg = week_entries.aggregate(
            m=Avg('mood_score'),
            s=Avg('sleep_score'),
            st=Avg('stress_score'),
            so=Avg('social_score'),
            e=Avg('energy_score'),
        )
        score = int(((avg['m'] or 3) + (avg['s'] or 3) + (avg['st'] or 3) + (avg['so'] or 3) + (avg['e'] or 3)) / 5 * 20)
        weekly_score = score
        latest_score = score
        if score >= 70:
            score_status = "You're doing great! 🌟"
        elif score >= 40:
            score_status = "Keep it up — you're improving"
        else:
            score_status = "Take care of yourself 💜"

    # Already checked in today?
    already_checked_in = entries.filter(date=now.date()).exists()

    # Latest checkin mood
    latest_checkin_mood = 3
    if already_checked_in and entries.first():
        latest_checkin_mood = entries.first().mood_score or 3

    # Journal entries
    try:
        journal_count = JournalEntry.objects.filter(user=user).count()
        recent_journals = JournalEntry.objects.filter(user=user).order_by('-created_at')[:3]
    except:
        journal_count = 0
        recent_journals = []

    # AI data
    ai_data = None
    if already_checked_in and entries.first():
        entry = entries.first()
        stress = entry.stress_score
        mood = entry.mood_score
        if stress <= 2 or mood <= 2:
            risk = 'high'
            reason = 'High stress / Low mood detected'
            insight = 'Your stress is quite high today. Please take breaks and breathe deeply. You are not alone. 💜'
            recs = ['Try 5-minute box breathing', 'Take a short walk outside', 'Talk to someone you trust']
        elif stress == 3 or mood == 3:
            risk = 'medium'
            reason = 'Moderate stress'
            insight = 'Moderate stress detected. Small breaks can make a big difference today.'
            recs = ['Listen to calming music', 'Drink water and stretch', 'Take short breaks between sessions']
        else:
            risk = 'low'
            reason = 'Stress is manageable'
            insight = 'You seem to be managing well today. Keep up the consistency! 🌟'
            recs = ['Maintain your sleep schedule', 'Stay socially connected', 'Keep journaling your feelings']
        ai_data = {
            'risk_level': risk,
            'risk_reason': reason,
            'insight': insight,
            'recommendations': recs
        }

    context = {
        'user': user,
        'avg_stress': round(avg_stress, 1) if avg_stress else 0,
        'avg_sleep': round(avg_sleep, 1) if avg_sleep else 0,
        'avg_mood': round(avg_mood, 1) if avg_mood else 0,
        'total_checkins': total_checkins,
        'recent_entries': recent_entries,
        'streak': streak,
        'longest_streak': longest_streak,
        'weekly_score': weekly_score,
        'latest_score': latest_score,
        'score_status': score_status,
        'already_checked_in': already_checked_in,
        'latest_checkin_mood': latest_checkin_mood,
        'journal_count': journal_count,
        'recent_journals': recent_journals,
        'ai_data': ai_data,
        'today': now,
    }
    return render(request, "dashboard/dashboard.html", context)