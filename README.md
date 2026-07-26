# ShipStream Backend

A production-style Project Management Backend built with Django REST Framework.

This project was developed as part of the ShipStream Backend Assignment and includes authentication, multi-tenancy, asynchronous task processing, real-time communication, caching, Docker support, CI/CD, and REST API best practices.

---

# Features

## Authentication
- JWT Authentication (SimpleJWT)
- User Registration
- User Login
- User Logout
- Token Blacklisting

## Organization Management
- Organization CRUD
- Membership Management
- Role Based Access Control (RBAC)

## Multi-Tenancy
- Organization based tenant isolation
- Tenant Middleware
- Organization level permissions
- Tenant aware queries

## Project Management
- Project CRUD
- Soft Delete
- Export Jobs

## Task Management
- Task CRUD
- Comments
- Labels
- Notifications
- Activity Logs

## REST API Features
- API Versioning
- Pagination
- Filtering
- Search
- Ordering
- Rate Throttling
- OpenAPI / Swagger Documentation

## Background Processing
- Celery
- Redis
- CSV Export Jobs
- Celery Beat Scheduled Tasks
- Automatic Retry
- Idempotent Tasks

## Real-Time Features
- Django Channels
- WebSocket Support
- Live Task Updates

## Performance Optimizations
- PostgreSQL
- select_related Query Optimization
- Redis Caching
- Database Constraints

## DevOps
- Docker
- Docker Compose
- GitHub Actions CI

---

# Tech Stack

- Python 3.13
- Django 4.2
- Django REST Framework
- PostgreSQL
- Redis
- Celery
- Celery Beat
- Django Channels
- Docker
- GitHub Actions
- SimpleJWT
- drf-spectacular

---

# Running the Project

## Clone the repository

```bash
git clone https://github.com/Dhanush-appiness/ShipStream.git

cd ShipStream
```

## Environment Variables

Create a `.env` file:

```env
DB_NAME=shipstream
DB_USER=postgres
DB_PASSWORD=postgres123
DB_HOST=localhost
DB_PORT=5432
```

## Using Docker

```bash
docker compose up --build
```

## Without Docker

```bash
python -m venv venv

venv\Scripts\activate

pip install -r requirements.txt

python manage.py migrate

python manage.py runserver
```

---

# API Documentation

Swagger

```
http://localhost:8000/api/schema/swagger-ui/
```

ReDoc

```
http://localhost:8000/api/schema/redoc/
```

---

# Project Structure

```
accounts/
common/
config/
notifications/
organizations/
projects/
tasks/

docker-compose.yml
Dockerfile
manage.py
```

---

# CI/CD

GitHub Actions automatically:

- Installs dependencies
- Runs migrations
- Executes tests

---

# Author

Dhanush J