import json
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.dateparse import parse_time
from django.db.models import Avg
from datetime import timedelta
from .models import DailyCheckIn, JournalEntry, MentalHealthScore, Streak, UserProfile
from .ai_evaluator import evaluate_checkin, _build_chat_system_prompt, call_ai_chat


# ── HELPER ────────────────────────────────────────────────────
def get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


# ── DASHBOARD ─────────────────────────────────────────────────
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

    entries = DailyCheckIn.objects.filter(user=user)
    avg_mood   = entries.aggregate(Avg('mood_score'))['mood_score__avg']
    avg_stress = entries.aggregate(Avg('stress_score'))['stress_score__avg']
    avg_sleep  = entries.aggregate(Avg('sleep_score'))['sleep_score__avg']

    ai_data = None
    if latest_checkin and latest_checkin.ai_insight:
        try:
            ai_data = json.loads(latest_checkin.ai_insight)
        except Exception:
            pass

    if weekly_score:
        if weekly_score >= 75:   score_status = 'Doing well 🌟'
        elif weekly_score >= 50: score_status = 'Keep going 💪'
        else:                    score_status = "Let's work on this 🌱"
    else:
        score_status = 'Complete your first check-in'

    context = {
        'already_checked_in':  already_checked_in,
        'latest_score':        latest_score,
        'weekly_score':        weekly_score,
        'streak':              streak_obj.current_streak,
        'longest_streak':      streak_obj.longest_streak,
        'total_checkins':      total_checkins,
        'recent_journals':     recent_journals,
        'journal_count':       journal_count,
        'ai_data':             ai_data,
        'score_status':        score_status,
        'latest_checkin_mood': latest_checkin.mood_score if latest_checkin else 3,
        'avg_mood':   round(avg_mood,   1) if avg_mood   else 0,
        'avg_stress': round(avg_stress, 1) if avg_stress else 0,
        'avg_sleep':  round(avg_sleep,  1) if avg_sleep  else 0,
    }
    return render(request, 'mood/dashboard.html', context)


# ── CHECK-IN ──────────────────────────────────────────────────
@login_required
def checkin(request):
    if request.method == 'POST':
        user  = request.user
        today = timezone.now().date()

        if DailyCheckIn.objects.filter(user=user, date=today).exists():
            return redirect('userboard')

        checkin_obj = DailyCheckIn.objects.create(
            user=user, date=today,
            mood_score=int(request.POST.get('mood_score',   3)),
            sleep_score=int(request.POST.get('sleep_score',  3)),
            stress_score=int(request.POST.get('stress_score', 3)),
            social_score=int(request.POST.get('social_score', 3)),
            energy_score=int(request.POST.get('energy_score', 3)),
            mood_note=request.POST.get('mood_note', ''),
        )

        streak_obj, _ = Streak.objects.get_or_create(user=user)
        yesterday = today - timedelta(days=1)
        streak_obj.current_streak = (
            streak_obj.current_streak + 1
            if streak_obj.last_checkin == yesterday else 1
        )
        if streak_obj.current_streak > streak_obj.longest_streak:
            streak_obj.longest_streak = streak_obj.current_streak
        streak_obj.last_checkin = today
        streak_obj.save()

        recent_journals = JournalEntry.objects.filter(user=user).order_by('-created_at')[:3]
        evaluate_checkin(checkin_obj, recent_journals=recent_journals)

        return redirect('userboard')
    return redirect('userboard')


# ── CHECK-IN AGAIN ────────────────────────────────────────────
@login_required
def checkin_again(request):
    if request.method == 'POST':
        today = timezone.now().date()
        DailyCheckIn.objects.filter(user=request.user, date=today).delete()
    return redirect('userboard')


# ── JOURNAL ───────────────────────────────────────────────────
@login_required
def journal_new(request):
    mood_choices = JournalEntry.MOOD_TAG_CHOICES
    if request.method == 'POST':
        title    = request.POST.get('title',    '').strip()
        content  = request.POST.get('content',  '').strip()
        mood_tag = request.POST.get('mood_tag', '').strip()

        if not content:
            messages.error(request, 'Journal entry cannot be empty.')
            return render(request, 'mood/journal_form.html', {
                'mood_choices': mood_choices,
                'entry': {'title': title, 'content': content, 'mood_tag': mood_tag},
                'mode': 'new',
            })

        if mood_tag and mood_tag not in {c[0] for c in mood_choices}:
            mood_tag = ''

        JournalEntry.objects.create(
            user=request.user, title=title,
            content=content, mood_tag=mood_tag,
        )
        messages.success(request, 'Journal entry saved.')
        return redirect('journal_list')

    return render(request, 'mood/journal_form.html', {
        'mood_choices': mood_choices, 'mode': 'new'
    })


