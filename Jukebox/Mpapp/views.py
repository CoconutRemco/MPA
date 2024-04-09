from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.csrf import csrf_exempt
from requests_oauthlib import OAuth2Session
from django.http import JsonResponse, HttpResponse
from django.db.models import Case, When, Value, IntegerField
from django.shortcuts import render, redirect, get_object_or_404
from bs4 import BeautifulSoup
from django.db.models import Q
import requests
from .forms import PlaylistForm
from .models import Playlist, Song, Genre
import json
import requests
import os
import logging

savedSession = ""


logger = logging.getLogger(__name__)

# Spotify API endpoints
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"

# Client keys
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# Server side parameter
REDIRECT_URI = "http://localhost:8000/spotify_callback"
SCOPE = "user-read-private user-read-email playlist-read-private"

def home(request):
    return render(request, 'Mpapp/home.html')

def logout_view(request):
    logout(request)
    return redirect('login')  # replace 'login' with the name of your login view

def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('jukebox')  # Redirect to jukebox page
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})


def spotify_auth(request):
    oauth = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=SCOPE)
    authorization_url, state = oauth.authorization_url(SPOTIFY_AUTH_URL)

    # State is used to prevent CSRF, keep this for later.
    request.session['oauth_state'] = state
    return redirect(authorization_url)

def spotify_callback(request):
    if 'oauth_state' not in request.session:
        return redirect('spotify_auth')
    request.session['oauth_state'] = savedSession
    request.session.save()
    oauth = OAuth2Session(CLIENT_ID, state=savedSession, redirect_uri=REDIRECT_URI)
    token = oauth.fetch_token(SPOTIFY_TOKEN_URL, client_secret=CLIENT_SECRET, authorization_response=request.get_full_path())

    request.session['oauth_token'] = token

    return redirect('jukebox')


def spotify_request(request):
    if not request.user.is_authenticated or 'oauth_token' not in request.session:
        return redirect('spotify_auth')

    token = request.session['oauth_token']
    headers = {'Authorization': f"Bearer {token['access_token']}"}

    # Delete only the playlists of the current user
    Playlist.objects.filter(user=request.user).delete()
    Song.objects.filter(playlist__user=request.user).delete()

    response = requests.get('https://api.spotify.com/v1/me/playlists', headers=headers)
    data = response.json()

    if 'items' in data:
        for item in data['items']:
            playlist, created = Playlist.objects.get_or_create(
                spotify_id=item['id'],
                defaults={
                    'name': item['name'],
                    'href': item['href'],
                    'owner': item['owner']['display_name'],
                    'image_url': item['images'][0]['url'] if item['images'] else 'https://default.com',
                    'total_tracks': item['tracks']['total'],
                    'user': request.user,  # Set the user field
                    'status': 'active',  # Set the status field
                }
            )

            # Fetch the tracks for the current playlist
            response = requests.get(item['tracks']['href'], headers=headers)
            tracks_data = response.json()

            if 'items' in tracks_data:
                for track_item in tracks_data['items']:
                    track = track_item['track']
                    song, created = Song.objects.get_or_create(
                        spotify_url=track['external_urls']['spotify'],
                        defaults={
                            'title': track['name'],
                            'artist': track['artists'][0]['name'] if track['artists'] else 'Unknown Artist',
                        }
                    )
                    song.image_url = get_image_url(song.spotify_url)
                    song.save()
                    playlist.songs.add(song)

    if response.status_code != 200:
        return redirect('spotify_auth')

    request.session['oauth_token'] = token

    return redirect('jukebox')

@login_required
def jukebox(request):
    # Fetch only the playlists of the current user
    playlists = Playlist.objects.filter(user=request.user)
    songs = Song.objects.filter(playlist__user=request.user)
    return render(request, 'Mpapp/jukebox.html', {'playlists': playlists, 'songs': songs})


@login_required
def song_detail(request, song_id):
    song = get_song(request, song_id)
    return render(request, 'Mpapp/song_detail.html', {'song': song})

def get_song(request, song_id):
    token = request.session['oauth_token']
    headers = {'Authorization': f"Bearer {token['access_token']}"}

    response = requests.get(f'https://api.spotify.com/v1/tracks/{song_id}', headers=headers)
    data = response.json()

    return data

