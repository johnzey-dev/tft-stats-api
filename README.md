# TFT Stats API

This project is a Flask-based API that consumes the Riot API to retrieve statistics for Teamfight Tactics (TFT). It provides endpoints to fetch a player's current rank, average position of rank, and details of their last 5 games.

## Features

- Retrieve TFT statistics for a specific username.
- Get current rank and average position of rank.
- Access details of the last 5 games played by the user.

## Project Structure

```
tft-stats-api
├── src
│   ├── main.py               # Entry point of the application
│   ├── api
│   │   ├── __init__.py       # Initializes the API package
│   │   └── routes
│   │       ├── __init__.py   # Initializes the routes package
│   │       └── stats.py       # Handles requests for TFT statistics
│   ├── services
│   │   ├── __init__.py       # Initializes the services package
│   │   └── riot_service.py    # Interacts with the Riot API
│   ├── models
│   │   ├── __init__.py       # Initializes the models package
│   │   └── stats.py          # Defines the TFT statistics model
│   └── config
│       ├── __init__.py       # Initializes the config package
│       └── settings.py       # Configuration settings
├── tests
│   ├── __init__.py           # Initializes the tests package
│   ├── test_routes.py        # Unit tests for the routes
│   └── test_riot_service.py  # Unit tests for the RiotService class
├── requirements.txt          # Project dependencies
├── .env.example              # Example environment variables
└── README.md                 # Project documentation
```

## Setup Instructions

1. Clone the repository:
   ```
   git clone <repository-url>
   cd tft-stats-api
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up your environment variables:
   - Copy `.env.example` to `.env` and fill in your Riot API key.

5. Run the application:
   ```
   python src/main.py
   ```

## Usage

To retrieve TFT statistics for a specific username, send a GET request to the following endpoint:

```
GET /api/stats/<username>
```

Replace `<username>` with the actual username of the player.

## License

This project is licensed under the MIT License.