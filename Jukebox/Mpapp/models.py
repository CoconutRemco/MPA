from django.db import models
from django.contrib.auth.models import User
from django.db.models import Manager
from django.contrib.auth import get_user_model

class PublishedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status='published')


class Genre(models.Model):
    name = models.CharField(max_length=200)
    published = PublishedManager()
    objects = models.Manager()


def get_default_user():
    User = get_user_model()
    default_user = User.objects.first()
    if default_user:
        return default_user.id
    else:
        # Handle the case where there are no users in the system
        # This could involve creating a new user and returning their ID
        pass


class Song(models.Model):
    title = models.CharField(max_length=200)
    artist = models.CharField(max_length=200)
    spotify_url = models.URLField(unique=True)
    image_url = models.URLField(null=True, blank=True)

    def __str__(self):
        return self.title

    def to_json(self):
        return {
            'id': self.id,
            'title': self.title,
            'artist': self.artist,
            'spotify_url': self.spotify_url,
            'image_url': self.image_url,
            # include other fields as needed
        }

class Playlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    spotify_id = models.CharField(max_length=200, unique=True)
    href = models.URLField()
    owner = models.CharField(max_length=200)
    image_url = models.URLField()
    total_tracks = models.IntegerField()
    songs = models.ManyToManyField(Song)
    status = models.CharField(max_length=200)  # Add this line

    def __str__(self):
        return self.name
