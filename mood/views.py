
# Create your views here.
from django.shortcuts import render, redirect
from .forms import MoodForm
from django.contrib.auth.decorators import login_required

@login_required
def mood_check(request):
    if request.method == 'POST':
        form = MoodForm(request.POST)
        if form.is_valid():
            mood = form.save(commit=False)
            mood.user = request.user
            mood.save()
            return redirect('/mood/success/')
    else:
        form = MoodForm()

    return render(request, 'mood/mood_form.html', {'form': form})


def success(request):
    return render(request, 'mood/success.html')