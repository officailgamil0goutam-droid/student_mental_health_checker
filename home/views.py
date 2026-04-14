from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from mood.models import MoodEntry
from django.db.models import Avg
from datetime import datetime, timedelta
from django.utils import timezone

def home(request):
    return render(request, "home/home.html")

@login_required(login_url='/accounts/login/')
def dashboard(request):
    user = request.user
    entries = MoodEntry.objects.filter(user=user).order_by('-created_at')
    
    # Avg mood (mood field string hai to stress use karte hain avg ke liye)
    avg_stress = entries.aggregate(Avg('stress_level'))['stress_level__avg']
    avg_sleep = entries.aggregate(Avg('sleep_quality'))['sleep_quality__avg']
    
    # Total check-ins this month
    now = timezone.now()
    this_month_entries = entries.filter(
        created_at__month=now.month,
        created_at__year=now.year
    )
    checkin_count = this_month_entries.count()
    
    # Recent 3 entries
    recent_entries = entries[:3]
    
    # Streak calculate karo
    streak = 0
    check_date = now.date()
    for i in range(30):
        day = check_date - timedelta(days=i)
        if entries.filter(created_at__date=day).exists():
            streak += 1
        else:
            break

    context = {
        'user': user,
        'avg_stress': round(avg_stress, 1) if avg_stress else 0,
        'avg_sleep': round(avg_sleep, 1) if avg_sleep else 0,
        'checkin_count': checkin_count,
        'recent_entries': recent_entries,
        'streak': streak,
        'today': now,
    }