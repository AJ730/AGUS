"""
Tests for app.flight_intel.FlightIntelligence
==============================================
Covers military detection, airline route estimation,
squawk alert detection, ICAO24 registration lookup,
and full flight enrichment.
"""

from __future__ import annotations

import pytest

from app.flight_intel import FlightIntelligence


@pytest.fixture
def intel() -> FlightIntelligence:
    return FlightIntelligence()


# ===================================================================
#  is_military()
# ===================================================================

class TestIsMilitary:
    """Tests for FlightIntelligence.is_military()."""

    def test_us_military_callsign_rch(self, intel: FlightIntelligence):
        """RCH (USAF Air Mobility Command) prefix should be detected as military."""
        assert intel.is_military("RCH471", "") is True

    def test_us_military_callsign_reach(self, intel: FlightIntelligence):
        """REACH prefix should be detected as military."""
        assert intel.is_military("REACH999", "") is True

    def test_us_navy_callsign(self, intel: FlightIntelligence):
        """NAVY prefix should be detected as military."""
        assert intel.is_military("NAVY42", "") is True

    def test_us_military_callsign_sam(self, intel: FlightIntelligence):
        """SAM (Special Air Mission) prefix should be detected as military."""
        assert intel.is_military("SAM1", "") is True

    def test_us_military_callsign_spar(self, intel: FlightIntelligence):
        """SPAR prefix should be detected as military."""
        assert intel.is_military("SPAR21", "") is True

    def test_uk_military_callsign_ascot(self, intel: FlightIntelligence):
        """ASCOT (RAF) prefix should be detected as military."""
        assert intel.is_military("ASCOT1", "") is True

    def test_german_military_callsign_gaf(self, intel: FlightIntelligence):
        """GAF (German Air Force) prefix should be detected as military."""
        assert intel.is_military("GAF689", "") is True

    def test_french_military_callsign_ctm(self, intel: FlightIntelligence):
        """CTM (French COTAM) prefix should be detected as military."""
        assert intel.is_military("CTM41", "") is True

    def test_russian_military_callsign_rsd(self, intel: FlightIntelligence):
        """RSD (Russian Air Force) prefix should be detected as military."""
        assert intel.is_military("RSD1", "") is True

    def test_chinese_military_callsign_cfc(self, intel: FlightIntelligence):
        """CFC (Chinese/Canadian Forces) prefix should be detected as military."""
        assert intel.is_military("CFC888", "") is True

    def test_israeli_military_callsign_iaf(self, intel: FlightIntelligence):
        """IAF (Israeli Air Force) prefix should be detected as military."""
        assert intel.is_military("IAF105", "") is True

    def test_nato_callsign(self, intel: FlightIntelligence):
        """NATO prefix should be detected as military."""
        assert intel.is_military("NATO1", "") is True

    def test_military_icao24_us_prefix_ae(self, intel: FlightIntelligence):
        """US military ICAO24 address block (ae) should be detected."""
        assert intel.is_military("", "ae1234") is True

    def test_military_icao24_us_prefix_af(self, intel: FlightIntelligence):
        """US military ICAO24 address block (af) should be detected."""
        assert intel.is_military("", "af9abc") is True

    def test_military_icao24_german_prefix(self, intel: FlightIntelligence):
        """German military ICAO24 prefix (3f) should be detected."""
        assert intel.is_military("", "3f1234") is True

    def test_military_icao24_uk_prefix(self, intel: FlightIntelligence):
        """UK military ICAO24 prefix (43) should be detected."""
        assert intel.is_military("", "430000") is True

    def test_military_icao24_russian_prefix(self, intel: FlightIntelligence):
        """Russian military ICAO24 prefix (70) should be detected."""
        assert intel.is_military("", "701234") is True

    def test_military_icao24_chinese_prefix(self, intel: FlightIntelligence):
        """Chinese military ICAO24 prefix (78) should be detected."""
        assert intel.is_military("", "780000") is True

    def test_civilian_callsign_not_military(self, intel: FlightIntelligence):
        """A normal airline callsign should NOT be detected as military."""
        assert intel.is_military("UAL100", "a12345") is False

    def test_civilian_delta_not_military(self, intel: FlightIntelligence):
        """Delta airline callsign should not be military."""
        assert intel.is_military("DAL47", "b12345") is False

    def test_empty_inputs_not_military(self, intel: FlightIntelligence):
        """Empty callsign and ICAO24 should not be detected as military."""
        assert intel.is_military("", "") is False

    def test_none_callsign_not_military(self, intel: FlightIntelligence):
        """None/empty callsign with civilian ICAO24 is not military."""
        assert intel.is_military("", "c00123") is False

    def test_case_insensitive_callsign(self, intel: FlightIntelligence):
        """Military detection should be case-insensitive for callsigns."""
        assert intel.is_military("rch471", "") is True
        assert intel.is_military("Rch471", "") is True

    def test_short_icao24_not_crash(self, intel: FlightIntelligence):
        """Short ICAO24 (less than 2 chars) should not crash."""
        assert intel.is_military("", "a") is False

    def test_both_military_callsign_and_icao24(self, intel: FlightIntelligence):
        """Both military callsign and ICAO24 should return True."""
        assert intel.is_military("RCH100", "ae1234") is True


