import subprocess
import sys


def test_packages_import() -> None:
    import card_game
    import deck_of_cards_sdk

    assert deck_of_cards_sdk.__name__ == "deck_of_cards_sdk"
    assert card_game.__name__ == "card_game"


def test_sdk_does_not_import_game() -> None:
    # A fresh interpreter is needed: pytest may already have imported card_game.
    code = "import sys, deck_of_cards_sdk; sys.exit('card_game' in sys.modules)"
    result = subprocess.run([sys.executable, "-c", code], check=False)

    assert result.returncode == 0
