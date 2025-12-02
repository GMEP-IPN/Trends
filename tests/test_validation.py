"""
Tests for API validation.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.api.server import app, PLCCreateRequest, TagCreateRequest
from pydantic import ValidationError


@pytest.fixture
def client():
    """Test client"""
    return TestClient(app)


class TestPLCValidation:
    """Tests for PLC validation"""
    
    def test_valid_plc(self):
        """Valid PLC data passes validation"""
        plc = PLCCreateRequest(
            name="TestPLC",
            ip_address="192.168.1.10",
            tcp_port=102,
            rack=0,
            slot=1
        )
        assert plc.name == "TestPLC"
        assert plc.ip_address == "192.168.1.10"
    
    def test_invalid_ip_address(self):
        """Invalid IP address fails validation"""
        with pytest.raises(ValidationError) as exc:
            PLCCreateRequest(
                name="TestPLC",
                ip_address="invalid.ip",
                tcp_port=102
            )
        assert "Invalid IP address" in str(exc.value)
    
    def test_invalid_ip_address_out_of_range(self):
        """IP address with out of range octet fails"""
        with pytest.raises(ValidationError) as exc:
            PLCCreateRequest(
                name="TestPLC",
                ip_address="256.1.1.1",
                tcp_port=102
            )
        assert "Invalid IP address" in str(exc.value)
    
    def test_empty_name(self):
        """Empty name fails validation"""
        with pytest.raises(ValidationError) as exc:
            PLCCreateRequest(
                name="   ",
                ip_address="192.168.1.10",
                tcp_port=102
            )
        assert "cannot be empty" in str(exc.value)
    
    def test_name_too_long(self):
        """Name over 100 characters fails"""
        with pytest.raises(ValidationError) as exc:
            PLCCreateRequest(
                name="A" * 101,
                ip_address="192.168.1.10",
                tcp_port=102
            )
        assert "too long" in str(exc.value)
    
    def test_invalid_port_too_low(self):
        """Port 0 fails validation"""
        with pytest.raises(ValidationError) as exc:
            PLCCreateRequest(
                name="TestPLC",
                ip_address="192.168.1.10",
                tcp_port=0
            )
        assert "Port must be" in str(exc.value)
    
    def test_invalid_port_too_high(self):
        """Port > 65535 fails validation"""
        with pytest.raises(ValidationError) as exc:
            PLCCreateRequest(
                name="TestPLC",
                ip_address="192.168.1.10",
                tcp_port=70000
            )
        assert "Port must be" in str(exc.value)
    
    def test_invalid_rack(self):
        """Rack > 7 fails validation"""
        with pytest.raises(ValidationError) as exc:
            PLCCreateRequest(
                name="TestPLC",
                ip_address="192.168.1.10",
                tcp_port=102,
                rack=8
            )
        assert "Rack must be" in str(exc.value)
    
    def test_invalid_slot(self):
        """Slot > 31 fails validation"""
        with pytest.raises(ValidationError) as exc:
            PLCCreateRequest(
                name="TestPLC",
                ip_address="192.168.1.10",
                tcp_port=102,
                slot=32
            )
        assert "Slot must be" in str(exc.value)
    
    def test_name_with_special_chars_allowed(self):
        """Name with dashes, dots, spaces allowed"""
        plc = PLCCreateRequest(
            name="Test-PLC_1.Main",
            ip_address="192.168.1.10",
            tcp_port=102
        )
        assert plc.name == "Test-PLC_1.Main"
    
    def test_localhost_ip(self):
        """Localhost IP is valid"""
        plc = PLCCreateRequest(
            name="SimPLC",
            ip_address="127.0.0.1",
            tcp_port=2000
        )
        assert plc.ip_address == "127.0.0.1"


class TestTagValidation:
    """Tests for Tag validation"""
    
    def test_valid_tag(self):
        """Valid tag data passes validation"""
        tag = TagCreateRequest(
            name="Temperature",
            db_number=1,
            start_address=0,
            data_type="real",
            data_size=4
        )
        assert tag.name == "Temperature"
        assert tag.data_type == "real"
    
    def test_empty_tag_name(self):
        """Empty tag name fails validation"""
        with pytest.raises(ValidationError) as exc:
            TagCreateRequest(
                name="",
                db_number=1,
                start_address=0,
                data_type="real",
                data_size=4
            )
        assert "cannot be empty" in str(exc.value)
    
    def test_invalid_db_number_zero(self):
        """DB number 0 fails validation"""
        with pytest.raises(ValidationError) as exc:
            TagCreateRequest(
                name="Test",
                db_number=0,
                start_address=0,
                data_type="real",
                data_size=4
            )
        assert "DB number must be" in str(exc.value)
    
    def test_invalid_db_number_negative(self):
        """Negative DB number fails validation"""
        with pytest.raises(ValidationError) as exc:
            TagCreateRequest(
                name="Test",
                db_number=-1,
                start_address=0,
                data_type="real",
                data_size=4
            )
        assert "DB number must be" in str(exc.value)
    
    def test_invalid_start_address_negative(self):
        """Negative start address fails validation"""
        with pytest.raises(ValidationError) as exc:
            TagCreateRequest(
                name="Test",
                db_number=1,
                start_address=-1,
                data_type="real",
                data_size=4
            )
        assert "Start address must be" in str(exc.value)
    
    def test_invalid_data_type(self):
        """Invalid data type fails validation"""
        with pytest.raises(ValidationError) as exc:
            TagCreateRequest(
                name="Test",
                db_number=1,
                start_address=0,
                data_type="invalid",
                data_size=4
            )
        assert "Invalid data type" in str(exc.value)
    
    def test_all_valid_data_types(self):
        """All valid data types pass"""
        valid_types = ['int', 'dint', 'real', 'bool', 'word', 'dword', 'string']
        
        for dtype in valid_types:
            tag = TagCreateRequest(
                name=f"Test_{dtype}",
                db_number=1,
                start_address=0,
                data_type=dtype,
                data_size=4
            )
            assert tag.data_type == dtype
    
    def test_data_type_case_insensitive(self):
        """Data type is case insensitive"""
        tag = TagCreateRequest(
            name="Test",
            db_number=1,
            start_address=0,
            data_type="REAL",
            data_size=4
        )
        assert tag.data_type == "real"
    
    def test_invalid_data_size_zero(self):
        """Data size 0 fails validation"""
        with pytest.raises(ValidationError) as exc:
            TagCreateRequest(
                name="Test",
                db_number=1,
                start_address=0,
                data_type="real",
                data_size=0
            )
        assert "Data size must be" in str(exc.value)
    
    def test_invalid_poll_interval_too_low(self):
        """Poll interval < 100ms fails"""
        with pytest.raises(ValidationError) as exc:
            TagCreateRequest(
                name="Test",
                db_number=1,
                start_address=0,
                data_type="real",
                data_size=4,
                poll_interval_ms=50
            )
        assert "Poll interval must be" in str(exc.value)
    
    def test_invalid_poll_interval_too_high(self):
        """Poll interval > 60000ms fails"""
        with pytest.raises(ValidationError) as exc:
            TagCreateRequest(
                name="Test",
                db_number=1,
                start_address=0,
                data_type="real",
                data_size=4,
                poll_interval_ms=100000
            )
        assert "Poll interval must be" in str(exc.value)


class TestAPIValidationEndpoints:
    """Tests for API endpoint validation"""
    
    def test_create_plc_invalid_ip(self, client):
        """Create PLC with invalid IP returns 422"""
        response = client.post("/api/plcs", json={
            "name": "TestPLC",
            "ip_address": "not.an.ip.address",
            "tcp_port": 102
        })
        
        assert response.status_code == 422
        assert "Invalid IP address" in response.text
    
    def test_create_tag_invalid_data_type(self, client):
        """Create tag with invalid data type returns 422"""
        with patch('app.api.server.get_session') as mock_session:
            session = MagicMock()
            mock_plc = MagicMock()
            mock_plc.id = 1
            session.query.return_value.filter.return_value.first.return_value = mock_plc
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            response = client.post("/api/tags", json={
                "name": "Test",
                "db_number": 1,
                "start_address": 0,
                "data_type": "invalid_type",
                "data_size": 4
            })
            
            assert response.status_code == 422
            assert "Invalid data type" in response.text

