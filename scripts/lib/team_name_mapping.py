#!/usr/bin/env python3
"""
Team name normalization library for sportsbook odds data.

Maps team names from various formats (abbreviations, full names) to ESPN abbreviations.
Used by ETL pipeline to normalize team names before ESPN game mapping.

Design Pattern: Dictionary Lookup with Fuzzy Matching Fallback
Algorithm: O(1) for exact match, O(n) for fuzzy match where n = number of team mappings
"""

from __future__ import annotations

# Mapping dictionary: various team name formats -> ESPN abbreviations
# Includes abbreviations from nba_2008-2025.csv and full names from nba_main_lines.csv
TEAM_NAME_MAPPING = {
    # Atlanta Hawks
    "atl": "ATL",
    "atlanta": "ATL",
    "Atlanta Hawks": "ATL",
    "Hawks": "ATL",
    
    # Boston Celtics
    "bos": "BOS",
    "boston": "BOS",
    "Boston Celtics": "BOS",
    "Celtics": "BOS",
    
    # Brooklyn Nets
    "bkn": "BKN",
    "brooklyn": "BKN",
    "Brooklyn Nets": "BKN",
    "Nets": "BKN",
    "nj": "BKN",  # New Jersey (old name)
    "new jersey": "BKN",
    
    # Charlotte Hornets
    "cha": "CHA",
    "charlotte": "CHA",
    "Charlotte Hornets": "CHA",
    "Hornets": "CHA",
    "cho": "CHA",  # Alternative abbreviation
    
    # Chicago Bulls
    "chi": "CHI",
    "chicago": "CHI",
    "Chicago Bulls": "CHI",
    "Bulls": "CHI",
    
    # Cleveland Cavaliers
    "cle": "CLE",
    "cleveland": "CLE",
    "Cleveland Cavaliers": "CLE",
    "Cavaliers": "CLE",
    "Cavs": "CLE",
    
    # Dallas Mavericks
    "dal": "DAL",
    "dallas": "DAL",
    "Dallas Mavericks": "DAL",
    "Mavericks": "DAL",
    "Mavs": "DAL",
    
    # Denver Nuggets
    "den": "DEN",
    "denver": "DEN",
    "Denver Nuggets": "DEN",
    "Nuggets": "DEN",
    
    # Detroit Pistons
    "det": "DET",
    "detroit": "DET",
    "Detroit Pistons": "DET",
    "Pistons": "DET",
    
    # Golden State Warriors
    "gs": "GS",
    "gsw": "GS",  # Golden State Warriors (alternative)
    "golden state": "GS",
    "Golden State Warriors": "GS",
    "Warriors": "GS",
    
    # Houston Rockets
    "hou": "HOU",
    "houston": "HOU",
    "Houston Rockets": "HOU",
    "Rockets": "HOU",
    
    # Indiana Pacers
    "ind": "IND",
    "indiana": "IND",
    "Indiana Pacers": "IND",
    "Pacers": "IND",
    
    # LA Clippers
    "lac": "LAC",
    "la clippers": "LAC",
    "Los Angeles Clippers": "LAC",
    "Clippers": "LAC",
    
    # Los Angeles Lakers
    "lal": "LAL",
    "la lakers": "LAL",
    "Los Angeles Lakers": "LAL",
    "L.A. Lakers": "LAL",
    "Lakers": "LAL",
    
    # Memphis Grizzlies
    "mem": "MEM",
    "memphis": "MEM",
    "Memphis Grizzlies": "MEM",
    "Grizzlies": "MEM",
    
    # Miami Heat
    "mia": "MIA",
    "miami": "MIA",
    "Miami Heat": "MIA",
    "Heat": "MIA",
    
    # Milwaukee Bucks
    "mil": "MIL",
    "milwaukee": "MIL",
    "Milwaukee Bucks": "MIL",
    "Bucks": "MIL",
    
    # Minnesota Timberwolves
    "min": "MIN",
    "minnesota": "MIN",
    "Minnesota Timberwolves": "MIN",
    "Timberwolves": "MIN",
    "Wolves": "MIN",
    
    # New Orleans Pelicans
    "no": "NO",
    "nop": "NO",  # New Orleans Pelicans (alternative)
    "new orleans": "NO",
    "New Orleans Pelicans": "NO",
    "Pelicans": "NO",
    
    # New York Knicks
    "ny": "NY",
    "nyk": "NY",  # ESPN uses "NY" not "NYK"
    "new york": "NY",
    "New York Knicks": "NY",
    "Knicks": "NY",
    
    # Oklahoma City Thunder
    "okc": "OKC",
    "oklahoma city": "OKC",
    "Oklahoma City Thunder": "OKC",
    "Thunder": "OKC",
    
    # Orlando Magic
    "orl": "ORL",
    "orlando": "ORL",
    "Orlando Magic": "ORL",
    "Magic": "ORL",
    
    # Philadelphia 76ers
    "phi": "PHI",
    "philadelphia": "PHI",
    "Philadelphia 76ers": "PHI",
    "76ers": "PHI",
    "Sixers": "PHI",
    
    # Phoenix Suns
    "phx": "PHX",
    "phoenix": "PHX",
    "Phoenix Suns": "PHX",
    "Suns": "PHX",
    
    # Portland Trail Blazers
    "por": "POR",
    "portland": "POR",
    "Portland Trail Blazers": "POR",
    "Trail Blazers": "POR",
    "Blazers": "POR",
    
    # Sacramento Kings
    "sac": "SAC",
    "sacramento": "SAC",
    "Sacramento Kings": "SAC",
    "Kings": "SAC",
    
    # San Antonio Spurs
    "sa": "SA",
    "san antonio": "SA",
    "San Antonio Spurs": "SA",
    "Spurs": "SA",
    
    # Toronto Raptors
    "tor": "TOR",
    "toronto": "TOR",
    "Toronto Raptors": "TOR",
    "Raptors": "TOR",
    
    # Utah Jazz
    "utah": "UTAH",
    "uta": "UTAH",  # Alternative abbreviation
    "Utah Jazz": "UTAH",
    "Jazz": "UTAH",
    # Note: ESPN uses "UTAH" (4 chars) - verified in database
    
    # Washington Wizards
    "wsh": "WSH",  # ESPN uses "WSH" not "WAS"
    "was": "WSH",
    "washington": "WSH",
    "Washington Wizards": "WSH",
    "Wizards": "WSH",
}


