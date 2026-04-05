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