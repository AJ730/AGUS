"""
Tests for app.generators
==========================
Covers FlightGenerator, SubmarineGenerator, and MilitaryBaseRegistry.
Validates counts, data structure, coordinate validity, and determinism.
"""

from __future__ import annotations

import pytest

from app.generators import FlightGenerator, SubmarineGenerator, MilitaryBaseRegistry


# ===================================================================
#  FlightGenerator
# ===================================================================

class TestFlightGenerator:
    """Tests for FlightGenerator."""

    @pytest.fixture
    def generator(self) -> FlightGenerator:
        return FlightGenerator(seed=42)

    @pytest.fixture
    def flights(self, generator: FlightGenerator) -> list:
        return generator.generate()

    def test_route_count(self):
        """The ROUTES class variable should contain the expected number of routes."""
        # The ROUTES list has entries across 11 regional groups
        assert len(FlightGenerator.ROUTES) > 250
        assert len(FlightGenerator.ROUTES) < 350

    def test_generates_correct_count(self, flights: list):
        """generate() should produce one flight per route definition."""
        assert len(flights) == len(FlightGenerator.ROUTES)

    def test_flight_count_approximately_300(self, flights: list):
        """There should be approximately 300 generated flights."""
        assert 250 < len(flights) < 350

    def test_flight_has_required_keys(self, flights: list):
        """Every flight dict should have all required keys."""
        required_keys = {
            "icao24", "callsign", "origin_country",
            "longitude", "latitude", "baro_altitude",
            "on_ground", "velocity", "heading",
            "vertical_rate", "squawk", "is_military", "is_cargo",
        }
        for flight in flights:
            assert required_keys.issubset(flight.keys()), (
                f"Missing keys: {required_keys - flight.keys()}"
            )

    def test_latitude_in_valid_range(self, flights: list):
        """All flight latitudes should be between -90 and 90."""
        for flight in flights:
            assert -90.0 <= flight["latitude"] <= 90.0, (
                f"Invalid latitude {flight['latitude']} for {flight['callsign']}"
            )

    def test_longitude_in_valid_range(self, flights: list):
        """All flight longitudes should be between -180 and 180."""
        for flight in flights:
            assert -180.0 <= flight["longitude"] <= 180.0, (
                f"Invalid longitude {flight['longitude']} for {flight['callsign']}"
            )

    def test_heading_in_valid_range(self, flights: list):
        """All flight headings should be between 0 and 360."""
        for flight in flights:
            assert 0.0 <= flight["heading"] <= 360.0, (
                f"Invalid heading {flight['heading']} for {flight['callsign']}"
            )

    def test_altitude_positive(self, flights: list):
        """All flight altitudes should be positive (in-flight)."""
        for flight in flights:
            assert flight["baro_altitude"] > 0, (
                f"Non-positive altitude {flight['baro_altitude']} for {flight['callsign']}"
            )

    def test_velocity_positive(self, flights: list):
        """All flight velocities should be positive."""
        for flight in flights:
            assert flight["velocity"] > 0, (
                f"Non-positive velocity {flight['velocity']} for {flight['callsign']}"
            )

    def test_none_on_ground(self, flights: list):
        """All generated flights should be airborne (on_ground=False)."""
        for flight in flights:
            assert flight["on_ground"] is False

    def test_icao24_is_six_hex_chars(self, flights: list):
        """All ICAO24 addresses should be 6-character hex strings."""
        for flight in flights:
            icao24 = flight["icao24"]
            assert len(icao24) == 6
            int(icao24, 16)  # Should not raise ValueError

    def test_callsign_not_empty(self, flights: list):
        """All callsigns should be non-empty."""
        for flight in flights:
            assert len(flight["callsign"]) > 0

    def test_military_flights_present(self, flights: list):
        """There should be some military flights in the generated data."""
        military = [f for f in flights if f["is_military"]]
        assert len(military) > 20, "Expected at least 20 military flights"

    def test_cargo_flights_present(self, flights: list):
        """There should be some cargo flights in the generated data."""
        cargo = [f for f in flights if f["is_cargo"]]
        assert len(cargo) > 15, "Expected at least 15 cargo flights"

    def test_civilian_flights_present(self, flights: list):
        """There should be many civilian (non-military, non-cargo) flights."""
        civilian = [f for f in flights if not f["is_military"] and not f["is_cargo"]]
        assert len(civilian) > 150, "Expected at least 150 civilian flights"

    def test_deterministic_output(self):
        """Same seed should produce identical results."""
        gen1 = FlightGenerator(seed=42)
        gen2 = FlightGenerator(seed=42)
        flights1 = gen1.generate()
        flights2 = gen2.generate()
        assert len(flights1) == len(flights2)
        for f1, f2 in zip(flights1, flights2):
            assert f1 == f2

    def test_different_seeds_different_output(self):
        """Different seeds should produce different positions."""
        gen1 = FlightGenerator(seed=42)
        gen2 = FlightGenerator(seed=99)
        flights1 = gen1.generate()
        flights2 = gen2.generate()
        # At least some positions should differ
        differences = sum(
            1 for f1, f2 in zip(flights1, flights2)
            if f1["latitude"] != f2["latitude"]
        )
        assert differences > 0

    def test_squawk_codes_are_valid(self, flights: list):
        """All squawk codes should be 4-digit strings."""
        for flight in flights:
            squawk = flight["squawk"]
            assert len(squawk) == 4
            assert squawk.isdigit()

    def test_origin_countries_not_empty(self, flights: list):
        """All flights should have a non-empty origin_country."""
        for flight in flights:
            assert len(flight["origin_country"]) > 0

    def test_great_circle_point_same_origin_dest(self):
        """Great circle computation with same origin and dest should return origin."""
        lat, lon, heading = FlightGenerator._great_circle_point(
            40.0, -73.0, 40.0, -73.0, 0.5
        )
        assert abs(lat - 40.0) < 0.01
        assert abs(lon - (-73.0)) < 0.01


