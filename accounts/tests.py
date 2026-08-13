from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import PasswordReset
from accounts.services import confirm_password_reset, request_password_reset


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield


@pytest.mark.django_db
def test_register_endpoint_returns_user_id(api_client):
    from accounts.models import User

    response=api_client.post(
        reverse('register',kwargs={'version':'v1'}),
        {'email':'newperson@example.com','password':'SecurePass123!'},
        format='json',
    )

    assert response.status_code==201
    assert response.data['id']==User.objects.get(email='newperson@example.com').id


@pytest.mark.django_db
def test_login_endpoint_returns_user_id(api_client,user):
    response=api_client.post(
        reverse('login',kwargs={'version':'v1'}),
        {'email':user.email,'password':'testpass123'},
        format='json',
    )

    assert response.status_code==200
    assert response.data['id']==user.id


@pytest.mark.django_db
def test_login_throttled_after_repeated_attempts(api_client):
    from django.core.cache import cache

    cache.clear()

    url=reverse('login',kwargs={'version':'v1'})

    for _ in range(5):
        api_client.post(
            url,
            {'email':'nobody@example.com','password':'wrong'},
            format='json',
        )

    response=api_client.post(
        url,
        {'email':'nobody@example.com','password':'wrong'},
        format='json',
    )

    assert response.status_code==429


@pytest.mark.django_db
def test_request_password_reset(user):
    password_reset=request_password_reset(user.email)

    assert password_reset.user==user
    assert password_reset.token
    assert password_reset.used_at is None
    assert password_reset.expires_at>timezone.now()


@pytest.mark.django_db
def test_confirm_password_reset(user):
    password_reset=request_password_reset(user.email)

    confirm_password_reset(
        password_reset.token,
        'NewSecurePass123!',
    )

    user.refresh_from_db()
    password_reset.refresh_from_db()

    assert user.check_password('NewSecurePass123!')
    assert password_reset.used_at is not None


@pytest.mark.django_db
def test_password_reset_token_cannot_be_reused(user):
    password_reset=request_password_reset(user.email)

    confirm_password_reset(
        password_reset.token,
        'NewSecurePass123!',
    )

    with pytest.raises(ValueError):
        confirm_password_reset(
            password_reset.token,
            'AnotherSecurePass123!',
        )


@pytest.mark.django_db
def test_expired_password_reset_fails(user):
    password_reset=PasswordReset.objects.create(
        user=user,
        token='expired-token',
        expires_at=timezone.now()-timedelta(hours=1),
    )

    with pytest.raises(ValueError):
        confirm_password_reset(
            password_reset.token,
            'NewSecurePass123!',
        )

    user.refresh_from_db()
    assert user.check_password('testpass123')


@pytest.mark.django_db
def test_invalid_password_reset_token_fails():
    with pytest.raises(ValueError):
        confirm_password_reset(
            'this-token-does-not-exist',
            'NewSecurePass123!',
        )

@pytest.mark.django_db
@patch('accounts.tasks.send_mail')
def test_send_password_reset_email(mock_send_mail,user):
    from accounts.tasks import send_password_reset_email

    password_reset=PasswordReset.objects.create(
        user=user,
        token='reset-email-token',
        expires_at=timezone.now()+timedelta(hours=1),
    )

    send_password_reset_email.run(password_reset.id)

    mock_send_mail.assert_called_once()

    kwargs=mock_send_mail.call_args.kwargs

    assert kwargs['recipient_list']==[user.email]
    assert 'reset-email-token' in kwargs['message']

@pytest.mark.django_db
@patch('accounts.tasks.send_mail')
def test_password_reset_email_not_sent_when_used(mock_send_mail,user):
    from accounts.tasks import send_password_reset_email

    password_reset=PasswordReset.objects.create(
        user=user,
        token='used-reset-token',
        expires_at=timezone.now()+timedelta(hours=1),
        used_at=timezone.now(),
    )

    send_password_reset_email.run(password_reset.id)

    mock_send_mail.assert_not_called()

@pytest.mark.django_db
def test_password_reset_request_endpoint(api_client,user):
    response=api_client.post(
        reverse(
            'password-reset',
            kwargs={'version':'v1'},
        ),
        {'email':user.email},
        format='json',
    )

    assert response.status_code==200
    assert PasswordReset.objects.filter(user=user).exists()

@pytest.mark.django_db
def test_password_reset_confirm_endpoint(api_client,user):
    password_reset=request_password_reset(user.email)

    response=api_client.post(
        reverse(
            'password-reset-confirm',
            kwargs={'version':'v1'},
        ),
        {
            'token':password_reset.token,
            'new_password':'NewSecurePass123!',
        },
        format='json',
    )

    assert response.status_code==200

    user.refresh_from_db()

    assert user.check_password('NewSecurePass123!')

@pytest.mark.django_db
def test_password_reset_unknown_email_does_not_reveal_user(api_client):
    response=api_client.post(
        reverse(
            'password-reset',
            kwargs={'version':'v1'},
        ),
        {'email':'does-not-exist@example.com'},
        format='json',
    )

    assert response.status_code==200

@pytest.mark.django_db
def test_token_refresh_endpoint(api_client,user):
    refresh=RefreshToken.for_user(user)

    response=api_client.post(
        reverse(
            'token_refresh',
            kwargs={'version':'v1'},
        ),
        {'refresh':str(refresh)},
        format='json',
    )

    assert response.status_code==200
    assert 'access' in response.data

@pytest.mark.django_db
@patch('accounts.tasks.send_password_reset_email.retry')
@patch('accounts.tasks.send_mail')
def test_password_reset_email_retries_on_failure(
    mock_send_mail,
    mock_retry,
    user,
):
    from accounts.tasks import send_password_reset_email

    password_reset=PasswordReset.objects.create(
        user=user,
        token='retry-reset-token',
        expires_at=timezone.now()+timedelta(hours=1),
    )

    error=Exception('Email server failed')
    mock_send_mail.side_effect=error
    mock_retry.side_effect=RuntimeError('Retry triggered')

    with pytest.raises(RuntimeError,match='Retry triggered'):
        send_password_reset_email.run(password_reset.id)

    mock_retry.assert_called_once_with(
        exc=error,
        countdown=60,
    )


@pytest.mark.django_db
def test_register_rejects_weak_password(api_client):
    response = api_client.post(
        reverse('register', kwargs={'version': 'v1'}),
        {
            'email': 'weakpass@example.com',
            'password': '123',
        },
        format='json',
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_register_accepts_valid_password(api_client):
    response = api_client.post(
        reverse('register', kwargs={'version': 'v1'}),
        {
            'email': 'validpass@example.com',
            'password': 'SecurePass123!',
        },
        format='json',
    )

    assert response.status_code == 201
