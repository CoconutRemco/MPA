from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from unittest.mock import patch
from .views import spotify_request

class SpotifyRequestViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()

    @patch('requests.get')
    def test_spotify_request_view(self, mock_get):
        # Mock the response from Spotify API
        mock_get.return_value.json.return_value = {
            'items': [
                {'name': 'Test Playlist 1'},
                {'name': 'Test Playlist 2'},
            ]
        }

        # Create a mock request
        request = self.factory.get(reverse('spotify_request'))

        # Add session data to the mock request
        request.session = {'oauth_token': {'access_token': 'mock_access_token'}}

        # Call the view with the mock request
        response = spotify_request(request)

        self.assertEqual(response.status_code, 200)  # Check if OK
        self.assertContains(response, 'Test Playlist 1')  # Check if the response contains the playlist name
        self.assertContains(response, 'Test Playlist 2')  # Check if the response contains the playlist name