# ===================================================================
#  SubmarineGenerator
# ===================================================================

class TestSubmarineGenerator:
    """Tests for SubmarineGenerator."""

    @pytest.fixture
    def generator(self) -> SubmarineGenerator:
        return SubmarineGenerator(seed=42)

    @pytest.fixture
    def submarines(self, generator: SubmarineGenerator) -> list:
        return generator.generate()

    def test_fleet_definitions_exist(self):
        """FLEETS list should have submarine fleet definitions."""
        assert len(SubmarineGenerator.FLEETS) > 0

    def test_total_submarine_count(self, submarines: list):
        """Total submarines should match the sum of all fleet counts."""
        expected = sum(fleet.count for fleet in SubmarineGenerator.FLEETS)
        assert len(submarines) == expected

    def test_approximately_89_submarines(self, submarines: list):
        """There should be approximately 89 submarines."""
        assert 80 <= len(submarines) <= 100

    def test_submarine_has_required_keys(self, submarines: list):
        """Every submarine dict should have all required keys."""
        required_keys = {
            "id", "name", "class", "type", "operator",
            "navy", "latitude", "longitude", "home_port",
            "status", "depth_estimate",
        }
        for sub in submarines:
            assert required_keys.issubset(sub.keys()), (
                f"Missing keys: {required_keys - sub.keys()} for {sub.get('id')}"
            )

    def test_latitude_in_valid_range(self, submarines: list):
        """All submarine latitudes should be in valid range."""
        for sub in submarines:
            assert -90.0 <= sub["latitude"] <= 90.0, (
                f"Invalid latitude {sub['latitude']} for {sub['id']}"
            )

    def test_longitude_in_valid_range(self, submarines: list):
        """All submarine longitudes should be in valid range."""
        for sub in submarines:
            assert -180.0 <= sub["longitude"] <= 180.0, (
                f"Invalid longitude {sub['longitude']} for {sub['id']}"
            )

    def test_ids_are_unique(self, submarines: list):
        """All submarine IDs should be unique."""
        ids = [sub["id"] for sub in submarines]
        assert len(ids) == len(set(ids))

    def test_id_format(self, submarines: list):
        """IDs should match the SUB-NNN format."""
        for sub in submarines:
            assert sub["id"].startswith("SUB-")
            assert len(sub["id"]) == 7  # SUB-NNN

    def test_first_submarine_in_port(self, submarines: list):
        """First submarine of each fleet should be 'in_port'."""
        idx = 0
        for fleet in SubmarineGenerator.FLEETS:
            assert submarines[idx]["status"] == "in_port", (
                f"First sub of {fleet.navy} {fleet.sub_class} should be in_port"
            )
            idx += fleet.count

    def test_patrol_submarines_on_patrol(self, submarines: list):
        """Non-first submarines should be 'on_patrol'."""
        idx = 0
        for fleet in SubmarineGenerator.FLEETS:
            for i in range(fleet.count):
                if i > 0:
                    assert submarines[idx + i]["status"] == "on_patrol"
            idx += fleet.count

    def test_us_navy_subs_present(self, submarines: list):
        """There should be US Navy submarines."""
        us_subs = [s for s in submarines if s["navy"] == "US Navy"]
        assert len(us_subs) > 20

    def test_russian_navy_subs_present(self, submarines: list):
        """There should be Russian Navy submarines."""
        ru_subs = [s for s in submarines if s["navy"] == "Russian Navy"]
        assert len(ru_subs) > 10

    def test_chinese_pla_subs_present(self, submarines: list):
        """There should be PLA Navy submarines."""
        cn_subs = [s for s in submarines if s["navy"] == "PLA Navy"]
        assert len(cn_subs) > 10

    def test_sub_types_include_ssbn(self, submarines: list):
        """SSBN type should be present (ballistic missile submarines)."""
        types = {s["type"] for s in submarines}
        assert "SSBN" in types

    def test_sub_types_include_ssn(self, submarines: list):
        """SSN type should be present (nuclear attack submarines)."""
        types = {s["type"] for s in submarines}
        assert "SSN" in types

    def test_sub_types_include_ssk(self, submarines: list):
        """SSK type should be present (diesel-electric submarines)."""
        types = {s["type"] for s in submarines}
        assert "SSK" in types

    def test_deterministic_output(self):
        """Same seed should produce identical submarines."""
        gen1 = SubmarineGenerator(seed=42)
        gen2 = SubmarineGenerator(seed=42)
        subs1 = gen1.generate()
        subs2 = gen2.generate()
        assert subs1 == subs2

    def test_depth_estimate_classified(self, submarines: list):
        """All submarines should have depth_estimate as 'classified'."""
        for sub in submarines:
            assert sub["depth_estimate"] == "classified"


