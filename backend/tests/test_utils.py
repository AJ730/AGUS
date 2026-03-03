"""
Tests for app.utils
=====================
Covers deep_get(), resolve_country_coords(), and COUNTRY_COORDS dict.
"""

from __future__ import annotations

import pytest

from app.utils import COUNTRY_COORDS, deep_get, resolve_country_coords


# ===================================================================
#  COUNTRY_COORDS
# ===================================================================

class TestCountryCoords:
    """Tests for the COUNTRY_COORDS lookup dict."""

    def test_has_many_countries(self):
        """COUNTRY_COORDS should contain a substantial number of countries."""
        assert len(COUNTRY_COORDS) > 90

    def test_us_coords(self):
        """United States should have approximately correct coordinates."""
        lat, lon = COUNTRY_COORDS["United States"]
        assert 25.0 < lat < 50.0
        assert -130.0 < lon < -60.0

    def test_uk_coords(self):
        """United Kingdom should have approximately correct coordinates."""
        lat, lon = COUNTRY_COORDS["United Kingdom"]
        assert 49.0 < lat < 61.0
        assert -10.0 < lon < 3.0

    def test_ukraine_coords(self):
        """Ukraine should have approximately correct coordinates."""
        lat, lon = COUNTRY_COORDS["Ukraine"]
        assert 44.0 < lat < 53.0
        assert 22.0 < lon < 41.0

    def test_china_coords(self):
        """China should have approximately correct coordinates."""
        lat, lon = COUNTRY_COORDS["China"]
        assert 18.0 < lat < 54.0
        assert 73.0 < lon < 135.0

    def test_alias_dem_rep_congo(self):
        """The alias 'Dem. Rep. Congo' should resolve to the same coords as the full name."""
        assert COUNTRY_COORDS["Dem. Rep. Congo"] == COUNTRY_COORDS["Democratic Republic of the Congo"]

    def test_alias_drc(self):
        """'DRC' alias should resolve to the same coords."""
        assert COUNTRY_COORDS["DRC"] == COUNTRY_COORDS["Democratic Republic of the Congo"]

    def test_alias_turkiye(self):
        """'Turkiye' alias should match Turkey coords."""
        assert COUNTRY_COORDS["Turkiye"] == COUNTRY_COORDS["Turkey"]

    def test_alias_palestine(self):
        """'State of Palestine' alias should match Palestine."""
        assert COUNTRY_COORDS["State of Palestine"] == COUNTRY_COORDS["Palestine"]

    def test_coords_are_tuples_of_two_floats(self):
        """All entries should be (lat, lon) tuples/pairs."""
        for country, coords in COUNTRY_COORDS.items():
            assert len(coords) == 2, f"Expected 2-element tuple for {country}"
            lat, lon = coords
            assert isinstance(lat, (int, float)), f"Lat for {country} is not numeric"
            assert isinstance(lon, (int, float)), f"Lon for {country} is not numeric"

    def test_all_latitudes_in_range(self):
        """All latitudes should be between -90 and 90."""
        for country, (lat, lon) in COUNTRY_COORDS.items():
            assert -90.0 <= lat <= 90.0, f"Invalid latitude for {country}: {lat}"

    def test_all_longitudes_in_range(self):
        """All longitudes should be between -180 and 180."""
        for country, (lat, lon) in COUNTRY_COORDS.items():
            assert -180.0 <= lon <= 180.0, f"Invalid longitude for {country}: {lon}"


# ===================================================================
#  deep_get()
# ===================================================================

class TestDeepGet:
    """Tests for the deep_get() utility function."""

    def test_simple_key(self):
        """Single-level key lookup."""
        d = {"name": "Alice"}
        assert deep_get(d, "name") == "Alice"

    def test_nested_key(self):
        """Dot-separated path to nested value."""
        d = {"level1": {"level2": {"level3": "value"}}}
        assert deep_get(d, "level1.level2.level3") == "value"

    def test_missing_key_returns_default(self):
        """Missing key should return the default (None)."""
        d = {"name": "Alice"}
        assert deep_get(d, "age") is None

    def test_missing_key_custom_default(self):
        """Missing key should return the custom default."""
        d = {"name": "Alice"}
        assert deep_get(d, "age", default=0) == 0

    def test_missing_nested_key(self):
        """Missing intermediate key should return default."""
        d = {"level1": {"level2": "value"}}
        assert deep_get(d, "level1.nonexistent.level3") is None

    def test_non_dict_intermediate(self):
        """If an intermediate value is not a dict, return default."""
        d = {"level1": "not_a_dict"}
        assert deep_get(d, "level1.level2") is None

    def test_empty_dict(self):
        """Empty dict should return default for any path."""
        d = {}
        assert deep_get(d, "anything") is None

    def test_deeply_nested_path(self):
        """4-level deep nesting should work."""
        d = {"a": {"b": {"c": {"d": 42}}}}
        assert deep_get(d, "a.b.c.d") == 42

    def test_returns_sub_dict(self):
        """deep_get can return a sub-dictionary."""
        d = {"a": {"b": {"inner": True}}}
        result = deep_get(d, "a.b")
        assert result == {"inner": True}

    def test_value_is_zero(self):
        """Falsy value (0) should be returned, not the default."""
        d = {"count": 0}
        assert deep_get(d, "count") == 0

    def test_value_is_empty_string(self):
        """Falsy value (empty string) should be returned."""
        d = {"name": ""}
        assert deep_get(d, "name") == ""

    def test_value_is_false(self):
        """Falsy value (False) should be returned."""
        d = {"active": False}
        assert deep_get(d, "active") is False

    def test_value_is_none_explicitly(self):
        """Explicit None value should be returned."""
        d = {"value": None}
        assert deep_get(d, "value") is None


