from django.contrib import admin
from .models import UserProfile, DailyCheckIn, JournalEntry, MentalHealthScore, Streak


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'university', 'year_of_study', 'streak_count', 'total_checkins', 'joined_date']
    search_fields = ['user__username', 'user__email', 'university']
    list_filter = ['year_of_study', 'subject_area']
    readonly_fields = ['joined_date']


@admin.register(DailyCheckIn)
class DailyCheckInAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'mood_score', 'sleep_score', 'stress_score', 'social_score', 'energy_score', 'mental_health_score', 'ai_risk_flag']
    search_fields = ['user__username', 'user__email']
    list_filter = ['date', 'mood_score', 'ai_risk_flag']
    readonly_fields = ['mental_health_score', 'created_at']
    date_hierarchy = 'date'
    ordering = ['-date']

    # highlight risk flagged entries in red
    def get_list_display_links(self, request, list_display):
        return ['user']


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'mood_tag', 'ai_sentiment_score', 'created_at']
    search_fields = ['user__username', 'title', 'content']
    list_filter = ['mood_tag', 'created_at']
    readonly_fields = ['created_at', 'updated_at', 'ai_sentiment_score', 'ai_summary', 'ai_themes']
    ordering = ['-created_at']


@admin.register(MentalHealthScore)
class MentalHealthScoreAdmin(admin.ModelAdmin):
    list_display = ['user', 'week_start', 'overall_score', 'avg_mood', 'avg_sleep', 'avg_stress', 'avg_social', 'avg_energy', 'ai_trend']
    search_fields = ['user__username']
    list_filter = ['week_start', 'ai_trend']
    readonly_fields = ['ai_weekly_insight', 'ai_trend']
    ordering = ['-week_start']


@admin.register(Streak)
class StreakAdmin(admin.ModelAdmin):
    list_display = ['user', 'current_streak', 'longest_streak', 'last_checkin']
    search_fields = ['user__username']
    ordering = ['-current_streak']
