# Overview

This is a Work From Home (WFH) Employee Monitoring System designed to track employee activity and presence during remote work. The system consists of two main components: a monitoring agent that runs on employee laptops and a central server that collects and stores monitoring data.

The agent sends regular heartbeats every 5 minutes to indicate the employee is online, and twice daily sends detailed logs including screenshots, IP addresses, and location data. The central server provides APIs for data collection and an admin dashboard for viewing employee activity.

## Current Status
✅ **FULLY OPERATIONAL** - Complete WFH monitoring system implemented with:
- FastAPI backend server with PostgreSQL database
- Admin-only authentication and dashboard  
- Working hours calculation based on agent heartbeats
- 45-day data retention with automatic cleanup
- Python agent for cross-platform employee laptop monitoring
- Real-time employee status tracking and detailed logging

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

## Core Framework Dependencies
- **FastAPI**: Web framework for building the REST API
- **Uvicorn**: ASGI server for running the FastAPI application
- **SQLAlchemy**: ORM for database operations
- **Psycopg2**: PostgreSQL adapter for Python

## Authentication & Security
- **python-jose**: JWT token handling and cryptographic operations
- **Passlib**: Password hashing with bcrypt support

## Agent Dependencies
- **Requests**: HTTP client for API communication
- **Pillow (PIL)**: Screenshot capture and image processing
- **Schedule**: Task scheduling for heartbeats and logs

## Database
- **PostgreSQL**: Primary database for storing heartbeats, logs, and admin users
- **Database Schema**: Three main tables for heartbeats, detailed logs, and admin authentication

## Additional Services
- **CORS Middleware**: Cross-origin request handling for web dashboard
- **Static File Serving**: For serving screenshots and web assets
- **GeoIP Integration**: Location approximation from public IP addresses
- **Multipart Form Processing**: For handling screenshot uploads from agents