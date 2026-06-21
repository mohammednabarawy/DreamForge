import json
import sys
from argparse import Namespace
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dreamforge_cli_inventory import handle_inventory_arguments, recommended_generation_models


def test_recommend_models_json(capsys):
    handled = handle_inventory_arguments(
        Namespace(
            recommend_models=True,
            profile="16gb",
            inventory_json=True,
            inventory_limit=None,
        )
    )
    assert handled is True
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "success"
    assert payload["profile"] == "16gb"
    assert isinstance(payload["models"], list)
    assert payload["models"] == recommended_generation_models(profile="16gb")


def test_check_model_deps_unknown_model_json(capsys):
    handled = handle_inventory_arguments(
        Namespace(
            check_model_deps="definitely-not-a-real-model-name-xyz",
            inventory_json=True,
        )
    )
    assert handled is True
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"
