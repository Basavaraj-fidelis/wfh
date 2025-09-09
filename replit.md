# Overview

This is a Work From Home (WFH) Employee Monitoring System designed to track employee activity and presence during remote work. The system consists of two main components: a monitoring agent that runs on employee laptops and a central server that collects and stores monitoring data.

The agent sends regular heartbeats every 5 minutes to indicate the employee is online, and twice daily sends detailed logs including screenshots, IP addresses, and location data. The central server provides APIs for data collection and an admin dashboard for viewing employee activity.

## Current Status
✅ **FULLY OPERATIONAL IN REPLIT ENVIRONMENT** - Complete WFH monitoring system successfully imported and configured for Replit:
- FastAPI backend server with PostgreSQL database and connection pooling
- Enhanced admin-only authentication with JWT security and account lockout protection
- Advanced working hours calculation with gap detection algorithm
- 45-day data retention with automatic cleanup and optimized database performance
- Cross-platform Python agent for Windows/Mac/Linux employee laptop monitoring
- Real-time employee status tracking with structured logging and performance monitoring
- Comprehensive security: rate limiting, input validation, CORS protection, security headers
- Error handling: retry logic, circuit breakers, graceful degradation patterns
- Configuration management: environment-based settings with validation
- Health checks and monitoring endpoints for operational visibility
- Scalability improvements: async operations, database indexing, connection pooling

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend Architecture
- **Framework**: FastAPI-based REST API server
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: JWT tokens for admin users, simple bearer tokens for agent authentication
- **File Storage**: Local filesystem storage for screenshots in a dedicated `screenshots/` directory
- **Data Models**: Three main entities - EmployeeHeartbeat, EmployeeLog, and AdminUser

## Agent Architecture
- **Platform**: Cross-platform Python application (Windows/Mac/Linux)
- **Scheduling**: Uses the `schedule` library for timing heartbeats and detailed logs
- **Screenshot Capture**: PIL (Pillow) library for desktop screenshots
- **Communication**: HTTPS requests with bearer token authentication
- **Randomization**: Random timing for detailed logs (2x per day between 8 AM - 10 PM)

## Data Flow
- **Heartbeats**: Every 5 minutes, agents send lightweight status updates
- **Detailed Logs**: Twice daily at randomized times, agents send comprehensive data including screenshots
- **Storage Pattern**: Heartbeats stored in database, screenshots saved to disk with paths in database

## Security Design
- **Agent Authentication**: Simple bearer token system for agent-to-server communication
- **Admin Authentication**: JWT-based authentication with bcrypt password hashing
- **Transport Security**: All communication over HTTPS
- **Password Security**: Bcrypt hashing for admin passwords

## API Structure
- **Agent Endpoints**: `/api/heartbeat` for status pings, `/api/log` for detailed submissions
- **Admin Endpoints**: Authentication and dashboard access endpoints
- **File Handling**: Multipart form data support for screenshot uploads

# External Dependencies

## Enhanced Architecture Components

### Core Framework Dependencies
- **FastAPI**: Web framework with async support and automatic API documentation
- **Uvicorn**: ASGI server with production-ready configuration
- **SQLAlchemy**: ORM with connection pooling and query optimization
- **Psycopg2**: PostgreSQL adapter with connection management
- **Pydantic**: Data validation and settings management
- **Pydantic-Settings**: Configuration management with environment variable support

### Security & Authentication
- **python-jose**: JWT token handling with enhanced security features
- **Passlib**: Password hashing with bcrypt and account lockout protection
- **Rate Limiting**: Custom middleware with burst detection and IP tracking
- **Input Validation**: SQL injection and XSS protection with pattern detection
- **Security Headers**: CORS, CSP, HSTS, and other security headers

### Monitoring & Logging
- **Structured Logging**: JSON-formatted logs with performance metrics
- **Health Checks**: Database connectivity and system resource monitoring
- **Error Tracking**: Comprehensive exception handling with retry logic
- **Performance Monitoring**: Request timing and database query optimization

### Agent Dependencies
- **Requests**: HTTP client with retry logic and circuit breaker patterns
- **Pillow (PIL)**: Screenshot capture with cross-platform compatibility
- **Schedule**: Task scheduling with randomization and error recovery
- **PSUtil**: System resource monitoring for health checks

### Database Enhancements
- **PostgreSQL**: Primary database with optimized indexing and partitioning
- **Connection Pooling**: QueuePool with connection recycling and health checks
- **Database Migrations**: Automated schema management (framework ready)
- **Query Optimization**: Indexed queries and performance monitoring

### Production Features
- **Environment Configuration**: Development, testing, and production settings
- **Docker Ready**: Containerization support for scalable deployment
- **Load Balancing**: Stateless design for horizontal scaling
- **Backup Integration**: Database backup hooks and disaster recovery
- **Monitoring Integration**: Metrics endpoints for Prometheus/Grafana