# ===================================================================
#  estimate_route()
# ===================================================================

class TestEstimateRoute:
    """Tests for FlightIntelligence.estimate_route()."""

    def test_american_airlines(self, intel: FlightIntelligence):
        """AAL prefix should return American Airlines."""
        result = intel.estimate_route("AAL106")
        assert result is not None
        assert "American Airlines" in result
        assert "106" in result

    def test_united_airlines(self, intel: FlightIntelligence):
        """UAL prefix should return United Airlines."""
        result = intel.estimate_route("UAL100")
        assert result is not None
        assert "United Airlines" in result

    def test_delta_air_lines(self, intel: FlightIntelligence):
        """DAL prefix should return Delta Air Lines."""
        result = intel.estimate_route("DAL47")
        assert result is not None
        assert "Delta Air Lines" in result

    def test_british_airways(self, intel: FlightIntelligence):
        """BAW prefix should return British Airways."""
        result = intel.estimate_route("BAW178")
        assert result is not None
        assert "British Airways" in result

    def test_lufthansa(self, intel: FlightIntelligence):
        """DLH prefix should return Lufthansa."""
        result = intel.estimate_route("DLH400")
        assert result is not None
        assert "Lufthansa" in result

    def test_ryanair(self, intel: FlightIntelligence):
        """RYR prefix should return Ryanair."""
        result = intel.estimate_route("RYR812")
        assert result is not None
        assert "Ryanair" in result

    def test_emirates(self, intel: FlightIntelligence):
        """UAE prefix should return Emirates."""
        result = intel.estimate_route("UAE203")
        assert result is not None
        assert "Emirates" in result

    def test_singapore_airlines(self, intel: FlightIntelligence):
        """SIA prefix should return Singapore Airlines."""
        result = intel.estimate_route("SIA321")
        assert result is not None
        assert "Singapore Airlines" in result

    def test_fedex_cargo(self, intel: FlightIntelligence):
        """FDX prefix should return FedEx Express."""
        result = intel.estimate_route("FDX901")
        assert result is not None
        assert "FedEx Express" in result

    def test_unknown_airline_returns_none(self, intel: FlightIntelligence):
        """Unknown airline prefix should return None."""
        result = intel.estimate_route("ZZZ999")
        assert result is None

    def test_short_callsign_returns_none(self, intel: FlightIntelligence):
        """Callsign shorter than 4 chars should return None."""
        assert intel.estimate_route("UA") is None
        assert intel.estimate_route("UAL") is None

    def test_empty_callsign_returns_none(self, intel: FlightIntelligence):
        """Empty callsign should return None."""
        assert intel.estimate_route("") is None

    def test_none_callsign_returns_none(self, intel: FlightIntelligence):
        """None callsign should return None."""
        assert intel.estimate_route(None) is None

    def test_flight_number_extracted(self, intel: FlightIntelligence):
        """Flight number should appear in the result."""
        result = intel.estimate_route("QTR777")
        assert result is not None
        assert "Qatar Airways" in result
        assert "777" in result


# ===================================================================
#  estimate_aircraft_type()
# ===================================================================

