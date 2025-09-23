/**
 * ConnectionManager - Enterprise Connection Pooling
 * Migrated from TypeScript to vanilla JavaScript for GitHub Pages  
 * Original: /frontend/src/lib/connections/ConnectionManager.ts (650+ lines)
 */

class ConnectionManager {
    constructor() {
        this.connections = new Map();
        this.pools = new Map();
        this.metadata = new Map();
        this.healthCheckIntervals = new Map();
        this.isShuttingDown = false;
        
        this.config = {
            maxConnections: 100,
            connectionTimeout: 30000,
            healthCheckInterval: 30000,
            enableAutoReconnect: true,
            reconnectMaxRetries: 3,
            reconnectDelay: 1000
        };
        
        console.log('🔗 ConnectionManager initialized');
        this.startMetricsCollection();
    }
    
    static getInstance() {
        if (!ConnectionManager.instance) {
            ConnectionManager.instance = new ConnectionManager();
        }
        return ConnectionManager.instance;
    }
    
    async createConnection(config) {
        const connectionId = config.id || this.generateConnectionId();
        const startTime = Date.now();
        
        try {
            console.log(`🔌 Creating connection: ${config.name} (${config.type})`);
            
            // Validate configuration
            this.validateConnectionConfig(config);
            
            // Check connection limits
            if (this.connections.size >= this.config.maxConnections) {
                throw new Error('Maximum connection limit reached');
            }
            
            // Create connector based on type
            const connector = await this.createConnector(config);
            
            // Test connection
            await this.testConnection(connector, config);
            
            // Register connection
            this.connections.set(connectionId, connector);
            this.metadata.set(connectionId, {
                config: config,
                createdAt: new Date(),
                lastActivity: new Date(),
                queryCount: 0,
                errorCount: 0,
                avgResponseTime: 0,
                status: 'connected'
            });
            
            // Start health monitoring
            this.startHealthMonitoring(connectionId);
            
            const duration = Date.now() - startTime;
            console.log(`✅ Connection created: ${config.name} (${duration}ms)`);
            
            return {
                connectionId,
                connector,
                metadata: this.metadata.get(connectionId)
            };
            
        } catch (error) {
            const duration = Date.now() - startTime;
            console.error(`❌ Connection failed: ${config.name}`, error);
            
            // Log failure metrics
            this.recordConnectionFailure(config, error, duration);
            throw error;
        }
    }
    
    async createConnector(config) {
        const { type } = config;
        
        switch (type) {
            case 'POSTGRESQL':
                return new PostgreSQLConnector(config);
            case 'MYSQL':
                return new MySQLConnector(config);
            case 'MONGODB':
                return new MongoDBConnector(config);
            case 'REST_API':
                return new RESTAPIConnector(config);
            case 'GRAPHQL':
                return new GraphQLConnector(config);
            default:
                throw new Error(`Unsupported connection type: ${type}`);
        }
    }
    
    async testConnection(connector, config) {
        const testStartTime = Date.now();
        
        try {
            console.log(`🧪 Testing connection: ${config.name}`);
            
            // Perform actual connection test
            const result = await connector.connect();
            
            const testDuration = Date.now() - testStartTime;
            console.log(`✅ Connection test passed: ${config.name} (${testDuration}ms)`);
            
            return {
                success: true,
                duration: testDuration,
                serverInfo: result.serverInfo || {},
                timestamp: new Date()
            };
            
        } catch (error) {
            const testDuration = Date.now() - testStartTime;
            console.error(`❌ Connection test failed: ${config.name}`, error);
            
            throw {
                success: false,
                error: error.message,
                duration: testDuration,
                timestamp: new Date()
            };
        }
    }
    
    startHealthMonitoring(connectionId) {
        const interval = setInterval(async () => {
            if (this.isShuttingDown) {
                clearInterval(interval);
                return;
            }
            
            try {
                await this.performHealthCheck(connectionId);
            } catch (error) {
                console.error(`❌ Health check failed for ${connectionId}:`, error);
            }
        }, this.config.healthCheckInterval);
        
        this.healthCheckIntervals.set(connectionId, interval);
    }
    
