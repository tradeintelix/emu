"""Country name -> international calling code (core/countries.json), so a flow can take a
country name plus a national number instead of an international '+' number. Any app flow
with a country picker can use this. Codes are verified in-app where possible (e.g. WhatsApp
resolves the typed code back to a country name), so a wrong entry fails the run, never sends."""
import collections
import json
from pathlib import Path

_CODES = json.loads((Path(__file__).parent / "countries.json").read_text())
_BY_LOWER = {name.lower(): code for name, code in _CODES.items()}
_BY_CODE = collections.defaultdict(list)
for _name, _code in _CODES.items():
    _BY_CODE[_code].append(_name)


def calling_code(country_name):
    """'Pakistan' -> '92'. Raises with a clear message if the name isn't in countries.json."""
    code = _BY_LOWER.get(country_name.strip().lower())
    if not code:
        raise KeyError(
            f"No calling code for {country_name!r} in core/countries.json. "
            f"Add it, or pass the number in international format (--phone +<code><number>).")
    return code


def country_for_digits(digits):
    """'263781815247' -> 'Zimbabwe': calling codes are prefix-free (targets/apps/whatsapp/pages/
    phone_page.py relies on the same property), so the first of length 1/2/3 that matches a known
    code is THE code - except '1' (US/Canada) and '7' (Russia/Kazakhstan), which this raises on
    since the number alone can't say which."""
    for length in (1, 2, 3):
        names = _BY_CODE.get(digits[:length])
        if names:
            if len(names) > 1:
                raise KeyError(
                    f"Calling code +{digits[:length]} is shared by {', '.join(names)}; "
                    f"pass --phone-country to say which one.")
            return names[0]
    raise KeyError(f"No calling code in core/countries.json matches {digits!r}.")
