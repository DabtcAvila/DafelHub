#!/usr/bin/env python3
"""
Basic functionality test for DafelHub
Tests core imports and basic CLI functionality
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_basic_imports():
    """Test that core modules can be imported without errors"""
    print("🧪 Testing basic imports...")
    
    try:
        from dafelhub import __version__
        print(f"✅ Core module imported - DafelHub v{__version__}")
    except Exception as e:
        print(f"❌ Core import failed: {e}")
        return False
    
    try:
        from dafelhub.core.config import settings
        print(f"✅ Configuration loaded - {settings.APP_NAME}")
    except Exception as e:
        print(f"❌ Config import failed: {e}")
        return False
    
    try:
        from dafelhub.core.logging import get_logger
        logger = get_logger('test')
        logger.info("Test log message")
        print("✅ Logging system working")
    except Exception as e:
        print(f"❌ Logging import failed: {e}")
        return False
    
    try:
        from dafelhub.core.encryption import VaultManager
        vault = VaultManager.get_instance()
        test_data = {"test": "encryption_working"}
        encrypted = vault.encrypt_data(test_data)
        decrypted = vault.decrypt_data(encrypted)
        assert decrypted == test_data
        print("✅ Encryption system working")
    except Exception as e:
        print(f"❌ Encryption test failed: {e}")
        return False
    
    return True

def test_cli_basic():
    """Test basic CLI functionality"""
    print("\n🧪 Testing CLI functionality...")
    
    try:
        from dafelhub.cli.main import app
        print("✅ CLI app imported successfully")
    except Exception as e:
        print(f"❌ CLI import failed: {e}")
        return False
    
    # Test individual command imports
    try:
        from dafelhub.cli.commands import check
        print("✅ Check command imported")
    except Exception as e:
        print(f"⚠️  Check command import issue: {e}")
    
    return True

def test_services():
    """Test service layer imports"""
    print("\n🧪 Testing service layer...")
    
    try:
        from dafelhub.services.agent_orchestrator import AgentOrchestrator
        orchestrator = AgentOrchestrator()
        print("✅ Agent orchestrator initialized")
    except Exception as e:
        print(f"❌ Agent orchestrator failed: {e}")
        return False
    
    return True

def main():
    """Run all basic tests"""
    print("🚀 DafelHub Basic Functionality Test")
    print("=" * 50)
    
    all_passed = True
    
    # Run tests
    all_passed &= test_basic_imports()
    all_passed &= test_cli_basic()
    all_passed &= test_services()
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All basic tests PASSED! DafelHub is ready to run.")
        print("\n📋 Next steps:")
        print("   1. PYTHONPATH=src python3 -m dafelhub.cli.main --help")
        print("   2. PYTHONPATH=src python3 -m dafelhub.cli.main check --help")
        print("   3. docker-compose up -d postgres redis")
    else:
        print("❌ Some tests FAILED. Check the errors above.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    exit(main())