from django import forms
from .models import Song, Playlist

class PlaylistForm(forms.ModelForm):
    songs = forms.ModelMultipleChoiceField(queryset=Song.objects.all(), required=False)

    class Meta:
        model = Playlist
        fields = ['name', 'songs']