def normalize_team_name(name: str) -> str | None:
    """
    Normalize team name to ESPN abbreviation.
    
    Args:
        name: Team name in various formats (abbreviation, full name, etc.)
    
    Returns:
        ESPN abbreviation (e.g., "LAL", "BOS") or None if no match found
    
    Examples:
        >>> normalize_team_name("Los Angeles Lakers")
        'LAL'
        >>> normalize_team_name("ny")
        'NYK'
        >>> normalize_team_name("Invalid Team")
        None
    """
    if not name:
        return None
    
    # Normalize input: lowercase, strip whitespace, normalize spaces
    normalized_input = " ".join(name.lower().strip().split())
    
    # Try exact match first (case-insensitive) - check all keys in lowercase
    for key, value in TEAM_NAME_MAPPING.items():
        if key.lower() == normalized_input:
            return value
    
    # Try with cleaned punctuation (for cases like "L.A. Lakers" -> "la lakers")
    cleaned = normalized_input.replace(".", "").replace("'", "").replace("-", " ")
    cleaned = " ".join(cleaned.split())  # Normalize spaces again
    for key, value in TEAM_NAME_MAPPING.items():
        if key.lower() == cleaned:
            return value
    
    # Try abbreviation match (if input is already an abbreviation)
    # Some abbreviations might be 2-3 characters
    if len(normalized_input) <= 3:
        # Check if it matches any key that's also short
        for key, value in TEAM_NAME_MAPPING.items():
            if key == normalized_input:
                return value
    
    # Try fuzzy matching (optional, requires fuzzywuzzy library)
    try:
        from fuzzywuzzy import fuzz
        
        best_match = None
        best_score = 0
        for key, value in TEAM_NAME_MAPPING.items():
            score = fuzz.ratio(normalized_input, key)
            if score > best_score and score >= 80:  # 80% similarity threshold
                best_match = value
                best_score = score
        
        if best_match:
            return best_match
    except ImportError:
        # fuzzywuzzy not available, skip fuzzy matching
        pass
    
    # No match found
    return None


def get_all_team_abbreviations() -> list[str]:
    """
    Get list of all ESPN team abbreviations.
    
    Returns:
        List of unique ESPN abbreviations
    """
    return sorted(set(TEAM_NAME_MAPPING.values()))


if __name__ == "__main__":
    # Test the normalization function
    test_cases = [
        ("Los Angeles Lakers", "LAL"),
        ("ny", "NYK"),
        ("Houston Rockets", "HOU"),
        ("Oklahoma City Thunder", "OKC"),
        ("cle", "CLE"),
        ("sa", "SA"),
        ("Invalid Team", None),
    ]
    
    print("Testing team name normalization:")
    for input_name, expected in test_cases:
        result = normalize_team_name(input_name)
        status = "✓" if result == expected else "✗"
        print(f"{status} {input_name!r} -> {result!r} (expected {expected!r})")

