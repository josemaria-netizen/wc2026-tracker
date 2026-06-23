"""
Country -> flag emoji. Flag emojis are built from a country's ISO 3166-1
alpha-2 code via regional-indicator characters; England/Scotland/Wales use
their special subdivision flags. Unknown teams fall back to a neutral 🏳.
"""

NAME_TO_ISO2 = {
    "Mexico": "MX", "South Korea": "KR", "Saudi Arabia": "SA", "Honduras": "HN",
    "Canada": "CA", "Belgium": "BE", "Ecuador": "EC", "Qatar": "QA",
    "Spain": "ES", "Uruguay": "UY", "Japan": "JP", "Egypt": "EG",
    "United States": "US", "Australia": "AU", "Senegal": "SN",
    "Argentina": "AR", "Austria": "AT", "Algeria": "DZ", "Jordan": "JO",
    "Brazil": "BR", "Morocco": "MA", "Haiti": "HT",
    "France": "FR", "Norway": "NO", "Ivory Coast": "CI", "New Zealand": "NZ",
    "Croatia": "HR", "Ghana": "GH", "Panama": "PA",
    "Portugal": "PT", "Colombia": "CO", "Iran": "IR", "Curacao": "CW",
    "Germany": "DE", "Switzerland": "CH", "Nigeria": "NG", "Uzbekistan": "UZ",
    "Netherlands": "NL", "Denmark": "DK", "Cameroon": "CM", "Bolivia": "BO",
    "Italy": "IT", "Poland": "PL", "Tunisia": "TN", "Costa Rica": "CR",
}

# Subdivisions without an ISO2 country code have dedicated flag emojis.
SPECIAL = {
    "England": "🏴\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F",
    "Scotland": "🏴\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F",
    "Wales": "🏴\U000E0067\U000E0062\U000E0077\U000E006C\U000E0073\U000E007F",
}


def _iso2_to_emoji(code):
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())


def flag(country):
    if country in SPECIAL:
        return SPECIAL[country]
    iso = NAME_TO_ISO2.get(country)
    return _iso2_to_emoji(iso) if iso else "🏳️"
