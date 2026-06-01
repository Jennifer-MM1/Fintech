from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    is_client = models.BooleanField(default=False, help_text="Designates whether the user is a client.")
    
    def __str__(self):
        return self.username
