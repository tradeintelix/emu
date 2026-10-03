"""Country name -> international calling code (core/countries.json), so a flow can take a
country name plus a national number instead of an international '+' number. Any app flow
with a country picker can use this. Codes are verified in-app where possible (e.g. WhatsApp
resolves the typed code back to a country name), so a wrong entry fails the run, never sends."""
import json
from pathlib import Path

_CODES = json.loads((Path(__file__).parent / "countries.json").read_text())
_BY_LOWER = {name.lower(): code for name, code in _CODES.items()}


def calling_code(country_name):
    """'Pakistan' -> '92'. Raises with a clear message if the name isn't in countries.json."""
    code = _BY_LOWER.get(country_name.strip().lower())
    if not code:
        raise KeyError(
            f"No calling code for {country_name!r} in core/countries.json. "
            f"Add it, or pass the number in international format (--phone +<code><number>).")
    return code