# ===================================================================
#  resolve_country_coords()
# ===================================================================

class TestResolveCountryCoords:
    """Tests for the resolve_country_coords() function."""

    def test_direct_lat_lon(self):
        """Item with direct latitude/longitude should return those coords."""
        item = {"latitude": 48.85, "longitude": 2.35}
        lat, lon = resolve_country_coords(item)
        assert lat == 48.85
        assert lon == 2.35

    def test_lat_lon_shorthand(self):
        """Item with lat/lon shorthand should resolve."""
        item = {"lat": 40.71, "lon": -74.01}
        lat, lon = resolve_country_coords(item)
        assert lat == 40.71
        assert lon == -74.01

    def test_nested_reliefweb_coords(self):
        """Item with nested ReliefWeb-style coordinates should resolve."""
        item = {
            "fields": {
                "primary_country": {
                    "location": {"lat": 35.86, "lon": 104.20},
                    "name": "China",
                },
            },
        }
        lat, lon = resolve_country_coords(item)
        assert lat == 35.86
        assert lon == 104.20

    def test_fallback_to_country_centroid_via_primary_country_dict(self):
        """When no coords present, should fall back to country centroid."""
        item = {
            "fields": {
                "primary_country": {"name": "Ukraine"},
            },
        }
        lat, lon = resolve_country_coords(item)
        expected_lat, expected_lon = COUNTRY_COORDS["Ukraine"]
        assert lat == expected_lat
        assert lon == expected_lon

    def test_fallback_to_country_centroid_via_primary_country_string(self):
        """When primary_country is a string, should use it for lookup."""
        item = {
            "fields": {
                "primary_country": "Syria",
            },
        }
        lat, lon = resolve_country_coords(item)
        expected_lat, expected_lon = COUNTRY_COORDS["Syria"]
        assert lat == expected_lat
        assert lon == expected_lon

    def test_fallback_to_country_list(self):
        """When primary_country absent, should try fields.country list."""
        item = {
            "fields": {
                "country": [{"name": "Somalia"}],
            },
        }
        lat, lon = resolve_country_coords(item)
        expected_lat, expected_lon = COUNTRY_COORDS["Somalia"]
        assert lat == expected_lat
        assert lon == expected_lon

    def test_unknown_country_returns_zero(self):
        """Unknown country should return (0.0, 0.0)."""
        item = {
            "fields": {
                "primary_country": {"name": "Atlantis"},
            },
        }
        lat, lon = resolve_country_coords(item)
        assert lat == 0.0
        assert lon == 0.0

    def test_empty_item_returns_zero(self):
        """Empty dict should return (0.0, 0.0)."""
        lat, lon = resolve_country_coords({})
        assert lat == 0.0
        assert lon == 0.0

    def test_string_numeric_coords_converted(self):
        """String latitude/longitude should be converted to float."""
        item = {"latitude": "51.5", "longitude": "-0.12"}
        lat, lon = resolve_country_coords(item)
        assert lat == 51.5
        assert lon == -0.12

    def test_invalid_string_coords_fallback(self):
        """Non-numeric string coords should trigger fallback."""
        item = {
            "latitude": "not_a_number",
            "longitude": "also_not",
            "fields": {
                "primary_country": {"name": "France"},
            },
        }
        lat, lon = resolve_country_coords(item)
        expected_lat, expected_lon = COUNTRY_COORDS["France"]
        assert lat == expected_lat
        assert lon == expected_lon

    def test_no_fields_no_coords_returns_zero(self):
        """Item with no fields and no coords returns (0.0, 0.0)."""
        item = {"title": "Something"}
        lat, lon = resolve_country_coords(item)
        assert lat == 0.0
        assert lon == 0.0

    def test_empty_country_list_returns_zero(self):
        """Empty country list should return (0.0, 0.0)."""
        item = {
            "fields": {
                "country": [],
            },
        }
        lat, lon = resolve_country_coords(item)
        assert lat == 0.0
        assert lon == 0.0
