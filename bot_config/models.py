from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class ConfigCategory(models.Model):
    """Categories for organizing configuration settings"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)
    
    class Meta:
        verbose_name_plural = "Config Categories"
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name


class ConfigSetting(models.Model):
    """Key-value configuration settings with type enforcement"""
    SETTING_TYPES = [
        ('string', 'String'),
        ('integer', 'Integer'),
        ('float', 'Float'),
        ('boolean', 'Boolean'),
        ('json', 'JSON'),
    ]
    
    category = models.ForeignKey(ConfigCategory, on_delete=models.CASCADE, related_name='settings')
    key = models.CharField(max_length=200, unique=True)
    value = models.TextField()
    value_type = models.CharField(max_length=20, choices=SETTING_TYPES, default='string')
    description = models.TextField(blank=True)
    default_value = models.TextField(blank=True)
    is_secret = models.BooleanField(default=False, help_text="Hide value in admin interface")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category__order', 'category__name', 'key']
    
    def __str__(self):
        return f"{self.category.name}: {self.key}"
    
    def get_typed_value(self):
        """Return value converted to proper Python type"""
        if self.value_type == 'boolean':
            return self.value.lower() in ('true', '1', 'yes', 'on')
        elif self.value_type == 'integer':
            return int(self.value)
        elif self.value_type == 'float':
            return float(self.value)
        elif self.value_type == 'json':
            import json
            return json.loads(self.value)
        return self.value


class TranslationPrompt(models.Model):
    """Translation prompts and system messages"""
    PROMPT_TYPES = [
        ('system', 'System Prompt'),
        ('user', 'User Prompt'),
        ('style', 'Style Instructions'),
        ('linking', 'Linking Rules'),
        ('anti_repetition', 'Anti-Repetition Rules'),
    ]
    
    name = models.CharField(max_length=200, unique=True)
    prompt_type = models.CharField(max_length=20, choices=PROMPT_TYPES)
    content = models.TextField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    version = models.CharField(max_length=50, default='1.0')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['prompt_type', 'name']
    
    def __str__(self):
        return f"{self.get_prompt_type_display()}: {self.name}"


class AIModelConfig(models.Model):
    """AI model configuration parameters"""
    MODEL_PROVIDERS = [
        ('anthropic', 'Anthropic (Claude)'),
        ('openai', 'OpenAI'),
        ('google', 'Google'),
        ('mistral', 'Mistral'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    provider = models.CharField(max_length=20, choices=MODEL_PROVIDERS)
    model_id = models.CharField(max_length=200)
    max_tokens = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(200000)])
    temperature = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(2.0)])
    thinking_budget_tokens = models.IntegerField(null=True, blank=True)
    timeout_seconds = models.IntegerField(default=30)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_default', 'provider', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.provider})"
    
    def save(self, *args, **kwargs):
        # Ensure only one default model
        if self.is_default:
            AIModelConfig.objects.filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)


class ProcessingLimits(models.Model):
    """Timeout and processing limit configurations"""
    name = models.CharField(max_length=100, unique=True)
    batch_timeout_seconds = models.IntegerField(default=300)
    batch_message_limit = models.IntegerField(default=10)
    fetch_timeout_seconds = models.IntegerField(default=60)
    processing_timeout_seconds = models.IntegerField(default=180)
    rate_limit_sleep_seconds = models.FloatField(default=1.0)
    timeout_buffer_seconds = models.IntegerField(default=30)
    environment = models.CharField(max_length=20, choices=[
        ('dev', 'Development'),
        ('prod', 'Production')
    ], default='prod')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['environment', 'name']
        verbose_name_plural = "Processing Limits"
    
    def __str__(self):
        return f"{self.name} ({self.environment})"


class TranslationMemoryConfig(models.Model):
    """Translation memory settings"""
    name = models.CharField(max_length=100, unique=True)
    default_recall_k = models.IntegerField(default=10)
    overfetch_multiplier = models.IntegerField(default=4)
    recency_weight = models.FloatField(default=0.3, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    embedding_model = models.CharField(max_length=100, default='text-embedding-ada-002')
    embedding_timeout_seconds = models.IntegerField(default=30)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_active', 'name']
    
    def __str__(self):
        return self.name


class ArticleExtractionConfig(models.Model):
    """Article extraction settings"""
    domain = models.CharField(max_length=200, unique=True)
    language_code = models.CharField(max_length=10)
    min_article_length = models.IntegerField(default=50)
    timeout_seconds = models.IntegerField(default=30)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['domain']
    
    def __str__(self):
        return f"{self.domain} → {self.language_code}"


class MessageTemplate(models.Model):
    """Message templates and formatting"""
    TEMPLATE_TYPES = [
        ('footer', 'Footer Template'),
        ('link', 'Link Format'),
        ('error', 'Error Message'),
        ('success', 'Success Message'),
        ('log', 'Log Message'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES)
    template = models.TextField()
    description = models.TextField(blank=True)
    variables = models.TextField(blank=True, help_text="Available variables (comma-separated)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['template_type', 'name']
    
    def __str__(self):
        return f"{self.get_template_type_display()}: {self.name}"


class EnvironmentConfig(models.Model):
    """Environment-specific configurations"""
    environment = models.CharField(max_length=20, unique=True, choices=[
        ('dev', 'Development'),
        ('prod', 'Production')
    ])
    session_name_pattern = models.CharField(max_length=100)
    log_level = models.CharField(max_length=20, choices=[
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical')
    ], default='INFO')
    log_format = models.CharField(max_length=200, default='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['environment']
    
    def __str__(self):
        return f"{self.environment} Environment"


class ConfigChangeLog(models.Model):
    """Track configuration changes for audit purposes"""
    config_type = models.CharField(max_length=100)  # Model name
    config_id = models.CharField(max_length=100)    # Object ID
    field_name = models.CharField(max_length=100)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    changed_by = models.CharField(max_length=100, blank=True)  # User or system
    changed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-changed_at']
    
    def __str__(self):
        return f"{self.config_type}.{self.field_name} changed at {self.changed_at}"
