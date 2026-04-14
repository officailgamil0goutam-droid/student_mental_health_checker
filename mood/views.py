import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import DailyCheckIn, JournalEntry, MentalHealthScore, Streak, UserProfile
from .ai_evaluator import evaluate_checkin, _build_chat_system_prompt, call_ai_chat


def get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


@login_required
def dashboard(request):
    user = request.user
    today = timezone.now().date()
    get_or_create_profile(user)

    already_checked_in = DailyCheckIn.objects.filter(user=user, date=today).exists()
    latest_checkin = DailyCheckIn.objects.filter(user=user).first()
    latest_score = round(latest_checkin.mental_health_score) if latest_checkin and latest_checkin.mental_health_score else None
    weekly = MentalHealthScore.objects.filter(user=user).first()
    weekly_score = round(weekly.overall_score) if weekly and weekly.overall_score else None
    streak_obj, _ = Streak.objects.get_or_create(user=user)
    total_checkins = DailyCheckIn.objects.filter(user=user).count()
    recent_journals = JournalEntry.objects.filter(user=user)[:3]
    journal_count = JournalEntry.objects.filter(user=user).count()

    ai_data = None
    if latest_checkin and latest_checkin.ai_insight:
        try:
            ai_data = json.loads(latest_checkin.ai_insight)
        except Exception:
            pass

    if weekly_score:
        if weekly_score >= 75: score_status = 'Doing well 🌟'
        elif weekly_score >= 50: score_status = 'Keep going 💪'
        else: score_status = "Let's work on this 🌱"
    else:
        score_status = 'Complete your first check-in'

    latest_checkin_mood = latest_checkin.mood_score if latest_checkin else 3

    context = {
        'already_checked_in': already_checked_in,
        'latest_score': latest_score,
        'weekly_score': weekly_score,
        'streak': streak_obj.current_streak,
        'longest_streak': streak_obj.longest_streak,
        'total_checkins': total_checkins,
        'recent_journals': recent_journals,
        'journal_count': journal_count,
        'ai_data': ai_data,
        'score_status': score_status,
        'latest_checkin_mood': latest_checkin_mood,
    }
    return render(request, 'mood/dashboard.html', context)


@login_required
def checkin(request):
    if request.method == 'POST':
        user = request.user
        today = timezone.now().date()
        if DailyCheckIn.objects.filter(user=user, date=today).exists():
            return redirect('userboard')

        checkin_obj = DailyCheckIn.objects.create(
            user=user, date=today,
            mood_score=int(request.POST.get('mood_score', 3)),
            sleep_score=int(request.POST.get('sleep_score', 3)),
            stress_score=int(request.POST.get('stress_score', 3)),
            social_score=int(request.POST.get('social_score', 3)),
            energy_score=int(request.POST.get('energy_score', 3)),
            mood_note=request.POST.get('mood_note', ''),
        )

        streak_obj, _ = Streak.objects.get_or_create(user=user)
        yesterday = today - timezone.timedelta(days=1)
        streak_obj.current_streak = streak_obj.current_streak + 1 if streak_obj.last_checkin == yesterday else 1
        if streak_obj.current_streak > streak_obj.longest_streak:
            streak_obj.longest_streak = streak_obj.current_streak
        streak_obj.last_checkin = today
        streak_obj.save()

        recent_journals = JournalEntry.objects.filter(user=user).order_by('-created_at')[:3]
        evaluate_checkin(checkin_obj, recent_journals=recent_journals)

        return redirect('userboard')
    return redirect('userboard')


@login_required
def checkin_again(request):
    if request.method == 'POST':
        today = timezone.now().date()
        DailyCheckIn.objects.filter(user=request.user, date=today).delete()
    return redirect('userboard')


@login_required
def journal_new(request):
    if request.method == 'POST':
        JournalEntry.objects.create(
            user=request.user,
            title=request.POST.get('title', ''),
            content=request.POST.get('content', ''),
            mood_tag=request.POST.get('mood_tag', ''),
        )
        return redirect('userboard')
    return render(request, 'mood/journal_new.html')


@login_required
def profile_view(request):
    user = request.user
    profile = get_or_create_profile(user)
    streak_obj, _ = Streak.objects.get_or_create(user=user)
    checkins = DailyCheckIn.objects.filter(user=user).order_by('-date')

    history = []
    for c in checkins:
        ai_data = None
        if c.ai_insight:
            try:
                ai_data = json.loads(c.ai_insight)
            except Exception:
                ai_data = {'insight': c.ai_insight, 'risk_level': 'low', 'risk_reason': '', 'recommendations': []}
        history.append({'checkin': c, 'ai': ai_data})

    total_checkins = checkins.count()
    scores = [c.mental_health_score for c in checkins if c.mental_health_score]
    avg_score = round(sum(scores) / len(scores)) if scores else None

    context = {
        'profile': profile,
        'history': history,
        'total_checkins': total_checkins,
        'avg_score': avg_score,
        'streak': streak_obj.current_streak,
        'longest_streak': streak_obj.longest_streak,
        'risk_count': checkins.filter(ai_risk_flag=True).count(),
        'journal_count': JournalEntry.objects.filter(user=user).count(),
    }
    return render(request, 'mood/profile.html', context)


@login_required
def profile_edit(request):
    profile = get_or_create_profile(request.user)
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.save()
        profile.university = request.POST.get('university', profile.university)
        profile.year_of_study = request.POST.get('year_of_study', profile.year_of_study)
        profile.subject_area = request.POST.get('subject_area', profile.subject_area)
        profile.pronouns = request.POST.get('pronouns', profile.pronouns)
        profile.avatar = request.POST.get('avatar', profile.avatar)
        profile.save()
        messages.success(request, 'Profile updated.')
        return redirect('profile_view')
    return render(request, 'mood/profile_edit.html', {'profile': profile})


@login_required
def settings_view(request):
    return render(request, 'mood/settings.html', {'profile': get_or_create_profile(request.user)})


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
@require_POST
def chat(request):
    try:
        data = json.loads(request.body)
        user_message = data.get('user_message', '').strip()
        history = data.get('messages', [])
        if not user_message:
            return JsonResponse({'error': 'Empty message'}, status=400)
        system_prompt = _build_chat_system_prompt(request.user)
        messages_list = history + [{'role': 'user', 'content': user_message}]
        reply = call_ai_chat(system_prompt, messages_list)
        return JsonResponse({'reply': reply})
    except Exception as e:
        print(f'Chat error: {e}')
        return JsonResponse({'reply': "I'm here with you. Something went wrong — could you say that again?"})