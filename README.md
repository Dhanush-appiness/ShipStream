# ShipStream Backend

Backend implementation for the ShipStream assignment using Django and Django REST Framework.

## Tech Stack

- Python 3.13
- Django 4.2
- Django REST Framework
- PostgreSQL
- SimpleJWT

## Features Implemented

### Authentication
- User Registration
- User Login
- User Logout

### Organizations
- Create Organization
- List Organizations
- Retrieve Organization
- Update Organization
- Delete Organization

## Setup

### Create a virtual environment

```bash
python -m venv venv
venv\Scripts\activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run migrations

```bash
python manage.py migrate
```

### Start the server

```bash
python manage.py runserver
```