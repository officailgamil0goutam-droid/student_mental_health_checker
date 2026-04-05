from django import forms
from .models import MoodEntry

class MoodForm(forms.ModelForm):
    class Meta:
        model = MoodEntry
        fields = ['mood', 'stress_level', 'sleep_quality', 'note']