@login_required
def journal_list(request):
    entries = JournalEntry.objects.filter(user=request.user).order_by('-created_at')
    selected_mood = request.GET.get('mood', '').strip()
    query         = request.GET.get('q',    '').strip()

    if selected_mood:
        entries = entries.filter(mood_tag=selected_mood)
    if query:
        entries = entries.filter(title__icontains=query) | entries.filter(content__icontains=query)

    return render(request, 'mood/journal_list.html', {
        'entries':       entries.distinct(),
        'mood_choices':  JournalEntry.MOOD_TAG_CHOICES,
        'selected_mood': selected_mood,
        'query':         query,
    })


@login_required
def journal_detail(request, pk):
    entry = get_object_or_404(JournalEntry, pk=pk, user=request.user)
    return render(request, 'mood/journal_detail.html', {'entry': entry})


@login_required
def journal_edit(request, pk):
    entry        = get_object_or_404(JournalEntry, pk=pk, user=request.user)
    mood_choices = JournalEntry.MOOD_TAG_CHOICES

    if request.method == 'POST':
        title    = request.POST.get('title',    '').strip()
        content  = request.POST.get('content',  '').strip()
        mood_tag = request.POST.get('mood_tag', '').strip()

        if not content:
            messages.error(request, 'Journal entry cannot be empty.')
        else:
            if mood_tag and mood_tag not in {c[0] for c in mood_choices}:
                mood_tag = ''
            entry.title    = title
            entry.content  = content
            entry.mood_tag = mood_tag
            entry.save()
            messages.success(request, 'Journal entry updated.')
            return redirect('journal_detail', pk=entry.pk)

    return render(request, 'mood/journal_form.html', {
        'entry': entry, 'mood_choices': mood_choices, 'mode': 'edit'
    })


@login_required
def journal_delete(request, pk):
    entry = get_object_or_404(JournalEntry, pk=pk, user=request.user)
    if request.method == 'POST':
        entry.delete()
        messages.success(request, 'Journal entry deleted.')
        return redirect('journal_list')
    return render(request, 'mood/journal_confirm_delete.html', {'entry': entry})


# ── PROFILE ───────────────────────────────────────────────────
@login_required
def profile_view(request):
    user    = request.user
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
    scores  = [c.mental_health_score for c in checkins if c.mental_health_score]
    avg_score = round(sum(scores) / len(scores)) if scores else None

    context = {
        'profile':            profile,
        'history':            history,
        'total_checkins':     total_checkins,
        'avg_score':          avg_score,
        'streak':             streak_obj.current_streak,
        'longest_streak':     streak_obj.longest_streak,
        'risk_count':         checkins.filter(ai_risk_flag=True).count(),
        'journal_count':      JournalEntry.objects.filter(user=user).count(),
        'show_progress_stats': getattr(profile, 'show_progress_stats', True),
    }
    return render(request, 'mood/profile.html', context)


@login_required
def profile_edit(request):
    profile = get_or_create_profile(request.user)
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name  = request.POST.get('last_name',  user.last_name)
        user.save()
        profile.university    = request.POST.get('university',    profile.university)
        profile.year_of_study = request.POST.get('year_of_study', profile.year_of_study)
        profile.subject_area  = request.POST.get('subject_area',  profile.subject_area)
        profile.pronouns      = request.POST.get('pronouns',      profile.pronouns)
        profile.avatar        = request.POST.get('avatar',        profile.avatar)
        profile.save()
        messages.success(request, 'Profile updated.')
        return redirect('profile_view')
    return render(request, 'mood/profile_edit.html', {'profile': profile})


# ── PROGRESS ──────────────────────────────────────────────────
@login_required
def progress_view(request):
    user    = request.user
    profile = get_or_create_profile(user)
    streak_obj, _ = Streak.objects.get_or_create(user=user)
    checkins = DailyCheckIn.objects.filter(user=user).order_by('-date')
    total_checkins = checkins.count()

    # Average score
    scores    = [c.mental_health_score for c in checkins if c.mental_health_score]
    avg_score = round(sum(scores) / len(scores)) if scores else None

    # Last 7 days bar chart data
    today     = timezone.now().date()
    week_days = []
    for i in range(6, -1, -1):
        day     = today - timedelta(days=i)
        entry   = checkins.filter(date=day).first()
        week_days.append({
            'day':   day.strftime('%a')[0],
            'date':  day,
            'score': round(entry.mental_health_score) if entry and entry.mental_health_score else None,
            'mood':  entry.mood_score if entry else None,
        })

    # History with AI data
    history = []
    for c in checkins[:10]:
        ai_data = None
        if c.ai_insight:
            try:
                ai_data = json.loads(c.ai_insight)
            except Exception:
                ai_data = {'insight': c.ai_insight, 'risk_level': 'low'}
        history.append({'checkin': c, 'ai': ai_data})

    # Averages
    avg_mood   = checkins.aggregate(Avg('mood_score'))['mood_score__avg']
    avg_sleep  = checkins.aggregate(Avg('sleep_score'))['sleep_score__avg']
    avg_stress = checkins.aggregate(Avg('stress_score'))['stress_score__avg']

    context = {
        'profile':          profile,
        'streak':           streak_obj.current_streak,
        'longest_streak':   streak_obj.longest_streak,
        'total_checkins':   total_checkins,
        'avg_score':        avg_score,
        'week_days':        week_days,
        'history':          history,
        'high_risk':        checkins.filter(ai_risk_flag=True).count(),
        'journal_count':    JournalEntry.objects.filter(user=user).count(),
        'avg_mood':         round(avg_mood,   1) if avg_mood   else 0,
        'avg_sleep':        round(avg_sleep,  1) if avg_sleep  else 0,
        'avg_stress':       round(avg_stress, 1) if avg_stress else 0,
    }
    return render(request, 'mood/progress.html', context)