@csrf_exempt
@login_required
def create_playlist(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        song_ids = data.get('song_ids')
        playlist_name = data.get('playlist_name')

        if not song_ids or not playlist_name:
            return JsonResponse({'error': 'Missing song IDs or playlist name'}, status=400)

        try:
            songs = Song.objects.filter(id__in=song_ids)
            if len(songs) != len(song_ids):
                raise ObjectDoesNotExist
        except ObjectDoesNotExist:
            return JsonResponse({'error': 'One or more songs do not exist'}, status=400)

        # Create a new playlist with total_tracks set to the number of songs
        user_playlists_count = Playlist.objects.filter(user=request.user).count()
        spotify_id = f"{request.user.username}-{user_playlists_count + 1}"
        playlist = Playlist.objects.create(name=playlist_name, user=request.user, total_tracks=len(songs), spotify_id=spotify_id)
        playlist.songs.set(songs)
        playlist.save()

        return JsonResponse({'message': 'Playlist created successfully', 'playlist_id': playlist.id})

    else:
        form = PlaylistForm()
        all_songs = Song.objects.all()  # Fetch all songs
        return render(request, 'Mpapp/create_playlist.html', {'form': form, 'all_songs': all_songs})

@login_required
def update_playlist(request, playlist_id):
    try:
        playlist = Playlist.objects.get(id=playlist_id)
    except Playlist.DoesNotExist:
        return HttpResponse("No Playlist matches the given query.", status=404)

    all_songs = Song.objects.all()  # Fetch all songs

    if request.method == 'POST':
        form = PlaylistForm(request.POST, instance=playlist)
        if form.is_valid():
            # ... your code here ...
            pass
    else:
        form = PlaylistForm(instance=playlist)
    return render(request, 'Mpapp/update_playlist.html', {'form': form, 'playlist': playlist, 'all_songs': all_songs})

@login_required
def delete_playlist(request, playlist_id):
    try:
        playlist = Playlist.objects.get(id=playlist_id)
    except Playlist.DoesNotExist:
        return HttpResponse("No Playlist matches the given query.", status=404)

    if request.method == 'POST':
        playlist.delete()
        return redirect('jukebox')

    return render(request, 'Mpapp/delete_playlist.html', {'playlist': playlist})

@login_required
def delete_song_from_playlist(request, playlist_id, song_id):
    try:
        playlist = Playlist.objects.get(id=playlist_id)
        song = Song.objects.get(id=song_id)
    except (Playlist.DoesNotExist, Song.DoesNotExist):
        return HttpResponse("No Playlist or Song matches the given query.", status=404)

    if request.method == 'POST':
        playlist.songs.remove(song)
        return redirect('update_playlist', playlist_id=playlist.id)

    return render(request, 'Mpapp/delete_song_from_playlist.html', {'playlist': playlist, 'song': song})

@login_required
def add_song_to_playlist(request, playlist_id):
    if request.method == 'POST':
        song_id = request.POST.get('song_id')
        playlist = get_object_or_404(Playlist, id=playlist_id)
        song = get_object_or_404(Song, id=song_id)
        playlist.songs.add(song)
        return redirect('update_playlist', playlist_id=playlist.id)


def get_image_url(webpage_url):
    response = requests.get(webpage_url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # This finds the first img tag in the HTML
    img_tag = soup.find('img')

    if img_tag and 'src' in img_tag.attrs:
        return img_tag['src']

    return None

@csrf_exempt
def search_songs(request):
    print(request.body)
    if request.method == 'POST':
        data = json.loads(request.body)
        query = data.get('query')

        # Search songs by title and artist
        songs = Song.objects.filter(Q(title__icontains=query) | Q(artist__icontains=query))

        # Annotate songs with a new field 'artist_match' that is 1 if the artist matches the query, and 0 otherwise
        songs = songs.annotate(
            artist_match=Case(
                When(artist__icontains=query, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )

        # Order songs by 'artist_match' in descending order, so that songs with a matching artist come first
        songs = songs.order_by('-artist_match')

        # Convert the songs to JSON and return them
        songs_json = [song.to_json() for song in songs]
        print(songs_json)
        return JsonResponse(songs_json, safe=False)
