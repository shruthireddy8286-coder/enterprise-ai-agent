"""
tests/test_web_actions.py

Covers: literal "open <site>" parsing, task-style booking/gaming intent
routing, and that the browser-launch call is invoked correctly (mocked so
tests run headless / without actually opening a browser).
"""

from unittest.mock import patch

from web_actions import open_in_browser, parse_action_command


def test_parse_known_site_youtube():
    result = parse_action_command("open youtube")
    assert result is not None
    display_name, url = result
    assert display_name == "youtube"
    assert url == "https://www.youtube.com"


def test_parse_go_to_phrasing():
    result = parse_action_command("go to netflix")
    assert result is not None
    _, url = result
    assert url == "https://www.netflix.com"


def test_parse_raw_domain():
    result = parse_action_command("open example.com")
    assert result is not None
    _, url = result
    assert url == "https://example.com"


def test_parse_unknown_site_falls_back_to_dot_com():
    result = parse_action_command("open somebrandnewsite")
    assert result is not None
    _, url = result
    assert url == "https://www.somebrandnewsite.com"


def test_book_a_cab_routes_to_uber():
    result = parse_action_command("can you book a cab for me")
    assert result is not None
    display_name, url = result
    assert url == "https://www.uber.com"
    assert "Uber" in display_name


def test_book_bus_tickets_routes_to_redbus():
    result = parse_action_command("I need to book bus tickets to Chennai")
    assert result is not None
    _, url = result
    assert url == "https://www.redbus.in"


def test_book_train_routes_to_irctc():
    result = parse_action_command("help me with train booking")
    assert result is not None
    _, url = result
    assert url == "https://www.irctc.co.in"


def test_book_flight_routes_to_makemytrip():
    result = parse_action_command("book a flight to Delhi")
    assert result is not None
    _, url = result
    assert url == "https://www.makemytrip.com"


def test_online_games_routes_to_crazygames():
    result = parse_action_command("open online games")
    assert result is not None
    _, url = result
    assert url == "https://www.crazygames.com"


def test_play_some_games_routes_to_crazygames():
    result = parse_action_command("I'm bored, play some games")
    assert result is not None
    _, url = result
    assert url == "https://www.crazygames.com"


def test_order_food_routes_to_swiggy():
    result = parse_action_command("order food for dinner")
    assert result is not None
    _, url = result
    assert url == "https://www.swiggy.com"


def test_non_command_text_returns_none():
    assert parse_action_command("What is the capital of France?") is None
    assert parse_action_command("Summarize my uploaded contract.") is None
    assert parse_action_command("") is None


def test_open_in_browser_success():
    with patch("web_actions.webbrowser.open", return_value=True) as mock_open:
        result = open_in_browser("https://www.youtube.com")
    assert result is True
    mock_open.assert_called_once_with("https://www.youtube.com", new=2)


def test_open_in_browser_handles_failure():
    with patch("web_actions.webbrowser.open", side_effect=Exception("no display")):
        result = open_in_browser("https://www.youtube.com")
    assert result is False


# ---------------------------------------------------------------- expanded categories

def test_book_a_hotel_routes_to_booking_dot_com():
    result = parse_action_command("I need to book a hotel in Goa")
    assert result is not None
    _, url = result
    assert url == "https://www.booking.com"


def test_order_groceries_routes_to_blinkit():
    result = parse_action_command("order groceries for the week")
    assert result is not None
    _, url = result
    assert url == "https://blinkit.com"


def test_order_medicine_routes_to_pharmeasy():
    result = parse_action_command("I need to order medicines urgently")
    assert result is not None
    _, url = result
    assert url == "https://pharmeasy.in"


def test_buy_online_routes_to_amazon():
    result = parse_action_command("I want to buy online today")
    assert result is not None
    _, url = result
    assert url == "https://www.amazon.com"


def test_listen_to_music_routes_to_spotify():
    result = parse_action_command("I want to listen to music")
    assert result is not None
    _, url = result
    assert url == "https://open.spotify.com"


def test_watch_a_movie_routes_to_netflix():
    result = parse_action_command("let's watch a movie tonight")
    assert result is not None
    _, url = result
    assert url == "https://www.netflix.com"


def test_start_a_video_call_routes_to_google_meet():
    result = parse_action_command("start a video call with the team")
    assert result is not None
    _, url = result
    assert url == "https://meet.google.com"


def test_take_a_course_routes_to_coursera():
    result = parse_action_command("I want to take a course on Python")
    assert result is not None
    _, url = result
    assert url == "https://www.coursera.org"


def test_find_a_job_routes_to_linkedin_jobs():
    result = parse_action_command("help me find a job")
    assert result is not None
    _, url = result
    assert url == "https://www.linkedin.com/jobs"


def test_track_my_parcel_routes_to_fedex():
    result = parse_action_command("track my parcel please")
    assert result is not None
    _, url = result
    assert url == "https://www.fedex.com"


def test_check_the_weather_routes_to_weather_dot_com():
    result = parse_action_command("check the weather for tomorrow")
    assert result is not None
    _, url = result
    assert url == "https://weather.com"


def test_open_known_brand_directly_flipkart():
    result = parse_action_command("open flipkart")
    assert result is not None
    _, url = result
    assert url == "https://www.flipkart.com"


def test_open_known_brand_directly_spotify():
    result = parse_action_command("open spotify")
    assert result is not None
    _, url = result
    assert url == "https://open.spotify.com"


def test_open_known_brand_directly_zoom():
    result = parse_action_command("open zoom")
    assert result is not None
    _, url = result
    assert url == "https://zoom.us"