class TestEstimateAircraftType:
    """Tests for FlightIntelligence.estimate_aircraft_type()."""

    def test_us_registered(self, intel: FlightIntelligence):
        """ICAO24 in US range should return 'United States-registered'."""
        result = intel.estimate_aircraft_type("a12345")
        assert result is not None
        assert "United States" in result

    def test_uk_registered(self, intel: FlightIntelligence):
        """ICAO24 in UK range should return 'United Kingdom-registered'."""
        result = intel.estimate_aircraft_type("400000")
        assert result is not None
        assert "United Kingdom" in result

    def test_germany_registered(self, intel: FlightIntelligence):
        """ICAO24 in Germany range should return 'Germany-registered'."""
        result = intel.estimate_aircraft_type("3c0000")
        assert result is not None
        assert "Germany" in result

    def test_japan_registered(self, intel: FlightIntelligence):
        """ICAO24 in Japan range should return 'Japan-registered'."""
        result = intel.estimate_aircraft_type("840000")
        assert result is not None
        assert "Japan" in result

    def test_australia_registered(self, intel: FlightIntelligence):
        """ICAO24 in Australia range should return 'Australia-registered'."""
        result = intel.estimate_aircraft_type("7c0000")
        assert result is not None
        assert "Australia" in result

    def test_unknown_range(self, intel: FlightIntelligence):
        """ICAO24 outside all known ranges should return None."""
        result = intel.estimate_aircraft_type("ffffff")
        assert result is None

    def test_empty_icao24(self, intel: FlightIntelligence):
        """Empty ICAO24 should return None."""
        assert intel.estimate_aircraft_type("") is None

    def test_none_icao24(self, intel: FlightIntelligence):
        """None ICAO24 should return None."""
        assert intel.estimate_aircraft_type(None) is None

    def test_short_icao24(self, intel: FlightIntelligence):
        """Single-character ICAO24 should return None."""
        assert intel.estimate_aircraft_type("a") is None


# ===================================================================
#  detect_squawk_alert()
# ===================================================================

class TestDetectSquawkAlert:
    """Tests for FlightIntelligence.detect_squawk_alert()."""

    def test_hijack_7500(self, intel: FlightIntelligence):
        """Squawk 7500 should return HIJACK alert."""
        assert intel.detect_squawk_alert("7500") == "HIJACK"

    def test_radio_failure_7600(self, intel: FlightIntelligence):
        """Squawk 7600 should return RADIO_FAILURE alert."""
        assert intel.detect_squawk_alert("7600") == "RADIO_FAILURE"

    def test_emergency_7700(self, intel: FlightIntelligence):
        """Squawk 7700 should return EMERGENCY alert."""
        assert intel.detect_squawk_alert("7700") == "EMERGENCY"

    def test_normal_squawk_no_alert(self, intel: FlightIntelligence):
        """Normal squawk code should return None."""
        assert intel.detect_squawk_alert("1200") is None

    def test_another_normal_squawk(self, intel: FlightIntelligence):
        """Another normal squawk code should return None."""
        assert intel.detect_squawk_alert("5423") is None

    def test_vfr_squawk_no_alert(self, intel: FlightIntelligence):
        """VFR squawk (1200) should return None."""
        assert intel.detect_squawk_alert("1200") is None


# ===================================================================
#  enrich_flight()
# ===================================================================