    async performHealthCheck(connectionId) {
        const connector = this.connections.get(connectionId);
        const metadata = this.metadata.get(connectionId);
        
        if (!connector || !metadata) return;
        
        const startTime = Date.now();
        
        try {
            // Perform health check query
            const isHealthy = await connector.healthCheck();
            const duration = Date.now() - startTime;
            
            // Update metadata
            metadata.lastActivity = new Date();
            metadata.status = isHealthy ? 'healthy' : 'unhealthy';
            
            // Update metrics
            this.updateHealthMetrics(connectionId, true, duration);
            
            console.log(`💚 Health check passed: ${connectionId} (${duration}ms)`);
            
        } catch (error) {
            const duration = Date.now() - startTime;
            
            // Update metadata
            metadata.status = 'error';
            metadata.errorCount += 1;
            
            // Update metrics
            this.updateHealthMetrics(connectionId, false, duration);
            
            console.error(`💔 Health check failed: ${connectionId}`, error);
            
            // Attempt reconnection if enabled
            if (this.config.enableAutoReconnect) {
                this.attemptReconnection(connectionId);
            }
        }
    }
    
    async attemptReconnection(connectionId) {
        console.log(`🔄 Attempting reconnection: ${connectionId}`);
        
        const metadata = this.metadata.get(connectionId);
        if (!metadata) return;
        
        try {
            // Use exponential backoff for retries
            for (let attempt = 1; attempt <= this.config.reconnectMaxRetries; attempt++) {
                const delay = this.config.reconnectDelay * Math.pow(2, attempt - 1);
                
                console.log(`🔄 Reconnection attempt ${attempt}/${this.config.reconnectMaxRetries} in ${delay}ms`);
                
                await new Promise(resolve => setTimeout(resolve, delay));
                
                try {
                    await this.createConnection(metadata.config);
                    console.log(`✅ Reconnection successful: ${connectionId}`);
                    return;
                } catch (error) {
                    console.log(`❌ Reconnection attempt ${attempt} failed:`, error.message);
                }
            }
            
            console.error(`💀 All reconnection attempts failed: ${connectionId}`);
            metadata.status = 'failed';
            
        } catch (error) {
            console.error(`💥 Reconnection process error: ${connectionId}`, error);
        }
    }
    
    getConnectionStatus(connectionId) {
        const metadata = this.metadata.get(connectionId);
        return metadata ? {
            id: connectionId,
            status: metadata.status,
            lastActivity: metadata.lastActivity,
            queryCount: metadata.queryCount,
            errorCount: metadata.errorCount,
            avgResponseTime: metadata.avgResponseTime,
            uptime: Date.now() - metadata.createdAt.getTime()
        } : null;
    }
    
    getAllConnectionsStatus() {
        const status = {
            totalConnections: this.connections.size,
            activeConnections: 0,
            healthyConnections: 0,
            errorConnections: 0,
            totalQueries: 0,
            avgResponseTime: 0
        };
        
        let totalResponseTime = 0;
        
        for (const [id, metadata] of this.metadata) {
            status.totalQueries += metadata.queryCount;
            totalResponseTime += metadata.avgResponseTime;
            
            switch (metadata.status) {
                case 'connected':
                case 'healthy':
                    status.activeConnections++;
                    status.healthyConnections++;
                    break;
                case 'error':
                case 'failed':
                    status.errorConnections++;
                    break;
            }
        }
        
        status.avgResponseTime = this.connections.size > 0 
            ? Math.round(totalResponseTime / this.connections.size)
            : 0;
        
        return status;
    }
    
    startMetricsCollection() {
        // Collect and report metrics every 60 seconds
        setInterval(() => {
            const status = this.getAllConnectionsStatus();
            console.log('📊 Connection Metrics:', status);
            
            // Emit metrics event for monitoring systems
            this.emit('metrics', status);
        }, 60000);
    }
    
    validateConnectionConfig(config) {
        const required = ['name', 'type', 'host'];
        const missing = required.filter(field => !config[field]);
        
        if (missing.length > 0) {
            throw new Error(`Missing required fields: ${missing.join(', ')}`);
        }
        
        // Validate port if provided
        if (config.port && (config.port < 1 || config.port > 65535)) {
            throw new Error('Port must be between 1 and 65535');
        }
        
        // Validate timeout values
        if (config.connectionTimeout && config.connectionTimeout < 1000) {
            throw new Error('Connection timeout must be at least 1000ms');
        }
    }
    
