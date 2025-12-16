"""
Tests for CollectorManager and CollectorStatus.
"""
import pytest
import threading
import time

from app.services.collector_manager import CollectorStatus, CollectorManager, collector_status


class TestCollectorStatus:
    """Tests for thread-safe CollectorStatus"""
    
    def test_initial_values(self):
        """Initial values are False/None"""
        status = CollectorStatus()
        
        assert status.running == False
        assert status.connected == False
        assert status.last_error is None
        assert status.plc_name is None
        assert status.restart_requested == False
    
    def test_set_running(self):
        """Setting running property"""
        status = CollectorStatus()
        
        status.running = True
        assert status.running == True
        
        status.running = False
        assert status.running == False
    
    def test_set_connected(self):
        """Setting connected property"""
        status = CollectorStatus()
        
        status.connected = True
        assert status.connected == True
    
    def test_set_plc_name(self):
        """Setting plc_name property"""
        status = CollectorStatus()
        
        status.plc_name = "TestPLC"
        assert status.plc_name == "TestPLC"
    
    def test_set_last_error(self):
        """Setting last_error property"""
        status = CollectorStatus()
        
        status.last_error = "Connection failed"
        assert status.last_error == "Connection failed"
    
    def test_request_restart(self):
        """Requesting restart"""
        status = CollectorStatus()
        
        assert status.restart_requested == False
        status.request_restart()
        assert status.restart_requested == True
    
    def test_clear_restart_request(self):
        """Clearing restart request returns previous state"""
        status = CollectorStatus()
        
        # Not requested - returns False
        result = status.clear_restart_request()
        assert result == False
        
        # Request and clear - returns True
        status.request_restart()
        result = status.clear_restart_request()
        assert result == True
        assert status.restart_requested == False
    
    def test_to_dict(self):
        """Converting to dict"""
        status = CollectorStatus()
        status.running = True
        status.connected = True
        status.plc_name = "TestPLC"
        
        d = status.to_dict()
        
        assert d["running"] == True
        assert d["connected"] == True
        assert d["plc_name"] == "TestPLC"
        assert d["last_error"] is None
        assert d["restart_requested"] == False
    
    def test_thread_safety(self):
        """Thread safety - concurrent access"""
        status = CollectorStatus()
        errors = []
        
        def writer():
            try:
                for i in range(100):
                    status.running = True
                    status.connected = False
                    status.plc_name = f"PLC_{i}"
            except Exception as e:
                errors.append(e)
        
        def reader():
            try:
                for _ in range(100):
                    _ = status.running
                    _ = status.connected
                    _ = status.to_dict()
            except Exception as e:
                errors.append(e)
        
        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Thread errors: {errors}"


class TestCollectorManager:
    """Tests for CollectorManager"""
    
    def test_create_manager(self):
        """Creating manager"""
        manager = CollectorManager(flush_interval_sec=5.0)
        
        assert manager.flush_interval_sec == 5.0
        assert manager.collector is None
    
    def test_get_status_no_collector(self):
        """Get status when no collector"""
        manager = CollectorManager()
        
        status = manager.get_status()
        
        assert status["plc_count"] == 0
        assert status["buffer_size"] == 0


class TestGlobalCollectorStatus:
    """Tests for global collector_status instance"""
    
    def test_global_instance_exists(self):
        """Global instance is accessible"""
        assert collector_status is not None
        assert isinstance(collector_status, CollectorStatus)
    
    def test_global_instance_is_singleton(self):
        """Global instance is consistent"""
        from app.services.collector_manager import collector_status as status2
        
        collector_status.plc_name = "TestSingleton"
        assert status2.plc_name == "TestSingleton"






