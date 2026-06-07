import json
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.dateparse import parse_time
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
    """Allows user to redo today's check-in by deleting the existing one."""
    if request.method == 'POST':
        today = timezone.now().date()
        DailyCheckIn.objects.filter(user=request.user, date=today).delete()
    return redirect('userboard')


@login_required
def journal_new(request):
    mood_choices = JournalEntry.MOOD_TAG_CHOICES
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        mood_tag = request.POST.get('mood_tag', '').strip()

        if not content:
            messages.error(request, 'Journal entry cannot be empty.')
            return render(request, 'mood/journal_form.html', {
                'mood_choices': mood_choices,
                'entry': {'title': title, 'content': content, 'mood_tag': mood_tag},
                'mode': 'new',
            })

        if mood_tag and mood_tag not in {choice[0] for choice in mood_choices}:
            mood_tag = ''

        JournalEntry.objects.create(
            user=request.user,
            title=title,
            content=content,
            mood_tag=mood_tag,
        )
        messages.success(request, 'Journal entry saved.')
        return redirect('journal_list')
    return render(request, 'mood/journal_form.html', {'mood_choices': mood_choices, 'mode': 'new'})


@login_required
def journal_list(request):
    entries = JournalEntry.objects.filter(user=request.user).order_by('-created_at')
    selected_mood = request.GET.get('mood', '').strip()
    query = request.GET.get('q', '').strip()

    if selected_mood:
        entries = entries.filter(mood_tag=selected_mood)
    if query:
        entries = entries.filter(title__icontains=query) | entries.filter(content__icontains=query)

    return render(request, 'mood/journal_list.html', {
        'entries': entries.distinct(),
        'mood_choices': JournalEntry.MOOD_TAG_CHOICES,
        'selected_mood': selected_mood,
        'query': query,
    })


@login_required
def journal_detail(request, pk):
    entry = get_object_or_404(JournalEntry, pk=pk, user=request.user)
    return render(request, 'mood/journal_detail.html', {'entry': entry})


@login_required
def journal_edit(request, pk):
    entry = get_object_or_404(JournalEntry, pk=pk, user=request.user)
    mood_choices = JournalEntry.MOOD_TAG_CHOICES

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        mood_tag = request.POST.get('mood_tag', '').strip()

        if not content:
            messages.error(request, 'Journal entry cannot be empty.')
        else:
            if mood_tag and mood_tag not in {choice[0] for choice in mood_choices}:
                mood_tag = ''
            entry.title = title
            entry.content = content
            entry.mood_tag = mood_tag
            entry.save()
            messages.success(request, 'Journal entry updated.')
            return redirect('journal_detail', pk=entry.pk)

    return render(request, 'mood/journal_form.html', {
        'entry': entry,
        'mood_choices': mood_choices,
        'mode': 'edit',
    })


@login_required
def journal_delete(request, pk):
    entry = get_object_or_404(JournalEntry, pk=pk, user=request.user)

    if request.method == 'POST':
        entry.delete()
        messages.success(request, 'Journal entry deleted.')
        return redirect('journal_list')

    return render(request, 'mood/journal_confirm_delete.html', {'entry': entry})


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
        'show_progress_stats': profile.show_progress_stats,
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
    profile = get_or_create_profile(request.user)

    if request.method == 'POST':
        user = request.user
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()

        theme = request.POST.get('theme', profile.theme)
        language = request.POST.get('language', profile.language)
        support_region = request.POST.get('crisis_resources_region', profile.crisis_resources_region)
        reminder_time = parse_time(request.POST.get('reminder_time', '') or '')

        valid_themes = {choice[0] for choice in UserProfile.THEME_CHOICES}
        valid_languages = {choice[0] for choice in UserProfile.LANGUAGE_CHOICES}
        valid_regions = {choice[0] for choice in UserProfile.SUPPORT_REGION_CHOICES}

        if not username or not email:
            messages.error(request, 'Username and email are required.')
        elif User.objects.exclude(pk=user.pk).filter(username=username).exists():
            messages.error(request, 'That username is already taken.')
        elif User.objects.exclude(pk=user.pk).filter(email=email).exists():
            messages.error(request, 'That email is already used by another account.')
        elif theme not in valid_themes or language not in valid_languages or support_region not in valid_regions:
            messages.error(request, 'One of the selected settings is not available.')
        else:
            user.username = username
            user.email = email
            user.save()

            profile.theme = theme
            profile.language = language
            profile.crisis_resources_region = support_region
            profile.reminder_time = reminder_time
            profile.reduce_motion = 'reduce_motion' in request.POST
            profile.email_notifications = 'email_notifications' in request.POST
            profile.checkin_reminders = 'checkin_reminders' in request.POST
            profile.weekly_summary = 'weekly_summary' in request.POST
            profile.ai_personalization = 'ai_personalization' in request.POST
            profile.private_profile = 'private_profile' in request.POST
            profile.show_progress_stats = 'show_progress_stats' in request.POST
            profile.save()

            messages.success(request, 'Settings updated.')
            return redirect('settings')

    return render(request, 'mood/settings.html', {'profile': profile})


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def password_change(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password updated successfully.')
            return redirect('password_change_done')
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'mood/password_change.html', {'form': form})


@login_required
def password_change_done(request):
    return render(request, 'mood/password_change_done.html')


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
        return JsonResponse({'reply': "I'm here with you. Something went wrong. Could you say that again?"})
