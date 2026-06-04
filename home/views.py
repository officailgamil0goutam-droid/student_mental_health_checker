from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from mood.models import MoodEntry
from django.db.models import Avg
from datetime import timedelta
from django.utils import timezone

def home(request):
    return render(request, "home/home.html")

@login_required(login_url='/accounts/login/')
def dashboard(request):
    user = request.user
    now = timezone.now()
    entries = MoodEntry.objects.filter(user=user).order_by('-created_at')

    # Avg stats
    avg_stress = entries.aggregate(Avg('stress_level'))['stress_level__avg']
    avg_sleep  = entries.aggregate(Avg('sleep_quality'))['sleep_quality__avg']

    # This month check-ins
    this_month = entries.filter(created_at__month=now.month, created_at__year=now.year)
    checkin_count = this_month.count()
    total_checkins = entries.count()

    # Recent entries
    recent_entries = entries[:3]

    # Streak
    streak = 0
    for i in range(30):
        day = now.date() - timedelta(days=i)
        if entries.filter(created_at__date=day).exists():
            streak += 1
        else:
            break

    # Longest streak
    longest_streak = streak  # simple version

    # Weekly score (avg of this week's entries, out of 100)
    week_start = now.date() - timedelta(days=7)
    week_entries = entries.filter(created_at__date__gte=week_start)
    weekly_score = None
    latest_score = None
    score_status = "Complete your first check-in"
    if week_entries.exists():
        avg = week_entries.aggregate(
            m=Avg('stress_level'), s=Avg('sleep_quality')
        )
        # stress inversely affects score, sleep positively
        score = max(0, min(100, int(
            (avg['s'] or 3) * 10 - (avg['m'] or 5) * 5 + 50
        )))
        weekly_score = score
        latest_score = score
        if score >= 70:
            score_status = "You're doing great! 🌟"
        elif score >= 40:
            score_status = "Keep it up — you're improving"
        else:
            score_status = "Take care of yourself 💜"

    # Already checked in today?
    already_checked_in = entries.filter(created_at__date=now.date()).exists()

    # Latest checkin mood (for chat)
    latest_checkin_mood = 3
    if already_checked_in and entries.first():
        latest_checkin_mood = entries.first().stress_level or 3

    # Journal count (placeholder — 0 if no journal model)
    try:
        from journal.models import JournalEntry
        journal_count = JournalEntry.objects.filter(user=user).count()
        recent_journals = JournalEntry.objects.filter(user=user).order_by('-created_at')[:3]
    except:
        journal_count = 0
        recent_journals = []

    # AI data (simple logic)
    ai_data = None
    if already_checked_in and entries.first():
        entry = entries.first()
        stress = entry.stress_level
        if stress >= 8:
            risk = 'high'
            reason = 'Very high stress detected'
            insight = 'Your stress is quite high today. Please take breaks and breathe deeply.'
            recs = ['Try 5-minute box breathing', 'Take a short walk outside', 'Talk to someone you trust']
        elif stress >= 5:
            risk = 'medium'
            reason = 'Moderate stress'
            insight = 'Moderate stress detected. Small breaks can make a big difference today.'
            recs = ['Listen to calming music', 'Drink water and stretch', 'Take short breaks between study sessions']
        else:
            risk = 'low'
            reason = 'Stress is manageable'
            insight = 'You seem to be managing well today. Keep up the consistency!'
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
        'checkin_count': checkin_count,
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