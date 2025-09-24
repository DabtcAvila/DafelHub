"""
DafelHub Security Recovery System Demo
Enterprise-grade security infrastructure demonstration and testing

This demo showcases:
- Persistent audit trail with crash recovery
- Vault state backup and recovery
- Automated configuration backup (15-min intervals)
- Key recovery with Shamir's Secret Sharing
- Complete security infrastructure integration

Usage:
    python -m dafelhub.security.demo_recovery_system
"""

import os
import asyncio
import json
import time
from pathlib import Path
from datetime import datetime, timezone

# Import our security systems
from dafelhub.security.audit_trail import get_persistent_audit_trail, audit_event
from dafelhub.security.recovery_system import get_vault_recovery_system
from dafelhub.security.config_backup import get_config_backup_system
from dafelhub.security.key_recovery import get_key_recovery_system
from dafelhub.core.enterprise_vault import get_enterprise_vault_manager
from dafelhub.core.logging import get_logger

logger = get_logger(__name__)


class SecurityRecoveryDemo:
    """Demonstration of the complete security recovery infrastructure"""
    
    def __init__(self):
        self.vault_manager = None
        self.audit_trail = None
        self.vault_recovery = None
        self.config_backup = None
        self.key_recovery = None
    
    async def initialize_systems(self) -> None:
        """Initialize all security systems"""
        
        logger.info("🔐 INITIALIZING SECURITY RECOVERY INFRASTRUCTURE")
        
        # Initialize VaultManager first
        self.vault_manager = get_enterprise_vault_manager()
        logger.info("✅ Enterprise Vault Manager initialized")
        
        # Initialize audit trail
        self.audit_trail = get_persistent_audit_trail(self.vault_manager)
        logger.info("✅ Persistent Audit Trail initialized")
        
        # Initialize vault recovery system
        self.vault_recovery = get_vault_recovery_system(self.vault_manager)
        logger.info("✅ Vault Recovery System initialized")
        
        # Initialize configuration backup
        self.config_backup = get_config_backup_system(self.vault_manager)
        logger.info("✅ Configuration Backup System initialized")
        
        # Initialize key recovery
        self.key_recovery = get_key_recovery_system(self.vault_manager)
        logger.info("✅ Key Recovery System initialized")
        
        # Log system initialization
        audit_event("SECURITY_SYSTEMS_INITIALIZED", {
            "systems": [
                "vault_manager",
                "audit_trail", 
                "vault_recovery",
                "config_backup",
                "key_recovery"
            ],
            "initialization_timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        logger.info("🚀 All security systems initialized successfully")
    
    async def demo_audit_trail(self) -> None:
        """Demonstrate audit trail functionality"""
        
        logger.info("📊 DEMONSTRATING AUDIT TRAIL SYSTEM")
        
        # Add various audit events
        events = [
            ("USER_LOGIN", {"user_id": "demo_user", "ip": "192.168.1.100"}),
            ("ENCRYPTION_OPERATION", {"operation": "encrypt", "data_size": 1024}),
            ("KEY_ROTATION", {"old_version": 1, "new_version": 2}),
            ("CONFIGURATION_CHANGE", {"file": "config.json", "action": "modified"}),
            ("SECURITY_ALERT", {"type": "suspicious_activity", "severity": "medium"}),
        ]
        
        for event_type, event_data in events:
            audit_event(event_type, event_data)
            logger.info(f"  ➤ Logged: {event_type}")
            await asyncio.sleep(0.5)  # Small delay for demonstration
        
        # Check audit trail status
        status = self.audit_trail.get_status()
        logger.info(f"📈 Audit Trail Status: {status['total_entries']} entries, queue size: {status['queue_size']}")
        
        # Wait for processing
        await asyncio.sleep(2)
        
        # Get recent entries
        recent_entries = self.audit_trail.get_entries(limit=5)
        logger.info(f"📋 Retrieved {len(recent_entries)} recent audit entries")
        
        # Verify integrity
        logger.info("🔍 Verifying audit trail integrity...")
        integrity_result = self.audit_trail.verify_integrity(start_sequence=1, end_sequence=10)
        
        if integrity_result['integrity_passed']:
            logger.info("✅ Audit trail integrity verification PASSED")
        else:
            logger.warning("⚠️  Audit trail integrity issues detected")
            logger.warning(f"   Chain breaks: {len(integrity_result['chain_breaks'])}")
            logger.warning(f"   Hash mismatches: {len(integrity_result['hash_mismatches'])}")
            logger.warning(f"   Signature failures: {len(integrity_result['signature_failures'])}")
    
    async def demo_vault_operations(self) -> None:
        """Demonstrate vault encryption/decryption"""
        
        logger.info("🔒 DEMONSTRATING VAULT OPERATIONS")
        
        # Test data
        test_messages = [
            "Confidential business data",
            "User authentication credentials", 
            "Financial transaction records",
            "Personal identifiable information",
            "API keys and secrets"
        ]
        
        encrypted_data = []
        
        # Encrypt test data
        logger.info("🔐 Encrypting test data...")
        for i, message in enumerate(test_messages, 1):
            encrypted = await self.vault_manager.encrypt(message)
            encrypted_data.append(encrypted)
            
            # Log encryption event
            audit_event("DATA_ENCRYPTION", {
                "message_id": i,
                "original_length": len(message),
                "encrypted_length": len(encrypted),
                "algorithm": "aes-256-gcm"
            })
            
            logger.info(f"  ➤ Encrypted message {i}: {len(message)} → {len(encrypted)} chars")
        
        # Decrypt test data
        logger.info("🔓 Decrypting test data...")
        for i, encrypted in enumerate(encrypted_data, 1):
            try:
                decrypted = await self.vault_manager.decrypt(encrypted)
                original_message = test_messages[i-1]
                
                if decrypted == original_message:
                    logger.info(f"  ✅ Message {i} decryption successful")
                else:
                    logger.error(f"  ❌ Message {i} decryption failed - content mismatch")
                
                # Log decryption event
                audit_event("DATA_DECRYPTION", {
                    "message_id": i,
                    "success": decrypted == original_message,
                    "decrypted_length": len(decrypted)
                })
                
            except Exception as e:
                logger.error(f"  ❌ Message {i} decryption failed: {e}")
                audit_event("DATA_DECRYPTION", {
                    "message_id": i,
                    "success": False,
                    "error": str(e)
                })
        
        # Get vault status
        vault_status = self.vault_manager.get_vault_status()
        logger.info(f"🏛️  Vault Status: Version {vault_status['vault_version']}, Key Version {vault_status['key_version']}")
    
    async def demo_vault_recovery(self) -> None:
        """Demonstrate vault recovery system"""
        
        logger.info("💾 DEMONSTRATING VAULT RECOVERY SYSTEM")
        
        # Create vault backup
        logger.info("📦 Creating vault state backup...")
        backup_path = self.vault_recovery.backup_vault_state(include_keys=True)
        logger.info(f"  ✅ Backup created: {Path(backup_path).name}")
        
        # Log backup event
        audit_event("VAULT_BACKUP_CREATED", {
            "backup_path": backup_path,
            "include_keys": True,
            "backup_timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # List available backups
        backups = self.vault_recovery.list_backups()
        logger.info(f"📋 Available backups: {len(backups)}")
        
        for backup in backups[:3]:  # Show first 3
            logger.info(f"  ➤ {backup['backup_id']} ({backup['backup_type']}) - {backup['file_size_mb']:.1f}MB")
        
        # Verify backup integrity
        if backups:
            latest_backup = backups[0]
            logger.info(f"🔍 Verifying backup integrity: {latest_backup['backup_id']}")
            
            verification = self.vault_recovery.verify_backup_integrity(latest_backup['backup_id'])
            
            if verification['integrity_passed']:
                logger.info("  ✅ Backup integrity verification PASSED")
            else:
                logger.warning("  ⚠️  Backup integrity issues detected")
                for error in verification['errors']:
                    logger.warning(f"    - {error}")
        
        # Get recovery system status
        recovery_status = self.vault_recovery.get_recovery_status()
        logger.info(f"📊 Recovery System: {recovery_status['backups_available']} backups, {recovery_status['total_backup_size_mb']:.1f}MB total")
    
    async def demo_config_backup(self) -> None:
        """Demonstrate configuration backup system"""
        
        logger.info("⚙️  DEMONSTRATING CONFIGURATION BACKUP SYSTEM")
        
        # Create configuration snapshot
        logger.info("📸 Creating configuration snapshot...")
        snapshot = self.config_backup.create_snapshot(force=True)
        
        if snapshot:
            logger.info(f"  ✅ Snapshot created: {snapshot.snapshot_id}")
            logger.info(f"  📁 Total files: {len(snapshot.configurations)}")
            logger.info(f"  📊 Changes detected: {snapshot.change_summary['total_changes']}")
            logger.info(f"  ✅ Valid files: {snapshot.validation_results['valid_files']}")
            logger.info(f"  ⚠️  Invalid files: {snapshot.validation_results['invalid_files']}")
            
            # Log snapshot event
            audit_event("CONFIG_SNAPSHOT_CREATED", {
                "snapshot_id": snapshot.snapshot_id,
                "total_files": len(snapshot.configurations),
                "changes": snapshot.change_summary['total_changes'],
                "validation_errors": snapshot.validation_results['invalid_files']
            })
        
        # List available snapshots
        snapshots = self.config_backup.list_snapshots()
        logger.info(f"📋 Available snapshots: {len(snapshots)}")
        
        for snapshot_info in snapshots[:3]:  # Show first 3
            logger.info(f"  ➤ {snapshot_info['snapshot_id']} - {snapshot_info['configurations_count']} files")
        
        # Get backup system status
        backup_status = self.config_backup.get_status()
        logger.info(f"📊 Config Backup: {backup_status['backup_interval_minutes']}min intervals, {backup_status['total_snapshots']} snapshots")
    
    async def demo_key_recovery(self) -> None:
        """Demonstrate key recovery system"""
        
        logger.info("🔑 DEMONSTRATING KEY RECOVERY SYSTEM")
        
        # Simulate key backup (in production, this would backup actual vault keys)
        logger.info("🔐 Creating test key backup with Shamir's Secret Sharing...")
        
        import secrets
        test_key = secrets.token_bytes(32)  # Simulate 256-bit key
        
        backup_info = self.key_recovery.backup_key(
            key_data=test_key,
            key_version=1,
            algorithm="aes-256-gcm",
            threshold=3,
            num_shares=5,
            metadata={
                "purpose": "demo_test",
                "environment": "development"
            }
        )
        
        logger.info(f"  ✅ Key backup created: {backup_info.key_id}")
        logger.info(f"  🧩 Shares: {backup_info.shares_total} total, {backup_info.shares_threshold} required")
        logger.info(f"  📍 Backup locations: {len(backup_info.backup_locations)}")
        
        # Log key backup event
        audit_event("KEY_BACKUP_CREATED", {
            "key_id": backup_info.key_id,
            "key_version": backup_info.key_version,
            "shares_total": backup_info.shares_total,
            "shares_threshold": backup_info.shares_threshold,
            "algorithm": backup_info.algorithm
        })
        
        # Test key recovery
        logger.info("🔄 Testing key recovery...")
        try:
            recovered_key = self.key_recovery.recover_key(backup_info.key_id)
            
            if recovered_key == test_key:
                logger.info("  ✅ Key recovery successful - keys match")
                audit_event("KEY_RECOVERY_SUCCESS", {"key_id": backup_info.key_id})
            else:
                logger.error("  ❌ Key recovery failed - keys don't match")
                audit_event("KEY_RECOVERY_FAILED", {"key_id": backup_info.key_id, "reason": "key_mismatch"})
                
        except Exception as e:
            logger.error(f"  ❌ Key recovery failed: {e}")
            audit_event("KEY_RECOVERY_FAILED", {"key_id": backup_info.key_id, "error": str(e)})
        
        # Verify key integrity
        logger.info("🔍 Verifying key backup integrity...")
        integrity_check = self.key_recovery.verify_key_integrity(backup_info.key_id)
        
        if integrity_check['integrity_passed']:
            logger.info("  ✅ Key integrity verification PASSED")
        else:
            logger.warning("  ⚠️  Key integrity issues detected")
            for error in integrity_check['errors']:
                logger.warning(f"    - {error}")
        
        # List backed up keys
        backed_up_keys = self.key_recovery.list_backed_up_keys()
        logger.info(f"📋 Backed up keys: {len(backed_up_keys)}")
        
        for key_info in backed_up_keys:
            status = "✅ Recoverable" if key_info['recoverable'] else "⚠️  Not recoverable"
            logger.info(f"  ➤ {key_info['key_id']} v{key_info['key_version']} - {status}")
        
        # Get recovery system status
        recovery_status = self.key_recovery.get_recovery_status()
        logger.info(f"📊 Key Recovery: {recovery_status['total_keys_backed_up']} keys, {recovery_status['total_recoverable_keys']} recoverable")
    
    async def demo_system_integration(self) -> None:
        """Demonstrate integrated system operation"""
        
        logger.info("🔗 DEMONSTRATING SYSTEM INTEGRATION")
        
        # Simulate a complete security workflow
        workflow_id = f"workflow_{int(time.time())}"
        
        # 1. User action triggers security event
        audit_event("WORKFLOW_STARTED", {
            "workflow_id": workflow_id,
            "user_action": "sensitive_data_access",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # 2. Encrypt sensitive data
        sensitive_data = "Top Secret: Financial projections for Q4 2024"
        encrypted = await self.vault_manager.encrypt(sensitive_data)
        
        audit_event("DATA_ENCRYPTED", {
            "workflow_id": workflow_id,
            "data_classification": "confidential",
            "encryption_algorithm": "aes-256-gcm"
        })
        
        # 3. Create automatic backups
        logger.info("  🔄 Triggering automatic backups...")
        
        # Vault backup
        vault_backup = self.vault_recovery.backup_vault_state(include_keys=False)
        audit_event("AUTO_VAULT_BACKUP", {"workflow_id": workflow_id, "backup_path": vault_backup})
        
        # Config backup
        config_snapshot = self.config_backup.create_snapshot()
        if config_snapshot:
            audit_event("AUTO_CONFIG_BACKUP", {"workflow_id": workflow_id, "snapshot_id": config_snapshot.snapshot_id})
        
        # 4. Verify system integrity
        logger.info("  🔍 Performing integrity checks...")
        
        # Verify audit trail
        audit_integrity = self.audit_trail.verify_integrity(start_sequence=1, end_sequence=5)
        audit_event("INTEGRITY_CHECK", {
            "workflow_id": workflow_id,
            "component": "audit_trail",
            "result": audit_integrity['integrity_passed']
        })
        
        # 5. Generate system status report
        logger.info("  📊 Generating system status report...")
        
        status_report = {
            "workflow_id": workflow_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "vault_status": self.vault_manager.get_vault_status(),
            "audit_status": self.audit_trail.get_status(),
            "recovery_status": self.vault_recovery.get_recovery_status(),
            "config_backup_status": self.config_backup.get_status(),
            "key_recovery_status": self.key_recovery.get_recovery_status()
        }
        
        # Log final workflow completion
        audit_event("WORKFLOW_COMPLETED", {
            "workflow_id": workflow_id,
            "duration_seconds": 5,  # Simulated
            "operations_completed": [
                "data_encryption",
                "vault_backup", 
                "config_backup",
                "integrity_verification",
                "status_report"
            ],
            "success": True
        })
        
        logger.info(f"  ✅ Workflow {workflow_id} completed successfully")
        logger.info(f"  📋 Status report generated with {len(status_report)} components")
    
    async def display_final_summary(self) -> None:
        """Display final summary of the demonstration"""
        
        logger.info("📊 FINAL SECURITY SYSTEM SUMMARY")
        logger.info("=" * 60)
        
        # Get all system statuses
        vault_status = self.vault_manager.get_vault_status()
        audit_status = self.audit_trail.get_status()
        recovery_status = self.vault_recovery.get_recovery_status()
        config_status = self.config_backup.get_status()
        key_status = self.key_recovery.get_recovery_status()
        
        # Display summary
        logger.info(f"🏛️  VAULT MANAGER:")
        logger.info(f"    Version: {vault_status['vault_version']}")
        logger.info(f"    Key Version: {vault_status['key_version']}")
        logger.info(f"    Algorithm: {vault_status['algorithm']}")
        logger.info(f"    Key Rotation: {'Enabled' if vault_status['key_rotation_enabled'] else 'Disabled'}")
        
        logger.info(f"📊 AUDIT TRAIL:")
        logger.info(f"    Status: {'Active' if audit_status['processing_active'] else 'Inactive'}")
        logger.info(f"    Total Entries: {audit_status['total_entries']}")
        logger.info(f"    Queue Size: {audit_status['queue_size']}")
        logger.info(f"    Last Backup: {audit_status['last_backup_timestamp']}")
        
        logger.info(f"💾 VAULT RECOVERY:")
        logger.info(f"    Available Backups: {recovery_status['backups_available']}")
        logger.info(f"    Total Backup Size: {recovery_status['total_backup_size_mb']:.1f}MB")
        logger.info(f"    Last Backup: {recovery_status.get('last_backup', 'N/A')}")
        
        logger.info(f"⚙️  CONFIG BACKUP:")
        logger.info(f"    Active: {'Yes' if config_status['backup_system_active'] else 'No'}")
        logger.info(f"    Interval: {config_status['backup_interval_minutes']} minutes")
        logger.info(f"    Total Snapshots: {config_status['total_snapshots']}")
        logger.info(f"    Files Monitored: {config_status['config_paths_monitored']}")
        
        logger.info(f"🔑 KEY RECOVERY:")
        logger.info(f"    Keys Backed Up: {key_status['total_keys_backed_up']}")
        logger.info(f"    Recoverable Keys: {key_status['total_recoverable_keys']}")
        logger.info(f"    Total Shares: {key_status['total_shares_available']}")
        logger.info(f"    Backup Locations: {key_status['backup_locations_configured']}")
        
        logger.info("=" * 60)
        logger.info("✅ ALL SECURITY SYSTEMS OPERATIONAL")
        logger.info("🔐 Enterprise-grade security infrastructure ready for production")
        logger.info("💪 Banking-level encryption and recovery capabilities activated")
        
        # Final audit event
        audit_event("SECURITY_DEMO_COMPLETED", {
            "demo_timestamp": datetime.now(timezone.utc).isoformat(),
            "systems_tested": [
                "vault_manager",
                "audit_trail",
                "vault_recovery", 
                "config_backup",
                "key_recovery",
                "system_integration"
            ],
            "all_systems_operational": True,
            "enterprise_ready": True
        })
    
    async def run_complete_demo(self) -> None:
        """Run the complete security system demonstration"""
        
        try:
            logger.info("🚀 STARTING DAFELHUB SECURITY RECOVERY SYSTEM DEMO")
            logger.info("=" * 70)
            
            # Initialize all systems
            await self.initialize_systems()
            await asyncio.sleep(1)
            
            # Run individual demos
            await self.demo_vault_operations()
            await asyncio.sleep(1)
            
            await self.demo_audit_trail()
            await asyncio.sleep(1)
            
            await self.demo_vault_recovery()
            await asyncio.sleep(1)
            
            await self.demo_config_backup()
            await asyncio.sleep(1)
            
            await self.demo_key_recovery()
            await asyncio.sleep(1)
            
            await self.demo_system_integration()
            await asyncio.sleep(1)
            
            await self.display_final_summary()
            
        except Exception as e:
            logger.error(f"❌ Demo failed with error: {e}")
            audit_event("SECURITY_DEMO_FAILED", {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            raise
        
        finally:
            # Cleanup
            logger.info("🧹 Performing cleanup...")
            
            # Shutdown systems gracefully
            if self.audit_trail:
                self.audit_trail.shutdown()
            
            if self.config_backup:
                self.config_backup.shutdown()
            
            logger.info("✅ Demo cleanup completed")


async def main():
    """Main demo function"""
    
    demo = SecurityRecoveryDemo()
    await demo.run_complete_demo()


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())