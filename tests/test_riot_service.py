import unittest
from unittest.mock import patch, MagicMock
from src.services.riot_service import RiotService

class TestRiotService(unittest.TestCase):

    @patch('src.services.riot_service.requests.get')
    def test_get_player_stats(self, mock_get):
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'rank': 'Gold',
            'average_position': 4.2
        }
        mock_get.return_value = mock_response
        service = RiotService(api_key='test_api_key')

        # Act
        stats = service.get_player_stats('test_username')

        # Assert
        self.assertEqual(stats['rank'], 'Gold')
        self.assertAlmostEqual(stats['average_position'], 4.2)

    @patch('src.services.riot_service.requests.get')
    def test_get_last_games(self, mock_get):
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'games': [
                {'position': 3},
                {'position': 5},
                {'position': 2},
                {'position': 4},
                {'position': 1}
            ]
        }
        mock_get.return_value = mock_response
        service = RiotService(api_key='test_api_key')

        # Act
        last_games = service.get_last_games('test_username')

        # Assert
        self.assertEqual(len(last_games), 5)
        self.assertEqual(last_games[0]['position'], 3)

if __name__ == '__main__':
    unittest.main()