# ── SETTINGS ──────────────────────────────────────────────────
@login_required
def settings_view(request):
    profile = get_or_create_profile(request.user)

    if request.method == 'POST':
        user     = request.user
        username = request.POST.get('username', '').strip()
        email    = request.POST.get('email',    '').strip()

        if not username or not email:
            messages.error(request, 'Username and email are required.')
        elif User.objects.exclude(pk=user.pk).filter(username=username).exists():
            messages.error(request, 'That username is already taken.')
        elif User.objects.exclude(pk=user.pk).filter(email=email).exists():
            messages.error(request, 'That email is already used by another account.')
        else:
            user.username   = username
            user.email      = email
            user.save()

            # Theme & appearance
            theme  = request.POST.get('theme',  getattr(profile, 'theme',  'midnight'))
            accent = request.POST.get('accent_colour', getattr(profile, 'accent_colour', 'purple'))

            valid_themes  = ['default', 'ocean', 'forest', 'sunset', 'midnight']
            valid_accents = ['purple', 'blue', 'green', 'pink', 'amber']

            if theme  in valid_themes:  profile.theme         = theme
            if accent in valid_accents: profile.accent_colour = accent

            # Notification toggles
            for field in ['email_notifications', 'checkin_reminders',
                          'weekly_summary', 'ai_personalization',
                          'private_profile', 'show_progress_stats',
                          'reduce_motion']:
                if hasattr(profile, field):
                    setattr(profile, field, field in request.POST)

            # Optional fields
            if hasattr(profile, 'language'):
                profile.language = request.POST.get('language', profile.language)
            if hasattr(profile, 'crisis_resources_region'):
                profile.crisis_resources_region = request.POST.get(
                    'crisis_resources_region', profile.crisis_resources_region)
            if hasattr(profile, 'reminder_time'):
                rt = parse_time(request.POST.get('reminder_time', '') or '')
                if rt: profile.reminder_time = rt

            profile.save()
            messages.success(request, 'Settings updated.')
            return redirect('settings')

    return render(request, 'mood/settings.html', {'profile': profile})


# ── PASSWORD CHANGE ───────────────────────────────────────────
@login_required
def password_change(request):
    error   = None
    success = None

    if request.method == 'POST':
        old_password     = request.POST.get('old_password',     '')
        new_password     = request.POST.get('new_password',     '')
        confirm_password = request.POST.get('confirm_password', '')

        if not old_password or not new_password or not confirm_password:
            error = 'All fields are required.'
        elif not request.user.check_password(old_password):
            error = 'Old password is incorrect.'
        elif len(new_password) < 8:
            error = 'New password must be at least 8 characters.'
        elif new_password != confirm_password:
            error = 'New passwords do not match.'
        else:
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)
            return redirect('password_change_done')

    return render(request, 'mood/password_change.html', {
        'error': error, 'success': success
    })


@login_required
def password_change_done(request):
    return render(request, 'mood/password_change_done.html')


# ── RESOURCES ─────────────────────────────────────────────────
@login_required
def resources_view(request):
    return render(request, 'mood/resources.html')


# ── NOTIFICATIONS ─────────────────────────────────────────────
@login_required
def notifications(request):
    return render(request, 'mood/notifications.html')


# ── CHAT ──────────────────────────────────────────────────────
@login_required
@require_POST
def chat(request):
    try:
        data         = json.loads(request.body)
        user_message = data.get('user_message', '').strip()
        history      = data.get('messages', [])

        if not user_message:
            return JsonResponse({'error': 'Empty message'}, status=400)

        system_prompt  = _build_chat_system_prompt(request.user)
        messages_list  = history + [{'role': 'user', 'content': user_message}]
        reply          = call_ai_chat(system_prompt, messages_list)
        return JsonResponse({'reply': reply})

    except Exception as e:
        print(f'Chat error: {e}')
        return JsonResponse({'reply': "I'm here with you. Something went wrong — could you say that again?"})


# ── LOGOUT ────────────────────────────────────────────────────
@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


# ── DELETE ACCOUNT ────────────────────────────────────────────
@login_required
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        logout(request)
        user.delete()
        return redirect('login')
    return render(request, 'mood/delete_account_confirm.html')