class TestEnrichFlight:
    """Tests for FlightIntelligence.enrich_flight()."""

    def _make_state_vector(
        self,
        icao24="a12345",
        callsign="UAL100  ",
        origin_country="United States",
        time_position=1700000000,
        last_contact=1700000005,
        longitude=-73.78,
        latitude=40.64,
        baro_altitude=10000.0,
        on_ground=False,
        velocity=250.0,
        heading=45.0,
        vertical_rate=0.0,
        sensors=None,
        geo_altitude=10200.0,
        squawk="1200",
        spi=False,
        position_source=0,
    ) -> list:
        """Create a 17-element OpenSky state vector."""
        return [
            icao24, callsign, origin_country,
            time_position, last_contact,
            longitude, latitude,
            baro_altitude, on_ground, velocity,
            heading, vertical_rate,
            sensors, geo_altitude,
            squawk, spi, position_source,
        ]

    def test_basic_enrichment(self, intel: FlightIntelligence):
        """A valid state vector should be enriched with all expected fields."""
        state = self._make_state_vector()
        result = intel.enrich_flight(state)

        assert result != {}
        assert result["icao24"] == "a12345"
        assert result["callsign"] == "UAL100"
        assert result["origin_country"] == "United States"
        assert result["longitude"] == -73.78
        assert result["latitude"] == 40.64
        assert result["baro_altitude"] == 10000.0
        assert result["on_ground"] is False
        assert result["velocity"] == 250.0
        assert result["heading"] == 45.0
        assert result["vertical_rate"] == 0.0
        assert result["squawk"] == "1200"
        assert result["spi"] is False
        assert result["position_source"] == "ADS-B"
        assert result["is_military"] is False
        assert result["squawk_alert"] is None

    def test_enrichment_with_airline_route(self, intel: FlightIntelligence):
        """Enrichment should include flight route for known airline callsigns."""
        state = self._make_state_vector(callsign="DAL47   ")
        result = intel.enrich_flight(state)
        assert result["flight_route"] is not None
        assert "Delta Air Lines" in result["flight_route"]

    def test_enrichment_military_callsign(self, intel: FlightIntelligence):
        """Military callsign should set is_military=True."""
        state = self._make_state_vector(callsign="RCH471  ", icao24="ae1234")
        result = intel.enrich_flight(state)
        assert result["is_military"] is True

    def test_enrichment_emergency_squawk(self, intel: FlightIntelligence):
        """Emergency squawk should trigger squawk_alert."""
        state = self._make_state_vector(squawk="7700")
        result = intel.enrich_flight(state)
        assert result["squawk_alert"] == "EMERGENCY"

    def test_enrichment_hijack_squawk(self, intel: FlightIntelligence):
        """Hijack squawk should trigger squawk_alert."""
        state = self._make_state_vector(squawk="7500")
        result = intel.enrich_flight(state)
        assert result["squawk_alert"] == "HIJACK"

    def test_enrichment_null_position_returns_empty(self, intel: FlightIntelligence):
        """State with None longitude/latitude should return empty dict."""
        state = self._make_state_vector(longitude=None, latitude=None)
        result = intel.enrich_flight(state)
        assert result == {}

    def test_enrichment_null_longitude_returns_empty(self, intel: FlightIntelligence):
        """State with None longitude only should return empty dict."""
        state = self._make_state_vector(longitude=None)
        result = intel.enrich_flight(state)
        assert result == {}

    def test_enrichment_short_state_vector(self, intel: FlightIntelligence):
        """State vector shorter than 17 elements should return empty dict."""
        result = intel.enrich_flight([1, 2, 3])
        assert result == {}

    def test_enrichment_empty_state_vector(self, intel: FlightIntelligence):
        """Empty state vector should return empty dict."""
        result = intel.enrich_flight([])
        assert result == {}

    def test_enrichment_position_source_mlat(self, intel: FlightIntelligence):
        """Position source 2 should be labeled MLAT."""
        state = self._make_state_vector(position_source=2)
        result = intel.enrich_flight(state)
        assert result["position_source"] == "MLAT"

    def test_enrichment_position_source_asterix(self, intel: FlightIntelligence):
        """Position source 1 should be labeled ASTERIX."""
        state = self._make_state_vector(position_source=1)
        result = intel.enrich_flight(state)
        assert result["position_source"] == "ASTERIX"

    def test_enrichment_aircraft_type_us(self, intel: FlightIntelligence):
        """US ICAO24 address should yield 'United States-registered' aircraft type."""
        state = self._make_state_vector(icao24="a12345")
        result = intel.enrich_flight(state)
        assert result["aircraft_type"] is not None
        assert "United States" in result["aircraft_type"]

    def test_enrichment_no_squawk_no_alert(self, intel: FlightIntelligence):
        """None squawk should result in None squawk_alert."""
        state = self._make_state_vector(squawk=None)
        result = intel.enrich_flight(state)
        assert result["squawk_alert"] is None

    def test_enrichment_callsign_stripped(self, intel: FlightIntelligence):
        """Callsign should be stripped of whitespace."""
        state = self._make_state_vector(callsign="  BAW178  ")
        result = intel.enrich_flight(state)
        assert result["callsign"] == "BAW178"
