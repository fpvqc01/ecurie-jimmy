"""Chargement de la config YAML + secrets depuis les variables d'environnement."""
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: str | None = None, require_oanda: bool = True) -> dict:
    """require_oanda=False : pour les scripts qui n'appellent pas l'API OANDA
    (ex: export_bias.py, qui ne lit que les donnees BIS publiques)."""
    cfg_path = Path(path) if path else ROOT / "config.yaml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    cfg["oanda"]["api_key"] = os.environ.get("OANDA_API_KEY", "")
    cfg["oanda"]["account_id"] = os.environ.get("OANDA_ACCOUNT_ID", "")

    missing = [name for name, val in [
        ("OANDA_API_KEY", cfg["oanda"]["api_key"]),
        ("OANDA_ACCOUNT_ID", cfg["oanda"]["account_id"]),
    ] if not val]
    if missing and require_oanda:
        sys.exit(
            "Variables d'environnement manquantes : " + ", ".join(missing)
            + "\nExemple (PowerShell) :\n"
            + '  $env:OANDA_API_KEY = "ton-jeton"\n'
            + '  $env:OANDA_ACCOUNT_ID = "101-002-1234567-001"'
        )

    env = cfg["oanda"]["environment"]
    if env == "live" and not cfg["oanda"].get("allow_live"):
        sys.exit(
            "SECURITE : environment=live mais allow_live=false dans config.yaml.\n"
            "Le bot ne tournera pas en argent reel tant que tu ne l'actives pas "
            "explicitement (et tu ne devrais pas avant des semaines de demo concluante)."
        )
    if env not in ("practice", "live"):
        sys.exit(f"environment invalide : {env}")
    return cfg
