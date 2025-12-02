"""
Tests for PLC client (siemens_s7.py).
"""
import pytest
from unittest.mock import patch, MagicMock

from app.collectors.S7Comm.siemens_s7 import (
    PLC, 
    PLCConnectionError, 
    PLCReadError
)


class TestPLCExceptions:
    """Tests for custom PLC exceptions"""
    
    def test_plc_connection_error(self):
        """PLCConnectionError is raised correctly"""
        with pytest.raises(PLCConnectionError) as exc:
            raise PLCConnectionError("Connection failed")
        
        assert "Connection failed" in str(exc.value)
    
    def test_plc_read_error(self):
        """PLCReadError is raised correctly"""
        with pytest.raises(PLCReadError) as exc:
            raise PLCReadError("Read failed")
        
        assert "Read failed" in str(exc.value)


class TestPLCClient:
    """Tests for PLC client"""
    
    def test_create_client(self):
        """Creating PLC client"""
        plc = PLC(
            plc_ip="192.168.1.10",
            tcp_port=102,
            rack=0,
            slot=1
        )
        
        assert plc.plc_ip == "192.168.1.10"
        assert plc.tcp_port == 102
        assert plc.rack == 0
        assert plc.slot == 1
        assert plc.connected == False
    
    def test_default_values(self):
        """Default values for PLC client"""
        plc = PLC(plc_ip="127.0.0.1")
        
        assert plc.tcp_port == 102
        assert plc.rack == 0
        assert plc.slot == 1
        assert plc.reconnect_delay == 2.0
        assert plc.max_reconnect_attempts == 10
    
    def test_custom_reconnect_settings(self):
        """Custom reconnect settings"""
        plc = PLC(
            plc_ip="127.0.0.1",
            reconnect_delay=5.0,
            max_reconnect_attempts=3
        )
        
        assert plc.reconnect_delay == 5.0
        assert plc.max_reconnect_attempts == 3
    
    def test_parsers_available(self):
        """All data type parsers are available"""
        plc = PLC(plc_ip="127.0.0.1")
        
        expected_types = ["int", "dint", "real", "word", "dword", "bool", "string"]
        
        for dtype in expected_types:
            assert dtype in plc.parsers
    
    def test_connect_success(self):
        """Successful connection"""
        plc = PLC(plc_ip="127.0.0.1", tcp_port=2000)
        
        with patch.object(plc.client, 'connect') as mock_connect:
            with patch.object(plc.client, 'db_read') as mock_read:
                mock_read.return_value = b'\x00'  # Successful test read
                
                result = plc.connect()
                
                assert result == True
                assert plc.connected == True
    
    def test_connect_failure(self):
        """Connection failure"""
        plc = PLC(plc_ip="192.168.255.255")
        
        with patch.object(plc.client, 'connect') as mock_connect:
            # Use generic Exception as snap7 may raise different exception types
            mock_connect.side_effect = Exception("Connection refused")
            
            result = plc.connect()
            
            assert result == False
            assert plc.connected == False
    
    def test_disconnect(self):
        """Disconnecting from PLC"""
        plc = PLC(plc_ip="127.0.0.1")
        plc.connected = True
        
        with patch.object(plc.client, 'disconnect') as mock_disconnect:
            plc.disconnect()
            
            mock_disconnect.assert_called_once()
            assert plc.connected == False
    
    def test_disconnect_when_not_connected(self):
        """Disconnecting when not connected does nothing"""
        plc = PLC(plc_ip="127.0.0.1")
        plc.connected = False
        
        with patch.object(plc.client, 'disconnect') as mock_disconnect:
            plc.disconnect()
            
            mock_disconnect.assert_not_called()
    
    def test_read_db_invalid_type(self):
        """Reading with invalid data type raises ValueError"""
        plc = PLC(plc_ip="127.0.0.1")
        plc.connected = True
        
        with pytest.raises(ValueError) as exc:
            plc.read_db(db_number=1, start=0, size=4, type_data="invalid_type")
        
        assert "invalid_type" in str(exc.value)
    
    def test_ensure_connection_max_attempts(self):
        """ensure_connection respects max_reconnect_attempts"""
        plc = PLC(
            plc_ip="192.168.255.255",
            reconnect_delay=0.01,  # Fast for testing
            max_reconnect_attempts=2
        )
        
        with patch.object(plc.client, 'connect') as mock_connect:
            mock_connect.side_effect = Exception("Fail")
            
            with pytest.raises(PLCConnectionError) as exc:
                plc.ensure_connection()
            
            assert "2 attempts" in str(exc.value)
            assert mock_connect.call_count == 2


class TestPLCDataTypes:
    """Tests for different data types"""
    
    def test_real_parser(self):
        """Parsing REAL (float) data"""
        plc = PLC(plc_ip="127.0.0.1")
        
        # IEEE 754 float representation of 25.5
        # In bytes: 0x41, 0xCC, 0x00, 0x00
        test_data = bytearray([0x41, 0xCC, 0x00, 0x00])
        
        result = plc.parsers["real"](test_data)
        
        assert abs(result - 25.5) < 0.01
    
    def test_int_parser(self):
        """Parsing INT data"""
        plc = PLC(plc_ip="127.0.0.1")
        
        # 16-bit signed integer 1000 = 0x03E8 (big-endian)
        test_data = bytearray([0x03, 0xE8])
        
        result = plc.parsers["int"](test_data)
        
        assert result == 1000
    
    def test_bool_parser(self):
        """Parsing BOOL data"""
        plc = PLC(plc_ip="127.0.0.1")
        
        # Bit 0 set
        test_data = bytearray([0x01])
        result = plc.parsers["bool"](test_data)
        assert result == True
        
        # Bit 0 not set
        test_data = bytearray([0x00])
        result = plc.parsers["bool"](test_data)
        assert result == False

