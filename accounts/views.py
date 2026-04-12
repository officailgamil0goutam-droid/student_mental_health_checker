import json
import random
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.mail import send_mail
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from mood.models import UserProfile


# ── ACCOUNTS LANDING ──────────────────────────────────────────
def accounts(request):
    if request.user.is_authenticated:
        return redirect('userboard')
    return redirect('login')


# ── LOGIN ─────────────────────────────────────────────────────
def login_view(request):
    if request.user.is_authenticated:
        return redirect('userboard')

    error = None
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)
        except User.DoesNotExist:
            user = None

        if user is not None:
            login(request, user)
            return redirect('userboard')
        else:
            error = 'Invalid email or password. Please try again.'

    return render(request, 'accounts/login.html', {'error': error})


# ── REGISTER ──────────────────────────────────────────────────
def register(request):
    if request.method == 'GET':
        return render(request, 'accounts/register.html')

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            is_social = data.get('is_social', False)

            if is_social:
                if not request.user.is_authenticated:
                    return JsonResponse({'success': False, 'error': 'Not authenticated'})
                user = request.user
            else:
                email = data.get('email', '').strip()
                first_name = data.get('first_name', '').strip()
                last_name = data.get('last_name', '').strip()
                password = data.get('password', '')

                if not email or not password:
                    return JsonResponse({'success': False, 'error': 'Email and password are required.'})

                if User.objects.filter(email=email).exists():
                    return JsonResponse({'success': False, 'error': 'An account with this email already exists.'})

                username = email.split('@')[0]
                base = username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base}{counter}"
                    counter += 1

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                )
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.university = data.get('university', '')
            profile.year_of_study = data.get('year_of_study', '')
            profile.subject_area = data.get('subject_area', '')
            profile.pronouns = data.get('pronouns', '')
            profile.avatar = data.get('avatar', '🌙')
            profile.save()

            return JsonResponse({'success': True})

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid data.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Method not allowed'})


# ── FORGOT PASSWORD — renders the custom page ─────────────────
def forget_password(request):
    return render(request, 'accounts/forget_password.html')


# ── SEND OTP ──────────────────────────────────────────────────
def send_otp(request):
    """
    POST JSON: { "email": "user@example.com" }
    Generates a 6-digit OTP, stores it in session, emails it to user.
    Returns: { "success": true } or { "success": false, "error": "..." }
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'})

    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip()

        if not email:
            return JsonResponse({'success': False, 'error': 'Email is required.'})

        if not User.objects.filter(email=email).exists():
            # security: don't reveal if email exists or not
            # still return success so attackers can't enumerate emails
            return JsonResponse({'success': True})

        # generate 6 digit OTP
        otp = str(random.randint(100000, 999999))

        # store in session with expiry time
        request.session['reset_otp'] = otp
        request.session['reset_email'] = email
        request.session['reset_otp_expiry'] = (
            timezone.now() + timedelta(minutes=10)
        ).isoformat()

        # send email
        send_mail(
            subject='MindMate — Your password reset code',
            message=f'Your MindMate password reset code is: {otp}\n\nThis code expires in 10 minutes.\n\nIf you did not request this, please ignore this email.',
            from_email='noreply@mindmate.app',
            recipient_list=[email],
            fail_silently=False,
        )

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ── VERIFY OTP ────────────────────────────────────────────────
def verify_otp(request):
    """
    POST JSON: { "otp": "123456" }
    Verifies the OTP against the session.
    Returns: { "success": true } or { "success": false, "error": "..." }
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'})

    try:
        data = json.loads(request.body)
        otp_entered = data.get('otp', '').strip()

        stored_otp = request.session.get('reset_otp')
        expiry_str = request.session.get('reset_otp_expiry')

        if not stored_otp:
            return JsonResponse({'success': False, 'error': 'No OTP found. Please request a new code.'})

        # check expiry
        expiry = timezone.datetime.fromisoformat(expiry_str)
        if timezone.now() > expiry:
            return JsonResponse({'success': False, 'error': 'Code has expired. Please request a new one.'})

        if otp_entered != stored_otp:
            return JsonResponse({'success': False, 'error': 'Incorrect code. Please try again.'})

        # mark OTP as verified in session
        request.session['reset_otp_verified'] = True

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ── RESET PASSWORD ────────────────────────────────────────────
def reset_password(request):
    """
    POST JSON: { "password": "newpassword123" }
    Resets password if OTP was verified.
    Returns: { "success": true } or { "success": false, "error": "..." }
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'})

    try:
        if not request.session.get('reset_otp_verified'):
            return JsonResponse({'success': False, 'error': 'OTP not verified. Please start again.'})

        data = json.loads(request.body)
        new_password = data.get('password', '')

        if len(new_password) < 8:
            return JsonResponse({'success': False, 'error': 'Password must be at least 8 characters.'})

        email = request.session.get('reset_email')
        user = User.objects.get(email=email)
        user.set_password(new_password)
        user.save()

        # clear session
        for key in ['reset_otp', 'reset_email', 'reset_otp_expiry', 'reset_otp_verified']:
            request.session.pop(key, None)

        return JsonResponse({'success': True})

    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})