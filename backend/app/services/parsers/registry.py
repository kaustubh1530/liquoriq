"""
services/parsers/registry.py — Parser registry

Maps a ReportSource to the right parser class.
When we add DoorDash or Uber Eats parsers in the future, we register them here.

Usage (in parse_service.py):
    parser = get_parser(ReportSource.POS)
    rows = parser.parse(file_path)
"""

from app.models.uploaded_report import ReportSource
from app.services.parsers.adventpos_parser import AdvEntPOSParser
from app.services.parsers.generic_parser import GenericParser

# ── Registry: source → (parser_class, channel_label) ─────────────────────────
_REGISTRY = {
    ReportSource.POS:       (AdvEntPOSParser, "pos"),
    ReportSource.WEBSITE:   (GenericParser,   "website"),
    ReportSource.UBER_EATS: (GenericParser,   "uber_eats"),
    ReportSource.DOORDASH:  (GenericParser,   "doordash"),
    ReportSource.OTHER:     (GenericParser,   "other"),
}


def get_parser(source: ReportSource):
    """
    Return an instantiated parser for the given report source.
    Falls back to GenericParser if no specific parser is registered.
    """
    parser_class, channel = _REGISTRY.get(source, (GenericParser, "other"))
    return parser_class(channel=channel)