# ===================================================================
#  MilitaryBaseRegistry
# ===================================================================

class TestMilitaryBaseRegistry:
    """Tests for MilitaryBaseRegistry."""

    @pytest.fixture
    def registry(self) -> MilitaryBaseRegistry:
        return MilitaryBaseRegistry()

    @pytest.fixture
    def bases(self, registry: MilitaryBaseRegistry) -> list:
        return registry.get_all()

    def test_bases_tuple_count(self):
        """BASES class variable should have the expected number of entries."""
        assert len(MilitaryBaseRegistry.BASES) > 150

    def test_total_base_count_157(self, bases: list):
        """get_all() should return exactly 157 bases."""
        assert len(bases) == 157

    def test_base_has_required_keys(self, bases: list):
        """Every base dict should have all required keys."""
        required_keys = {
            "name", "country", "operator",
            "latitude", "longitude", "type",
            "branch", "status",
        }
        for base in bases:
            assert required_keys.issubset(base.keys()), (
                f"Missing keys for {base.get('name')}: {required_keys - base.keys()}"
            )

    def test_latitude_in_valid_range(self, bases: list):
        """All base latitudes should be in valid range."""
        for base in bases:
            assert -90.0 <= base["latitude"] <= 90.0, (
                f"Invalid latitude {base['latitude']} for {base['name']}"
            )

    def test_longitude_in_valid_range(self, bases: list):
        """All base longitudes should be in valid range."""
        for base in bases:
            assert -180.0 <= base["longitude"] <= 180.0, (
                f"Invalid longitude {base['longitude']} for {base['name']}"
            )

    def test_us_bases_present(self, bases: list):
        """There should be US-operated bases."""
        us = [b for b in bases if "United States" in b["operator"]]
        assert len(us) > 30

    def test_russian_bases_present(self, bases: list):
        """There should be Russian-operated bases."""
        ru = [b for b in bases if "Russia" in b["operator"]]
        assert len(ru) > 15

    def test_chinese_bases_present(self, bases: list):
        """There should be Chinese-operated bases."""
        cn = [b for b in bases if "China" in b["operator"]]
        assert len(cn) > 15

    def test_nato_bases_present(self, bases: list):
        """There should be NATO bases."""
        nato = [b for b in bases if "NATO" in b["operator"]]
        assert len(nato) > 5

    def test_ramstein_exists(self, bases: list):
        """Ramstein Air Base should be in the registry."""
        names = {b["name"] for b in bases}
        assert "Ramstein Air Base" in names

    def test_diego_garcia_exists(self, bases: list):
        """Diego Garcia should be in the registry."""
        names = {b["name"] for b in bases}
        assert "Diego Garcia" in names

    def test_khmeimim_exists(self, bases: list):
        """Khmeimim Air Base (Russian base in Syria) should be in the registry."""
        names = {b["name"] for b in bases}
        assert "Khmeimim Air Base" in names

    def test_fiery_cross_reef_exists(self, bases: list):
        """Fiery Cross Reef (Chinese SCS base) should be in the registry."""
        names = {b["name"] for b in bases}
        assert "Fiery Cross Reef" in names

    def test_all_statuses_valid(self, bases: list):
        """All base statuses should be one of the known values."""
        valid_statuses = {"active", "abandoned", "under_construction"}
        for base in bases:
            assert base["status"] in valid_statuses, (
                f"Invalid status '{base['status']}' for {base['name']}"
            )

    def test_base_names_not_empty(self, bases: list):
        """All base names should be non-empty."""
        for base in bases:
            assert len(base["name"]) > 0

    def test_base_types_diverse(self, bases: list):
        """There should be multiple types of military bases."""
        types = {b["type"] for b in bases}
        assert "air_base" in types
        assert "naval_base" in types
        assert "submarine_base" in types

    def test_returns_list_of_dicts(self, bases: list):
        """get_all() should return a list of dictionaries."""
        assert isinstance(bases, list)
        for b in bases:
            assert isinstance(b, dict)
