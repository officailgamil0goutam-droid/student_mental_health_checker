from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.CharField(max_length=10, default='🌙')
    university = models.CharField(max_length=200, blank=True)
    year_of_study = models.CharField(max_length=50, blank=True)
    subject_area = models.CharField(max_length=100, blank=True)
    pronouns = models.CharField(max_length=50, blank=True)
    streak_count = models.IntegerField(default=0)
    last_checkin_date = models.DateField(null=True, blank=True)
    total_checkins = models.IntegerField(default=0)
    joined_date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username}'s profile"


class DailyCheckIn(models.Model):
    MOOD_CHOICES = [(1,'Very Low'),(2,'Low'),(3,'Neutral'),(4,'Good'),(5,'Great')]
    SLEEP_CHOICES = [(1,'Less than 4 hours'),(2,'4-6 hours'),(3,'6-7 hours'),(4,'7-8 hours'),(5,'8+ hours')]
    STRESS_CHOICES = [(1,'Very High'),(2,'High'),(3,'Moderate'),(4,'Low'),(5,'None')]
    SOCIAL_CHOICES = [(1,'Very isolated'),(2,'Somewhat isolated'),(3,'Neutral'),(4,'Connected'),(5,'Very connected')]
    ENERGY_CHOICES = [(1,'Exhausted'),(2,'Tired'),(3,'Okay'),(4,'Energised'),(5,'Very energised')]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='checkins')
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    mood_score = models.IntegerField(choices=MOOD_CHOICES)
    mood_note = models.CharField(max_length=500, blank=True)
    sleep_score = models.IntegerField(choices=SLEEP_CHOICES)
    stress_score = models.IntegerField(choices=STRESS_CHOICES)
    stress_trigger = models.CharField(max_length=200, blank=True)
    social_score = models.IntegerField(choices=SOCIAL_CHOICES)
    energy_score = models.IntegerField(choices=ENERGY_CHOICES)
    mental_health_score = models.FloatField(null=True, blank=True)
    ai_insight = models.TextField(blank=True)
    ai_risk_flag = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['-date']

    def save(self, *args, **kwargs):
        scores = [self.mood_score, self.sleep_score, self.stress_score, self.social_score, self.energy_score]
        if all(scores):
            self.mental_health_score = (sum(scores) / (len(scores) * 5)) * 100
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} — {self.date} — {self.mental_health_score}"


class JournalEntry(models.Model):
    MOOD_TAG_CHOICES = [
        ('grateful','Grateful'),('anxious','Anxious'),('hopeful','Hopeful'),
        ('sad','Sad'),('proud','Proud'),('overwhelmed','Overwhelmed'),
        ('calm','Calm'),('angry','Angry'),('confused','Confused'),('happy','Happy'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='journal_entries')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    mood_tag = models.CharField(max_length=20, choices=MOOD_TAG_CHOICES, blank=True)
    ai_sentiment_score = models.FloatField(null=True, blank=True)
    ai_summary = models.TextField(blank=True)
    ai_themes = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} — {self.created_at.date()} — {self.title or 'Untitled'}"


class MentalHealthScore(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mh_scores')
    week_start = models.DateField()
    avg_mood = models.FloatField(null=True, blank=True)
    avg_sleep = models.FloatField(null=True, blank=True)
    avg_stress = models.FloatField(null=True, blank=True)
    avg_social = models.FloatField(null=True, blank=True)
    avg_energy = models.FloatField(null=True, blank=True)
    overall_score = models.FloatField(null=True, blank=True)
    ai_weekly_insight = models.TextField(blank=True)
    ai_trend = models.CharField(max_length=20, blank=True,
        choices=[('improving','Improving'),('stable','Stable'),('declining','Declining')])

    class Meta:
        unique_together = ('user', 'week_start')
        ordering = ['-week_start']

    def __str__(self):
        return f"{self.user.username} — week of {self.week_start} — {self.overall_score}"


class Streak(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='streak')
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_checkin = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} — streak: {self.current_streak}"