    generateConnectionId() {
        return `conn_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    updateHealthMetrics(connectionId, success, duration) {
        const metadata = this.metadata.get(connectionId);
        if (!metadata) return;
        
        metadata.queryCount += 1;
        
        // Update average response time using exponential moving average
        const alpha = 0.1; // Smoothing factor
        metadata.avgResponseTime = metadata.avgResponseTime 
            ? (alpha * duration) + ((1 - alpha) * metadata.avgResponseTime)
            : duration;
        
        if (!success) {
            metadata.errorCount += 1;
        }
    }
    
    recordConnectionFailure(config, error, duration) {
        // In a real system, this would write to audit logs
        console.error('📝 Connection failure recorded:', {
            name: config.name,
            type: config.type,
            error: error.message,
            duration: duration,
            timestamp: new Date()
        });
    }
    
    emit(event, data) {
        // Simple event emitter for monitoring integration
        const detail = { type: event, data: data };
        document.dispatchEvent(new CustomEvent('connectionManager', { detail }));
    }
    
    async shutdown() {
        console.log('🛑 ConnectionManager shutting down...');
        this.isShuttingDown = true;
        
        // Clear all health check intervals
        for (const interval of this.healthCheckIntervals.values()) {
            clearInterval(interval);
        }
        
        // Close all connections
        for (const [id, connector] of this.connections) {
            try {
                await connector.disconnect();
                console.log(`✅ Connection closed: ${id}`);
            } catch (error) {
                console.error(`❌ Error closing connection ${id}:`, error);
            }
        }
        
        // Clear all data structures
        this.connections.clear();
        this.pools.clear();
        this.metadata.clear();
        this.healthCheckIntervals.clear();
        
        console.log('✅ ConnectionManager shutdown complete');
    }
}

// Mock connector classes for demo
class PostgreSQLConnector {
    constructor(config) {
        this.config = config;
        this.status = 'disconnected';
    }
    
    async connect() {
        // Simulate real PostgreSQL connection
        console.log(`🐘 Connecting to PostgreSQL: ${this.config.host}:${this.config.port}`);
        
        await new Promise(resolve => setTimeout(resolve, 1000 + Math.random() * 2000));
        
        this.status = 'connected';
        return {
            success: true,
            serverInfo: {
                version: 'PostgreSQL 14.8',
                encoding: 'UTF8',
                timezone: 'UTC'
            }
        };
    }
    
    async healthCheck() {
        // Simulate health check query
        await new Promise(resolve => setTimeout(resolve, 30 + Math.random() * 20));
        return Math.random() > 0.05; // 95% success rate
    }
    
    async disconnect() {
        this.status = 'disconnected';
        console.log('🐘 PostgreSQL connection closed');
    }
}

class MySQLConnector {
    constructor(config) {
        this.config = config;
        this.status = 'disconnected';
    }
    
    async connect() {
        console.log(`🐬 Connecting to MySQL: ${this.config.host}:${this.config.port}`);
        await new Promise(resolve => setTimeout(resolve, 800 + Math.random() * 1500));
        this.status = 'connected';
        return { success: true, serverInfo: { version: 'MySQL 8.0.33' } };
    }
    
    async healthCheck() {
        await new Promise(resolve => setTimeout(resolve, 25 + Math.random() * 15));
        return Math.random() > 0.03;
    }
    
    async disconnect() {
        this.status = 'disconnected';
        console.log('🐬 MySQL connection closed');
    }
}

class MongoDBConnector {
    constructor(config) {
        this.config = config;
        this.status = 'disconnected';
    }
    
    async connect() {
        console.log(`🍃 Connecting to MongoDB: ${this.config.host}:${this.config.port}`);
        await new Promise(resolve => setTimeout(resolve, 600 + Math.random() * 1200));
        this.status = 'connected';
        return { success: true, serverInfo: { version: 'MongoDB 6.0.8' } };
    }
    
    async healthCheck() {
        await new Promise(resolve => setTimeout(resolve, 20 + Math.random() * 10));
        return Math.random() > 0.02;
    }
    
    async disconnect() {
        this.status = 'disconnected';
        console.log('🍃 MongoDB connection closed');
    }
}

// Make available globally
window.ConnectionManager = ConnectionManager;
window.PostgreSQLConnector = PostgreSQLConnector;
window.MySQLConnector = MySQLConnector;
window.MongoDBConnector = MongoDBConnector;

// Auto-initialize
document.addEventListener('DOMContentLoaded', () => {
    window.connectionManager = ConnectionManager.getInstance();
    console.log('🚀 Enterprise ConnectionManager ready');
});