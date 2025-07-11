from django.contrib import admin
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin
from .models import (
    ConfigCategory, ConfigSetting, TranslationPrompt, AIModelConfig,
    ProcessingLimits, TranslationMemoryConfig, ArticleExtractionConfig,
    MessageTemplate, EnvironmentConfig, ConfigChangeLog
)


@admin.register(ConfigCategory)
class ConfigCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'order', 'setting_count')
    list_editable = ('order',)
    ordering = ('order', 'name')
    search_fields = ('name', 'description')
    
    def setting_count(self, obj):
        return obj.settings.count()
    setting_count.short_description = 'Settings Count'


@admin.register(ConfigSetting)
class ConfigSettingAdmin(ImportExportModelAdmin):
    list_display = ('key', 'category', 'value_type', 'is_secret', 'updated_at')
    list_filter = ('category', 'value_type', 'is_secret', 'created_at')
    search_fields = ('key', 'description', 'value')
    list_editable = ('value_type',)
    ordering = ('category__order', 'category__name', 'key')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('category', 'key', 'description')
        }),
        ('Value Configuration', {
            'fields': ('value', 'value_type', 'default_value', 'is_secret')
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj and obj.is_secret:
            # Hide value for secret fields in admin
            form.base_fields['value'].widget.attrs['type'] = 'password'
        return form


@admin.register(TranslationPrompt)
class TranslationPromptAdmin(ImportExportModelAdmin):
    list_display = ('name', 'prompt_type', 'is_active', 'version', 'updated_at')
    list_filter = ('prompt_type', 'is_active', 'created_at')
    search_fields = ('name', 'description', 'content')
    list_editable = ('is_active',)
    ordering = ('prompt_type', 'name')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'prompt_type', 'description', 'version')
        }),
        ('Prompt Content', {
            'fields': ('content',),
            'classes': ('wide',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Make content field larger for editing prompts
        form.base_fields['content'].widget.attrs['rows'] = 20
        form.base_fields['content'].widget.attrs['cols'] = 80
        return form


@admin.register(AIModelConfig)
class AIModelConfigAdmin(ImportExportModelAdmin):
    list_display = ('name', 'provider', 'model_id', 'max_tokens', 'temperature', 'is_default', 'updated_at')
    list_filter = ('provider', 'is_default', 'created_at')
    search_fields = ('name', 'model_id')
    list_editable = ('is_default',)
    ordering = ('-is_default', 'provider', 'name')
    
    fieldsets = (
        ('Basic Configuration', {
            'fields': ('name', 'provider', 'model_id', 'is_default')
        }),
        ('Model Parameters', {
            'fields': ('max_tokens', 'temperature', 'thinking_budget_tokens', 'timeout_seconds')
        }),
    )
    
    actions = ['make_default', 'remove_default']
    
    def make_default(self, request, queryset):
        # Ensure only one default model
        AIModelConfig.objects.update(is_default=False)
        queryset.update(is_default=True)
    make_default.short_description = "Set as default model"
    
    def remove_default(self, request, queryset):
        queryset.update(is_default=False)
    remove_default.short_description = "Remove default status"


@admin.register(ProcessingLimits)
class ProcessingLimitsAdmin(ImportExportModelAdmin):
    list_display = ('name', 'environment', 'batch_timeout_seconds', 'batch_message_limit', 'updated_at')
    list_filter = ('environment', 'created_at')
    search_fields = ('name',)
    ordering = ('environment', 'name')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'environment')
        }),
        ('Batch Processing', {
            'fields': ('batch_timeout_seconds', 'batch_message_limit')
        }),
        ('Timeouts', {
            'fields': ('fetch_timeout_seconds', 'processing_timeout_seconds', 'timeout_buffer_seconds')
        }),
        ('Rate Limiting', {
            'fields': ('rate_limit_sleep_seconds',)
        }),
    )


@admin.register(TranslationMemoryConfig)
class TranslationMemoryConfigAdmin(ImportExportModelAdmin):
    list_display = ('name', 'default_recall_k', 'overfetch_multiplier', 'recency_weight', 'is_active', 'updated_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'embedding_model')
    list_editable = ('is_active',)
    ordering = ('-is_active', 'name')
    
    fieldsets = (
        ('Basic Configuration', {
            'fields': ('name', 'is_active')
        }),
        ('Memory Parameters', {
            'fields': ('default_recall_k', 'overfetch_multiplier', 'recency_weight')
        }),
        ('Embedding Configuration', {
            'fields': ('embedding_model', 'embedding_timeout_seconds')
        }),
    )


@admin.register(ArticleExtractionConfig)
class ArticleExtractionConfigAdmin(ImportExportModelAdmin):
    list_display = ('domain', 'language_code', 'min_article_length', 'timeout_seconds', 'is_active', 'updated_at')
    list_filter = ('language_code', 'is_active', 'created_at')
    search_fields = ('domain',)
    list_editable = ('is_active',)
    ordering = ('domain',)
    
    fieldsets = (
        ('Domain Configuration', {
            'fields': ('domain', 'language_code', 'is_active')
        }),
        ('Extraction Settings', {
            'fields': ('min_article_length', 'timeout_seconds')
        }),
    )


@admin.register(MessageTemplate)
class MessageTemplateAdmin(ImportExportModelAdmin):
    list_display = ('name', 'template_type', 'is_active', 'variables_display', 'updated_at')
    list_filter = ('template_type', 'is_active', 'created_at')
    search_fields = ('name', 'template', 'variables')
    list_editable = ('is_active',)
    ordering = ('template_type', 'name')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'template_type', 'description', 'is_active')
        }),
        ('Template Configuration', {
            'fields': ('template', 'variables'),
            'classes': ('wide',)
        }),
    )
    
    def variables_display(self, obj):
        if obj.variables:
            return format_html('<span style="font-family: monospace;">{}</span>', obj.variables)
        return '-'
    variables_display.short_description = 'Available Variables'
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Make template field larger
        form.base_fields['template'].widget.attrs['rows'] = 5
        form.base_fields['template'].widget.attrs['cols'] = 80
        return form


@admin.register(EnvironmentConfig)
class EnvironmentConfigAdmin(ImportExportModelAdmin):
    list_display = ('environment', 'session_name_pattern', 'log_level', 'is_active', 'updated_at')
    list_filter = ('environment', 'log_level', 'is_active', 'created_at')
    search_fields = ('session_name_pattern', 'log_format')
    list_editable = ('is_active',)
    ordering = ('environment',)
    
    fieldsets = (
        ('Environment Settings', {
            'fields': ('environment', 'is_active')
        }),
        ('Session Configuration', {
            'fields': ('session_name_pattern',)
        }),
        ('Logging Configuration', {
            'fields': ('log_level', 'log_format'),
            'classes': ('wide',)
        }),
    )


@admin.register(ConfigChangeLog)
class ConfigChangeLogAdmin(admin.ModelAdmin):
    list_display = ('config_type', 'config_id', 'field_name', 'changed_by', 'changed_at')
    list_filter = ('config_type', 'changed_at', 'changed_by')
    search_fields = ('config_type', 'config_id', 'field_name', 'old_value', 'new_value')
    readonly_fields = ('config_type', 'config_id', 'field_name', 'old_value', 'new_value', 'changed_by', 'changed_at')
    ordering = ('-changed_at',)
    
    # Make this read-only since it's an audit log
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


# Customize the admin site
admin.site.site_header = 'Telegram Zoomer Bot Configuration'
admin.site.site_title = 'Bot Admin'
admin.site.index_title = 'Configuration Management'
