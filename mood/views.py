mood/views.py


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

mood/models.py

from django.db import models

# Create your models here.
from django.contrib.auth.models import User

class MoodEntry(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    mood = models.CharField(max_length=20)
    stress_level = models.IntegerField()
    sleep_quality = models.IntegerField()
    
    note = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username


